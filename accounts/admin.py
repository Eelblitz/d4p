from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.db.models import Q
from .models import User, UserReport


class SellerFilter(admin.SimpleListFilter):
    """Custom filter for seller status"""
    title = 'Seller Status'
    parameter_name = 'seller_status'
    
    def lookups(self, request, model_admin):
        return [
            ('pending', 'Pending Approval'),
            ('approved', 'Approved Sellers'),
            ('buyers', 'Buyers Only'),
            ('blocked', 'Blocked Users'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'pending':
            return queryset.filter(is_seller=True, seller_approved=False)
        elif self.value() == 'approved':
            return queryset.filter(is_seller=True, seller_approved=True)
        elif self.value() == 'buyers':
            return queryset.filter(is_seller=False)
        elif self.value() == 'blocked':
            return queryset.filter(is_blocked=True)
        return queryset


class VerificationFilter(admin.SimpleListFilter):
    """Filter by email verification status"""
    title = 'Email Verification'
    parameter_name = 'email_verified'
    
    def lookups(self, request, model_admin):
        return [
            ('verified', 'Email Verified'),
            ('unverified', 'Not Verified'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'verified':
            return queryset.filter(email_verified=True)
        elif self.value() == 'unverified':
            return queryset.filter(email_verified=False)
        return queryset


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = [
        'username',
        'email_badge',
        'seller_status_badge',
        'verified_badge',
        'trust_score_display',
        'verification_badge',
        'email',
        'date_joined',
    ]
    
    list_filter = [
        SellerFilter,
        VerificationFilter,
        'is_blocked',
        'date_joined',
    ]
    
    readonly_fields = [
        'trust_score',
        'created_at',
        'updated_at',
        'phone_verified',
    ]
    
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Seller Information', {
            'fields': ('is_seller', 'seller_approved', 'is_verified')
        }),
        ('Verification', {
            'fields': ('email_verified', 'email_verification_token', 'phone_number', 'phone_verified')
        }),
        ('Security & Trust', {
            'fields': ('is_blocked', 'trust_score', 'blocked_users')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_sellers', 'reject_sellers', 'block_users', 'unblock_users', 'verify_emails', 'unverify_emails']
    
    def email_badge(self, obj):
        """Display email verification status"""
        if obj.email_verified:
            return mark_safe(
                '<span style="color: green; font-weight: bold;">✅ Verified</span>'
            )
        else:
            return mark_safe(
                '<span style="color: red; font-weight: bold;">❌ Not Verified</span>'
            )
    email_badge.short_description = 'Email Status'
    
    def seller_status_badge(self, obj):
        """Display seller status with badge"""
        if obj.is_blocked:
            return mark_safe(
                '<span style="background-color: #c0392b; color: white; padding: 5px 10px; border-radius: 3px; font-weight: bold;">🚫 BLOCKED</span>'
            )
        elif not obj.is_seller:
            return mark_safe(
                '<span style="background-color: #95a5a6; color: white; padding: 5px 10px; border-radius: 3px;">👤 Buyer</span>'
            )
        elif obj.seller_approved:
            return mark_safe(
                '<span style="background-color: #27ae60; color: white; padding: 5px 10px; border-radius: 3px; font-weight: bold;">✅ Approved Seller</span>'
            )
        else:
            return mark_safe(
                '<span style="background-color: #f39c12; color: white; padding: 5px 10px; border-radius: 3px; font-weight: bold;">⏳ Pending Approval</span>'
            )
    seller_status_badge.short_description = 'Status'
    
    def trust_score_display(self, obj):
        """Display trust score with color coding"""
        if obj.trust_score >= 80:
            color = 'green'
        elif obj.trust_score >= 60:
            color = 'orange'
        else:
            color = 'red'
        return mark_safe(
            f'<span style="color: {color}; font-weight: bold;">{obj.trust_score}/100</span>'
        )
    trust_score_display.short_description = 'Trust Score'
    
    def verification_badge(self, obj):
        """Display if user is fully trusted"""
        if obj.is_trusted():
            return mark_safe(
                '<span style="background-color: #27ae60; color: white; padding: 3px 8px; border-radius: 3px; font-size: 0.9rem;">🔒 Trusted</span>'
            )
        return '—'
    verification_badge.short_description = 'Trust Status'
    
    def verified_badge(self, obj):
        """Display seller's verified status"""
        if obj.is_seller and obj.seller_approved:
            if obj.is_verified:
                return mark_safe(
                    '<span style="background-color: #f39c12; color: white; padding: 3px 8px; border-radius: 3px; font-size: 0.9rem;">✨ Verified</span>'
                )
            else:
                return '—'
        return '—'
    verified_badge.short_description = 'Seller Verified'
    
    def approve_sellers(self, request, queryset):
        """Action to approve pending sellers"""
        pending_sellers = queryset.filter(is_seller=True, seller_approved=False)
        count = pending_sellers.update(seller_approved=True)
        self.message_user(request, f'✅ {count} seller(s) approved!')
    approve_sellers.short_description = '✅ Approve Selected Sellers'
    
    def reject_sellers(self, request, queryset):
        """Action to reject/remove seller status"""
        sellers = queryset.filter(is_seller=True)
        count = sellers.update(is_seller=False, seller_approved=False)
        self.message_user(request, f'❌ {count} seller application(s) rejected!')
    reject_sellers.short_description = '❌ Reject Seller Applications'
    
    def block_users(self, request, queryset):
        """Action to block users"""
        count = queryset.update(is_blocked=True)
        self.message_user(request, f'🚫 {count} user(s) blocked!')
    block_users.short_description = '🚫 Block Selected Users'
    
    def unblock_users(self, request, queryset):
        """Action to unblock users"""
        count = queryset.update(is_blocked=False)
        self.message_user(request, f'✅ {count} user(s) unblocked!')
    unblock_users.short_description = '✅ Unblock Selected Users'
    
    def verify_emails(self, request, queryset):
        """Action to verify email addresses"""
        count = queryset.update(email_verified=True)
        self.message_user(request, f'✅ {count} email(s) verified!')
    verify_emails.short_description = '✅ Verify Email Addresses'
    
    def unverify_emails(self, request, queryset):
        """Action to unverify email addresses"""
        count = queryset.update(email_verified=False)
        self.message_user(request, f'❌ {count} email(s) unverified!')
    unverify_emails.short_description = '❌ Unverify Email Addresses'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.prefetch_related('blocked_users', 'reports_received', 'reports_made')


@admin.register(UserReport)
class UserReportAdmin(admin.ModelAdmin):
    list_display = [
        'reporter_badge',
        'reported_user_badge',
        'reason_badge',
        'created_at',
        'is_resolved_badge',
    ]
    
    list_filter = [
        'reason',
        'is_resolved',
        'created_at',
    ]
    
    readonly_fields = [
        'reporter',
        'reported_user',
        'created_at',
    ]
    
    fieldsets = (
        ('Report Details', {
            'fields': ('reporter', 'reported_user', 'reason', 'description')
        }),
        ('Resolution', {
            'fields': ('is_resolved',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_resolved', 'mark_unresolved']
    
    def reporter_badge(self, obj):
        """Display reporter info"""
        return mark_safe(
            f'<a href="/admin/accounts/user/{obj.reporter.id}/change/">{obj.reporter.username}</a>'
        )
    reporter_badge.short_description = 'Reporter'
    
    def reported_user_badge(self, obj):
        """Display reported user with link"""
        return mark_safe(
            f'<a href="/admin/accounts/user/{obj.reported_user.id}/change/">{obj.reported_user.username}</a>'
        )
    reported_user_badge.short_description = 'Reported User'
    
    def reason_badge(self, obj):
        """Display reason with color"""
        colors = {
            'fraud': '#c0392b',
            'harassment': '#e74c3c',
            'inappropriate': '#f39c12',
            'spam': '#95a5a6',
            'other': '#34495e',
        }
        color = colors.get(obj.reason, '#34495e')
        return mark_safe(
            f'<span style="background-color: {color}; color: white; padding: 5px 10px; border-radius: 3px; font-weight: 600;">{obj.get_reason_display()}</span>'
        )
    reason_badge.short_description = 'Reason'
    
    def is_resolved_badge(self, obj):
        """Display resolution status"""
        if obj.is_resolved:
            return mark_safe(
                '<span style="color: green; font-weight: bold;">✅ Resolved</span>'
            )
        else:
            return mark_safe(
                '<span style="color: red; font-weight: bold;">⏳ Pending</span>'
            )
    is_resolved_badge.short_description = 'Status'
    
    def mark_resolved(self, request, queryset):
        """Mark reports as resolved"""
        count = queryset.update(is_resolved=True)
        self.message_user(request, f'✅ {count} report(s) marked as resolved!')
    mark_resolved.short_description = '✅ Mark as Resolved'
    
    def mark_unresolved(self, request, queryset):
        """Mark reports as unresolved"""
        count = queryset.update(is_resolved=False)
        self.message_user(request, f'⏳ {count} report(s) marked as pending!')
    mark_unresolved.short_description = '⏳ Mark as Pending'