from django.urls import path
from . import views

urlpatterns = [
    path('available/', views.AvailableTasksView.as_view(), name='available-tasks'),
    path('my-tasks/', views.MyTasksView.as_view(), name='my-tasks'),
    path('stream/', views.task_stream, name='task-stream'),
    path('<int:pk>/', views.TaskDetailView.as_view(), name='task-detail'),
    path('<int:task_id>/accept/', views.accept_task, name='accept-task'),
    path('<int:task_id>/submit/', views.submit_task, name='submit-task'),
    path('<int:task_id>/validations/', views.TaskValidationView.as_view(), name='task-validations'),
]