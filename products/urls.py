from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    # Public product browsing
    path('', views.product_list, name='list'),
    path('<int:pk>/', views.product_detail, name='detail'),
    
    # Seller dashboard
    path('seller/dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('seller/add/', views.add_product, name='add_product'),
    path('seller/<int:pk>/edit/', views.edit_product, name='edit_product'),
    path('seller/<int:pk>/delete/', views.delete_product, name='delete_product'),
    path('seller/<int:pk>/images/', views.product_images, name='product_images'),
    path('seller/image/<int:image_id>/delete/', views.delete_image, name='delete_image'),
    path('seller/image/<int:image_id>/set-primary/', views.set_primary_image, name='set_primary_image'),
    
    # Product rating
    path('<int:pk>/rate/', views.rate_product, name='rate_product'),
    path('<int:pk>/contact/', views.track_contact_click, name='track_contact_click'),
    
    # Product and seller reporting
    path('<int:pk>/report/', views.report_product, name='report_product'),
    path('seller/<int:user_id>/report/', views.report_seller, name='report_seller'),

    # Trust & Safety static page
    path('trust-safety/', views.trust_safety, name='trust_safety'),
    
    # Product promotion page
    path('promote/', views.promote_product, name='promote_product'),
    path('promote/checkout/', views.promotion_checkout, name='promotion_checkout'),
    path('promote/checkout/callback/', views.promotion_payment_callback, name='promotion_payment_callback'),
    path('promote/confirmation/<int:transaction_id>/', views.promotion_confirmation, name='promotion_confirmation'),
]
