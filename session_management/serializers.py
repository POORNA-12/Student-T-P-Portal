from rest_framework import serializers
from .models import Student

class RegisterNumberSerializer(serializers.Serializer):
    register_number = serializers.CharField()

class OTPVerifySerializer(serializers.Serializer):
    register_number = serializers.CharField()
    otp = serializers.CharField()

class SetPasswordSerializer(serializers.Serializer):
    register_number = serializers.CharField()
    password = serializers.CharField()

class LoginSerializer(serializers.Serializer):
    register_number = serializers.CharField()
    password = serializers.CharField()

class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = '__all__'

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add register_number to the token payload
        token['user_id'] = user.register_number
        return token