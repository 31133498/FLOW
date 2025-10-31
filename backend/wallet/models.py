from django.db import models
from django.contrib.auth import get_user_model
from djmoney.models.fields import MoneyField

User = get_user_model()

class WalletTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('task_payment', 'Task Payment'),
        ('refund', 'Refund'),
        ('advance', 'Advance'),
        ('escrow_funding', 'Escrow Funding'),
        ('escrow_release', 'Escrow Release'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    amount = MoneyField(max_digits=14, decimal_places=2, default_currency='NGN')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    metadata = models.JSONField(default=dict, blank=True)
    reference = models.CharField(max_length=100, unique=True)
    payment_provider_ref = models.CharField(max_length=200, null=True, blank=True)
    provider_response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.user.username}"

class EscrowLedger(models.Model):
    project = models.ForeignKey('projects.EnterpriseProject', on_delete=models.CASCADE, related_name='escrow_entries')
    amount = MoneyField(max_digits=14, decimal_places=2, default_currency='NGN')
    transaction_type = models.CharField(max_length=50)  # 'funding', 'payout', 'refund'
    reference = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Escrow {self.transaction_type} - {self.amount} - {self.project.title}"

class BankAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bank_accounts')
    bank_name = models.CharField(max_length=100)
    bank_code = models.CharField(max_length=10)
    account_number = models.CharField(max_length=20)
    account_name = models.CharField(max_length=100)
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'account_number']
    
    def __str__(self):
        return f"{self.account_name} - {self.bank_name}"

class PaymentProviderLog(models.Model):
    provider = models.CharField(max_length=50)  # paystack, monnify, etc.
    action = models.CharField(max_length=100)
    reference = models.CharField(max_length=100)
    request_data = models.JSONField(default=dict)
    response_data = models.JSONField(default=dict)
    status = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.provider} - {self.action} - {self.reference}"