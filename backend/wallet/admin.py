from django.contrib import admin
from .models import WalletTransaction, BankAccount, EscrowLedger, PaymentProviderLog

@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'transaction_type', 'status', 'reference', 'created_at')
    list_filter = ('transaction_type', 'status', 'created_at')
    search_fields = ('user__username', 'reference', 'payment_provider_ref')
    readonly_fields = ('created_at', 'completed_at')
    
    def has_add_permission(self, request):
        return False  # Prevent manual creation of transactions

@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'bank_name', 'account_number', 'account_name', 'is_verified', 'is_primary')
    list_filter = ('bank_name', 'is_verified', 'is_primary')
    search_fields = ('user__username', 'account_number', 'account_name')
    readonly_fields = ('created_at',)

@admin.register(EscrowLedger)
class EscrowLedgerAdmin(admin.ModelAdmin):
    list_display = ('project', 'amount', 'transaction_type', 'reference', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('project__title', 'reference')
    readonly_fields = ('created_at',)

@admin.register(PaymentProviderLog)
class PaymentProviderLogAdmin(admin.ModelAdmin):
    list_display = ('provider', 'action', 'reference', 'status', 'created_at')
    list_filter = ('provider', 'status', 'created_at')
    search_fields = ('reference', 'action')
    readonly_fields = ('created_at',)
    
    def has_add_permission(self, request):
        return False