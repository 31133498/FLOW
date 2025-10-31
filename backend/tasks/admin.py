from django.contrib import admin
from .models import TaskUnit, TaskSubmission, PhysicalVerification, TaskValidation

@admin.register(TaskUnit)
class TaskUnitAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'type', 'status', 'assigned_to', 'pay_amount', 'created_at')
    list_filter = ('status', 'type', 'verification_strategy', 'created_at')
    search_fields = ('title', 'project__title', 'assigned_to__username')
    readonly_fields = ('created_at', 'assigned_at', 'submitted_at', 'completed_at')

@admin.register(TaskSubmission)
class TaskSubmissionAdmin(admin.ModelAdmin):
    list_display = ('task_unit', 'submitted_by', 'submitted_at')
    list_filter = ('submitted_at',)
    search_fields = ('task_unit__title', 'submitted_by__username')

@admin.register(PhysicalVerification)
class PhysicalVerificationAdmin(admin.ModelAdmin):
    list_display = ('task_unit', 'verified_by', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('task_unit__title', 'verified_by__username')

@admin.register(TaskValidation)
class TaskValidationAdmin(admin.ModelAdmin):
    list_display = ('task_unit', 'validator', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('task_unit__title', 'validator__username')