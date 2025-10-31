from django.db import models
from django.contrib.auth import get_user_model
from djmoney.models.fields import MoneyField

User = get_user_model()

class EnterpriseProject(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('funded', 'Funded'),
        ('processing', 'Processing'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    TASK_TYPE_CHOICES = (
        ('digital', 'Digital'),
        ('physical', 'Physical'),
        ('hybrid', 'Hybrid'),
    )
    
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    title = models.CharField(max_length=255)
    description = models.TextField()
    task_type = models.CharField(max_length=20, choices=TASK_TYPE_CHOICES, default='digital')
    total_amount = MoneyField(max_digits=14, decimal_places=2, default_currency='NGN')
    escrow_locked = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_units = models.IntegerField(default=0)
    completed_units = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.client.username}"
    
    def progress_percentage(self):
        if self.total_units == 0:
            return 0
        return (self.completed_units / self.total_units) * 100

class ProjectFile(models.Model):
    project = models.ForeignKey(EnterpriseProject, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='project_files/')
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.file_name

class ProjectAudit(models.Model):
    project = models.ForeignKey(EnterpriseProject, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=100)
    description = models.TextField()
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Audit: {self.action} - {self.project.title}"