from rest_framework import serializers
from .models import TaskUnit, TaskSubmission, PhysicalVerification

class TaskUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskUnit
        fields = '__all__'
        read_only_fields = ('created_at', 'assigned_at', 'submitted_at', 'completed_at')

class TaskUnitListSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskUnit
        fields = ('id', 'title', 'type', 'pay_amount', 'estimated_time_seconds', 
                 'status', 'created_at')

class TaskSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskSubmission
        fields = '__all__'
        read_only_fields = ('submitted_by', 'submitted_at')

class PhysicalVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhysicalVerification
        fields = '__all__'