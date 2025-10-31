from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
import uuid
from .models import WalletTransaction, BankAccount, EscrowLedger
from .serializers import (
    WalletTransactionSerializer, BankAccountSerializer, 
    WithdrawalRequestSerializer, DepositRequestSerializer
)
from projects.models import EnterpriseProject

class WalletTransactionListView(generics.ListAPIView):
    serializer_class = WalletTransactionSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        return WalletTransaction.objects.filter(user=self.request.user)

class BankAccountListView(generics.ListCreateAPIView):
    serializer_class = BankAccountSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        return BankAccount.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def request_withdrawal(request):
    serializer = WithdrawalRequestSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    
    data = serializer.validated_data
    user = request.user
    
    try:
        bank_account = BankAccount.objects.get(id=data['bank_account_id'], user=user)
    except BankAccount.DoesNotExist:
        return Response(
            {"error": "Bank account not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    with transaction.atomic():
        # Create withdrawal transaction
        transaction_ref = f"WDR{uuid.uuid4().hex[:12].upper()}"
        
        withdrawal = WalletTransaction.objects.create(
            user=user,
            amount=data['amount'],
            transaction_type='withdrawal',
            status='pending',
            reference=transaction_ref,
            metadata={
                'bank_account_id': bank_account.id,
                'bank_name': bank_account.bank_name,
                'account_number': bank_account.account_number
            }
        )
        
        # Deduct from user's wallet
        user.wallet_balance -= data['amount']
        user.save()
        
        # Process withdrawal via payment provider (async)
        from .tasks import process_withdrawal
        process_withdrawal.delay(withdrawal.id)
    
    return Response({
        "message": "Withdrawal request submitted",
        "transaction_reference": transaction_ref
    })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def fund_escrow(request):
    serializer = DepositRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    data = serializer.validated_data
    user = request.user
    
    if not user.role == 'enterprise':
        return Response(
            {"error": "Only enterprise users can fund escrow"}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    project_id = data.get('project_id')
    if project_id:
        try:
            project = EnterpriseProject.objects.get(id=project_id, client=user)
        except EnterpriseProject.DoesNotExist:
            return Response(
                {"error": "Project not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    else:
        # General escrow funding
        project = None
    
    # In a real implementation, this would initiate a payment with Paystack/Monnify
    # For MVP, we'll simulate successful payment
    
    transaction_ref = f"ESC{uuid.uuid4().hex[:12].upper()}"
    
    # Create escrow ledger entry
    escrow_entry = EscrowLedger.objects.create(
        project=project,
        amount=data['amount'],
        transaction_type='funding',
        reference=transaction_ref,
        metadata={'user_id': user.id}
    )
    
    if project:
        project.escrow_locked = True
        project.status = 'active'
        project.save()
    
    return Response({
        "message": "Escrow funded successfully",
        "reference": transaction_ref,
        "escrow_entry_id": escrow_entry.id
    })