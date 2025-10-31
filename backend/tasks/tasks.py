from celery import shared_task
from django.db import transaction
from django.utils import timezone
import random
from .models import TaskUnit, TaskValidation
from wallet.models import WalletTransaction
from users.models import User

@shared_task
def check_validation_consensus(task_id):
    """
    Check if we have enough validations to reach consensus
    """
    try:
        task = TaskUnit.objects.get(id=task_id)
        validations = TaskValidation.objects.filter(task_unit=task)
        
        total_validations = validations.count()
        approved_count = validations.filter(status='approved').count()
        rejected_count = validations.filter(status='rejected').count()
        
        # Get required consensus from verification metadata
        required_consensus = task.verification_metadata.get('peer_count', 2)
        required_approvals = task.verification_metadata.get('required_approvals', 1)
        
        if total_validations >= required_consensus:
            if approved_count >= required_approvals:
                # Consensus reached - approve task
                complete_task(task.id)
            else:
                # Consensus failed - mark as disputed
                task.status = 'disputed'
                task.save()
                
                # Create system alert for admin
                from admin_dashboard.models import SystemAlert
                SystemAlert.objects.create(
                    title=f'Task Disputed - #{task.id}',
                    description=f'Task {task.title} failed peer consensus validation',
                    alert_type='verification_failure',
                    severity='medium'
                )
                
    except TaskUnit.DoesNotExist:
        pass

@shared_task
def atomize_project_tasks(project_id):
    """
    Atomize a project into individual task units
    This is a simplified version - in production, this would use ML/models
    """
    from projects.models import EnterpriseProject
    
    try:
        project = EnterpriseProject.objects.get(id=project_id)
    except EnterpriseProject.DoesNotExist:
        return
    
    # Simple atomization logic - create 10 sample tasks
    task_count = 10
    base_pay = project.total_amount.amount / task_count
    
    for i in range(task_count):
        task_type = project.task_type
        
        # Create task unit
        TaskUnit.objects.create(
            project=project,
            unit_index=i + 1,
            title=f"Task {i + 1} - {project.title}",
            description=f"Complete this task for project: {project.title}",
            type=task_type,
            pay_amount=base_pay,
            estimated_time_seconds=1800,  # 30 minutes
            payload={
                "instructions": f"Complete task {i + 1} for {project.title}",
                "requirements": ["Quality work", "On time submission"]
            },
            verification_strategy="peer_consensus",
            verification_metadata={"peer_count": 2},
            status='available'
        )
    
    # Update project with total units
    project.total_units = task_count
    project.status = 'active'
    project.save()

@shared_task
def process_task_verification(task_id):
    """
    Process task verification using AI + peer consensus
    Simplified version for MVP
    """
    try:
        task = TaskUnit.objects.get(id=task_id)
        
        # Step 1: Simple AI verification simulation
        ai_verified = simulate_ai_verification(task)
        
        if ai_verified:
            if task.verification_strategy == 'ai_only':
                # If AI-only verification, complete task immediately
                complete_task(task.id)
            else:
                # For peer consensus, select validators
                task.status = 'verifying'
                task.save()
                select_peer_validators.delay(task.id)
        else:
            # If AI verification fails, mark for admin review
            task.status = 'disputed'
            task.save()
            
    except TaskUnit.DoesNotExist:
        pass

@shared_task
def select_peer_validators(task_id):
    """
    Select peer validators for consensus verification
    """
    try:
        task = TaskUnit.objects.get(id=task_id)
        
        # Find available validators (students with good reputation, not the task owner)
        validators = User.objects.filter(
            role='student',
            reputation_score__gte=4.0,
            is_verified=True
        ).exclude(id=task.assigned_to.id)[:2]  # Get 2 validators
        
        # Create validation records
        for validator in validators:
            TaskValidation.objects.create(
                task_unit=task,
                validator=validator,
                status='pending'
            )
        
        # For demo, simulate quick validation
        simulate_peer_validation.delay(task.id)
        
    except TaskUnit.DoesNotExist:
        pass

@shared_task
def simulate_peer_validation(task_id):
    """
    Simulate peer validation (in production, validators would actually validate)
    """
    try:
        task = TaskUnit.objects.get(id=task_id)
        validations = TaskValidation.objects.filter(task_unit=task)
        
        # Simulate validation results (80% pass rate for demo)
        approved_count = 0
        for validation in validations:
            if random.random() < 0.8:  # 80% chance of approval
                validation.status = 'approved'
                approved_count += 1
            else:
                validation.status = 'rejected'
            validation.save()
        
        # Check consensus (simple majority)
        if approved_count >= 1:  # At least 1 approval for 2 validators
            complete_task(task.id)
        else:
            task.status = 'disputed'
            task.save()
            
    except TaskUnit.DoesNotExist:
        pass

@shared_task
def complete_task(task_id):
    """
    Mark task as completed and release payment
    """
    with transaction.atomic():
        try:
            task = TaskUnit.objects.select_for_update().get(id=task_id)
            task.status = 'completed'
            task.completed_at = timezone.now()
            task.save()
            
            # Credit student's wallet
            student = task.assigned_to
            student.wallet_balance += task.pay_amount
            student.save()
            
            # Create wallet transaction
            from wallet.models import WalletTransaction
            WalletTransaction.objects.create(
                user=student,
                amount=task.pay_amount,
                transaction_type='task_payment',
                status='completed',
                reference=f"TASK_{task.id}",
                metadata={'task_id': task.id, 'project_id': task.project.id}
            )
            
            # Release escrow funds
            from wallet.tasks import release_escrow_funds
            release_escrow_funds.delay(task.id)
            
            # Update project progress
            project = task.project
            project.completed_units += 1
            project.save()
            
            # Update student reputation
            update_student_reputation.delay(student.id)
            
        except TaskUnit.DoesNotExist:
            pass

@shared_task
def update_student_reputation(student_id):
    """
    Update student reputation based on completed tasks
    """
    from users.models import User
    try:
        student = User.objects.get(id=student_id)
        completed_tasks = TaskUnit.objects.filter(
            assigned_to=student,
            status='completed'
        ).count()
        
        # Simple reputation calculation
        base_reputation = 3.0  # Starting point
        task_bonus = min(completed_tasks * 0.1, 2.0)  # Max 2.0 bonus
        student.reputation_score = base_reputation + task_bonus
        
        # Update tier based on reputation
        if student.reputation_score >= 4.5:
            student.tier = 3
        elif student.reputation_score >= 3.5:
            student.tier = 2
        else:
            student.tier = 1
            
        student.save()
        
    except User.DoesNotExist:
        pass

def simulate_ai_verification(task):
    """
    Simulate AI verification - in production, this would use actual ML models
    """
    # Simple simulation - 90% pass rate
    return random.random() < 0.9