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
    
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    title = models.CharField(max_length=255)
    description = models.TextField()
    total_amount = MoneyField(max_digits=14, decimal_places=2, default_currency='NGN')
    escrow_locked = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    metadata = models.JSONField(default=dict, blank=True)  # Additional project-specific data
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.client.username}"

class ProjectFile(models.Model):
    project = models.ForeignKey(EnterpriseProject, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='project_files/')
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.file_name