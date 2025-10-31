from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import AdminDashboard, SystemAlert, AuditLog, DisputeCase
from users.models import User, KYCRecord
from projects.models import EnterpriseProject
from tasks.models import TaskUnit
from wallet.models import WalletTransaction

User = get_user_model()

class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for dashboard statistics"""
    total_students = serializers.IntegerField()
    total_enterprises = serializers.IntegerField()
    total_projects = serializers.IntegerField()
    total_tasks_completed = serializers.IntegerField()
    total_volume_processed = serializers.DecimalField(max_digits=12, decimal_places=2)
    platform_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    pending_kyc = serializers.IntegerField()
    pending_disputes = serializers.IntegerField()
    pending_withdrawals = serializers.IntegerField()
    
    # Recent activity counts
    projects_today = serializers.IntegerField()
    tasks_today = serializers.IntegerField()
    withdrawals_today = serializers.IntegerField()

class SystemAlertSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    resolved_by_username = serializers.CharField(source='resolved_by.username', read_only=True, allow_null=True)
    
    class Meta:
        model = SystemAlert
        fields = '__all__'
        read_only_fields = ('created_at', 'resolved_at')

class AuditLogSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True, allow_null=True)
    user_email = serializers.CharField(source='user.email', read_only=True, allow_null=True)
    
    class Meta:
        model = AuditLog
        fields = '__all__'
        read_only_fields = ('created_at',)

class DisputeCaseSerializer(serializers.ModelSerializer):
    raised_by_username = serializers.CharField(source='raised_by.username', read_only=True)
    assigned_admin_username = serializers.CharField(source='assigned_admin.username', read_only=True, allow_null=True)
    resolved_by_username = serializers.CharField(source='resolved_by.username', read_only=True, allow_null=True)
    task_title = serializers.CharField(source='task.title', read_only=True)
    project_title = serializers.CharField(source='task.project.title', read_only=True)
    
    class Meta:
        model = DisputeCase
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'resolved_at')

class DisputeResolutionSerializer(serializers.Serializer):
    resolution = serializers.ChoiceField(choices=DisputeCase.RESOLUTION_CHOICES)
    resolution_notes = serializers.CharField(required=True)

class UserManagementSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'phone', 'role', 'kyc_completed', 
                 'wallet_balance', 'reputation_score', 'tier', 'is_verified', 
                 'date_joined', 'last_login', 'profile')
    
    def get_profile(self, obj):
        from users.serializers import UserProfileSerializer
        try:
            profile = obj.profile
            return UserProfileSerializer(profile).data
        except:
            return None

class KYCReviewSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = KYCRecord
        fields = '__all__'

class ProjectManagementSerializer(serializers.ModelSerializer):
    client_username = serializers.CharField(source='client.username', read_only=True)
    client_email = serializers.CharField(source='client.email', read_only=True)
    progress_percentage = serializers.FloatField(read_only=True)
    
    class Meta:
        model = EnterpriseProject
        fields = '__all__'

class FinancialOverviewSerializer(serializers.Serializer):
    total_escrow_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_wallet_balances = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_withdrawals_today = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_deposits_today = serializers.DecimalField(max_digits=14, decimal_places=2)
    pending_withdrawals_count = serializers.IntegerField()
    failed_transactions_count = serializers.IntegerField()
    
    # Transaction breakdown
    transactions_today = serializers.IntegerField()
    transactions_this_week = serializers.IntegerField()
    transactions_this_month = serializers.IntegerField()