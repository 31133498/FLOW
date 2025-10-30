from rest_framework import serializers
from .models import WalletTransaction, BankAccount, EscrowLedger

class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = '__all__'
        read_only_fields = ('user', 'reference', 'payment_provider_ref', 'completed_at')

class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = '__all__'
        read_only_fields = ('user',)

class WithdrawalRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=100)  # Minimum 100 units
    bank_account_id = serializers.IntegerField()
    
    def validate(self, attrs):
        user = self.context['request'].user
        amount = attrs['amount']
        
        # Check if user has sufficient balance
        if user.wallet_balance.amount < amount:
            raise serializers.ValidationError("Insufficient balance")
        
        # Check KYC requirements for large withdrawals
        if amount > 50000 and not user.kyc_completed:  # 50,000 threshold
            raise serializers.ValidationError("KYC required for withdrawals above 50,000")
        
        return attrs

class DepositRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1000)  # Minimum 1000 units
    project_id = serializers.IntegerField(required=False)