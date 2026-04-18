"""
Create a superuser for DM4PRICE.

Usage:
    python create_admin.py

Reads credentials from environment variables or .env file:
    ADMIN_USERNAME  (default: admin)
    ADMIN_EMAIL     (default: admin@example.com)
    ADMIN_PASSWORD  (required — no insecure default)
"""
import os
import django
from decouple import config

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User

username = config('ADMIN_USERNAME', default='admin')
email = config('ADMIN_EMAIL', default='admin@example.com')
password = config('ADMIN_PASSWORD', default='')

if not password:
    raise SystemExit(
        "ERROR: Set ADMIN_PASSWORD in your .env file before running this script.\n"
        "Example: ADMIN_PASSWORD=MyStr0ngP@ss"
    )

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"✅ Superuser '{username}' created!")
else:
    print(f"ℹ️  Superuser '{username}' already exists — skipped.")
