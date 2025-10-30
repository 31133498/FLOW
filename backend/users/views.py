from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .serializers import UserRegistrationSerializer, UserSerializer, UserProfileSerializer, KYCRecordSerializer
from .models import UserProfile, KYCRecord

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserRegistrationSerializer

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_object(self):
        return self.request.user

class UserProfileDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

class KYCRecordView(generics.ListCreateAPIView):
    serializer_class = KYCRecordSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        return KYCRecord.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def send_otp(request):
    # Implement OTP sending logic here
    phone = request.data.get('phone')
    # Integration with SMS provider
    return Response({"message": "OTP sent successfully"})

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def verify_otp(request):
    # Implement OTP verification logic here
    phone = request.data.get('phone')
    otp = request.data.get('otp')
    # Verify OTP and return tokens
    return Response({"message": "OTP verified successfully"})