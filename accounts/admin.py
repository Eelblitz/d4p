from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.safestring import mark_safe

from .models import SellerVerificationPayment, User, UserReport


class SellerFilter(admin.SimpleListFilter):
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
        if self.value() == 'approved':
            return queryset.filter(is_seller=True, seller_approved=True)
        if self.value() == 'buyers':
            return queryset.filter(is_seller=False)
        if self.value() == 'blocked':
            return queryset.filter(is_blocked=True)
        return queryset


class VerificationFilter(admin.SimpleListFilter):
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
        if self.value() == 'unverified':
            return queryset.filter(email_verified=False)
        return queryset


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = [
        'username',
        'email',
        'email_badge',
        'seller_status_badge',
        'nin_status_badge',
        'verified_badge',
        'trust_score_display',
        'date_joined',
    ]
    list_filter = [
        SellerFilter,
        VerificationFilter,
        'is_blocked',
        'nin_verification_status',
        'date_joined',
    ]
    readonly_fields = [
        'trust_score',
        'created_at',
        'updated_at',
        'phone_verified',
        'nin_hash',
        'nin_last4',
        'nin_verification_reference',
        'nin_verification_provider',
        'nin_verified_at',
    ]
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Seller Information', {
            'fields': ('is_seller', 'seller_approved', 'is_verified')
        }),
        ('Verification', {
            'fields': (
                'email_verified',
                'email_verification_token',
                'phone_number',
                'phone_verified',
                'nin_verification_status',
                'nin_last4',
                'nin_full_name',
                'nin_failure_reason',
                'nin_verification_reference',
                'nin_verification_provider',
                'nin_verified_at',
                'nin_hash',
            )
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
        if obj.email_verified:
            return mark_safe('<span style="color: green; font-weight: bold;">Verified</span>')
        return mark_safe('<span style="color: #c0392b; font-weight: bold;">Not Verified</span>')
    email_badge.short_description = 'Email Status'

    def seller_status_badge(self, obj):
        if obj.is_blocked:
            return mark_safe('<span style="background:#c0392b;color:white;padding:4px 8px;border-radius:4px;">Blocked</span>')
        if not obj.is_seller:
            return mark_safe('<span style="background:#95a5a6;color:white;padding:4px 8px;border-radius:4px;">Buyer</span>')
        if obj.seller_approved:
            return mark_safe('<span style="background:#27ae60;color:white;padding:4px 8px;border-radius:4px;">Approved Seller</span>')
        return mark_safe('<span style="background:#f39c12;color:white;padding:4px 8px;border-radius:4px;">Pending Approval</span>')
    seller_status_badge.short_description = 'Seller Status'

    def nin_status_badge(self, obj):
        colors = {
            User.NINVerificationStatus.NOT_SUBMITTED: '#c0392b',
            User.NINVerificationStatus.PENDING: '#f39c12',
            User.NINVerificationStatus.VERIFIED: '#27ae60',
            User.NINVerificationStatus.FAILED: '#c0392b',
        }
        label = obj.get_nin_verification_status_display()
        color = colors.get(obj.nin_verification_status, '#7f8c8d')
        return mark_safe(f'<span style="background:{color};color:white;padding:4px 8px;border-radius:4px;">{label}</span>')
    nin_status_badge.short_description = 'NIN Status'

    def trust_score_display(self, obj):
        if obj.trust_score >= 80:
            color = 'green'
        elif obj.trust_score >= 60:
            color = 'orange'
        else:
            color = 'red'
        return mark_safe(f'<span style="color:{color};font-weight:bold;">{obj.trust_score}/100</span>')
    trust_score_display.short_description = 'Trust Score'

    def verified_badge(self, obj):
        if obj.is_seller and obj.seller_approved and obj.is_verified:
            return mark_safe('<span style="background:#ba7800;color:white;padding:4px 8px;border-radius:4px;">Verified Seller</span>')
        return '-'
    verified_badge.short_description = 'Seller Badge'

    def approve_sellers(self, request, queryset):
        from products.models import MonetizationSettings

        settings_obj = MonetizationSettings.objects.first()
        fee_required = bool(settings_obj and settings_obj.verification_fee > 0)
        eligible_sellers = queryset.filter(
            is_seller=True,
            seller_approved=False,
            nin_verification_status=User.NINVerificationStatus.VERIFIED,
        )
        count = 0
        for seller in eligible_sellers:
            if fee_required and not seller.has_completed_seller_verification_payment():
                continue
            seller.seller_approved = True
            seller.save(update_fields=['seller_approved'])
            count += 1
        self.message_user(request, f'Approved {count} seller(s) that met the verification checks.')
    approve_sellers.short_description = 'Approve Selected Sellers'

    def reject_sellers(self, request, queryset):
        count = queryset.filter(is_seller=True).update(is_seller=False, seller_approved=False)
        self.message_user(request, f'Rejected {count} seller application(s).')
    reject_sellers.short_description = 'Reject Seller Applications'

    def block_users(self, request, queryset):
        count = queryset.update(is_blocked=True)
        self.message_user(request, f'Blocked {count} user(s).')
    block_users.short_description = 'Block Selected Users'

    def unblock_users(self, request, queryset):
        count = queryset.update(is_blocked=False)
        self.message_user(request, f'Unblocked {count} user(s).')
    unblock_users.short_description = 'Unblock Selected Users'

    def verify_emails(self, request, queryset):
        count = queryset.update(email_verified=True)
        self.message_user(request, f'Verified {count} email address(es).')
    verify_emails.short_description = 'Verify Email Addresses'

    def unverify_emails(self, request, queryset):
        count = queryset.update(email_verified=False)
        self.message_user(request, f'Marked {count} email address(es) as unverified.')
    unverify_emails.short_description = 'Unverify Email Addresses'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('blocked_users', 'reports_received', 'reports_made')


@admin.register(UserReport)
class UserReportAdmin(admin.ModelAdmin):
    list_display = ['reporter', 'reported_user', 'reason', 'created_at', 'is_resolved']
    list_filter = ['reason', 'is_resolved', 'created_at']
    readonly_fields = ['reporter', 'reported_user', 'created_at']
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

    def mark_resolved(self, request, queryset):
        count = queryset.update(is_resolved=True)
        self.message_user(request, f'Marked {count} report(s) as resolved.')
    mark_resolved.short_description = 'Mark as Resolved'

    def mark_unresolved(self, request, queryset):
        count = queryset.update(is_resolved=False)
        self.message_user(request, f'Marked {count} report(s) as pending.')
    mark_unresolved.short_description = 'Mark as Pending'


@admin.register(SellerVerificationPayment)
class SellerVerificationPaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'status', 'payment_reference', 'provider', 'paid_at', 'created_at']
    list_filter = ['status', 'provider', 'created_at']
    search_fields = ['user__username', 'user__email', 'payment_reference']
    readonly_fields = ['created_at', 'updated_at', 'paid_at']
