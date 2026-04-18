import json
from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Count, Case, When, Value, IntegerField, OuterRef, Subquery, Exists, FloatField
from django.db.models.functions import Coalesce
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from accounts.models import User
from .models import (
    Product,
    ProductRating,
    ProductImage,
    ProductReport,
    SellerReport,
    PromotionPlan,
    PromotionTransaction,
    ProductEngagement,
    MonetizationSettings,
)
from .forms import ProductForm, ProductImageForm, ProductRatingForm, ProductReportForm, SellerReportForm


def _product_queryset_with_market_signals(queryset, search_query=''):
    """Annotate products with ranking signals used across discovery surfaces."""
    now = timezone.now()
    rating_stats = ProductRating.objects.filter(product=OuterRef('pk')).values('product')
    active_promotions = PromotionTransaction.objects.filter(
        product=OuterRef('pk'),
        status='completed',
        starts_at__lte=now,
        ends_at__gte=now,
    )

    queryset = queryset.annotate(
        avg_rating=Coalesce(
            Subquery(
                rating_stats.annotate(avg=Avg('score')).values('avg')[:1],
                output_field=FloatField(),
            ),
            Value(0.0),
        ),
        rating_count=Coalesce(
            Subquery(
                rating_stats.annotate(total=Count('id')).values('total')[:1],
                output_field=IntegerField(),
            ),
            Value(0),
        ),
        is_promoted=Exists(active_promotions),
    )

    if search_query:
        queryset = queryset.annotate(
            search_rank=Case(
                When(name__icontains=search_query, then=Value(2)),
                When(description__icontains=search_query, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    else:
        queryset = queryset.annotate(search_rank=Value(0, output_field=IntegerField()))

    return queryset.select_related('seller').prefetch_related('images')


def _prepare_product_cards(products):
    """Attach UI-friendly card data without extra template complexity."""
    for product in products:
        product.avg_rating = round(product.avg_rating or 0, 1)
        product.rating_count = product.rating_count or 0
        primary_image = product.images.filter(is_primary=True).first()
        if primary_image and primary_image.file_exists:
            product.first_image = primary_image
        else:
            product.first_image = next((img for img in product.images.all() if img.file_exists), None)

    return products


def _get_client_source(request):
    return request.GET.get('source', '').strip()[:50] or request.POST.get('source', '').strip()[:50]


def _log_product_engagement(request, product, event_type, source=''):
    if not request.session.session_key:
        request.session.save()

    ProductEngagement.objects.create(
        product=product,
        seller=product.seller,
        viewer=request.user if request.user.is_authenticated else None,
        event_type=event_type,
        session_key=request.session.session_key or '',
        source=source[:50],
    )

def homepage(request):
    """Display the DM4PRICE landing page"""
    featured_products = _product_queryset_with_market_signals(
        Product.objects.filter(is_active=True)
    ).order_by('-is_promoted', '-avg_rating', '-rating_count', '-created_at')[:6]
    featured_products = _prepare_product_cards(featured_products)
    
    # Get platform stats
    total_products = Product.objects.filter(is_active=True).count()
    total_sellers = Product.objects.filter(is_active=True).values('seller').distinct().count()
    
    context = {
        'featured_products': featured_products,
        'total_products': total_products,
        'total_sellers': total_sellers,
    }
    return render(request, 'products/homepage.html', context)

def trust_safety(request):
    """Show Trust & Safety policies and guidance"""
    return render(request, 'trust_safety.html')

def promote_product(request):
    """Show product promotion plans and information"""
    import json
    plans = PromotionPlan.objects.filter(is_active=True).order_by('display_order')
    
    # Parse features JSON for each plan
    for plan in plans:
        try:
            plan.features_list = json.loads(plan.features)
        except (json.JSONDecodeError, TypeError):
            plan.features_list = []
    
    context = {
        'plans': plans,
    }
    return render(request, 'promote_product.html', context)

def product_list(request):
    """Display all active products with filtering and search"""
    search = request.GET.get('q', '').strip()
    products = _product_queryset_with_market_signals(
        Product.objects.filter(is_active=True),
        search_query=search,
    )

    # Search by name or description
    if search:
        products = products.filter(Q(name__icontains=search) | Q(description__icontains=search))

    # Filter by category
    category = request.GET.get('category', '').strip()
    if category:
        products = products.filter(category=category)

    # Filter by price range
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    if min_price:
        try:
            products = products.filter(price__gte=float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            products = products.filter(price__lte=float(max_price))
        except ValueError:
            pass

    sort = request.GET.get('sort', '').strip() or 'best'
    sort_options = [
        ('best', 'Best match'),
        ('newest', 'Newest first'),
        ('top_rated', 'Top rated'),
        ('price_low', 'Price: low to high'),
        ('price_high', 'Price: high to low'),
    ]

    if sort == 'newest':
        products = products.order_by('-is_promoted', '-created_at')
    elif sort == 'top_rated':
        products = products.order_by('-avg_rating', '-rating_count', '-is_promoted', '-created_at')
    elif sort == 'price_low':
        products = products.order_by('price', '-is_promoted', '-avg_rating', '-created_at')
    elif sort == 'price_high':
        products = products.order_by('-price', '-is_promoted', '-avg_rating', '-created_at')
    else:
        products = products.order_by(
            '-search_rank',
            '-is_promoted',
            '-seller__is_verified',
            '-avg_rating',
            '-rating_count',
            '-created_at',
        )
        sort = 'best'

    products = _prepare_product_cards(products)

    context = {
        'products': products,
        'search_query': search,
        'selected_category': category,
        'min_price': min_price,
        'max_price': max_price,
        'selected_sort': sort,
        'sort_options': sort_options,
        'categories': [
            ('', 'All Categories'),
            ('electronics', 'Electronics'),
            ('fashion', 'Fashion'),
            ('food', 'Food'),
            ('furniture', 'Furniture'),
            ('phones', 'Phones'),
            ('other', 'Other'),
        ]
    }
    return render(request, 'products/product_list.html', context)

def product_detail(request, pk):
    """Display detailed view of a single product"""
    product = get_object_or_404(Product, pk=pk, is_active=True)
    _log_product_engagement(request, product, ProductEngagement.EventType.PRODUCT_VIEW, source='product_detail')
    
    # Get product ratings
    ratings = product.ratings.all()
    avg_rating = ratings.aggregate(Avg('score'))['score__avg'] or 0
    avg_rating = round(avg_rating, 1)
    
    # Get seller info
    seller = product.seller
    seller_avg_rating = seller.seller_ratings.aggregate(Avg('score'))['score__avg'] or 0
    seller_avg_rating = round(seller_avg_rating, 1)
    seller_rating_count = seller.seller_ratings.count()
    
    # Check if user has already rated this product
    user_rating = None
    rating_form = None
    if request.user.is_authenticated:
        user_rating = product.ratings.filter(user=request.user).first()
        rating_form = ProductRatingForm()
    
    context = {
        'product': product,
        'images': product.images.all(),
        'primary_image': next((img for img in product.images.all() if img.is_primary and img.file_exists), 
                             next((img for img in product.images.all() if img.file_exists), None)),
        'ratings': ratings,
        'avg_rating': avg_rating,
        'rating_count': ratings.count(),
        'seller': seller,
        'seller_avg_rating': seller_avg_rating,
        'seller_rating_count': seller_rating_count,
        'user_rating': user_rating,
        'rating_form': rating_form,
    }
    return render(request, 'products/product_detail.html', context)


# ==================== SELLER DASHBOARD ====================

@login_required(login_url='accounts:login')
def seller_dashboard(request):
    """Seller dashboard - overview of seller's products"""
    if not request.user.is_seller:
        messages.error(request, 'You need to be a seller to access this page.')
        return redirect('accounts:profile')
    
    seller_products = _product_queryset_with_market_signals(
        Product.objects.filter(seller=request.user)
    ).annotate(
        view_count=Count('engagements', filter=Q(engagements__event_type=ProductEngagement.EventType.PRODUCT_VIEW), distinct=True),
        contact_click_count=Count('engagements', filter=Q(engagements__event_type=ProductEngagement.EventType.CONTACT_CLICK), distinct=True),
        image_count=Count('images', distinct=True),
    ).prefetch_related('ratings').order_by('-is_promoted', '-created_at')
    
    # Calculate stats
    total_products = seller_products.count()
    active_products = seller_products.filter(is_active=True).count()
    inactive_products = seller_products.filter(is_active=False).count()
    
    # Calculate average rating
    avg_rating = 0
    total_ratings = request.user.seller_ratings.all()
    if total_ratings.exists():
        avg_rating = round(total_ratings.aggregate(Avg('score'))['score__avg'], 1)
    
    total_views = 0
    total_contact_clicks = 0
    promoted_product_count = 0
    promoted_views = 0
    promoted_contact_clicks = 0

    # Add product stats
    for product in seller_products:
        product.view_count = product.view_count or 0
        product.contact_click_count = product.contact_click_count or 0
        product.ctr = round((product.contact_click_count / product.view_count) * 100, 1) if product.view_count else 0
        total_views += product.view_count
        total_contact_clicks += product.contact_click_count
        if product.is_promoted:
            promoted_product_count += 1
            promoted_views += product.view_count
            promoted_contact_clicks += product.contact_click_count

    overall_ctr = round((total_contact_clicks / total_views) * 100, 1) if total_views else 0
    promoted_ctr = round((promoted_contact_clicks / promoted_views) * 100, 1) if promoted_views else 0
    top_performing_product = max(
        seller_products,
        key=lambda product: (product.contact_click_count, product.view_count, product.avg_rating),
        default=None,
    )
    
    context = {
        'seller_products': seller_products,
        'total_products': total_products,
        'active_products': active_products,
        'inactive_products': inactive_products,
        'seller_avg_rating': avg_rating,
        'seller_rating_count': total_ratings.count(),
        'total_views': total_views,
        'total_contact_clicks': total_contact_clicks,
        'overall_ctr': overall_ctr,
        'promoted_product_count': promoted_product_count,
        'promoted_views': promoted_views,
        'promoted_contact_clicks': promoted_contact_clicks,
        'promoted_ctr': promoted_ctr,
        'top_performing_product': top_performing_product,
    }
    return render(request, 'products/seller_dashboard.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def add_product(request):
    """Add a new product"""
    if not request.user.is_seller:
        messages.error(request, 'You need to be a seller to add products.')
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.save()
            messages.success(request, 'Product created successfully!')
            return redirect('products:edit_product', pk=product.pk)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = ProductForm()
    
    context = {'form': form, 'page_title': 'Add Product'}
    return render(request, 'products/product_form.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def edit_product(request, pk):
    """Edit an existing product"""
    product = get_object_or_404(Product, pk=pk, seller=request.user)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated successfully!')
            return redirect('products:seller_dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = ProductForm(instance=product)
    
    images = product.images.all()
    context = {
        'form': form,
        'product': product,
        'images': images,
        'page_title': f'Edit: {product.name}'
    }
    return render(request, 'products/product_form.html', context)


@login_required(login_url='accounts:login')
def delete_product(request, pk):
    """Delete a product"""
    product = get_object_or_404(Product, pk=pk, seller=request.user)
    
    if request.method == 'POST':
        product_name = product.name
        product.delete()
        messages.success(request, f'Product "{product_name}" deleted successfully!')
        return redirect('products:seller_dashboard')
    
    context = {'product': product}
    return render(request, 'products/delete_product.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def product_images(request, pk):
    """Manage images for a product"""
    product = get_object_or_404(Product, pk=pk, seller=request.user)
    
    if request.method == 'POST':
        form = ProductImageForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.save(commit=False)
            image.product = product
            try:
                image.save()
                messages.success(request, 'Image uploaded successfully!')
                return redirect('products:product_images', pk=product.pk)
            except Exception as e:
                messages.error(request, f'Failed to save image: {e}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = ProductImageForm()
    
    images = product.images.all()
    context = {
        'product': product,
        'images': images,
        'form': form
    }
    return render(request, 'products/product_images.html', context)


def track_contact_click(request, pk):
    """Log a high-intent seller contact click and redirect to WhatsApp."""
    product = get_object_or_404(Product, pk=pk, is_active=True)
    source = _get_client_source(request) or 'product_detail'
    _log_product_engagement(request, product, ProductEngagement.EventType.CONTACT_CLICK, source=source)
    return HttpResponseRedirect(f'https://wa.me/{product.whatsapp_number}')


@login_required(login_url='accounts:login')
def delete_image(request, image_id):
    """Delete a product image"""
    image = get_object_or_404(ProductImage, pk=image_id, product__seller=request.user)
    product_id = image.product.id
    
    if request.method == 'POST':
        image.delete()
        messages.success(request, 'Image deleted successfully!')
        return redirect('products:product_images', pk=product_id)
    
    context = {'image': image}
    return render(request, 'products/delete_image.html', context)


@login_required(login_url='accounts:login')
def set_primary_image(request, image_id):
    """Set an image as primary for a product"""
    image = get_object_or_404(ProductImage, pk=image_id, product__seller=request.user)
    product = image.product
    
    # Unset all other primary images
    product.images.all().update(is_primary=False)
    # Set this image as primary
    image.is_primary = True
    image.save()
    
    messages.success(request, 'Primary image updated!')
    return redirect('products:product_images', pk=product.pk)


@login_required(login_url='accounts:login')
@require_http_methods(["POST"])
def rate_product(request, pk):
    """Rate a product"""
    product = get_object_or_404(Product, pk=pk, is_active=True)
    
    # Check if user has already rated this product
    existing_rating = product.ratings.filter(user=request.user).first()
    
    form = ProductRatingForm(request.POST)
    if form.is_valid():
        if existing_rating:
            # Update existing rating
            existing_rating.score = form.cleaned_data['score']
            existing_rating.save()
            messages.success(request, 'Your rating has been updated!')
        else:
            # Create new rating
            rating = form.save(commit=False)
            rating.product = product
            rating.user = request.user
            rating.save()
            messages.success(request, 'Thank you for rating this product!')
    else:
        messages.error(request, 'Invalid rating.')
    
    return redirect('products:detail', pk=product.pk)


# ==================== REPORTING SYSTEM ====================

@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def report_product(request, pk):
    """Report a product"""
    product = get_object_or_404(Product, pk=pk, is_active=True)
    
    if request.method == 'POST':
        form = ProductReportForm(request.POST)
        if form.is_valid():
            # Check if user already reported this product for the same reason
            existing = ProductReport.objects.filter(
                reporter=request.user,
                product=product,
                reason=form.cleaned_data['reason']
            ).first()
            
            if existing:
                messages.warning(request, 'You have already reported this product for this reason. Our team will review it shortly.')
                return redirect('products:detail', pk=product.pk)
            
            # Create new report
            report = form.save(commit=False)
            report.reporter = request.user
            report.product = product
            report.save()
            messages.success(request, 'Thank you for reporting this product. Our safety team will review it.')
            return redirect('products:detail', pk=product.pk)
    else:
        form = ProductReportForm()
    
    context = {
        'form': form,
        'product': product,
        'report_type': 'Product'
    }
    return render(request, 'products/report_item.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def report_seller(request, user_id):
    """Report a seller"""
    seller = get_object_or_404(User, pk=user_id, is_seller=True)
    
    if request.user == seller:
        messages.error(request, 'You cannot report yourself.')
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        form = SellerReportForm(request.POST)
        if form.is_valid():
            # Check if user already reported this seller for the same reason
            existing = SellerReport.objects.filter(
                reporter=request.user,
                seller=seller,
                reason=form.cleaned_data['reason']
            ).first()
            
            if existing:
                messages.warning(request, 'You have already reported this seller for this reason. Our team will review it shortly.')
                return redirect('accounts:profile')
            
            # Create new report
            report = form.save(commit=False)
            report.reporter = request.user
            report.seller = seller
            report.save()
            messages.success(request, 'Thank you for reporting this seller. Our safety team will review it.')
            return redirect('accounts:profile')
    else:
        form = SellerReportForm()
    
    context = {
        'form': form,
        'seller': seller,
        'report_type': 'Seller'
    }
    return render(request, 'products/report_item.html', context)


@login_required(login_url='accounts:login')
def promotion_checkout(request):
    """Checkout flow for purchasing a promotion plan"""
    if not request.user.is_seller:
        messages.error(request, 'You need to be a seller to purchase promotions.')
        return redirect('accounts:profile')

    selected_plan = None
    plan_id = request.GET.get('plan') or request.POST.get('plan_id')
    if plan_id:
        selected_plan = get_object_or_404(PromotionPlan, pk=plan_id, is_active=True)

    products = Product.objects.filter(seller=request.user, is_active=True)
    monetization = MonetizationSettings.objects.first()

    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        plan_id = request.POST.get('plan_id')
        product = get_object_or_404(Product, pk=product_id, seller=request.user, is_active=True)
        plan = get_object_or_404(PromotionPlan, pk=plan_id, is_active=True)

        if monetization and not monetization.promotion_enabled:
            messages.error(request, 'Promotions are currently disabled by the platform.')
            return redirect('products:promote_product')

        now = timezone.now()
        transaction = PromotionTransaction.objects.create(
            user=request.user,
            product=product,
            plan=plan,
            amount=plan.price,
            status='completed',
            payment_reference=f'PMT-{timezone.now().strftime("%Y%m%d%H%M%S")}-{product.id}',
            starts_at=now,
            ends_at=now + timedelta(days=plan.duration_days),
            notes='Auto-completed promotion purchase',
        )

        messages.success(request, f'Your promotion purchase for {product.name} was successful.')
        return redirect('products:promotion_confirmation', transaction_id=transaction.id)

    context = {
        'products': products,
        'plans': PromotionPlan.objects.filter(is_active=True).order_by('display_order'),
        'selected_plan': selected_plan,
        'monetization': monetization,
    }
    return render(request, 'promotion_checkout.html', context)


@login_required(login_url='accounts:login')
def promotion_confirmation(request, transaction_id):
    transaction = get_object_or_404(PromotionTransaction, pk=transaction_id, user=request.user)
    return render(request, 'promotion_confirmation.html', {'transaction': transaction})
