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
    
    project = models.ForeignKey('projects.EnterpriseProject', on_delete=models.CASCADE, related_name='task_units')
    unit_index = models.IntegerField()
    title = models.CharField(max_length=255)
    description = models.TextField()
    type = models.CharField(max_length=20, choices=TASK_TYPES)
    pay_amount = MoneyField(max_digits=10, decimal_places=2, default_currency='NGN')
    estimated_time_seconds = models.IntegerField()  # Estimated time in seconds
    payload = models.JSONField(default=dict)  # Data the student needs
    verification_strategy = models.JSONField(default=dict)  # How to verify this task
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

class TaskSubmission(models.Model):
    task_unit = models.OneToOneField(TaskUnit, on_delete=models.CASCADE, related_name='submission')
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    submission_data = models.JSONField()  # Main submission content
    photos = models.JSONField(default=list, blank=True)  # List of photo URLs
    gps_location = models.JSONField(null=True, blank=True)  # {lat: x, lng: y}
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