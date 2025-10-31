from django.test import TestCase
from django.test.utils import override_settings
from django.contrib.auth import get_user_model
from django.db import transaction
from celery import shared_task
from celery.result import AsyncResult
from unittest.mock import patch, MagicMock
import time

from .models import TaskUnit, TaskValidation
from .tasks import (
    check_validation_consensus,
    atomize_project_tasks,
    process_task_verification,
    select_peer_validators,
    simulate_peer_validation,
    complete_task,
    update_student_reputation,
    simulate_ai_verification
)
from projects.models import EnterpriseProject
from wallet.models import WalletTransaction
from admin_dashboard.models import SystemAlert

User = get_user_model()


class CeleryTaskTestCase(TestCase):
    """Test Celery tasks with Redis broker"""

    def setUp(self):
        """Set up test data"""
        # Create test users
        self.client_user = User.objects.create_user(
            username='test_client',
            email='client@test.com',
            password='testpass123',
            role='client'
        )
        self.student_user = User.objects.create_user(
            username='test_student',
            email='student@test.com',
            password='testpass123',
            role='student',
            reputation_score=4.5,
            is_verified=True
        )

        # Create test project
        self.project = EnterpriseProject.objects.create(
            title='Test Project',
            description='Test project for Celery tasks',
            client=self.client_user,
            total_amount=1000.00,
            task_type='data_entry',
            status='draft'
        )

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_atomize_project_tasks(self):
        """Test project atomization task"""
        # Execute task
        result = atomize_project_tasks.delay(self.project.id)

        # Verify task completed
        self.assertTrue(result.successful())

        # Refresh project from database
        self.project.refresh_from_db()

        # Verify project was atomized
        self.assertEqual(self.project.status, 'active')
        self.assertEqual(self.project.total_units, 10)

        # Verify tasks were created
        tasks = TaskUnit.objects.filter(project=self.project)
        self.assertEqual(tasks.count(), 10)

        # Verify task properties
        first_task = tasks.first()
        self.assertEqual(first_task.title, f"Task 1 - {self.project.title}")
        self.assertEqual(first_task.status, 'available')
        self.assertEqual(first_task.type, self.project.task_type)
        self.assertEqual(first_task.pay_amount, 100.0)  # 1000 / 10

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_complete_task_workflow(self):
        """Test complete task workflow with payment"""
        # Create a task
        task = TaskUnit.objects.create(
            project=self.project,
            unit_index=1,
            title="Test Task",
            description="Test task description",
            type='data_entry',
            pay_amount=50.00,
            estimated_time_seconds=1800,
            verification_strategy="peer_consensus",
            verification_metadata={"peer_count": 2},
            status='assigned',
            assigned_to=self.student_user
        )

        # Execute complete_task
        result = complete_task.delay(task.id)
        self.assertTrue(result.successful())

        # Refresh task and user from database
        task.refresh_from_db()
        self.student_user.refresh_from_db()

        # Verify task completion
        self.assertEqual(task.status, 'completed')
        self.assertIsNotNone(task.completed_at)

        # Verify payment was credited
        self.assertEqual(self.student_user.wallet_balance, 50.00)

        # Verify wallet transaction was created
        transaction = WalletTransaction.objects.filter(
            user=self.student_user,
            transaction_type='task_payment',
            reference=f"TASK_{task.id}"
        ).first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.status, 'completed')

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_peer_validation_workflow(self):
        """Test peer validation workflow"""
        # Create task
        task = TaskUnit.objects.create(
            project=self.project,
            unit_index=1,
            title="Test Task",
            description="Test task description",
            type='data_entry',
            pay_amount=50.00,
            estimated_time_seconds=1800,
            verification_strategy="peer_consensus",
            verification_metadata={"peer_count": 2},
            status='verifying',
            assigned_to=self.student_user
        )

        # Create another student for validation
        validator = User.objects.create_user(
            username='validator',
            email='validator@test.com',
            password='testpass123',
            role='student',
            reputation_score=4.0,
            is_verified=True
        )

        # Execute select_peer_validators
        result = select_peer_validators.delay(task.id)
        self.assertTrue(result.successful())

        # Verify validation records were created
        validations = TaskValidation.objects.filter(task_unit=task)
        self.assertEqual(validations.count(), 1)  # Only one validator available

        # Execute simulate_peer_validation
        result = simulate_peer_validation.delay(task.id)
        self.assertTrue(result.successful())

        # Refresh task
        task.refresh_from_db()

        # Task should be completed (simulated approval)
        self.assertEqual(task.status, 'completed')

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_update_student_reputation(self):
        """Test student reputation update"""
        # Create completed tasks for student
        for i in range(5):
            TaskUnit.objects.create(
                project=self.project,
                unit_index=i+1,
                title=f"Task {i+1}",
                description=f"Test task {i+1}",
                type='data_entry',
                pay_amount=10.00,
                status='completed',
                assigned_to=self.student_user
            )

        # Execute reputation update
        result = update_student_reputation.delay(self.student_user.id)
        self.assertTrue(result.successful())

        # Refresh user
        self.student_user.refresh_from_db()

        # Verify reputation increased
        self.assertGreater(self.student_user.reputation_score, 3.0)
        # Should be 3.0 + min(5 * 0.1, 2.0) = 3.5
        self.assertEqual(self.student_user.reputation_score, 3.5)
        self.assertEqual(self.student_user.tier, 2)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_check_validation_consensus(self):
        """Test validation consensus checking"""
        # Create task
        task = TaskUnit.objects.create(
            project=self.project,
            unit_index=1,
            title="Test Task",
            description="Test task description",
            type='data_entry',
            pay_amount=50.00,
            verification_strategy="peer_consensus",
            verification_metadata={"peer_count": 2, "required_approvals": 1},
            status='verifying',
            assigned_to=self.student_user
        )

        # Create validations
        validator = User.objects.create_user(
            username='validator',
            email='validator@test.com',
            password='testpass123',
            role='student'
        )

        TaskValidation.objects.create(
            task_unit=task,
            validator=validator,
            status='approved'
        )

        # Execute consensus check
        result = check_validation_consensus.delay(task.id)
        self.assertTrue(result.successful())

        # Refresh task
        task.refresh_from_db()

        # Task should be completed due to consensus
        self.assertEqual(task.status, 'completed')

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_simulate_ai_verification(self):
        """Test AI verification simulation"""
        # Create task
        task = TaskUnit.objects.create(
            project=self.project,
            unit_index=1,
            title="Test Task",
            description="Test task description",
            type='data_entry',
            pay_amount=50.00,
            verification_strategy="ai_only",
            status='submitted',
            assigned_to=self.student_user
        )

        # Mock AI verification to return True
        with patch('tasks.tasks.simulate_ai_verification', return_value=True):
            result = process_task_verification.delay(task.id)
            self.assertTrue(result.successful())

            # Refresh task
            task.refresh_from_db()

            # Task should be completed
            self.assertEqual(task.status, 'completed')

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_task_failure_handling(self):
        """Test handling of task failures"""
        # Test with non-existent task ID
        result = complete_task.delay(99999)
        self.assertTrue(result.successful())  # Should not raise exception

        # Test atomize with non-existent project
        result = atomize_project_tasks.delay(99999)
        self.assertTrue(result.successful())  # Should not raise exception


class RedisConnectivityTestCase(TestCase):
    """Test Redis connectivity for Celery"""

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_redis_broker_connection(self):
        """Test that Celery can connect to Redis broker"""
        from django.conf import settings

        # Verify Redis settings
        self.assertEqual(settings.CELERY_BROKER_URL, 'redis://localhost:6379/0')
        self.assertEqual(settings.CELERY_RESULT_BACKEND, 'redis://localhost:6379/0')

        # Test basic task execution
        @shared_task
        def test_task():
            return "Redis connection successful"

        result = test_task.delay()
        self.assertTrue(result.successful())
        self.assertEqual(result.result, "Redis connection successful")

    def test_celery_configuration(self):
        """Test Celery configuration"""
        from backend.celery import app

        # Verify app configuration
        self.assertEqual(app.main, 'backend')
        self.assertIn('redis://localhost:6379/0', str(app.conf.broker_url))
        self.assertIn('redis://localhost:6379/0', str(app.conf.result_backend))
