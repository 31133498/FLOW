import json
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from .models import TaskUnit, TaskSubmission
from .serializers import TaskUnitSerializer, TaskUnitListSerializer, TaskSubmissionSerializer
from apps.wallet.models import WalletTransaction

class AvailableTasksView(generics.ListAPIView):
    serializer_class = TaskUnitListSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        # Only show available tasks that match user's tier and are not assigned
        user = self.request.user
        return TaskUnit.objects.filter(
            status='available',
            project__status='active',
            project__escrow_locked=True
        ).exclude(
            # Exclude tasks already attempted or completed by user
            project__task_units__assigned_to=user,
            project__task_units__status__in=['assigned', 'submitted', 'completed']
        )[:50]  # Limit results

class AcceptTaskView(generics.UpdateAPIView):
    queryset = TaskUnit.objects.filter(status='available')
    serializer_class = TaskUnitSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def update(self, request, *args, **kwargs):
        task = self.get_object()
        
        with transaction.atomic():
            task.assigned_to = request.user
            task.status = 'assigned'
            task.assigned_at = timezone.now()
            task.save()
            
        serializer = self.get_serializer(task)
        return Response(serializer.data)

class SubmitTaskView(generics.CreateAPIView):
    serializer_class = TaskSubmissionSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def create(self, request, *args, **kwargs):
        task_id = kwargs.get('task_id')
        
        try:
            task = TaskUnit.objects.get(id=task_id, assigned_to=request.user, status='assigned')
        except TaskUnit.DoesNotExist:
            return Response(
                {"error": "Task not found or not assigned to you"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        with transaction.atomic():
            submission_serializer = self.get_serializer(data=request.data)
            submission_serializer.is_valid(raise_exception=True)
            submission = submission_serializer.save(
                task_unit=task,
                submitted_by=request.user
            )
            
            # Update task status
            task.status = 'submitted'
            task.submitted_at = timezone.now()
            task.submission_data = submission.submission_data
            task.save()
            
            # Trigger verification process
            self.trigger_verification(task, submission)
        
        return Response(
            {"message": "Task submitted successfully", "submission": submission_serializer.data},
            status=status.HTTP_201_CREATED
        )
    
    def trigger_verification(self, task, submission):
        # This will be handled by Celery task
        from .tasks import process_task_verification
        process_task_verification.delay(task.id, submission.id)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def task_stream(request):
    # Simple implementation - in production, use WebSockets or Server-Sent Events
    user = request.user
    available_tasks = TaskUnit.objects.filter(
        status='available',
        project__status='active'
    ).exclude(
        project__task_units__assigned_to=user,
        project__task_units__status__in=['assigned', 'submitted', 'completed']
    )[:10]
    
    serializer = TaskUnitListSerializer(available_tasks, many=True)
    return Response(serializer.data)