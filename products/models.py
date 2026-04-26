from django.db import models
import os
from accounts.models import User

class Category(models.TextChoices):
    ELECTRONICS = 'electronics', 'Electronics'
    FASHION = 'fashion', 'Fashion'
    FOOD = 'food', 'Food'
    FURNITURE = 'furniture', 'Furniture'
    PHONES = 'phones', 'Phones'
    OTHER = 'other', 'Other'

class Product(models.Model):
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Leave blank for 'Contact for price'")
    is_negotiable = models.BooleanField(default=False, help_text="Check if price is negotiable")
    whatsapp_number = models.CharField(max_length=20)
    category = models.CharField(max_length=50, choices=Category.choices, default=Category.OTHER)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['seller', 'is_active']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return self.name

class ProductRating(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True, help_text="Optional written review")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user')  # one rating per user per product

    def __str__(self):
        return f"{self.user} rated {self.product} — {self.score}★"

class SellerRating(models.Model):
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seller_ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_ratings')
    score = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('seller', 'user')  # one rating per user per seller

    def __str__(self):
        return f"{self.user} rated seller {self.seller} — {self.score}★"

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    is_primary = models.BooleanField(default=False)  # marks the main display image
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.product.name}"

    @property
    def file_exists(self):
        """Check if the image file exists on disk"""
        if self.image:
            return os.path.exists(self.image.path)
        return False


class ProductReport(models.Model):
    REASON_CHOICES = [
        ('fraud', 'Fraudulent Product'),
        ('fake', 'Counterfeit/Fake Item'),
        ('inappropriate', 'Inappropriate Content'),
        ('dangerous', 'Dangerous/Harmful Item'),
        ('spam', 'Spam/Misleading'),
        ('other', 'Other'),
    ]
    
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_reports_made')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    description = models.TextField()
    is_resolved = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        unique_together = ('reporter', 'product', 'reason')  # prevent duplicate reports
        indexes = [
            models.Index(fields=['is_resolved', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.reporter} reported {self.product} for {self.reason}"


class SellerReport(models.Model):
    REASON_CHOICES = [
        ('fraud', 'Fraudulent Activity'),
        ('harassment', 'Harassment/Abuse'),
        ('scam', 'Scam/Non-delivery'),
        ('inappropriate', 'Inappropriate Content'),
        ('spam', 'Spam'),
        ('other', 'Other'),
    ]
    
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seller_reports_made')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seller_reports_received')
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    description = models.TextField()
    is_resolved = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        unique_together = ('reporter', 'seller', 'reason')  # prevent duplicate reports
        indexes = [
            models.Index(fields=['is_resolved', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.reporter} reported seller {self.seller} for {self.reason}"


class PromotionPlan(models.Model):
    """Model to store and manage promotion plan details"""
    name = models.CharField(max_length=100, unique=True)  # e.g., "Quick Boost", "Popular", "Long-Term"
    duration_days = models.IntegerField()  # e.g., 3, 7, 30
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_featured = models.BooleanField(default=False)  # Mark "Best Value" plan
    description = models.CharField(max_length=255, blank=True)  # Short description for pricing card
    features = models.TextField(help_text="Enter features as JSON array, e.g., [\"Feature 1\", \"Feature 2\"]")
    display_order = models.IntegerField(default=0)  # Order on the page
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'id']

    def __str__(self):
        return f"{self.name} - ₦{self.price}/{self.duration_days}d"


class PromotionTransaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='promotion_transactions')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='promotion_transactions')
    plan = models.ForeignKey(PromotionPlan, on_delete=models.SET_NULL, null=True, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_reference = models.CharField(max_length=255, blank=True, null=True)
    access_code = models.CharField(max_length=255, blank=True)
    authorization_url = models.URLField(blank=True)
    channels = models.JSONField(default=list, blank=True)
    provider = models.CharField(max_length=30, default='paystack')
    paid_at = models.DateTimeField(null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = self.get_status_display()
        return f"{self.user.username} - {self.product.name} ({status})"


class ProductEngagement(models.Model):
    class EventType(models.TextChoices):
        PRODUCT_VIEW = 'product_view', 'Product View'
        CONTACT_CLICK = 'contact_click', 'Contact Click'

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='engagements')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_engagements')
    viewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='engagement_events')
    event_type = models.CharField(max_length=30, choices=EventType.choices, db_index=True)
    session_key = models.CharField(max_length=40, blank=True)
    source = models.CharField(max_length=50, blank=True, help_text="Where the interaction happened, e.g. detail page or homepage")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['product', 'event_type', 'created_at']),
            models.Index(fields=['seller', 'event_type', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} - {self.get_event_type_display()}"


# ==================== ADMIN CONTROL MODELS ====================

class UserPromotionStatus(models.Model):
    """Model to track and manage user promotions/demotions (seller status, admin status, etc.)"""
    
    STATUS_CHOICES = [
        ('regular_user', 'Regular User'),
        ('verified_seller', 'Verified Seller'),
        ('premium_seller', 'Premium Seller'),
        ('suspended', 'Suspended'),
        ('banned', 'Permanently Banned'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='promotion_status')
    current_status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='regular_user')
    is_seller = models.BooleanField(default=False)
    is_admin_verified = models.BooleanField(default=False)
    reason_for_status = models.TextField(blank=True, help_text="Admin notes on why user has this status")
    promoted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='promotions_given', help_text="Admin who promoted/demoted this user")
    promoted_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.get_current_status_display()}"


class MonetizationSettings(models.Model):
    """Model to control platform monetization rates and fees"""
    
    platform_commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5.00, help_text="Commission % on each sale")
    seller_payout_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Minimum amount before seller can withdraw")
    promotion_enabled = models.BooleanField(default=True, help_text="Enable/disable product promotions")
    verification_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Fee to become verified seller")
    marketplace_tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Tax on platform transactions")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='monetization_updates')
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Monetization Settings"
    
    def __str__(self):
        return f"Platform Commission: {self.platform_commission_percentage}%"


class ModerationAction(models.Model):
    """Model to track all admin moderation actions"""
    
    ACTION_TYPES = [
        ('user_suspend', 'User Suspended'),
        ('user_ban', 'User Banned'),
        ('user_restore', 'User Restored'),
        ('product_deactivate', 'Product Deactivated'),
        ('product_reactivate', 'Product Reactivated'),
        ('seller_promote', 'Seller Promoted'),
        ('seller_demote', 'Seller Demoted'),
        ('report_resolved', 'Report Resolved'),
        ('review_removed', 'Review Removed'),
        ('listing_flagged', 'Listing Flagged'),
        ('other', 'Other'),
    ]
    
    admin_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='moderation_actions')
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='moderation_against')
    target_product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='moderation_actions')
    reason = models.TextField(help_text="Reason for this moderation action")
    notes = models.TextField(blank=True, help_text="Additional admin notes")
    is_active = models.BooleanField(default=True, help_text="Whether this action is currently in effect")
    duration_days = models.IntegerField(null=True, blank=True, help_text="Duration in days (null = permanent)")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="When this action expires (if temporary)")
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_action_type_display()} by {self.admin_user.username} on {self.created_at.date()}"


class UserInteractionLog(models.Model):
    """Model to log all user interactions (ratings, reviews, reports, messages, etc.)"""
    
    INTERACTION_TYPES = [
        ('product_view', 'Product View'),
        ('product_added_to_cart', 'Product Added to Cart'),
        ('product_rated', 'Product Rated'),
        ('seller_rated', 'Seller Rated'),
        ('product_reported', 'Product Reported'),
        ('seller_reported', 'Seller Reported'),
        ('review_posted', 'Review Posted'),
        ('seller_contacted', 'Seller Contacted'),
        ('purchase_completed', 'Purchase Completed'),
        ('refund_requested', 'Refund Requested'),
        ('dispute_opened', 'Dispute Opened'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interaction_logs')
    interaction_type = models.CharField(max_length=50, choices=INTERACTION_TYPES)
    related_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='interactions_targeting')
    related_product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "User Interaction Logs"
    
    def __str__(self):
        return f"{self.user.username} - {self.get_interaction_type_display()}"


class AdminAuditLog(models.Model):
    """Model to track all admin actions for compliance and auditing"""
    
    admin_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=255, help_text="Description of admin action")
    model_name = models.CharField(max_length=100, help_text="Model that was modified")
    object_id = models.IntegerField(null=True, blank=True)
    old_values = models.TextField(blank=True, help_text="Previous values (JSON)")
    new_values = models.TextField(blank=True, help_text="New values (JSON)")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Admin Audit Logs"
    
    def __str__(self):
        return f"{self.admin_user.username} - {self.action} ({self.created_at.date()})"
