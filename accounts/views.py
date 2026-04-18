from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Avg, Count, Q
from django.utils import timezone
from .models import User, UserReport
from .forms import CustomUserCreationForm, CustomAuthenticationForm


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
    
    context = {
        'user': user,
        'is_seller': user.is_seller,
        'seller_approved': user.seller_approved if user.is_seller else False,
        'seller_rating_count': seller_rating_count,
        'product_rating_count': product_rating_count,
        'is_trusted': user.is_trusted(),
        'blocked_users_count': user.blocked_users.count(),
    }
    return render(request, 'accounts/profile.html', context)


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
    
    context = {
        'pending_sellers': pending_sellers,
        'approved_sellers': approved_sellers,
        'blocked_users': blocked_users,
        'pending_reports': pending_reports,
        'unverified_users': unverified_users,
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
