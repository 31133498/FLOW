from django.contrib import admin
from .models import EnterpriseProject, ProjectFile, ProjectAudit

@admin.register(EnterpriseProject)
class EnterpriseProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'client', 'task_type', 'total_amount', 'status', 'progress_percentage', 'created_at')
    list_filter = ('status', 'task_type', 'created_at')
    search_fields = ('title', 'client__username', 'description')
    readonly_fields = ('total_units', 'completed_units', 'created_at', 'updated_at')

@admin.register(ProjectFile)
class ProjectFileAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'project', 'file_size', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('file_name', 'project__title')

@admin.register(ProjectAudit)
class ProjectAuditAdmin(admin.ModelAdmin):
    list_display = ('project', 'action', 'performed_by', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('project__title', 'action', 'description')
    readonly_fields = ('created_at',)