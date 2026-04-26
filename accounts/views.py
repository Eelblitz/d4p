import hashlib
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django.urls import reverse

from products.models import MonetizationSettings
from integrations.paystack import PaystackClient, PaystackError
from integrations.prembly import PremblyClient, PremblyError

from .models import User, UserReport, SellerVerificationPayment
from .forms import CustomUserCreationForm, CustomAuthenticationForm, NINVerificationForm


def get_verification_settings():
    return MonetizationSettings.objects.first()


def get_verification_fee():
    settings_obj = get_verification_settings()
    if settings_obj:
        return settings_obj.verification_fee
    return Decimal('0.00')


def seller_requires_verification_payment():
    return get_verification_fee() > 0


def seller_is_ready_for_approval(user):
    if user.nin_verification_status != User.NINVerificationStatus.VERIFIED:
        return False
    if seller_requires_verification_payment() and not user.has_completed_seller_verification_payment():
        return False
    return True


def build_callback_url(request, route_name, *args):
    return request.build_absolute_uri(reverse(route_name, args=args))


def mask_nin(last4):
    return f'*******{last4}' if last4 else 'Not submitted'


@require_http_methods(["GET", "POST"])
def register(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('products:list')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Generate email verification token
            token = user.generate_email_verification_token()
            
            # Send verification email
            verify_url = request.build_absolute_uri(f'/accounts/verify-email/{token}/')
            send_verification_email(user.email, verify_url)
            
            # Show verification pending page
            context = {
                'user_email': user.email,
                'verification_link': verify_url,
            }
            return render(request, 'accounts/verify_pending.html', context)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = CustomUserCreationForm()
    
    context = {'form': form}
    return render(request, 'accounts/register.html', context)


def send_verification_email(email, verify_url):
    """Send email verification link"""
    subject = '🛒 Verify Your DM4PRICE Account'
    message = f'''
    Welcome to DM4PRICE!
    
    Please verify your email by clicking the link below:
    {verify_url}
    
    This link will expire in 24 hours.
    
    If you didn't create this account, please ignore this email.
    
    Best regards,
    DM4PRICE Team
    '''
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)


@require_http_methods(["GET"])
def verify_email(request, token):
    """Verify user email with token"""
    user = User.objects.filter(email_verification_token=token).first()
    
    if user:
        token_created = user.email_verification_token_created
        if token_created and (timezone.now() - token_created).total_seconds() > 86400:
            context = {'expired': True}
            return render(request, 'accounts/verify_error.html', context)

        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_token_created = None
        user.save()
        context = {'user': user}
        return render(request, 'accounts/email_verified.html', context)
    else:
        context = {'invalid_token': True}
        return render(request, 'accounts/verify_error.html', context)


@require_http_methods(["GET", "POST"])
def resend_verification_email(request):
    """Resend verification email to user"""
    if request.user.is_authenticated and request.user.email_verified:
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        
        if not email:
            messages.error(request, 'Please enter your email address.')
            return render(request, 'accounts/resend_verification.html')
        
        user = User.objects.filter(email=email).first()
        
        if not user:
            messages.error(request, 'No account found with this email address.')
            return render(request, 'accounts/resend_verification.html')
        
        if user.email_verified:
            messages.info(request, '✅ Your email is already verified! You can login now.')
            return redirect('accounts:login')
        
        # Generate new token and send email
        token = user.generate_email_verification_token()
        verify_url = request.build_absolute_uri(f'/accounts/verify-email/{token}/')
        send_verification_email(user.email, verify_url)
        
        messages.success(request, f'✅ Verification email sent to {email}. Check your inbox!')
        context = {
            'user_email': email,
            'verification_link': verify_url,
            'resent': True,
        }
        return render(request, 'accounts/verify_pending.html', context)
    
    return render(request, 'accounts/resend_verification.html')


@require_http_methods(["GET", "POST"])
def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('products:list')
    
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                if user.is_blocked:
                    messages.error(request, 'Your account has been suspended.')
                    return redirect('accounts:login')
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('products:list')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = CustomAuthenticationForm()
    
    context = {'form': form}
    return render(request, 'accounts/login.html', context)


@login_required(login_url='accounts:login')
def logout_view(request):
    """User logout view"""
    username = request.user.username
    logout(request)
    messages.success(request, f'You have been logged out. See you soon!')
    return redirect('products:list')


@login_required(login_url='accounts:login')
def profile(request):
    """User profile view"""
    user = request.user
    seller_rating_count = user.seller_ratings.count() if user.is_seller else 0
    product_rating_count = user.given_ratings.count()
    verification_fee = get_verification_fee()
    latest_payment = user.seller_verification_payments.first()

    context = {
        'user': user,
        'is_seller': user.is_seller,
        'seller_approved': user.seller_approved if user.is_seller else False,
        'seller_rating_count': seller_rating_count,
        'product_rating_count': product_rating_count,
        'is_trusted': user.is_trusted(),
        'blocked_users_count': user.blocked_users.count(),
        'nin_form': NINVerificationForm(),
        'nin_masked': mask_nin(user.nin_last4),
        'verification_fee': verification_fee,
        'seller_requires_verification_payment': seller_requires_verification_payment(),
        'has_completed_seller_verification_payment': user.has_completed_seller_verification_payment(),
        'seller_is_ready_for_approval': seller_is_ready_for_approval(user),
        'latest_seller_payment': latest_payment,
    }
    return render(request, 'accounts/profile.html', context)


@login_required(login_url='accounts:login')
@require_http_methods(["POST"])
def verify_nin(request):
    """Verify a seller's NIN using Prembly before approval."""
    if not request.user.is_seller:
        messages.error(request, 'Only seller accounts can submit NIN verification.')
        return redirect('accounts:profile')

    form = NINVerificationForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect('accounts:profile')

    nin_number = form.cleaned_data['nin_number']
    client = PremblyClient()
    request.user.nin_verification_status = User.NINVerificationStatus.PENDING
    request.user.save(update_fields=['nin_verification_status'])

    try:
        payload = client.verify_nin_basic(nin_number)
    except PremblyError as exc:
        request.user.nin_verification_status = User.NINVerificationStatus.FAILED
        request.user.nin_failure_reason = str(exc)
        request.user.save(update_fields=['nin_verification_status', 'nin_failure_reason'])
        messages.error(request, str(exc))
        return redirect('accounts:profile')

    verification = payload.get('verification', {})
    nin_data = payload.get('nin_data', {})
    verification_status = verification.get('status')
    if verification_status != 'VERIFIED':
        request.user.nin_verification_status = User.NINVerificationStatus.FAILED
        request.user.nin_failure_reason = payload.get('detail', 'NIN verification failed.')
        request.user.save(update_fields=['nin_verification_status', 'nin_failure_reason'])
        messages.error(request, request.user.nin_failure_reason)
        return redirect('accounts:profile')

    full_name = ' '.join(
        value for value in [
            nin_data.get('firstname', '').strip(),
            nin_data.get('middlename', '').strip(),
            nin_data.get('surname', '').strip(),
        ] if value
    )
    request.user.nin_verification_status = User.NINVerificationStatus.VERIFIED
    request.user.nin_hash = hashlib.sha256(nin_number.encode('utf-8')).hexdigest()
    request.user.nin_last4 = nin_number[-4:]
    request.user.nin_verification_reference = verification.get('reference', '')
    request.user.nin_verification_provider = 'prembly'
    request.user.nin_verified_at = timezone.now()
    request.user.nin_full_name = full_name
    request.user.nin_failure_reason = ''
    request.user.save(
        update_fields=[
            'nin_verification_status',
            'nin_hash',
            'nin_last4',
            'nin_verification_reference',
            'nin_verification_provider',
            'nin_verified_at',
            'nin_full_name',
            'nin_failure_reason',
        ]
    )
    messages.success(request, 'Your NIN has been verified successfully. You can continue your seller approval steps.')
    return redirect('accounts:profile')


@login_required(login_url='accounts:login')
@require_http_methods(["POST"])
def start_seller_verification_payment(request):
    """Initialize Paystack payment for seller verification fees."""
    if not request.user.is_seller:
        messages.error(request, 'Only sellers can start seller verification payments.')
        return redirect('accounts:profile')

    if request.user.seller_approved:
        messages.info(request, 'Your seller account is already approved.')
        return redirect('accounts:profile')

    fee = get_verification_fee()
    if fee <= 0:
        messages.info(request, 'Seller verification fee is currently disabled.')
        return redirect('accounts:profile')

    reference = f'SVP-{timezone.now().strftime("%Y%m%d%H%M%S")}-{request.user.id}'
    payment = SellerVerificationPayment.objects.create(
        user=request.user,
        amount=fee,
        status='pending',
        payment_reference=reference,
        channels=['ussd', 'bank_transfer'],
        notes='Seller verification payment initialized',
    )

    client = PaystackClient()
    callback_url = build_callback_url(request, 'accounts:seller_verification_payment_callback')
    try:
        paystack_data = client.initialize_transaction(
            email=request.user.email,
            amount_kobo=int(fee * 100),
            reference=reference,
            callback_url=callback_url,
            channels=['ussd', 'bank_transfer'],
            metadata={
                'purpose': 'seller_verification',
                'user_id': request.user.id,
                'payment_reference': reference,
            },
        )
    except PaystackError as exc:
        payment.status = 'failed'
        payment.notes = str(exc)
        payment.save(update_fields=['status', 'notes', 'updated_at'])
        messages.error(request, str(exc))
        return redirect('accounts:profile')

    payment.access_code = paystack_data.get('access_code', '')
    payment.authorization_url = paystack_data.get('authorization_url', '')
    payment.status = 'processing'
    payment.save(update_fields=['access_code', 'authorization_url', 'status', 'updated_at'])
    return redirect(payment.authorization_url)


@require_http_methods(["GET"])
def seller_verification_payment_callback(request):
    """Verify Paystack callback for seller verification payment."""
    reference = request.GET.get('reference', '').strip()
    if not reference:
        messages.error(request, 'Missing payment reference.')
        return redirect('accounts:profile')

    payment = get_object_or_404(SellerVerificationPayment, payment_reference=reference)
    client = PaystackClient()
    try:
        verification = client.verify_transaction(reference)
    except PaystackError as exc:
        payment.status = 'failed'
        payment.notes = str(exc)
        payment.save(update_fields=['status', 'notes', 'updated_at'])
        messages.error(request, str(exc))
        return redirect('accounts:profile')

    payment_status = verification.get('status')
    payment.notes = verification.get('gateway_response', payment.notes)
    if payment_status == 'success':
        payment.status = 'completed'
        payment.paid_at = timezone.now()
        messages.success(request, 'Seller verification payment completed successfully.')
        update_fields = ['status', 'paid_at', 'notes', 'updated_at']
    elif payment_status in ['pending', 'processing', 'ongoing']:
        payment.status = 'processing'
        messages.info(request, 'Your payment is still being processed. Check again shortly.')
        update_fields = ['status', 'notes', 'updated_at']
    else:
        payment.status = 'failed'
        messages.error(request, 'Seller verification payment was not successful.')
        update_fields = ['status', 'notes', 'updated_at']

    payment.save(update_fields=update_fields)
    if request.user.is_authenticated and request.user.id == payment.user_id:
        return redirect('accounts:profile')
    return redirect('accounts:login')


@login_required(login_url='accounts:login')
@require_http_methods(["POST"])
def block_user(request, user_id):
    """Block a user"""
    user_to_block = get_object_or_404(User, pk=user_id)
    
    if user_to_block == request.user:
        messages.error(request, 'You cannot block yourself.')
    elif user_to_block in request.user.blocked_users.all():
        request.user.blocked_users.remove(user_to_block)
        messages.success(request, f'You have unblocked {user_to_block.username}.')
    else:
        request.user.blocked_users.add(user_to_block)
        messages.success(request, f'You have blocked {user_to_block.username}.')
    
    return redirect('accounts:profile')


@login_required(login_url='accounts:login')
def report_user(request, user_id):
    """Report a user for violations"""
    user_to_report = get_object_or_404(User, pk=user_id)
    
    if user_to_report == request.user:
        messages.error(request, 'You cannot report yourself.')
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'other')
        description = request.POST.get('description', '').strip()
        
        if not description:
            messages.error(request, 'Please provide a description.')
            return redirect('accounts:report_user', user_id=user_id)
        
        # Check for existing report
        existing = UserReport.objects.filter(
            reporter=request.user, 
            reported_user=user_to_report,
            reason=reason
        ).first()
        
        if existing:
            messages.warning(request, f'You have already reported this user for {reason}.')
        else:
            UserReport.objects.create(
                reporter=request.user,
                reported_user=user_to_report,
                reason=reason,
                description=description
            )
            messages.success(request, 'Thank you for reporting. Our team will review this.')
        
        return redirect('accounts:profile')
    
    context = {
        'user_to_report': user_to_report,
        'reason_choices': UserReport.REASON_CHOICES
    }
    return render(request, 'accounts/report_user.html', context)


def is_admin(user):
    """Check if user is admin"""
    return user.is_staff or user.is_superuser


@user_passes_test(is_admin)
def admin_dashboard(request):
    """Admin dashboard for seller verification and user management"""
    
    # Get pending seller approvals
    pending_sellers = User.objects.filter(
        is_seller=True,
        seller_approved=False,
        is_blocked=False
    ).annotate(
        product_count=Count('products'),
        rating_count=Count('seller_ratings')
    ).order_by('-created_at')
    
    # Get approved sellers
    approved_sellers = User.objects.filter(
        is_seller=True,
        seller_approved=True,
        is_blocked=False
    ).annotate(
        product_count=Count('products'),
        avg_rating=Avg('seller_ratings__score')
    ).order_by('-date_joined')[:10]
    
    # Get blocked users
    blocked_users = User.objects.filter(is_blocked=True).order_by('-updated_at')[:10]
    
    # Get pending reports
    pending_reports = UserReport.objects.filter(
        is_resolved=False
    ).select_related('reporter', 'reported_user').order_by('-created_at')[:10]
    
    # Get unverified users
    unverified_users = User.objects.filter(
        email_verified=False
    ).order_by('-created_at')[:10]
    
    # Statistics
    total_users = User.objects.count()
    total_sellers = User.objects.filter(is_seller=True).count()
    pending_seller_count = pending_sellers.count()
    reported_users_count = User.objects.filter(reports_received__is_resolved=False).distinct().count()

    for seller in pending_sellers:
        seller.has_completed_payment = seller.has_completed_seller_verification_payment()
        seller.ready_for_approval = seller_is_ready_for_approval(seller)

    for seller in approved_sellers:
        seller.has_completed_payment = seller.has_completed_seller_verification_payment()
    
    context = {
        'pending_sellers': pending_sellers,
        'approved_sellers': approved_sellers,
        'blocked_users': blocked_users,
        'pending_reports': pending_reports,
        'unverified_users': unverified_users,
        'verification_fee': get_verification_fee(),
        'seller_requires_verification_payment': seller_requires_verification_payment(),
        'stats': {
            'total_users': total_users,
            'total_sellers': total_sellers,
            'pending_seller_count': pending_seller_count,
            'reported_users_count': reported_users_count,
            'blocked_users_count': blocked_users.count(),
            'unverified_users_count': User.objects.filter(email_verified=False).count(),
        }
    }
    
    return render(request, 'accounts/admin_dashboard.html', context)


@user_passes_test(is_admin)
@require_http_methods(["POST"])
def approve_seller(request, user_id):
    """Approve a seller application"""
    user = get_object_or_404(User, pk=user_id, is_seller=True)
    if not seller_is_ready_for_approval(user):
        if user.nin_verification_status != User.NINVerificationStatus.VERIFIED:
            messages.error(request, f'{user.username} must complete NIN verification before approval.')
        else:
            messages.error(request, f'{user.username} must complete the seller verification payment before approval.')
        return redirect('accounts:admin_dashboard')
    user.seller_approved = True
    user.save()
    messages.success(request, f'✅ {user.username} has been approved as a seller!')
    return redirect('accounts:admin_dashboard')


@user_passes_test(is_admin)
@require_http_methods(["POST"])
def reject_seller(request, user_id):
    """Reject a seller application"""
    user = get_object_or_404(User, pk=user_id, is_seller=True, seller_approved=False)
    user.is_seller = False
    user.seller_approved = False
    user.save()
    messages.success(request, f'❌ {user.username} seller application has been rejected!')
    return redirect('accounts:admin_dashboard')


@user_passes_test(is_admin)
@require_http_methods(["POST"])
def toggle_seller_verified(request, user_id):
    """Toggle verified badge for a seller"""
    user = get_object_or_404(User, pk=user_id, is_seller=True, seller_approved=True)
    user.is_verified = not user.is_verified
    user.save()
    status = "verified" if user.is_verified else "unverified"
    messages.success(request, f'✨ {user.username} has been marked as {status}!')
    return redirect('accounts:admin_dashboard')


@user_passes_test(is_admin)
@require_http_methods(["POST"])
def block_user_admin(request, user_id):
    """Block a user (admin action)"""
    user = get_object_or_404(User, pk=user_id)
    if user == request.user:
        messages.error(request, 'You cannot block yourself!')
    else:
        user.is_blocked = True
        user.save()
        messages.success(request, f'🚫 {user.username} has been blocked!')
    return redirect('accounts:admin_dashboard')


@user_passes_test(is_admin)
@require_http_methods(["POST"])
def unblock_user_admin(request, user_id):
    """Unblock a user (admin action)"""
    user = get_object_or_404(User, pk=user_id, is_blocked=True)
    user.is_blocked = False
    user.save()
    messages.success(request, f'✅ {user.username} has been unblocked!')
    return redirect('accounts:admin_dashboard')


@user_passes_test(is_admin)
@require_http_methods(["POST"])
def resolve_report(request, report_id):
    """Mark a report as resolved"""
    report = get_object_or_404(UserReport, pk=report_id)
    report.is_resolved = True
    report.save()
    
    # Optional: Reduce trust score of reported user if fraud/harassment
    if report.reason in ['fraud', 'harassment']:
        if report.reported_user.trust_score > 0:
            report.reported_user.trust_score -= 10
            report.reported_user.save()
    
    messages.success(request, f'✅ Report against {report.reported_user.username} resolved!')
    return redirect('accounts:admin_dashboard')
