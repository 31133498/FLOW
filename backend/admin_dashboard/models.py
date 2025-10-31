from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class AdminDashboard(models.Model):
    """Main dashboard model for storing aggregated stats"""
    total_students = models.IntegerField(default=0)
    total_enterprises = models.IntegerField(default=0)
    total_projects = models.IntegerField(default=0)
    total_tasks_completed = models.IntegerField(default=0)
    total_volume_processed = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_recorded = models.DateField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Dashboard Snapshot'
        verbose_name_plural = 'Dashboard Snapshots'
    
    def __str__(self):
        return f"Dashboard Stats - {self.date_recorded}"

class SystemAlert(models.Model):
    SEVERITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )
    
    ALERT_TYPES = (
        ('payment_issue', 'Payment Issue'),
        ('verification_failure', 'Verification Failure'),
        ('system_error', 'System Error'),
        ('security_alert', 'Security Alert'),
        ('performance_issue', 'Performance Issue'),
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_severity_display()}: {self.title}"

class AuditLog(models.Model):
    ACTION_CHOICES = (
        ('user_created', 'User Created'),
        ('user_modified', 'User Modified'),
        ('project_created', 'Project Created'),
        ('project_funded', 'Project Funded'),
        ('task_completed', 'Task Completed'),
        ('payment_processed', 'Payment Processed'),
        ('withdrawal_processed', 'Withdrawal Processed'),
        ('kyc_approved', 'KYC Approved'),
        ('kyc_rejected', 'KYC Rejected'),
        ('dispute_resolved', 'Dispute Resolved'),
        ('system_config_changed', 'System Configuration Changed'),
    )
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_actions')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    resource_id = models.CharField(max_length=100, blank=True)  # ID of the affected resource
    resource_type = models.CharField(max_length=50, blank=True)  # Type of resource
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username if self.user else 'System'}: {self.action}"

class DisputeCase(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('under_review', 'Under Review'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated'),
    )
    
    RESOLUTION_CHOICES = (
        ('student_favor', 'In Student Favor'),
        ('enterprise_favor', 'In Enterprise Favor'),
        ('partial_refund', 'Partial Refund'),
        ('full_refund', 'Full Refund'),
        ('task_reattempt', 'Task Reattempt'),
        ('dismissed', 'Dismissed'),
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    resolution = models.CharField(max_length=20, choices=RESOLUTION_CHOICES, blank=True)
    
    # Related entities
    task = models.ForeignKey('tasks.TaskUnit', on_delete=models.CASCADE, related_name='disputes')
    raised_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='disputes_raised')
    assigned_admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_disputes')
    
    # Resolution details
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_disputes')
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Dispute: {self.title} - {self.status}"