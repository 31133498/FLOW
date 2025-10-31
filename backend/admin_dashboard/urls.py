from django.urls import path
from . import views

urlpatterns = [
    # Dashboard overview
    path('stats/', views.dashboard_stats, name='dashboard-stats'),
    path('financial-overview/', views.financial_overview, name='financial-overview'),
    path('recent-activity/', views.recent_activity, name='recent-activity'),
    
    # System alerts
    path('alerts/', views.SystemAlertListView.as_view(), name='system-alerts'),
    path('alerts/<int:pk>/', views.SystemAlertDetailView.as_view(), name='system-alert-detail'),
    
    # Audit logs
    path('audit-logs/', views.AuditLogListView.as_view(), name='audit-logs'),
    
    # Dispute management
    path('disputes/', views.DisputeCaseListView.as_view(), name='dispute-cases'),
    path('disputes/<int:pk>/', views.DisputeCaseDetailView.as_view(), name='dispute-case-detail'),
    
    # User management
    path('users/', views.UserManagementListView.as_view(), name='user-management'),
    path('users/<int:pk>/', views.UserManagementDetailView.as_view(), name='user-management-detail'),
    
    # KYC management
    path('kyc-applications/', views.KYCReviewListView.as_view(), name='kyc-applications'),
    path('kyc/<int:kyc_id>/approve/', views.approve_kyc, name='approve-kyc'),
    path('kyc/<int:kyc_id>/reject/', views.reject_kyc, name='reject-kyc'),
    
    # Project management
    path('projects/', views.ProjectManagementListView.as_view(), name='project-management'),
]
