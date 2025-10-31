from rest_framework import serializers
from .models import TaskUnit, TaskSubmission, PhysicalVerification, TaskValidation

class TaskUnitSerializer(serializers.ModelSerializer):
    project_title = serializers.CharField(source='project.title', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True, allow_null=True)
    
    class Meta:
        model = TaskUnit
        fields = '__all__'
        read_only_fields = ('created_at', 'assigned_at', 'submitted_at', 'completed_at')

class TaskUnitListSerializer(serializers.ModelSerializer):
    project_title = serializers.CharField(source='project.title', read_only=True)
    
    class Meta:
        model = TaskUnit
        fields = ('id', 'title', 'type', 'pay_amount', 'estimated_time_seconds', 
                 'status', 'project_title', 'created_at', 'unit_index')

class TaskSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskSubmission
        fields = '__all__'
        read_only_fields = ('submitted_by', 'submitted_at')

class CreateTaskSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskSubmission
        fields = ('submission_data', 'photos', 'gps_location', 'supervisor_code')
    
    def validate(self, attrs):
        task_unit = self.context['task_unit']
        
        # Validate physical tasks
        if task_unit.type in ['physical', 'hybrid']:
            if not attrs.get('gps_location'):
                raise serializers.ValidationError("GPS location is required for physical tasks")
            if not attrs.get('photos'):
                raise serializers.ValidationError("Photos are required for physical tasks")
        
        return attrs

class PhysicalVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhysicalVerification
        fields = '__all__'

class TaskValidationSerializer(serializers.ModelSerializer):
    validator_name = serializers.CharField(source='validator.username', read_only=True)
    
    class Meta:
        model = TaskValidation
        fields = '__all__'
        read_only_fields = ('validator', 'created_at', 'updated_at')

class AcceptTaskSerializer(serializers.Serializer):
    task_id = serializers.IntegerField()

class TaskStreamSerializer(serializers.ModelSerializer):
    project_title = serializers.CharField(source='project.title', read_only=True)
    
    class Meta:
        model = TaskUnit
        fields = ('id', 'title', 'description', 'type', 'pay_amount', 
                 'estimated_time_seconds', 'project_title', 'unit_index', 'created_at')