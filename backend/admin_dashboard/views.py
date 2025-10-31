from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Count, Sum, Q, F
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

from .models import AdminDashboard, SystemAlert, AuditLog, DisputeCase
from .serializers import (
    DashboardStatsSerializer, SystemAlertSerializer, AuditLogSerializer,
    DisputeCaseSerializer, DisputeResolutionSerializer, UserManagementSerializer,
    KYCReviewSerializer, ProjectManagementSerializer, FinancialOverviewSerializer
)
from users.models import User, KYCRecord
from projects.models import EnterpriseProject
from tasks.models import TaskUnit
from wallet.models import WalletTransaction, EscrowLedger

User = get_user_model()

class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow admin users to access the view.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'

@api_view(['GET'])
@permission_classes([IsAdminUser])
def dashboard_stats(request):
    """
    Get comprehensive dashboard statistics
    """
    # User statistics
    total_students = User.objects.filter(role='student').count()
    total_enterprises = User.objects.filter(role='enterprise').count()
    
    # Project statistics
    total_projects = EnterpriseProject.objects.count()
    total_tasks_completed = TaskUnit.objects.filter(status='completed').count()
    
    # Financial statistics
    total_volume_processed = TaskUnit.objects.filter(
        status='completed'
    ).aggregate(total=Sum('pay_amount'))['total'] or 0
    
    # Platform earnings (simplified - 5% platform fee)
    platform_earnings = float(total_volume_processed) * 0.05 if total_volume_processed else 0
    
    # Pending items
    pending_kyc = KYCRecord.objects.filter(status='pending').count()
    pending_disputes = DisputeCase.objects.filter(status='open').count()
    pending_withdrawals = WalletTransaction.objects.filter(
        transaction_type='withdrawal',
        status__in=['pending', 'processing']
    ).count()
    
    # Today's activity
    today = timezone.now().date()
    projects_today = EnterpriseProject.objects.filter(created_at__date=today).count()
    tasks_today = TaskUnit.objects.filter(created_at__date=today).count()
    withdrawals_today = WalletTransaction.objects.filter(
        transaction_type='withdrawal',
        created_at__date=today
    ).count()
    
    stats = {
        'total_students': total_students,
        'total_enterprises': total_enterprises,
        'total_projects': total_projects,
        'total_tasks_completed': total_tasks_completed,
        'total_volume_processed': total_volume_processed,
        'platform_earnings': platform_earnings,
        'pending_kyc': pending_kyc,
        'pending_disputes': pending_disputes,
        'pending_withdrawals': pending_withdrawals,
        'projects_today': projects_today,
        'tasks_today': tasks_today,
        'withdrawals_today': withdrawals_today,
    }
    
    serializer = DashboardStatsSerializer(stats)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def financial_overview(request):
    """
    Get financial overview and metrics
    """
    today = timezone.now().date()
    
    # Escrow calculations
    total_escrow_balance = EnterpriseProject.objects.filter(
        escrow_locked=True
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Wallet balances
    total_wallet_balances = User.objects.aggregate(
        total=Sum('wallet_balance')
    )['total'] or 0
    
    # Today's transactions
    total_withdrawals_today = WalletTransaction.objects.filter(
        transaction_type='withdrawal',
        created_at__date=today,
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_deposits_today = WalletTransaction.objects.filter(
        transaction_type__in=['deposit', 'escrow_funding'],
        created_at__date=today,
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Counts
    pending_withdrawals_count = WalletTransaction.objects.filter(
        transaction_type='withdrawal',
        status__in=['pending', 'processing']
    ).count()
    
    failed_transactions_count = WalletTransaction.objects.filter(
        status='failed'
    ).count()
    
    # Transaction timelines
    transactions_today = WalletTransaction.objects.filter(
        created_at__date=today
    ).count()
    
    week_ago = today - timedelta(days=7)
    transactions_this_week = WalletTransaction.objects.filter(
        created_at__date__gte=week_ago
    ).count()
    
    month_ago = today - timedelta(days=30)
    transactions_this_month = WalletTransaction.objects.filter(
        created_at__date__gte=month_ago
    ).count()
    
    financial_data = {
        'total_escrow_balance': total_escrow_balance,
        'total_wallet_balances': total_wallet_balances,
        'total_withdrawals_today': total_withdrawals_today,
        'total_deposits_today': total_deposits_today,
        'pending_withdrawals_count': pending_withdrawals_count,
        'failed_transactions_count': failed_transactions_count,
        'transactions_today': transactions_today,
        'transactions_this_week': transactions_this_week,
        'transactions_this_month': transactions_this_month,
    }
    
    serializer = FinancialOverviewSerializer(financial_data)
    return Response(serializer.data)

class SystemAlertListView(generics.ListCreateAPIView):
    serializer_class = SystemAlertSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        return SystemAlert.objects.all().order_by('-created_at')

class SystemAlertDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = SystemAlertSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        return SystemAlert.objects.all()

class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        # Filter by date range if provided
        days = self.request.query_params.get('days', 30)
        try:
            days = int(days)
            since_date = timezone.now() - timedelta(days=days)
            return AuditLog.objects.filter(created_at__gte=since_date)
        except ValueError:
            return AuditLog.objects.all()
    
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        
        # Add summary statistics
        days = self.request.query_params.get('days', 30)
        try:
            days = int(days)
            since_date = timezone.now() - timedelta(days=days)
            
            action_counts = AuditLog.objects.filter(
                created_at__gte=since_date
            ).values('action').annotate(count=Count('action'))
            
            response.data['summary'] = {
                'total_actions': sum(item['count'] for item in action_counts),
                'action_breakdown': list(action_counts)
            }
        except ValueError:
            pass
        
        return response

class DisputeCaseListView(generics.ListAPIView):
    serializer_class = DisputeCaseSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        status_filter = self.request.query_params.get('status', None)
        queryset = DisputeCase.objects.all()
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-created_at')

class DisputeCaseDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = DisputeCaseSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        return DisputeCase.objects.all()
    
    def update(self, request, *args, **kwargs):
        dispute = self.get_object()
        
        if 'status' in request.data and request.data['status'] == 'resolved':
            # Handle dispute resolution
            resolution_serializer = DisputeResolutionSerializer(data=request.data)
            if resolution_serializer.is_valid():
                dispute.resolution = resolution_serializer.validated_data['resolution']
                dispute.resolution_notes = resolution_serializer.validated_data['resolution_notes']
                dispute.resolved_by = request.user
                dispute.resolved_at = timezone.now()
                dispute.status = 'resolved'
                dispute.save()
                
                # Create audit log
                AuditLog.objects.create(
                    user=request.user,
                    action='dispute_resolved',
                    description=f'Resolved dispute #{dispute.id} with resolution: {dispute.resolution}',
                    resource_id=str(dispute.id),
                    resource_type='dispute'
                )
                
                return Response(DisputeCaseSerializer(dispute).data)
            else:
                return Response(resolution_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        return super().update(request, *args, **kwargs)

class UserManagementListView(generics.ListAPIView):
    serializer_class = UserManagementSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        role_filter = self.request.query_params.get('role', None)
        queryset = User.objects.all()
        
        if role_filter:
            queryset = queryset.filter(role=role_filter)
        
        return queryset.order_by('-date_joined')

class UserManagementDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = UserManagementSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        return User.objects.all()

class KYCReviewListView(generics.ListAPIView):
    serializer_class = KYCReviewSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        status_filter = self.request.query_params.get('status', 'pending')
        return KYCRecord.objects.filter(status=status_filter).order_by('created_at')

@api_view(['POST'])
@permission_classes([IsAdminUser])
def approve_kyc(request, kyc_id):
    """
    Approve a KYC application
    """
    try:
        kyc_record = KYCRecord.objects.get(id=kyc_id)
    except KYCRecord.DoesNotExist:
        return Response(
            {"error": "KYC record not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    kyc_record.status = 'approved'
    kyc_record.verified_by = request.user
    kyc_record.verified_at = timezone.now()
    kyc_record.save()
    
    # Update user KYC status
    user = kyc_record.user
    user.kyc_completed = True
    user.save()
    
    # Create audit log
    AuditLog.objects.create(
        user=request.user,
        action='kyc_approved',
        description=f'Approved KYC for user {user.username}',
        resource_id=str(user.id),
        resource_type='user'
    )
    
    return Response({
        "message": "KYC approved successfully",
        "kyc_id": kyc_record.id,
        "user_id": user.id
    })

@api_view(['POST'])
@permission_classes([IsAdminUser])
def reject_kyc(request, kyc_id):
    """
    Reject a KYC application
    """
    try:
        kyc_record = KYCRecord.objects.get(id=kyc_id)
    except KYCRecord.DoesNotExist:
        return Response(
            {"error": "KYC record not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    rejection_reason = request.data.get('reason', '')
    
    kyc_record.status = 'rejected'
    kyc_record.verified_by = request.user
    kyc_record.verified_at = timezone.now()
    kyc_record.metadata['rejection_reason'] = rejection_reason
    kyc_record.save()
    
    # Create audit log
    AuditLog.objects.create(
        user=request.user,
        action='kyc_rejected',
        description=f'Rejected KYC for user {kyc_record.user.username}. Reason: {rejection_reason}',
        resource_id=str(kyc_record.user.id),
        resource_type='user'
    )
    
    return Response({
        "message": "KYC rejected successfully",
        "kyc_id": kyc_record.id
    })

class ProjectManagementListView(generics.ListAPIView):
    serializer_class = ProjectManagementSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        status_filter = self.request.query_params.get('status', None)
        queryset = EnterpriseProject.objects.all()
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-created_at')

@api_view(['GET'])
@permission_classes([IsAdminUser])
def recent_activity(request):
    """
    Get recent platform activity for admin dashboard
    """
    # Recent users
    recent_users = User.objects.order_by('-date_joined')[:5]
    
    # Recent projects
    recent_projects = EnterpriseProject.objects.order_by('-created_at')[:5]
    
    # Recent transactions
    recent_transactions = WalletTransaction.objects.order_by('-created_at')[:10]
    
    # Recent tasks
    recent_tasks = TaskUnit.objects.order_by('-created_at')[:10]
    
    # System alerts
    active_alerts = SystemAlert.objects.filter(is_resolved=False).order_by('-created_at')[:5]
    
    activity_data = {
        'recent_users': UserManagementSerializer(recent_users, many=True).data,
        'recent_projects': ProjectManagementSerializer(recent_projects, many=True).data,
        'recent_transactions': [],  # You'd need a transaction serializer
        'recent_tasks': [],  # You'd need a task serializer
        'active_alerts': SystemAlertSerializer(active_alerts, many=True).data,
    }
    
    return Response(activity_data)