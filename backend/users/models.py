from django.contrib.auth.models import AbstractUser
from django.db import models
from djmoney.models.fields import MoneyField

class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('enterprise', 'Enterprise'),
        ('admin', 'Admin'),
    )
    
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    kyc_completed = models.BooleanField(default=False)
    wallet_balance = MoneyField(
        max_digits=14, 
        decimal_places=2, 
        default_currency='NGN',
        default=0
    )
    reputation_score = models.FloatField(default=0.0)
    tier = models.IntegerField(default=1)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.username} ({self.role})"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    student_id = models.CharField(max_length=50, null=True, blank=True)
    bank_account_number = models.CharField(max_length=20, null=True, blank=True)
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    bank_code = models.CharField(max_length=10, null=True, blank=True)
    mobile_money_number = models.CharField(max_length=20, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"Profile for {self.user.username}"

class KYCRecord(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kyc_records')
    document_type = models.CharField(max_length=50)
    document_number = models.CharField(max_length=100)
    document_front = models.ImageField(upload_to='kyc_documents/')
    document_back = models.ImageField(upload_to='kyc_documents/', null=True, blank=True)
    selfie_photo = models.ImageField(upload_to='kyc_selfies/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_kyc')
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"KYC for {self.user.username}"