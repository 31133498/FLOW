from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from .models import WalletTransaction, BankAccount, EscrowLedger
from .paystack_client import paystack_client
import time

@shared_task
def process_withdrawal(transaction_id):
    """
    Process withdrawal request using Paystack
    """
    try:
        with transaction.atomic():
            withdrawal = WalletTransaction.objects.select_for_update().get(
                id=transaction_id, 
                transaction_type='withdrawal',
                status='pending'
            )
            
            # Get bank account details
            bank_account_id = withdrawal.metadata.get('bank_account_id')
            try:
                bank_account = BankAccount.objects.get(id=bank_account_id, user=withdrawal.user)
            except BankAccount.DoesNotExist:
                withdrawal.status = 'failed'
                withdrawal.metadata['error'] = 'Bank account not found'
                withdrawal.save()
                return
            
            # Update status to processing
            withdrawal.status = 'processing'
            withdrawal.save()
            
            # Create transfer recipient if not exists
            if not bank_account.metadata.get('recipient_code'):
                recipient_response = paystack_client.create_transfer_recipient(
                    name=bank_account.account_name,
                    account_number=bank_account.account_number,
                    bank_code=bank_account.bank_code
                )
                
                if recipient_response.get('status'):
                    recipient_code = recipient_response['data']['recipient_code']
                    bank_account.metadata['recipient_code'] = recipient_code
                    bank_account.save()
                else:
                    withdrawal.status = 'failed'
                    withdrawal.metadata['error'] = recipient_response.get('message', 'Failed to create recipient')
                    withdrawal.save()
                    return
            
            # Initiate transfer
            transfer_response = paystack_client.initiate_transfer(
                amount=withdrawal.amount.amount,
                recipient_code=bank_account.metadata['recipient_code'],
                reference=withdrawal.reference
            )
            
            if transfer_response.get('status'):
                withdrawal.status = 'completed'
                withdrawal.payment_provider_ref = transfer_response['data']['reference']
                withdrawal.completed_at = timezone.now()
                withdrawal.provider_response = transfer_response
            else:
                withdrawal.status = 'failed'
                withdrawal.metadata['error'] = transfer_response.get('message', 'Transfer failed')
                withdrawal.provider_response = transfer_response
            
            withdrawal.save()
            
    except WalletTransaction.DoesNotExist:
        pass
    except Exception as e:
        # Mark as failed in case of unexpected errors
        try:
            withdrawal = WalletTransaction.objects.get(id=transaction_id)
            withdrawal.status = 'failed'
            withdrawal.metadata['error'] = str(e)
            withdrawal.save()
        except WalletTransaction.DoesNotExist:
            pass

@shared_task
def process_escrow_funding(project_id, amount, reference):
    """
    Process escrow funding for a project
    In production, this would handle actual payment processing
    For MVP, we simulate successful payment
    """
    from projects.models import EnterpriseProject
    
    try:
        with transaction.atomic():
            project = EnterpriseProject.objects.select_for_update().get(id=project_id)
            
            # Simulate payment processing delay
            time.sleep(2)
            
            # Create escrow ledger entry
            EscrowLedger.objects.create(
                project=project,
                amount=amount,
                transaction_type='funding',
                reference=reference,
                metadata={'status': 'completed', 'provider': 'paystack_simulated'}
            )
            
            # Update project status
            project.escrow_locked = True
            project.status = 'funded'
            project.save()
            
            # Create audit log
            from projects.models import ProjectAudit
            ProjectAudit.objects.create(
                project=project,
                action='ESCROW_FUNDED',
                description=f'Escrow funded with {amount} via Paystack',
                performed_by=project.client
            )
            
    except EnterpriseProject.DoesNotExist:
        pass

@shared_task
def release_escrow_funds(task_id):
    """
    Release escrow funds when a task is completed
    This is called from the tasks app when a task is verified
    """
    from tasks.models import TaskUnit
    
    try:
        task = TaskUnit.objects.get(id=task_id)
        project = task.project
        
        with transaction.atomic():
            # Create escrow release entry
            EscrowLedger.objects.create(
                project=project,
                amount=task.pay_amount,
                transaction_type='payout',
                reference=f"PAYOUT_{task.id}",
                metadata={'task_id': task.id, 'student_id': task.assigned_to.id}
            )
            
            # Create audit log
            from projects.models import ProjectAudit
            ProjectAudit.objects.create(
                project=project,
                action='ESCROW_RELEASED',
                description=f'Escrow released {task.pay_amount} for task {task.id}',
                performed_by=project.client
            )
            
    except TaskUnit.DoesNotExist:
        pass

@shared_task
def verify_bank_account(bank_account_id):
    """
    Verify bank account using Paystack
    """
    try:
        bank_account = BankAccount.objects.get(id=bank_account_id)
        
        # Verify account with Paystack
        verification_response = paystack_client.verify_account_number(
            account_number=bank_account.account_number,
            bank_code=bank_account.bank_code
        )
        
        if verification_response.get('status'):
            bank_account.is_verified = True
            bank_account.account_name = verification_response['data']['account_name']
            bank_account.metadata['verification_response'] = verification_response
            bank_account.save()
        else:
            bank_account.metadata['verification_error'] = verification_response.get('message', 'Verification failed')
            bank_account.save()
            
    except BankAccount.DoesNotExist:
        pass

@shared_task
def process_deposit(transaction_id):
    """
    Process deposit transaction (for enterprise funding)
    """
    try:
        deposit = WalletTransaction.objects.get(
            id=transaction_id, 
            transaction_type='deposit',
            status='pending'
        )
        
        # Simulate Paystack payment initialization
        # In production, this would create an actual payment link
        payment_response = paystack_client.initialize_transaction(
            email=deposit.user.email,
            amount=deposit.amount.amount,
            reference=deposit.reference,
            metadata={'user_id': deposit.user.id, 'purpose': 'wallet_funding'}
        )
        
        if payment_response.get('status'):
            deposit.status = 'processing'
            deposit.payment_provider_ref = payment_response['data']['reference']
            deposit.metadata['authorization_url'] = payment_response['data']['authorization_url']
        else:
            deposit.status = 'failed'
            deposit.metadata['error'] = payment_response.get('message', 'Payment initialization failed')
        
        deposit.provider_response = payment_response
        deposit.save()
        
    except WalletTransaction.DoesNotExist:
        pass

@shared_task
def check_pending_transactions():
    """
    Periodic task to check status of pending transactions
    """
    pending_withdrawals = WalletTransaction.objects.filter(
        status='processing',
        transaction_type='withdrawal'
    )
    
    for withdrawal in pending_withdrawals:
        if withdrawal.payment_provider_ref:
            # Verify transaction status with Paystack
            verification_response = paystack_client.verify_transaction(
                withdrawal.payment_provider_ref
            )
            
            if verification_response.get('status'):
                if verification_response['data']['status'] == 'success':
                    withdrawal.status = 'completed'
                    withdrawal.completed_at = timezone.now()
                elif verification_response['data']['status'] == 'failed':
                    withdrawal.status = 'failed'
                    withdrawal.metadata['error'] = 'Transaction failed at provider'
                
                withdrawal.provider_response = verification_response
                withdrawal.save()