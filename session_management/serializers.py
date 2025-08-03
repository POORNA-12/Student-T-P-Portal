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

