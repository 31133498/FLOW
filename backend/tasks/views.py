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
from .tasks import check_validation_consensus

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
        
class MyValidationsView(generics.ListAPIView):
    """
    Get tasks that a student can validate (for peer consensus)
    """
    serializer_class = TaskUnitListSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role != 'student':
            return TaskUnit.objects.none()
        
        # Find tasks that need validation and user can validate
        available_for_validation = TaskUnit.objects.filter(
            status='verifying',
            verification_strategy='peer_consensus'
        ).exclude(
            Q(assigned_to=user) |  # Can't validate own tasks
            Q(validations__validator=user)  # Already validating
        )
        
        return available_for_validation

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def submit_validation(request, task_id):
    """
    Submit validation for a task (peer consensus)
    """
    if request.user.role != 'student':
        return Response(
            {"error": "Only students can validate tasks"}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        task = TaskUnit.objects.get(id=task_id, status='verifying')
    except TaskUnit.DoesNotExist:
        return Response(
            {"error": "Task not found or not available for validation"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if user can validate this task (using the utility function)
    if not can_user_validate_task(task, request.user):
        return Response(
            {"error": "Cannot validate this task"}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = TaskValidationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    # Create validation
    validation = serializer.save(
        task_unit=task,
        validator=request.user
    )
    
    # Check if we have enough validations to make a decision
    check_validation_consensus.delay(task.id)
    
    return Response({
        "message": "Validation submitted successfully",
        "validation_id": validation.id
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def validation_stats(request):
    """
    Get validation statistics for a student
    """
    if request.user.role != 'student':
        return Response(
            {"error": "Only students can access validation stats"}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    user = request.user
    stats = {
        'validations_completed': TaskValidation.objects.filter(validator=user).count(),
        'validations_approved': TaskValidation.objects.filter(validator=user, status='approved').count(),
        'validations_rejected': TaskValidation.objects.filter(validator=user, status='rejected').count(),
        'accuracy_rate': 0,  # This would be calculated based on consensus
        'reputation_impact': user.reputation_score,
    }
    
    # Calculate accuracy rate (simplified)
    total_validations = stats['validations_completed']
    if total_validations > 0:
        # This is a simplified calculation - in reality, you'd compare with final outcomes
        stats['accuracy_rate'] = (stats['validations_approved'] / total_validations) * 100
    
    return Response(stats)

def can_user_validate_task(task, user):
    """Check if user can validate this task"""
    if user == task.assigned_to:
        return False  # Can't validate own task
    if user.role != 'student':
        return False
    if not user.is_verified:
        return False
    # Check if user is already validating this task
    return not TaskValidation.objects.filter(
        task_unit=task, 
        validator=user
    ).exists()