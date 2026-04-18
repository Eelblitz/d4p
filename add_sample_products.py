"""
Seed the database with sample products for development/testing.

Usage:
    python add_sample_products.py

Reads seller credentials from .env:
    SAMPLE_SELLER_USERNAME  (default: john_seller)
    SAMPLE_SELLER_PASSWORD  (default: change_me_seller)
    SAMPLE_SELLER_EMAIL     (default: john@example.com)
"""
import os
import django
from decouple import config

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User
from products.models import Product, ProductRating

SELLER_USERNAME = config('SAMPLE_SELLER_USERNAME', default='john_seller')
SELLER_EMAIL    = config('SAMPLE_SELLER_EMAIL',    default='john@example.com')
SELLER_PASSWORD = config('SAMPLE_SELLER_PASSWORD', default='change_me_seller')

seller, created = User.objects.get_or_create(
    username=SELLER_USERNAME,
    defaults={'email': SELLER_EMAIL, 'is_seller': True, 'seller_approved': True},
)
if created or not seller.has_usable_password():
    seller.set_password(SELLER_PASSWORD)
    seller.save()

sample_products = [
    {
        'name': 'iPhone 15 Pro',
        'description': 'Latest iPhone 15 Pro with A17 Pro chip and advanced camera system.\n\n• 6.1-inch display\n• Titanium design\n• Triple camera setup\n• 5G ready',
        'category': 'phones',
        'price': 1_200_000,
        'is_negotiable': True,
        'whatsapp_number': '+2348012345678',
    },
    {
        'name': 'Wireless Bluetooth Headphones',
        'description': 'Premium quality wireless headphones with noise cancellation.\n\n• Active noise cancellation\n• 30-hour battery life\n• Comfortable fit\n• Crystal clear sound',
        'category': 'electronics',
        'price': 45_000,
        'is_negotiable': False,
        'whatsapp_number': '+2348012345678',
    },
    {
        'name': 'Samsung 65" Smart TV',
        'description': 'Ultra HD Samsung Smart TV with built-in apps.\n\n• 4K resolution\n• HDR support\n• Smart TV features\n• Great for streaming',
        'category': 'electronics',
        'price': 350_000,
        'is_negotiable': True,
        'whatsapp_number': '+2348012345678',
    },
    {
        'name': 'Designer Fashion Watch',
        'description': 'Elegant stainless steel watch perfect for any occasion.\n\n• Stainless steel band\n• Water resistant\n• Date display\n• Automatic movement',
        'category': 'fashion',
        'price': 85_000,
        'is_negotiable': False,
        'whatsapp_number': '+2348012345678',
    },
    {
        'name': 'Wooden Coffee Table',
        'description': 'Beautiful wooden coffee table with storage compartment.\n\n• Solid oak wood\n• Storage drawer\n• Modern design\n• Perfect for living rooms',
        'category': 'furniture',
        'price': 120_000,
        'is_negotiable': True,
        'whatsapp_number': '+2348012345678',
    },
    {
        'name': 'Organic Coffee Beans',
        'description': 'Premium organic coffee beans from Ethiopia.\n\n• 100% organic\n• Single origin\n• Fresh roasted\n• Rich aroma and taste',
        'category': 'food',
        'price': 8_500,
        'is_negotiable': False,
        'whatsapp_number': '+2348012345678',
    },
]

for data in sample_products:
    product, created = Product.objects.get_or_create(
        name=data['name'],
        seller=seller,
        defaults={
            'description': data['description'],
            'category': data['category'],
            'price': data['price'],
            'is_negotiable': data['is_negotiable'],
            'whatsapp_number': data['whatsapp_number'],
            'is_active': True,
        }
    )

    if created:
        for i in range(1, 4):
            buyer, _ = User.objects.get_or_create(
                username=f'sample_user{i}',
                defaults={'email': f'sampleuser{i}@example.com'},
            )
            ProductRating.objects.get_or_create(
                product=product,
                user=buyer,
                defaults={
                    'score': (i + 3) % 5 + 1,
                    'comment': f'Sample review from user {i}.',
                }
            )
        print(f"✅ Created: {product.name} — ₦{product.price:,.0f}")
    else:
        print(f"⏭️  Already exists: {product.name}")

print("\n✨ Sample data setup complete!")
