import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from products.models import (
    Product, ProductRating, PromotionPlan, PromotionTransaction, ProductEngagement,
    MonetizationSettings, UserPromotionStatus,
)

User = get_user_model()


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def make_seller(username='seller', **kwargs):
    return User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='testpass123',
        is_seller=True,
        seller_approved=True,
        **kwargs,
    )


def make_buyer(username='buyer'):
    return User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='testpass123',
    )


def make_product(seller, **kwargs):
    defaults = dict(
        name='Test Product',
        description='A sample product',
        whatsapp_number='08012345678',
        category='electronics',
        price=50_000,
        is_active=True,
    )
    defaults.update(kwargs)
    return Product.objects.create(seller=seller, **defaults)


# ─────────────────────────────────────────────
# Product model
# ─────────────────────────────────────────────

class ProductModelTests(TestCase):
    def setUp(self):
        self.seller = make_seller()
        self.product = make_product(self.seller, price=25_000, is_negotiable=True)

    def test_product_stores_price_and_negotiable_flag(self):
        self.assertEqual(self.product.price, 25_000)
        self.assertTrue(self.product.is_negotiable)

    def test_product_price_can_be_null(self):
        p = make_product(self.seller, name='No Price', price=None)
        self.assertIsNone(p.price)

    def test_product_updated_at_changes_on_save(self):
        t1 = self.product.updated_at
        self.product.name = 'Updated Name'
        self.product.save()
        self.product.refresh_from_db()
        self.assertGreaterEqual(self.product.updated_at, t1)

    def test_product_str(self):
        self.assertEqual(str(self.product), 'Test Product')


# ─────────────────────────────────────────────
# ProductRating — comment field
# ─────────────────────────────────────────────

class ProductRatingTests(TestCase):
    def setUp(self):
        self.seller = make_seller()
        self.buyer = make_buyer()
        self.product = make_product(self.seller)

    def test_rating_with_comment_saved(self):
        r = ProductRating.objects.create(
            product=self.product,
            user=self.buyer,
            score=5,
            comment='Absolutely brilliant!'
        )
        r.refresh_from_db()
        self.assertEqual(r.comment, 'Absolutely brilliant!')

    def test_rating_comment_is_optional(self):
        r = ProductRating.objects.create(
            product=self.product,
            user=self.buyer,
            score=3,
        )
        self.assertEqual(r.comment, '')

    def test_rate_product_view_saves_comment(self):
        self.client.force_login(self.buyer)
        self.client.post(
            reverse('products:rate_product', args=[self.product.pk]),
            {'score': '4', 'comment': 'Good value for money'},
        )
        rating = ProductRating.objects.get(product=self.product, user=self.buyer)
        self.assertEqual(rating.score, 4)
        self.assertEqual(rating.comment, 'Good value for money')


# ─────────────────────────────────────────────
# Homepage & product detail
# ─────────────────────────────────────────────

class HomepageViewTests(TestCase):
    def setUp(self):
        self.seller = make_seller(is_verified=True)
        self.product = make_product(self.seller, price=15_000)
        self.rater = make_buyer()
        ProductRating.objects.create(product=self.product, user=self.rater, score=4)

    def test_homepage_provides_featured_products_and_stats(self):
        response = self.client.get(reverse('products:list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('products', response.context)
        self.assertEqual(response.context['products'].count(), 1)

    def test_product_detail_calculates_average_rating(self):
        self.client.force_login(self.rater)
        response = self.client.get(reverse('products:detail', args=[self.product.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['avg_rating'], 4.0)
        self.assertEqual(response.context['rating_count'], 1)

    def test_product_detail_shows_price(self):
        response = self.client.get(reverse('products:detail', args=[self.product.id]))
        self.assertContains(response, '15')  # price digits appear in the page

    def test_homepage_prioritizes_active_promotions_in_featured_products(self):
        promoted_product = make_product(self.seller, name='Boosted Product', price=20_000)
        plan = PromotionPlan.objects.create(
            name='Homepage Boost',
            duration_days=7,
            price='3000.00',
            description='Priority placement',
            features='[]',
            display_order=1,
            is_active=True,
        )
        PromotionTransaction.objects.create(
            user=self.seller,
            product=promoted_product,
            plan=plan,
            amount=plan.price,
            status='completed',
            starts_at=timezone.now() - timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=6),
        )

        response = self.client.get(reverse('homepage'))
        featured_products = list(response.context['featured_products'])
        self.assertEqual(featured_products[0].name, 'Boosted Product')

    def test_product_detail_logs_view_event(self):
        self.client.get(reverse('products:detail', args=[self.product.id]))
        self.assertEqual(
            ProductEngagement.objects.filter(
                product=self.product,
                event_type=ProductEngagement.EventType.PRODUCT_VIEW,
            ).count(),
            1,
        )


# ─────────────────────────────────────────────
# Product list filtering — search, category, price
# ─────────────────────────────────────────────

class ProductListViewTests(TestCase):
    def setUp(self):
        self.seller = make_seller()
        make_product(self.seller, name='Red Phone', description='A red phone', category='phones', price=80_000)
        make_product(self.seller, name='Blue Shirt', description='A nice shirt', category='fashion', price=12_000)

    def test_search_filters_products_by_name_or_description(self):
        response = self.client.get(reverse('products:list'), {'q': 'phone'})
        self.assertEqual(response.context['products'].count(), 1)
        self.assertEqual(response.context['products'].first().name, 'Red Phone')

    def test_category_filter_returns_matching_products(self):
        response = self.client.get(reverse('products:list'), {'category': 'fashion'})
        self.assertEqual(response.context['products'].count(), 1)
        self.assertEqual(response.context['products'].first().category, 'fashion')

    def test_price_min_filter(self):
        response = self.client.get(reverse('products:list'), {'min_price': '50000'})
        products = response.context['products']
        self.assertEqual(products.count(), 1)
        self.assertEqual(products.first().name, 'Red Phone')

    def test_price_max_filter(self):
        response = self.client.get(reverse('products:list'), {'max_price': '20000'})
        products = response.context['products']
        self.assertEqual(products.count(), 1)
        self.assertEqual(products.first().name, 'Blue Shirt')

    def test_combined_price_range_filter(self):
        response = self.client.get(reverse('products:list'), {'min_price': '10000', 'max_price': '50000'})
        self.assertEqual(response.context['products'].count(), 1)

    def test_invalid_price_filter_ignored_gracefully(self):
        response = self.client.get(reverse('products:list'), {'min_price': 'abc'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['products'].count(), 2)

    def test_default_sort_prioritizes_boosted_products(self):
        budget_phone = Product.objects.get(name='Red Phone')
        style_shirt = Product.objects.get(name='Blue Shirt')
        buyer = make_buyer('rank_buyer')
        ProductRating.objects.create(product=budget_phone, user=buyer, score=5)

        plan = PromotionPlan.objects.create(
            name='Discovery Boost',
            duration_days=3,
            price='1500.00',
            description='Top placement',
            features='[]',
            display_order=1,
            is_active=True,
        )
        PromotionTransaction.objects.create(
            user=self.seller,
            product=style_shirt,
            plan=plan,
            amount=plan.price,
            status='completed',
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(days=2),
        )

        response = self.client.get(reverse('products:list'))
        products = list(response.context['products'])
        self.assertEqual(products[0].name, 'Blue Shirt')

    def test_top_rated_sort_can_override_promotion_priority(self):
        budget_phone = Product.objects.get(name='Red Phone')
        style_shirt = Product.objects.get(name='Blue Shirt')
        ProductRating.objects.create(product=budget_phone, user=make_buyer('buyer_one'), score=5)
        ProductRating.objects.create(product=budget_phone, user=make_buyer('buyer_two'), score=4)

        plan = PromotionPlan.objects.create(
            name='Sort Boost',
            duration_days=3,
            price='1500.00',
            description='Top placement',
            features='[]',
            display_order=1,
            is_active=True,
        )
        PromotionTransaction.objects.create(
            user=self.seller,
            product=style_shirt,
            plan=plan,
            amount=plan.price,
            status='completed',
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(days=2),
        )

        response = self.client.get(reverse('products:list'), {'sort': 'top_rated'})
        products = list(response.context['products'])
        self.assertEqual(products[0].name, 'Red Phone')


# ─────────────────────────────────────────────
# Seller dashboard & product CRUD
# ─────────────────────────────────────────────

class SellerDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='regular', email='regular@example.com',
            password='testpass123', is_seller=False,
        )
        self.seller = make_seller('dashseller')
        self.product = make_product(self.seller)

    def test_non_seller_is_redirected_from_seller_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('products:seller_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('accounts:profile'))

    def test_seller_can_see_dashboard(self):
        self.client.force_login(self.seller)
        response = self.client.get(reverse('products:seller_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_seller_can_add_product_with_price(self):
        self.client.force_login(self.seller)
        response = self.client.post(reverse('products:add_product'), {
            'name': 'New Gadget',
            'description': 'A shiny new gadget',
            'category': 'electronics',
            'price': '35000',
            'is_negotiable': False,
            'whatsapp_number': '+2348099991111',
            'is_active': True,
        })
        self.assertEqual(Product.objects.filter(name='New Gadget').count(), 1)
        p = Product.objects.get(name='New Gadget')
        self.assertEqual(p.price, 35_000)

    def test_seller_can_add_product_without_price(self):
        self.client.force_login(self.seller)
        self.client.post(reverse('products:add_product'), {
            'name': 'Contact For Price Item',
            'description': 'Call for pricing',
            'category': 'other',
            'price': '',
            'is_negotiable': False,
            'whatsapp_number': '+2348099991111',
            'is_active': True,
        })
        p = Product.objects.get(name='Contact For Price Item')
        self.assertIsNone(p.price)

    def test_seller_can_delete_product(self):
        self.client.force_login(self.seller)
        self.client.post(reverse('products:delete_product', args=[self.product.pk]))
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_non_owner_cannot_edit_product(self):
        other_seller = make_seller('other')
        self.client.force_login(other_seller)
        response = self.client.get(reverse('products:edit_product', args=[self.product.pk]))
        self.assertEqual(response.status_code, 404)

    def test_contact_click_redirect_logs_engagement(self):
        response = self.client.get(reverse('products:track_contact_click', args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('wa.me', response.url)
        self.assertEqual(
            ProductEngagement.objects.filter(
                product=self.product,
                event_type=ProductEngagement.EventType.CONTACT_CLICK,
            ).count(),
            1,
        )

    def test_seller_dashboard_includes_engagement_analytics(self):
        ProductEngagement.objects.create(
            product=self.product,
            seller=self.seller,
            event_type=ProductEngagement.EventType.PRODUCT_VIEW,
            session_key='session-a',
            source='product_detail',
        )
        ProductEngagement.objects.create(
            product=self.product,
            seller=self.seller,
            event_type=ProductEngagement.EventType.CONTACT_CLICK,
            session_key='session-a',
            source='product_detail',
        )
        self.client.force_login(self.seller)
        response = self.client.get(reverse('products:seller_dashboard'))
        self.assertEqual(response.context['total_views'], 1)
        self.assertEqual(response.context['total_contact_clicks'], 1)
        self.assertEqual(response.context['overall_ctr'], 100.0)
        self.assertEqual(response.context['top_performing_product'].id, self.product.id)


# ─────────────────────────────────────────────
# UserPromotionStatus → sync_seller_flags
# ─────────────────────────────────────────────

class UserPromotionStatusTests(TestCase):
    def setUp(self):
        self.user = make_buyer('promo_user')

    def test_sync_seller_flags_verified_seller(self):
        UserPromotionStatus.objects.create(
            user=self.user,
            current_status='verified_seller',
            is_seller=True,
        )
        self.user.sync_seller_flags()
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_seller)
        self.assertTrue(self.user.seller_approved)
        self.assertFalse(self.user.is_blocked)

    def test_sync_seller_flags_banned_user(self):
        UserPromotionStatus.objects.create(
            user=self.user,
            current_status='banned',
        )
        self.user.sync_seller_flags()
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_seller)
        self.assertTrue(self.user.is_blocked)

    def test_effective_seller_status_without_promotion_record(self):
        # No UserPromotionStatus exists — should return 'regular_user' safely
        self.assertEqual(self.user.effective_seller_status, 'regular_user')


# ─────────────────────────────────────────────
# Promotion plans
# ─────────────────────────────────────────────

class PromotionPlanViewTests(TestCase):
    def test_promote_product_parses_json_features(self):
        PromotionPlan.objects.create(
            name='Premium Boost', duration_days=7, price='2500.00',
            description='Featured placement',
            features=json.dumps(['Highlight listing', 'Priority placement']),
            display_order=1, is_active=True,
        )
        response = self.client.get(reverse('products:promote_product'))
        self.assertEqual(response.status_code, 200)
        plans = response.context['plans']
        self.assertEqual(plans[0].features_list, ['Highlight listing', 'Priority placement'])

    def test_promote_product_handles_invalid_json_gracefully(self):
        PromotionPlan.objects.create(
            name='Broken Plan', duration_days=3, price='1200.00',
            description='Invalid', features='not-json', display_order=2, is_active=True,
        )
        response = self.client.get(reverse('products:promote_product'))
        self.assertEqual(response.context['plans'][0].features_list, [])

    def test_promote_product_only_shows_active_plans_ordered_by_display_order(self):
        PromotionPlan.objects.create(name='Low', duration_days=3, price='1200.00', description='', features='[]', display_order=2, is_active=True)
        PromotionPlan.objects.create(name='High', duration_days=7, price='2500.00', description='', features='[]', display_order=1, is_active=True)
        PromotionPlan.objects.create(name='Inactive', duration_days=1, price='500.00', description='', features='[]', display_order=0, is_active=False)
        response = self.client.get(reverse('products:promote_product'))
        names = [p.name for p in response.context['plans']]
        self.assertEqual(names, ['High', 'Low'])

    def test_promotion_plan_string_representation_includes_price(self):
        plan = PromotionPlan.objects.create(
            name='Test Plan', duration_days=5, price='1800.00',
            description='', features='[]', display_order=1, is_active=True,
        )
        self.assertIn('₦1800.00', str(plan))


# ─────────────────────────────────────────────
# Promotion checkout
# ─────────────────────────────────────────────

class PromotionCheckoutTests(TestCase):
    def setUp(self):
        self.seller = make_seller('checkout_seller')
        self.product = make_product(self.seller, name='Checkout Product', price=50_000)
        self.plan = PromotionPlan.objects.create(
            name='Checkout Plan', duration_days=5, price='1800.00',
            description='', features=json.dumps(['Dashboard analytics']),
            display_order=1, is_active=True,
        )
        self.non_seller = make_buyer('regularuser')

    def test_checkout_requires_login(self):
        response = self.client.get(reverse('products:promotion_checkout'))
        self.assertIn(reverse('accounts:login'), response.url)

    def test_checkout_redirects_non_seller(self):
        self.client.force_login(self.non_seller)
        response = self.client.get(reverse('products:promotion_checkout'), follow=True)
        self.assertRedirects(response, reverse('accounts:profile'))

    @patch('products.views.PaystackClient.initialize_transaction')
    def test_purchase_creates_transaction_and_redirects_to_paystack(self, mock_initialize_transaction):
        mock_initialize_transaction.return_value = {
            'access_code': 'access-123',
            'authorization_url': 'https://checkout.paystack.com/pay/promo',
        }
        self.client.force_login(self.seller)
        response = self.client.post(
            reverse('products:promotion_checkout'),
            {'product_id': self.product.id, 'plan_id': self.plan.id}
        )
        self.assertEqual(PromotionTransaction.objects.count(), 1)
        t = PromotionTransaction.objects.first()
        self.assertEqual(t.status, 'processing')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'https://checkout.paystack.com/pay/promo')

    @patch('products.views.PaystackClient.verify_transaction')
    def test_callback_completes_transaction_after_successful_payment(self, mock_verify_transaction):
        transaction = PromotionTransaction.objects.create(
            user=self.seller,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='processing',
            payment_reference='PMT-REF-123',
            channels=['ussd', 'bank_transfer'],
        )
        mock_verify_transaction.return_value = {
            'status': 'success',
            'gateway_response': 'Approved',
        }

        self.client.force_login(self.seller)
        response = self.client.get(
            reverse('products:promotion_payment_callback'),
            {'reference': transaction.payment_reference},
        )

        transaction.refresh_from_db()
        self.assertEqual(transaction.status, 'completed')
        self.assertIsNotNone(transaction.paid_at)
        self.assertIsNotNone(transaction.starts_at)
        self.assertIsNotNone(transaction.ends_at)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('products:promotion_confirmation', args=[transaction.id]))

    def test_promotion_disabled_returns_error(self):
        MonetizationSettings.objects.create(
            platform_commission_percentage='5.00',
            seller_payout_threshold='1000.00',
            promotion_enabled=False,
            verification_fee='0.00',
            marketplace_tax_percentage='0.00',
        )
        self.client.force_login(self.seller)
        self.client.post(
            reverse('products:promotion_checkout'),
            {'product_id': self.product.id, 'plan_id': self.plan.id},
            follow=True
        )
        self.assertEqual(PromotionTransaction.objects.count(), 0)
