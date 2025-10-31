from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UserProfile, KYCRecord

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'phone', 'role', 'kyc_completed', 'wallet_balance', 'is_verified')
    list_filter = ('role', 'kyc_completed', 'is_verified', 'is_staff')
    search_fields = ('username', 'email', 'phone')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Flow Specific', {
            'fields': ('phone', 'role', 'kyc_completed', 'wallet_balance', 'reputation_score', 'tier', 'is_verified')
        }),
    )

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'student_id', 'bank_name')
    search_fields = ('user__username', 'student_id', 'bank_name')

@admin.register(KYCRecord)
class KYCRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'document_type', 'status', 'created_at')
    list_filter = ('status', 'document_type')
    search_fields = ('user__username', 'document_number')