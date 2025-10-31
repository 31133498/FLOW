from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.login_view, name='login'),
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('profile/detail/', views.UserProfileDetailView.as_view(), name='user-profile-detail'),
    path('kyc/', views.KYCRecordView.as_view(), name='kyc-records'),
    path('send-otp/', views.send_otp, name='send-otp'),
    path('verify-otp/', views.verify_otp, name='verify-otp'),
    path('stats/', views.user_stats, name='user-stats'),
]