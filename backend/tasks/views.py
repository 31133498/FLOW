import json
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from .models import TaskUnit, TaskSubmission, TaskValidation
from .serializers import (
    TaskUnitSerializer, TaskUnitListSerializer, CreateTaskSubmissionSerializer,
    TaskValidationSerializer, AcceptTaskSerializer, TaskStreamSerializer
)
from wallet.models import WalletTransaction

class AvailableTasksView(generics.ListAPIView):
    serializer_class = TaskUnitListSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role != 'student':
            return TaskUnit.objects.none()
        
        # Only show available tasks that match user's tier and are not assigned
        return TaskUnit.objects.filter(
            status='available',
            project__status='active',
            project__escrow_locked=True
        ).exclude(
            # Exclude tasks already attempted or completed by user
            Q(assigned_to=user) & 
            Q(status__in=['assigned', 'submitted', 'completed'])
        )[:50]  # Limit results

class TaskDetailView(generics.RetrieveAPIView):
    serializer_class = TaskUnitSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'student':
            return TaskUnit.objects.filter(
                Q(assigned_to=user) | Q(status='available')
            )
        elif user.role == 'enterprise':
            return TaskUnit.objects.filter(project__client=user)
        elif user.role == 'admin':
            return TaskUnit.objects.all()
        
        return TaskUnit.objects.none()

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def accept_task(request, task_id):
    """
    Student accepts an available task
    """
    if request.user.role != 'student':
        return Response(
            {"error": "Only students can accept tasks"}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        task = TaskUnit.objects.get(id=task_id, status='available')
    except TaskUnit.DoesNotExist:
        return Response(
            {"error": "Task not available or already taken"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if student has too many pending tasks
    pending_tasks = TaskUnit.objects.filter(
        assigned_to=request.user,
        status__in=['assigned', 'submitted']
    ).count()
    
    if pending_tasks >= 5:  # Limit concurrent tasks
        return Response(
            {"error": "You have too many pending tasks. Complete some before accepting new ones."}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    with transaction.atomic():
        task.assigned_to = request.user
        task.status = 'assigned'
        task.assigned_at = timezone.now()
        task.save()
    
    serializer = TaskUnitSerializer(task)
    return Response({
        "message": "Task accepted successfully",
        "task": serializer.data
    })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def submit_task(request, task_id):
    """
    Student submits a completed task
    """
    if request.user.role != 'student':
        return Response(
            {"error": "Only students can submit tasks"}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        task = TaskUnit.objects.get(id=task_id, assigned_to=request.user, status='assigned')
    except TaskUnit.DoesNotExist:
        return Response(
            {"error": "Task not found or not assigned to you"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    serializer = CreateTaskSubmissionSerializer(
        data=request.data, 
        context={'task_unit': task}
    )
    serializer.is_valid(raise_exception=True)
    
    with transaction.atomic():
        # Create submission
        submission = serializer.save(
            task_unit=task,
            submitted_by=request.user
        )
        
        # Update task status
        task.status = 'submitted'
        task.submitted_at = timezone.now()
        task.submission_data = submission.submission_data
        task.save()
        
        # Trigger verification process
        from .tasks import process_task_verification
        process_task_verification.delay(task.id)
    
    return Response({
        "message": "Task submitted successfully",
        "submission_id": submission.id,
        "task_status": task.status
    })

class MyTasksView(generics.ListAPIView):
    serializer_class = TaskUnitListSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'student':
            status_filter = self.request.query_params.get('status', None)
            queryset = TaskUnit.objects.filter(assigned_to=user)
            
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            return queryset
        
        return TaskUnit.objects.none()

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def task_stream(request):
    """
    Simple task stream endpoint - returns available tasks
    In production, this would use WebSockets or Server-Sent Events
    """
    if request.user.role != 'student':
        return Response(
            {"error": "Only students can access task stream"}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    available_tasks = TaskUnit.objects.filter(
        status='available',
        project__status='active',
        project__escrow_locked=True
    ).exclude(
        assigned_to=request.user
    )[:20]  # Limit for performance
    
    serializer = TaskStreamSerializer(available_tasks, many=True)
    return Response(serializer.data)

class TaskValidationView(generics.ListCreateAPIView):
    serializer_class = TaskValidationSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        # Students can validate tasks for peer consensus
        if self.request.user.role == 'student':
            return TaskValidation.objects.filter(validator=self.request.user)
        return TaskValidation.objects.none()
    
    def perform_create(self, serializer):
        task_id = self.kwargs.get('task_id')
        
        try:
            task = TaskUnit.objects.get(id=task_id)
        except TaskUnit.DoesNotExist:
            raise serializers.ValidationError("Task not found")
        
        # Check if user is already validating this task
        existing_validation = TaskValidation.objects.filter(
            task_unit=task,
            validator=self.request.user
        ).exists()
        
        if existing_validation:
            raise serializers.ValidationError("You are already validating this task")
        
        serializer.save(
            task_unit=task,
            validator=self.request.user
        )