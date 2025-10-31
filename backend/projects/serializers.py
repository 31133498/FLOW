from rest_framework import serializers
from .models import EnterpriseProject, ProjectFile, ProjectAudit

class ProjectFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectFile
        fields = '__all__'
        read_only_fields = ('project', 'uploaded_at')

class EnterpriseProjectSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.username', read_only=True)
    progress_percentage = serializers.FloatField(read_only=True)
    files = ProjectFileSerializer(many=True, read_only=True)
    
    class Meta:
        model = EnterpriseProject
        fields = '__all__'
        read_only_fields = ('client', 'escrow_locked', 'status', 'total_units', 
                           'completed_units', 'created_at', 'updated_at')

class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnterpriseProject
        fields = ('title', 'description', 'task_type', 'total_amount', 'metadata')
    
    def create(self, validated_data):
        validated_data['client'] = self.context['request'].user
        return super().create(validated_data)

class ProjectAuditSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.username', read_only=True)
    
    class Meta:
        model = ProjectAudit
        fields = '__all__'
        read_only_fields = ('project', 'performed_by', 'created_at')

class ProjectStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=EnterpriseProject.STATUS_CHOICES)