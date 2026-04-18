from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0004_adminauditlog_moderationaction_monetizationsettings_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Leave blank for 'Contact for price'",
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='is_negotiable',
            field=models.BooleanField(default=False, help_text='Check if price is negotiable'),
        ),
        migrations.AddField(
            model_name='product',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='productrating',
            name='comment',
            field=models.TextField(blank=True, help_text='Optional written review'),
        ),
    ]
