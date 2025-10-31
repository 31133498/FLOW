from django.contrib import admin
from .models import AdminDashboard, SystemAlert, AuditLog, DisputeCase

@admin.register(AdminDashboard)
class AdminDashboardAdmin(admin.ModelAdmin):
    list_display = ('date_recorded', 'total_students', 'total_enterprises', 'total_projects', 'total_tasks_completed')
    readonly_fields = ('date_recorded',)
    
    def has_add_permission(self, request):
        return False

@admin.register(SystemAlert)
class SystemAlertAdmin(admin.ModelAdmin):
    list_display = ('title', 'alert_type', 'severity', 'is_resolved', 'created_at')
    list_filter = ('alert_type', 'severity', 'is_resolved', 'created_at')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'resolved_at')
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # Only on creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user', 'resource_type', 'created_at')
    list_filter = ('action', 'resource_type', 'created_at')
    search_fields = ('user__username', 'description', 'resource_id')
    readonly_fields = ('created_at',)
    
    def has_add_permission(self, request):
        return False

@admin.register(DisputeCase)
class DisputeCaseAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'resolution', 'raised_by', 'assigned_admin', 'created_at')
    list_filter = ('status', 'resolution', 'created_at')
    search_fields = ('title', 'description', 'raised_by__username')
    readonly_fields = ('created_at', 'updated_at', 'resolved_at')
    
    def save_model(self, request, obj, form, change):
        if obj.status == 'resolved' and not obj.resolved_by:
            obj.resolved_by = request.user
        super().save_model(request, obj, form, change)