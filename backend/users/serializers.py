from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import UserProfile, KYCRecord

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    phone = serializers.CharField(required=True)
    
    class Meta:
        model = User
        fields = ('email', 'phone', 'username', 'password', 'password_confirm', 'role')
        extra_kwargs = {
            'email': {'required': True},
            'username': {'required': True}
        }
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Password fields don't match."})
        
        # Validate role
        if attrs.get('role') not in ['student', 'enterprise']:
            raise serializers.ValidationError({"role": "Role must be either 'student' or 'enterprise'"})
        
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        
        # Create user profile
        UserProfile.objects.create(user=user)
        
        return user

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'
        read_only_fields = ('user',)

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'phone', 'role', 'kyc_completed', 
                 'wallet_balance', 'reputation_score', 'tier', 'is_verified', 
                 'profile', 'created_at')
        read_only_fields = ('id', 'kyc_completed', 'wallet_balance', 
                           'reputation_score', 'tier', 'is_verified', 'created_at')

class KYCRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCRecord
        fields = '__all__'
        read_only_fields = ('user', 'status', 'verified_by', 'verified_at')

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        email = attrs.get('email')
        phone = attrs.get('phone')
        
        if not email and not phone:
            raise serializers.ValidationError("Either email or phone must be provided.")
        
        return attrs