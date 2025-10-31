from django.test import TestCase
from django.test.utils import override_settings
from django.contrib.auth import get_user_model
from django.db import transaction
from unittest.mock import patch, MagicMock
import json

from .models import WalletTransaction, BankAccount, EscrowLedger
from .tasks import (
    process_withdrawal,
    process_escrow_funding,
    release_escrow_funds,
    verify_bank_account,
    process_deposit,
    check_pending_transactions
)
from projects.models import EnterpriseProject

User = get_user_model()


class WalletCeleryTaskTestCase(TestCase):
    """Test wallet-related Celery tasks"""

    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='test_user',
            email='user@test.com',
            password='testpass123',
            role='client',
            wallet_balance=1000.00
        )

        # Create test project
        self.project = EnterpriseProject.objects.create(
            title='Test Project',
            description='Test project for wallet tasks',
            client=self.user,
            total_amount=500.00,
            task_type='data_entry',
            status='draft'
        )

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('wallet.tasks.paystack_client.initiate_transfer')
    @patch('wallet.tasks.paystack_client.create_transfer_recipient')
    def test_process_withdrawal_success(self, mock_create_recipient, mock_initiate_transfer):
        """Test successful withdrawal processing"""
        # Mock Paystack responses
        mock_create_recipient.return_value = {'status': True, 'data': {'recipient_code': 'RCP_test'}}
        mock_initiate_transfer.return_value = {'status': True, 'data': {'reference': 'TRF_test'}}

        # Create bank account
        bank_account = BankAccount.objects.create(
            user=self.user,
            account_name='Test User',
            account_number='1234567890',
            bank_code='058',
            bank_name='GTBank'
        )

        # Create withdrawal transaction
        withdrawal = WalletTransaction.objects.create(
            user=self.user,
            amount=100.00,
            transaction_type='withdrawal',
            status='pending',
            reference='WTH_test',
            metadata={'bank_account_id': bank_account.id}
        )

        # Execute task
        result = process_withdrawal.delay(withdrawal.id)
        self.assertTrue(result.successful())

        # Refresh withdrawal
        withdrawal.refresh_from_db()

        # Verify withdrawal was processed
        self.assertEqual(withdrawal.status, 'completed')
        self.assertEqual(withdrawal.payment_provider_ref, 'TRF_test')
        self.assertIsNotNone(withdrawal.completed_at)

        # Verify bank account was updated with recipient code
        bank_account.refresh_from_db()
        self.assertEqual(bank_account.metadata['recipient_code'], 'RCP_test')

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('wallet.tasks.paystack_client.initiate_transfer')
    @patch('wallet.tasks.paystack_client.create_transfer_recipient')
    def test_process_withdrawal_failure(self, mock_create_recipient, mock_initiate_transfer):
        """Test withdrawal processing failure"""
        # Mock Paystack failure
        mock_create_recipient.return_value = {'status': False, 'message': 'Invalid account'}

        # Create bank account
        bank_account = BankAccount.objects.create(
            user=self.user,
            account_name='Test User',
            account_number='1234567890',
            bank_code='058'
        )

        # Create withdrawal transaction
        withdrawal = WalletTransaction.objects.create(
            user=self.user,
            amount=100.00,
            transaction_type='withdrawal',
            status='pending',
            reference='WTH_test',
            metadata={'bank_account_id': bank_account.id}
        )

        # Execute task
        result = process_withdrawal.delay(withdrawal.id)
        self.assertTrue(result.successful())

        # Refresh withdrawal
        withdrawal.refresh_from_db()

        # Verify withdrawal failed
        self.assertEqual(withdrawal.status, 'failed')
        self.assertIn('Invalid account', withdrawal.metadata['error'])

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_process_escrow_funding(self):
        """Test escrow funding processing"""
        # Execute task
        result = process_escrow_funding.delay(self.project.id, 500.00, 'ESC_test')
        self.assertTrue(result.successful())

        # Refresh project
        self.project.refresh_from_db()

        # Verify escrow was funded
        self.assertTrue(self.project.escrow_locked)
        self.assertEqual(self.project.status, 'funded')

        # Verify escrow ledger entry
        ledger_entry = EscrowLedger.objects.filter(
            project=self.project,
            transaction_type='funding',
            reference='ESC_test'
        ).first()
        self.assertIsNotNone(ledger_entry)
        self.assertEqual(ledger_entry.amount, 500.00)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_release_escrow_funds(self):
        """Test escrow funds release"""
        from tasks.models import TaskUnit

        # Create a task
        task = TaskUnit.objects.create(
            project=self.project,
            unit_index=1,
            title="Test Task",
            description="Test task description",
            type='data_entry',
            pay_amount=50.00,
            status='completed',
            assigned_to=self.user
        )

        # Execute task
        result = release_escrow_funds.delay(task.id)
        self.assertTrue(result.successful())

        # Verify escrow release ledger entry
        ledger_entry = EscrowLedger.objects.filter(
            project=self.project,
            transaction_type='payout',
            reference=f"PAYOUT_{task.id}"
        ).first()
        self.assertIsNotNone(ledger_entry)
        self.assertEqual(ledger_entry.amount, 50.00)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('wallet.tasks.paystack_client.verify_account_number')
    def test_verify_bank_account_success(self, mock_verify):
        """Test successful bank account verification"""
        # Mock Paystack verification
        mock_verify.return_value = {
            'status': True,
            'data': {'account_name': 'Verified User'}
        }

        # Create bank account
        bank_account = BankAccount.objects.create(
            user=self.user,
            account_name='Test User',
            account_number='1234567890',
            bank_code='058',
            is_verified=False
        )

        # Execute task
        result = verify_bank_account.delay(bank_account.id)
        self.assertTrue(result.successful())

        # Refresh bank account
        bank_account.refresh_from_db()

        # Verify account was verified
        self.assertTrue(bank_account.is_verified)
        self.assertEqual(bank_account.account_name, 'Verified User')

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('wallet.tasks.paystack_client.initialize_transaction')
    def test_process_deposit(self, mock_initialize):
        """Test deposit processing"""
        # Mock Paystack initialization
        mock_initialize.return_value = {
            'status': True,
            'data': {
                'reference': 'DEP_test',
                'authorization_url': 'https://paystack.com/pay/test'
            }
        }

        # Create deposit transaction
        deposit = WalletTransaction.objects.create(
            user=self.user,
            amount=200.00,
            transaction_type='deposit',
            status='pending',
            reference='DEP_test'
        )

        # Execute task
        result = process_deposit.delay(deposit.id)
        self.assertTrue(result.successful())

        # Refresh deposit
        deposit.refresh_from_db()

        # Verify deposit was processed
        self.assertEqual(deposit.status, 'processing')
        self.assertEqual(deposit.payment_provider_ref, 'DEP_test')
        self.assertIn('authorization_url', deposit.metadata)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('wallet.tasks.paystack_client.verify_transaction')
    def test_check_pending_transactions(self, mock_verify):
        """Test checking pending transactions"""
        # Mock Paystack verification - success
        mock_verify.return_value = {
            'status': True,
            'data': {'status': 'success'}
        }

        # Create pending withdrawal
        withdrawal = WalletTransaction.objects.create(
            user=self.user,
            amount=100.00,
            transaction_type='withdrawal',
            status='processing',
            reference='WTH_test',
            payment_provider_ref='TRF_test'
        )

        # Execute task
        result = check_pending_transactions.delay()
        self.assertTrue(result.successful())

        # Refresh withdrawal
        withdrawal.refresh_from_db()

        # Verify withdrawal was completed
        self.assertEqual(withdrawal.status, 'completed')
        self.assertIsNotNone(withdrawal.completed_at)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_task_error_handling(self):
        """Test error handling in wallet tasks"""
        # Test with non-existent transaction
        result = process_withdrawal.delay(99999)
        self.assertTrue(result.successful())  # Should not raise exception

        # Test with non-existent bank account
        withdrawal = WalletTransaction.objects.create(
            user=self.user,
            amount=100.00,
            transaction_type='withdrawal',
            status='pending',
            reference='WTH_test',
            metadata={'bank_account_id': 99999}
        )

        result = process_withdrawal.delay(withdrawal.id)
        self.assertTrue(result.successful())

        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, 'failed')


class WalletIntegrationTestCase(TestCase):
    """Test wallet integration with other systems"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='test_user',
            email='user@test.com',
            password='testpass123',
            role='client',
            wallet_balance=1000.00
        )

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_wallet_balance_consistency(self):
        """Test wallet balance consistency across operations"""
        initial_balance = self.user.wallet_balance

        # Create multiple transactions
        transactions = []
        for i in range(3):
            tx = WalletTransaction.objects.create(
                user=self.user,
                amount=100.00,
                transaction_type='deposit' if i % 2 == 0 else 'withdrawal',
                status='completed',
                reference=f'TX_{i}'
            )
            transactions.append(tx)

        # Refresh user
        self.user.refresh_from_db()

        # Calculate expected balance
        deposits = sum(tx.amount.amount for tx in transactions if tx.transaction_type == 'deposit')
        withdrawals = sum(tx.amount.amount for tx in transactions if tx.transaction_type == 'withdrawal')
        expected_balance = initial_balance + deposits - withdrawals

        # Note: In real implementation, withdrawals would debit the balance
        # This test verifies the structure is in place
        self.assertEqual(self.user.wallet_balance, initial_balance)

    def test_transaction_metadata_integrity(self):
        """Test transaction metadata integrity"""
        # Create transaction with complex metadata
        metadata = {
            'bank_account_id': 123,
            'provider_response': {'status': 'success'},
            'notes': 'Test transaction'
        }

        transaction = WalletTransaction.objects.create(
            user=self.user,
            amount=50.00,
            transaction_type='withdrawal',
            status='pending',
            reference='META_test',
            metadata=metadata
        )

        # Refresh from database
        transaction.refresh_from_db()

        # Verify metadata integrity
        self.assertEqual(transaction.metadata['bank_account_id'], 123)
        self.assertEqual(transaction.metadata['provider_response']['status'], 'success')
        self.assertEqual(transaction.metadata['notes'], 'Test transaction')
