from rest_framework import serializers
from .models import WalletTransaction, BankAccount, EscrowLedger, PaymentProviderLog

class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = '__all__'
        read_only_fields = ('user', 'reference', 'payment_provider_ref', 
                           'provider_response', 'completed_at', 'created_at')

class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = '__all__'
        read_only_fields = ('user', 'is_verified', 'created_at')

class EscrowLedgerSerializer(serializers.ModelSerializer):
    project_title = serializers.CharField(source='project.title', read_only=True)
    
    class Meta:
        model = EscrowLedger
        fields = '__all__'

class WithdrawalRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=100)  # Minimum 100 Naira
    bank_account_id = serializers.IntegerField()
    
    def validate(self, attrs):
        user = self.context['request'].user
        amount = attrs['amount']
        
        # Check if user has sufficient balance
        if user.wallet_balance.amount < amount:
            raise serializers.ValidationError("Insufficient balance")
        
        # Check KYC requirements for large withdrawals
        kyc_threshold = 50000  # 50,000 Naira
        if amount > kyc_threshold and not user.kyc_completed:
            raise serializers.ValidationError(
                f"KYC verification required for withdrawals above {kyc_threshold} NGN"
            )
        
        # Check if bank account exists and belongs to user
        try:
            bank_account = BankAccount.objects.get(
                id=attrs['bank_account_id'], 
                user=user
            )
            if not bank_account.is_verified:
                raise serializers.ValidationError("Bank account must be verified before withdrawal")
        except BankAccount.DoesNotExist:
            raise serializers.ValidationError("Bank account not found")
        
        return attrs

class DepositRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1000)  # Minimum 1000 Naira
    project_id = serializers.IntegerField(required=False)

class BankVerificationSerializer(serializers.Serializer):
    account_number = serializers.CharField(max_length=10)
    bank_code = serializers.CharField(max_length=10)