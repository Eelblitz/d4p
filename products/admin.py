from django.contrib import admin
from .models import Product, ProductEngagement, ProductImage, ProductRating, SellerRating, ProductReport, SellerReport, PromotionPlan, PromotionTransaction, UserPromotionStatus, MonetizationSettings, ModerationAction, UserInteractionLog, AdminAuditLog

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3        # shows 3 empty image slots by default
    max_num = 10     # maximum 10 images per product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImageInline]
    list_display = ['name', 'seller', 'category', 'is_active', 'created_at']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'seller__username']

@admin.register(ProductRating)
class ProductRatingAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'score', 'created_at']

@admin.register(SellerRating)
class SellerRatingAdmin(admin.ModelAdmin):
    list_display = ['seller', 'user', 'score', 'created_at']

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'is_primary', 'uploaded_at']


@admin.register(ProductReport)
class ProductReportAdmin(admin.ModelAdmin):
    list_display = ['product', 'reporter', 'reason', 'is_resolved', 'created_at']
    list_filter = ['reason', 'is_resolved', 'created_at']
    search_fields = ['product__name', 'reporter__username', 'description']
    readonly_fields = ['created_at', 'reporter', 'product']
    
    fieldsets = (
        ('Report Info', {
            'fields': ('product', 'reporter', 'reason', 'description', 'created_at')
        }),
        ('Status', {
            'fields': ('is_resolved',)
        }),
    )


@admin.register(SellerReport)
class SellerReportAdmin(admin.ModelAdmin):
    list_display = ['seller', 'reporter', 'reason', 'is_resolved', 'created_at']
    list_filter = ['reason', 'is_resolved', 'created_at']
    search_fields = ['seller__username', 'reporter__username', 'description']
    readonly_fields = ['created_at', 'reporter', 'seller']
    
    fieldsets = (
        ('Report Info', {
            'fields': ('seller', 'reporter', 'reason', 'description', 'created_at')
        }),
        ('Status', {
            'fields': ('is_resolved',)
        }),
    )


@admin.register(PromotionPlan)
class PromotionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'duration_days', 'price', 'is_featured', 'is_active', 'display_order']
    list_filter = ['is_active', 'is_featured', 'duration_days']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Plan Info', {
            'fields': ('name', 'duration_days', 'price', 'description')
        }),
        ('Settings', {
            'fields': ('is_featured', 'is_active', 'display_order')
        }),
        ('Features', {
            'fields': ('features',),
            'description': 'Enter features as JSON array: ["Feature 1", "Feature 2", "Feature 3"]'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PromotionTransaction)
class PromotionTransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'plan', 'amount', 'status', 'provider', 'paid_at', 'created_at']
    list_filter = ['status', 'created_at', 'plan']
    search_fields = ['user__username', 'product__name', 'payment_reference']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('user', 'product', 'plan', 'amount', 'status', 'payment_reference', 'provider', 'channels', 'access_code', 'authorization_url', 'paid_at')
        }),
        ('Promotion Timing', {
            'fields': ('starts_at', 'ends_at')
        }),
        ('Metadata', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProductEngagement)
class ProductEngagementAdmin(admin.ModelAdmin):
    list_display = ['product', 'seller', 'viewer', 'event_type', 'source', 'created_at']
    list_filter = ['event_type', 'source', 'created_at']
    search_fields = ['product__name', 'seller__username', 'viewer__username', 'session_key']
    readonly_fields = ['created_at']


# ==================== ADMIN CONTROL INTERFACES ====================

@admin.register(UserPromotionStatus)
class UserPromotionStatusAdmin(admin.ModelAdmin):
    list_display = ['user', 'current_status', 'is_seller', 'is_admin_verified', 'promoted_at']
    list_filter = ['current_status', 'is_seller', 'is_admin_verified', 'promoted_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['promoted_at']
    
    fieldsets = (
        ('User Info', {
            'fields': ('user', 'current_status', 'is_seller', 'is_admin_verified')
        }),
        ('Admin Action', {
            'fields': ('promoted_by', 'reason_for_status', 'promoted_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.promoted_by = request.user
        else:
            obj.promoted_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(MonetizationSettings)
class MonetizationSettingsAdmin(admin.ModelAdmin):
    list_display = ['platform_commission_percentage', 'seller_payout_threshold', 'verification_fee', 'promotion_enabled']
    readonly_fields = ['updated_at', 'updated_by']
    
    fieldsets = (
        ('Commission & Fees', {
            'fields': ('platform_commission_percentage', 'marketplace_tax_percentage', 'verification_fee')
        }),
        ('Seller Settings', {
            'fields': ('seller_payout_threshold',)
        }),
        ('Platform Features', {
            'fields': ('promotion_enabled',)
        }),
        ('Metadata', {
            'fields': ('updated_by', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ModerationAction)
class ModerationActionAdmin(admin.ModelAdmin):
    list_display = ['action_type', 'target_user', 'admin_user', 'is_active', 'created_at']
    list_filter = ['action_type', 'is_active', 'created_at']
    search_fields = ['target_user__username', 'admin_user__username', 'reason']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Action Details', {
            'fields': ('admin_user', 'action_type', 'is_active')
        }),
        ('Target', {
            'fields': ('target_user', 'target_product')
        }),
        ('Reason & Notes', {
            'fields': ('reason', 'notes')
        }),
        ('Duration', {
            'fields': ('duration_days', 'expires_at'),
            'description': 'Leave blank for permanent action'
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.admin_user = request.user
        super().save_model(request, obj, form, change)


@admin.register(UserInteractionLog)
class UserInteractionLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'interaction_type', 'related_user', 'created_at']
    list_filter = ['interaction_type', 'created_at']
    search_fields = ['user__username', 'related_user__username', 'description']
    readonly_fields = ['created_at', 'user', 'related_user', 'related_product', 'interaction_type', 'description', 'ip_address']
    
    def has_add_permission(self, request):
        return False  # Logs are created automatically
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superuser can delete logs


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ['admin_user', 'action', 'model_name', 'created_at']
    list_filter = ['model_name', 'created_at', 'admin_user']
    search_fields = ['admin_user__username', 'action', 'model_name']
    readonly_fields = ['admin_user', 'action', 'model_name', 'object_id', 'old_values', 'new_values', 'ip_address', 'created_at']
    
    def has_add_permission(self, request):
        return False  # Logs are created automatically
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superuser can delete logs
