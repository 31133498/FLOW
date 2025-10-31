from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from .serializers import (
    UserRegistrationSerializer, UserSerializer, UserProfileSerializer, 
    KYCRecordSerializer, UserLoginSerializer
)
from .models import UserProfile, KYCRecord

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user, context=self.get_serializer_context()).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_view(request):
    serializer = UserLoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    data = serializer.validated_data
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')
    
    # Authenticate user
    if email:
        user = authenticate(request, email=email, password=password)
    else:
        try:
            user = User.objects.get(phone=phone)
            if user.check_password(password):
                user = user
            else:
                user = None
        except User.DoesNotExist:
            user = None
    
    if user is not None:
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })
    else:
        return Response(
            {'error': 'Invalid credentials'}, 
            status=status.HTTP_401_UNAUTHORIZED
        )

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
    """
    Simple OTP simulation - in production, integrate with SMS provider
    """
    phone = request.data.get('phone')
    
    if not phone:
        return Response({'error': 'Phone number is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # For demo purposes, we'll just return a static OTP
    # In production, generate random OTP and store with expiration
    demo_otp = "123456"
    
    return Response({
        "message": "OTP sent successfully", 
        "demo_otp": demo_otp  # Remove this in production
    })

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def verify_otp(request):
    """
    Verify OTP - in production, validate against stored OTP
    """
    phone = request.data.get('phone')
    otp = request.data.get('otp')
    
    if not phone or not otp:
        return Response(
            {'error': 'Phone and OTP are required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # For demo, accept any OTP. In production, validate against stored OTP
    try:
        user = User.objects.get(phone=phone)
        refresh = RefreshToken.for_user(user)
        
        return Response({
            "message": "OTP verified successfully",
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })
        
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_stats(request):
    """
    Get user statistics for dashboard
    """
    user = request.user
    
    stats = {
        'wallet_balance': user.wallet_balance,
        'reputation_score': user.reputation_score,
        'tier': user.tier,
        'kyc_completed': user.kyc_completed,
        'tasks_completed': user.assigned_tasks.filter(status='completed').count(),
        'tasks_pending': user.assigned_tasks.filter(status__in=['assigned', 'submitted']).count(),
    }
    
    return Response(stats)