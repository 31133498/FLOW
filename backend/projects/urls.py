from django.urls import path
from . import views

urlpatterns = [
    path('', views.ProjectListView.as_view(), name='project-list'),
    path('<int:pk>/', views.ProjectDetailView.as_view(), name='project-detail'),
    path('<int:project_id>/files/', views.ProjectFileUploadView.as_view(), name='project-file-upload'),
    path('<int:project_id>/fund-escrow/', views.fund_project_escrow, name='fund-project-escrow'),
    path('<int:project_id>/atomize/', views.trigger_atomization, name='trigger-atomization'),
    path('<int:project_id>/audit-logs/', views.ProjectAuditListView.as_view(), name='project-audit-logs'),
]