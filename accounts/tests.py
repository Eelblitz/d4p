from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import SellerVerificationPayment, UserReport
from products.models import MonetizationSettings

User = get_user_model()


class UserModelTests(TestCase):
    def test_generate_email_verification_token_sets_token(self):
        user = User.objects.create_user(username='tester', email='tester@example.com', password='testpass123')
        self.assertIsNone(user.email_verification_token)

        token = user.generate_email_verification_token()

        self.assertIsNotNone(token)
        self.assertEqual(user.email_verification_token, token)

    def test_is_trusted_requires_email_verified_and_trust_score(self):
        user = User.objects.create_user(username='trusted', email='trusted@example.com', password='testpass123')
        user.trust_score = 85
        user.email_verified = False
        user.save()
        self.assertFalse(user.is_trusted())

        user.email_verified = True
        user.save()
        self.assertTrue(user.is_trusted())

        user.trust_score = 75
        user.save()
        self.assertFalse(user.is_trusted())


class AccountViewTests(TestCase):
    def setUp(self):
        self.reporter = User.objects.create_user(
            username='reporter',
            email='reporter@example.com',
            password='testpass123'
        )
        self.reported_user = User.objects.create_user(
            username='reported',
            email='reported@example.com',
            password='testpass123'
        )
        self.client.force_login(self.reporter)

    def test_verify_email_view_valid_token_sets_email_verified(self):
        self.reported_user.email_verification_token = 'valid-token'
        self.reported_user.save()

        response = self.client.get(reverse('accounts:verify_email', args=['valid-token']))

        self.reported_user.refresh_from_db()
        self.assertTrue(self.reported_user.email_verified)
        self.assertIsNone(self.reported_user.email_verification_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['user'], self.reported_user)

    def test_verify_email_view_invalid_token_returns_error(self):
        response = self.client.get(reverse('accounts:verify_email', args=['invalid-token']))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['invalid_token'])

    def test_report_user_prevents_duplicate_reports(self):
        url = reverse('accounts:report_user', args=[self.reported_user.id])

        self.client.post(
            url,
            {'reason': 'fraud', 'description': 'This seller is scamming buyers.'},
            follow=True
        )

        self.assertEqual(
            UserReport.objects.filter(
                reporter=self.reporter,
                reported_user=self.reported_user,
                reason='fraud'
            ).count(),
            1
        )

        self.client.post(
            url,
            {'reason': 'fraud', 'description': 'Another duplicate report.'},
            follow=True
        )

        self.assertEqual(
            UserReport.objects.filter(
                reporter=self.reporter,
                reported_user=self.reported_user,
                reason='fraud'
            ).count(),
            1
        )

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_resend_verification_email_generates_token_and_sends_email(self):
        unverified = User.objects.create_user(
            username='unverified',
            email='unverified@example.com',
            password='testpass123'
        )
        self.client.logout()
        self.client.force_login(unverified)

        response = self.client.post(
            reverse('accounts:resend_verification'),
            {'email': unverified.email},
            follow=True
        )

        unverified.refresh_from_db()
        self.assertFalse(unverified.email_verified)
        self.assertIsNotNone(unverified.email_verification_token)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(unverified.email, mail.outbox[0].to)
        self.assertContains(response, 'Verification email sent')


class SellerVerificationFlowTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            username='seller',
            email='seller@example.com',
            password='testpass123',
            is_seller=True,
        )
        self.client.force_login(self.seller)

    @patch('accounts.views.PremblyClient.verify_nin_basic')
    def test_verify_nin_marks_user_verified(self, mock_verify_nin_basic):
        mock_verify_nin_basic.return_value = {
            'status': True,
            'verification': {'status': 'VERIFIED', 'reference': 'NIN-REF-123'},
            'nin_data': {
                'firstname': 'Ada',
                'middlename': 'N',
                'surname': 'Okafor',
            },
        }

        response = self.client.post(
            reverse('accounts:verify_nin'),
            {'nin_number': '12345678901'},
            follow=True,
        )

        self.seller.refresh_from_db()
        self.assertEqual(self.seller.nin_verification_status, User.NINVerificationStatus.VERIFIED)
        self.assertEqual(self.seller.nin_last4, '8901')
        self.assertEqual(self.seller.nin_verification_reference, 'NIN-REF-123')
        self.assertEqual(self.seller.nin_full_name, 'Ada N Okafor')
        self.assertNotEqual(self.seller.nin_hash, '')
        self.assertEqual(response.status_code, 200)

    @patch('accounts.views.PaystackClient.initialize_transaction')
    def test_start_seller_verification_payment_redirects_to_paystack(self, mock_initialize_transaction):
        MonetizationSettings.objects.create(
            platform_commission_percentage='5.00',
            seller_payout_threshold='1000.00',
            promotion_enabled=True,
            verification_fee='2500.00',
            marketplace_tax_percentage='0.00',
        )
        mock_initialize_transaction.return_value = {
            'access_code': 'access-123',
            'authorization_url': 'https://checkout.paystack.com/pay/test',
        }

        response = self.client.post(reverse('accounts:start_seller_verification_payment'))

        payment = SellerVerificationPayment.objects.get(user=self.seller)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'https://checkout.paystack.com/pay/test')
        self.assertEqual(payment.status, 'processing')
        self.assertEqual(payment.channels, ['ussd', 'bank_transfer'])

    @patch('accounts.views.PaystackClient.verify_transaction')
    def test_seller_payment_callback_marks_payment_completed(self, mock_verify_transaction):
        payment = SellerVerificationPayment.objects.create(
            user=self.seller,
            amount='2500.00',
            status='processing',
            payment_reference='SVP-REF-123',
            channels=['ussd', 'bank_transfer'],
        )
        mock_verify_transaction.return_value = {
            'status': 'success',
            'gateway_response': 'Approved',
        }

        response = self.client.get(
            reverse('accounts:seller_verification_payment_callback'),
            {'reference': payment.payment_reference},
            follow=True,
        )

        payment.refresh_from_db()
        self.assertEqual(payment.status, 'completed')
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(response.status_code, 200)


class AdminControlTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        self.seller_applicant = User.objects.create_user(
            username='seller_applicant',
            email='seller_applicant@example.com',
            password='testpass123',
            is_seller=True,
            seller_approved=False,
            is_blocked=False
        )
        self.verified_seller = User.objects.create_user(
            username='verified_seller',
            email='verified_seller@example.com',
            password='testpass123',
            is_seller=True,
            seller_approved=True,
            is_verified=False,
            trust_score=100
        )
        self.target_user = User.objects.create_user(
            username='target_user',
            email='target_user@example.com',
            password='testpass123'
        )
        self.reporter = User.objects.create_user(
            username='reporter_admin',
            email='reporter_admin@example.com',
            password='testpass123'
        )
        self.reported_user = User.objects.create_user(
            username='reported_admin',
            email='reported_admin@example.com',
            password='testpass123',
            trust_score=100
        )
        self.report = UserReport.objects.create(
            reporter=self.reporter,
            reported_user=self.reported_user,
            reason='fraud',
            description='Test fraud report'
        )
        self.client.force_login(self.admin_user)

    def test_admin_dashboard_builds_context(self):
        response = self.client.get(reverse('accounts:admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('pending_sellers', response.context)
        self.assertEqual(response.context['pending_sellers'].count(), 1)
        self.assertEqual(response.context['stats']['total_users'], 6)

    def test_approve_seller_requires_verified_nin(self):
        response = self.client.post(reverse('accounts:approve_seller', args=[self.seller_applicant.id]), follow=True)
        self.seller_applicant.refresh_from_db()
        self.assertFalse(self.seller_applicant.seller_approved)
        self.assertEqual(response.status_code, 200)

    def test_approve_seller_requires_payment_when_fee_enabled(self):
        MonetizationSettings.objects.create(
            platform_commission_percentage='5.00',
            seller_payout_threshold='1000.00',
            promotion_enabled=True,
            verification_fee='2500.00',
            marketplace_tax_percentage='0.00',
        )
        self.seller_applicant.nin_verification_status = User.NINVerificationStatus.VERIFIED
        self.seller_applicant.save(update_fields=['nin_verification_status'])

        response = self.client.post(reverse('accounts:approve_seller', args=[self.seller_applicant.id]), follow=True)

        self.seller_applicant.refresh_from_db()
        self.assertFalse(self.seller_applicant.seller_approved)
        self.assertEqual(response.status_code, 200)

    def test_approve_seller_succeeds_after_nin_and_payment(self):
        MonetizationSettings.objects.create(
            platform_commission_percentage='5.00',
            seller_payout_threshold='1000.00',
            promotion_enabled=True,
            verification_fee='2500.00',
            marketplace_tax_percentage='0.00',
        )
        self.seller_applicant.nin_verification_status = User.NINVerificationStatus.VERIFIED
        self.seller_applicant.save(update_fields=['nin_verification_status'])
        SellerVerificationPayment.objects.create(
            user=self.seller_applicant,
            amount='2500.00',
            status='completed',
            payment_reference='SVP-READY-123',
            channels=['ussd', 'bank_transfer'],
        )

        response = self.client.post(reverse('accounts:approve_seller', args=[self.seller_applicant.id]), follow=True)

        self.seller_applicant.refresh_from_db()
        self.assertTrue(self.seller_applicant.seller_approved)
        self.assertEqual(response.status_code, 200)

    def test_reject_seller_resets_seller_flags(self):
        response = self.client.post(reverse('accounts:reject_seller', args=[self.seller_applicant.id]), follow=True)
        self.seller_applicant.refresh_from_db()
        self.assertFalse(self.seller_applicant.is_seller)
        self.assertFalse(self.seller_applicant.seller_approved)
        self.assertEqual(response.status_code, 200)

    def test_toggle_seller_verified_flips_status(self):
        self.assertFalse(self.verified_seller.is_verified)
        response = self.client.post(reverse('accounts:toggle_seller_verified', args=[self.verified_seller.id]), follow=True)
        self.verified_seller.refresh_from_db()
        self.assertTrue(self.verified_seller.is_verified)
        self.assertEqual(response.status_code, 200)

    def test_block_and_unblock_user_admin(self):
        response = self.client.post(reverse('accounts:block_user_admin', args=[self.target_user.id]), follow=True)
        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.is_blocked)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(reverse('accounts:unblock_user_admin', args=[self.target_user.id]), follow=True)
        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.is_blocked)
        self.assertEqual(response.status_code, 200)

    def test_resolve_report_marks_resolved_and_reduces_trust(self):
        response = self.client.post(reverse('accounts:resolve_report', args=[self.report.id]), follow=True)
        self.report.refresh_from_db()
        self.reported_user.refresh_from_db()
        self.assertTrue(self.report.is_resolved)
        self.assertEqual(self.reported_user.trust_score, 90)
        self.assertEqual(response.status_code, 200)
