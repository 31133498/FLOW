from django.db import models
from django.contrib.auth import get_user_model
from djmoney.models.fields import MoneyField

User = get_user_model()

class TaskUnit(models.Model):
    TASK_TYPES = (
        ('digital', 'Digital'),
        ('physical', 'Physical'),
        ('hybrid', 'Hybrid'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('submitted', 'Submitted'),
        ('verifying', 'Verifying'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('disputed', 'Disputed'),
    )
    
    VERIFICATION_STRATEGIES = (
        ('ai_only', 'AI Only'),
        ('peer_consensus', 'Peer Consensus'),
        ('supervisor', 'Supervisor'),
        ('hybrid', 'Hybrid'),
    )
    
    project = models.ForeignKey('projects.EnterpriseProject', on_delete=models.CASCADE, related_name='task_units')
    unit_index = models.IntegerField()
    title = models.CharField(max_length=255)
    description = models.TextField()
    type = models.CharField(max_length=20, choices=TASK_TYPES)
    pay_amount = MoneyField(max_digits=10, decimal_places=2, default_currency='NGN')
    estimated_time_seconds = models.IntegerField(default=1800)  # Default 30 minutes
    payload = models.JSONField(default=dict)  # Data the student needs
    verification_strategy = models.CharField(max_length=20, choices=VERIFICATION_STRATEGIES, default='peer_consensus')
    verification_metadata = models.JSONField(default=dict)  # Strategy-specific config
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    assigned_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    submission_data = models.JSONField(null=True, blank=True)  # Student's submission
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['unit_index']
        unique_together = ['project', 'unit_index']
    
    def __str__(self):
        return f"Unit {self.unit_index} - {self.project.title}"
    
    @property
    def requires_physical_verification(self):
        """Check if this task requires physical verification"""
        return self.type in ['physical', 'hybrid']
    
    @property
    def verification_required(self):
        """Check if verification is pending"""
        return self.status in ['submitted', 'verifying']
    
    def can_be_validated_by(self, user):
        """Check if user can validate this task"""
        if user == self.assigned_to:
            return False  # Can't validate own task
        if user.role != 'student':
            return False
        if not user.is_verified:
            return False
        # Check if user is already validating this task
        return not TaskValidation.objects.filter(
            task_unit=self, 
            validator=user
        ).exists()

class TaskSubmission(models.Model):
    task_unit = models.OneToOneField(TaskUnit, on_delete=models.CASCADE, related_name='submission_details')
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    submission_data = models.JSONField()  # Main submission content
    photos = models.JSONField(default=list, blank=True)  # List of photo URLs or metadata
    gps_location = models.JSONField(null=True, blank=True)  # {lat: x, lng: y, accuracy: z}
    supervisor_code = models.CharField(max_length=50, null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Submission for {self.task_unit}"

class PhysicalVerification(models.Model):
    task_unit = models.OneToOneField(TaskUnit, on_delete=models.CASCADE, related_name='physical_verification')
    gps_lat = models.FloatField()
    gps_lng = models.FloatField()
    photos = models.JSONField()  # List of photo metadata
    supervisor_code = models.CharField(max_length=50, null=True, blank=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Physical verification for {self.task_unit}"

class TaskValidation(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    task_unit = models.ForeignKey(TaskUnit, on_delete=models.CASCADE, related_name='validations')
    validator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_validations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    validation_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['task_unit', 'validator']
    
    def __str__(self):
        return f"Validation by {self.validator.username} for {self.task_unit}"
    
    
    @property
    def is_approved(self):
        return self.status == 'approved'
    
    @property
    def is_rejected(self):
        return self.status == 'rejected'
    
    class Meta:
        # ... existing meta ...
        verbose_name = 'Task Validation'
        verbose_name_plural = 'Task Validations'
