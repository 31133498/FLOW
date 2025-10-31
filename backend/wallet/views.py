from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
import uuid
from .models import WalletTransaction, BankAccount, EscrowLedger
from .serializers import (
    WalletTransactionSerializer, BankAccountSerializer, 
    WithdrawalRequestSerializer, DepositRequestSerializer, BankVerificationSerializer
)
from .tasks import process_withdrawal, process_escrow_funding, verify_bank_account
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
        bank_account = serializer.save(user=self.request.user)
        
        # Trigger bank account verification
        verify_bank_account.delay(bank_account.id)

class BankAccountDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BankAccountSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        return BankAccount.objects.filter(user=self.request.user)

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
                'account_number': bank_account.account_number,
                'account_name': bank_account.account_name
            }
        )
        
        # Process withdrawal via Celery task
        process_withdrawal.delay(withdrawal.id)
    
    return Response({
        "message": "Withdrawal request submitted",
        "transaction_reference": transaction_ref,
        "transaction_id": withdrawal.id
    })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def fund_escrow(request):
    """
    Fund project escrow using Paystack
    """
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
        return Response(
            {"error": "Project ID is required for escrow funding"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if project.escrow_locked:
        return Response(
            {"error": "Project already funded"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Create transaction reference
    transaction_ref = f"ESC{uuid.uuid4().hex[:12].upper()}"
    
    # Create wallet transaction for tracking
    wallet_transaction = WalletTransaction.objects.create(
        user=user,
        amount=data['amount'],
        transaction_type='escrow_funding',
        status='processing',
        reference=transaction_ref,
        metadata={'project_id': project.id}
    )
    
    # Process escrow funding via Celery task
    process_escrow_funding.delay(project.id, data['amount'], transaction_ref)
    
    return Response({
        "message": "Escrow funding initiated",
        "reference": transaction_ref,
        "project_id": project.id
    })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def verify_bank_account_view(request):
    """
    Manually trigger bank account verification
    """
    serializer = BankVerificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    data = serializer.validated_data
    
    try:
        bank_account = BankAccount.objects.get(
            account_number=data['account_number'],
            bank_code=data['bank_code'],
            user=request.user
        )
        
        # Trigger verification
        verify_bank_account.delay(bank_account.id)
        
        return Response({
            "message": "Bank account verification initiated",
            "bank_account_id": bank_account.id
        })
        
    except BankAccount.DoesNotExist:
        return Response(
            {"error": "Bank account not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def wallet_summary(request):
    """
    Get wallet summary including balance and recent transactions
    """
    user = request.user
    
    summary = {
        'balance': user.wallet_balance,
        'total_earned': WalletTransaction.objects.filter(
            user=user,
            transaction_type='task_payment',
            status='completed'
        ).aggregate(total=models.Sum('amount'))['total'] or 0,
        'total_withdrawn': WalletTransaction.objects.filter(
            user=user,
            transaction_type='withdrawal',
            status='completed'
        ).aggregate(total=models.Sum('amount'))['total'] or 0,
        'pending_withdrawals': WalletTransaction.objects.filter(
            user=user,
            transaction_type='withdrawal',
            status__in=['pending', 'processing']
        ).aggregate(total=models.Sum('amount'))['total'] or 0,
        'recent_transactions': WalletTransactionSerializer(
            WalletTransaction.objects.filter(user=user)[:5],
            many=True
        ).data
    }
    
    return Response(summary)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_supported_banks(request):
    """
    Get list of supported banks from Paystack
    """
    from .paystack_client import paystack_client
    
    banks_response = paystack_client.list_banks()
    
    if banks_response.get('status'):
        banks = [
            {
                'name': bank['name'],
                'code': bank['code'],
                'id': bank['id']
            }
            for bank in banks_response['data']
        ]
        return Response(banks)
    else:
        return Response(
            {"error": "Failed to fetch banks list"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# Add the missing import for models
from django.db import models