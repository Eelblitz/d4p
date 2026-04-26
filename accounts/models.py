from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import uuid

class User(AbstractUser):
    class NINVerificationStatus(models.TextChoices):
        NOT_SUBMITTED = 'not_submitted', 'Not Submitted'
        PENDING = 'pending', 'Pending'
        VERIFIED = 'verified', 'Verified'
        FAILED = 'failed', 'Failed'

    is_seller = models.BooleanField(default=False, db_index=True)
    seller_approved = models.BooleanField(default=False, db_index=True)
    is_verified = models.BooleanField(default=False)  # verified badge for sellers
    is_blocked = models.BooleanField(default=False, db_index=True)
    
    # Verification fields
    email_verified = models.BooleanField(default=False, db_index=True)
    email_verification_token = models.CharField(max_length=255, blank=True, null=True)
    email_verification_token_created = models.DateTimeField(blank=True, null=True)  # for expiry validation
    
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    phone_verified = models.BooleanField(default=False)
    nin_verification_status = models.CharField(
        max_length=20,
        choices=NINVerificationStatus.choices,
        default=NINVerificationStatus.NOT_SUBMITTED,
        db_index=True,
    )
    nin_hash = models.CharField(max_length=64, blank=True)
    nin_last4 = models.CharField(max_length=4, blank=True)
    nin_verification_reference = models.CharField(max_length=255, blank=True)
    nin_verification_provider = models.CharField(max_length=50, blank=True)
    nin_verified_at = models.DateTimeField(blank=True, null=True)
    nin_full_name = models.CharField(max_length=255, blank=True)
    nin_failure_reason = models.CharField(max_length=255, blank=True)
    
    # User relationships
    blocked_users = models.ManyToManyField('self', symmetrical=False, related_name='blocked_by', blank=True)
    
    # Reputation
    trust_score = models.IntegerField(default=100)  # starts at 100, goes down with violations
    
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['email_verified', 'is_seller']),
            models.Index(fields=['is_seller', 'seller_approved']),
            models.Index(fields=['is_blocked', 'created_at']),
        ]
    
    def __str__(self):
        return self.username
    
    def generate_email_verification_token(self):
        """Generate a unique token for email verification"""
        self.email_verification_token = str(uuid.uuid4())
        self.email_verification_token_created = timezone.now()
        self.save()
        return self.email_verification_token
    
    def is_trusted(self):
        """Check if user is trusted (verified + good reputation)"""
        return self.email_verified and self.trust_score >= 80

    @property
    def effective_seller_status(self):
        """Single source of truth for seller status, derived from UserPromotionStatus if it exists."""
        try:
            return self.promotion_status.current_status
        except Exception:
            return 'regular_user'

    def sync_seller_flags(self):
        """Keep is_seller / seller_approved in sync with UserPromotionStatus."""
        try:
            status = self.promotion_status.current_status
            self.is_seller = status in ('verified_seller', 'premium_seller')
            self.seller_approved = self.is_seller
            self.is_blocked = status in ('suspended', 'banned')
            User.objects.filter(pk=self.pk).update(
                is_seller=self.is_seller,
                seller_approved=self.seller_approved,
                is_blocked=self.is_blocked,
            )
        except Exception:
            pass

    def has_completed_seller_verification_payment(self):
        return self.seller_verification_payments.filter(status='completed').exists()

    def meets_seller_approval_requirements(self):
        if self.nin_verification_status != self.NINVerificationStatus.VERIFIED:
            return False
        return True


class SellerVerificationPayment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seller_verification_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    payment_reference = models.CharField(max_length=255, unique=True)
    access_code = models.CharField(max_length=255, blank=True)
    authorization_url = models.URLField(blank=True)
    channels = models.JSONField(default=list, blank=True)
    provider = models.CharField(max_length=30, default='paystack')
    paid_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - seller verification ({self.status})"


class UserReport(models.Model):
    REASON_CHOICES = [
        ('fraud', 'Fraudulent Activity'),
        ('harassment', 'Harassment/Abuse'),
        ('inappropriate', 'Inappropriate Content'),
        ('spam', 'Spam'),
        ('other', 'Other'),
    ]
    
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_made')
    reported_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_received')
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    description = models.TextField()
    is_resolved = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        unique_together = ('reporter', 'reported_user', 'reason')  # prevent duplicate reports
        indexes = [
            models.Index(fields=['is_resolved', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.reporter} reported {self.reported_user} for {self.reason}"
