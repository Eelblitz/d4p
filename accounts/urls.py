from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('profile/verify-nin/', views.verify_nin, name='verify_nin'),
    path('profile/seller-payment/', views.start_seller_verification_payment, name='start_seller_verification_payment'),
    path('profile/seller-payment/callback/', views.seller_verification_payment_callback, name='seller_verification_payment_callback'),
    
    # Email verification
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),
    
    # User safety
    path('block/<int:user_id>/', views.block_user, name='block_user'),
    path('report/<int:user_id>/', views.report_user, name='report_user'),
    
    # Admin Dashboard
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/seller/<int:user_id>/approve/', views.approve_seller, name='approve_seller'),
    path('admin/seller/<int:user_id>/reject/', views.reject_seller, name='reject_seller'),
    path('admin/seller/<int:user_id>/verify/', views.toggle_seller_verified, name='toggle_seller_verified'),
    path('admin/user/<int:user_id>/block/', views.block_user_admin, name='block_user_admin'),
    path('admin/user/<int:user_id>/unblock/', views.unblock_user_admin, name='unblock_user_admin'),
    path('admin/report/<int:report_id>/resolve/', views.resolve_report, name='resolve_report'),
]
