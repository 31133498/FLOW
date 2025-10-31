from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q
from .models import EnterpriseProject, ProjectFile, ProjectAudit
from .serializers import (
    EnterpriseProjectSerializer, ProjectCreateSerializer, 
    ProjectFileSerializer, ProjectAuditSerializer, ProjectStatusUpdateSerializer
)

class ProjectListView(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ProjectCreateSerializer
        return EnterpriseProjectSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'enterprise':
            # Enterprises see their own projects
            return EnterpriseProject.objects.filter(client=user)
        elif user.role == 'student':
            # Students see active projects they can work on
            return EnterpriseProject.objects.filter(status='active')
        elif user.role == 'admin':
            # Admins see all projects
            return EnterpriseProject.objects.all()
        
        return EnterpriseProject.objects.none()
    
    def perform_create(self, serializer):
        project = serializer.save()
        
        # Create audit log
        ProjectAudit.objects.create(
            project=project,
            action='PROJECT_CREATED',
            description=f'Project "{project.title}" created',
            performed_by=self.request.user
        )

class ProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = EnterpriseProjectSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'enterprise':
            return EnterpriseProject.objects.filter(client=user)
        elif user.role == 'admin':
            return EnterpriseProject.objects.all()
        
        return EnterpriseProject.objects.filter(status='active')

class ProjectFileUploadView(generics.CreateAPIView):
    serializer_class = ProjectFileSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_id')
        
        try:
            project = EnterpriseProject.objects.get(
                id=project_id, 
                client=self.request.user
            )
        except EnterpriseProject.DoesNotExist:
            raise serializers.ValidationError("Project not found or access denied")
        
        file_obj = self.request.FILES.get('file')
        if file_obj:
            serializer.save(
                project=project,
                file_name=file_obj.name,
                file_size=file_obj.size
            )
            
            # Create audit log
            ProjectAudit.objects.create(
                project=project,
                action='FILE_UPLOADED',
                description=f'File "{file_obj.name}" uploaded',
                performed_by=self.request.user
            )

class ProjectAuditListView(generics.ListAPIView):
    serializer_class = ProjectAuditSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        user = self.request.user
        
        try:
            if user.role == 'enterprise':
                project = EnterpriseProject.objects.get(id=project_id, client=user)
            elif user.role == 'admin':
                project = EnterpriseProject.objects.get(id=project_id)
            else:
                return ProjectAudit.objects.none()
            
            return ProjectAudit.objects.filter(project=project)
            
        except EnterpriseProject.DoesNotExist:
            return ProjectAudit.objects.none()

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def fund_project_escrow(request, project_id):
    """
    Simulate escrow funding for a project
    In production, this would integrate with payment providers
    """
    try:
        project = EnterpriseProject.objects.get(id=project_id, client=request.user)
    except EnterpriseProject.DoesNotExist:
        return Response(
            {"error": "Project not found or access denied"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    if project.escrow_locked:
        return Response(
            {"error": "Project already funded"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Simulate payment processing
    with transaction.atomic():
        project.escrow_locked = True
        project.status = 'funded'
        project.save()
        
        # Create audit log
        ProjectAudit.objects.create(
            project=project,
            action='ESCROW_FUNDED',
            description=f'Project funded with {project.total_amount}',
            performed_by=request.user
        )
    
    return Response({
        "message": "Project funded successfully",
        "project_id": project.id,
        "status": project.status
    })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def trigger_atomization(request, project_id):
    """
    Trigger task atomization for a funded project
    This would typically be a Celery task
    """
    try:
        project = EnterpriseProject.objects.get(id=project_id, client=request.user)
    except EnterpriseProject.DoesNotExist:
        return Response(
            {"error": "Project not found or access denied"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    if not project.escrow_locked:
        return Response(
            {"error": "Project must be funded before atomization"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if project.status not in ['funded', 'draft']:
        return Response(
            {"error": "Project cannot be atomized in current state"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Simulate atomization process
    from tasks.tasks import atomize_project_tasks
    atomize_project_tasks.delay(project.id)
    
    # Update project status
    project.status = 'processing'
    project.save()
    
    # Create audit log
    ProjectAudit.objects.create(
        project=project,
        action='ATOMIZATION_TRIGGERED',
        description='Task atomization process started',
        performed_by=request.user
    )
    
    return Response({
        "message": "Atomization process started",
        "project_id": project.id,
        "status": project.status
    })