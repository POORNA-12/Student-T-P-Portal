from rest_framework import serializers
from .models import Student
from django.utils.dateparse import parse_date

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

class ForgotPasswordSerializer(serializers.Serializer):
    register_number = serializers.CharField(max_length=20, required=True)
    otp = serializers.CharField(max_length=6, required=False)
    new_password = serializers.CharField(max_length=128, required=False)

class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = '__all__'

class UpdateStudentSerializer(serializers.Serializer):
    register_number = serializers.CharField(max_length=20, required=True)
    otp = serializers.CharField(max_length=6, required=True)
    dob = serializers.CharField(required=False, allow_null=True)
    gender = serializers.CharField(max_length=10, required=False, allow_null=True)
    father_name = serializers.CharField(max_length=100, required=False, allow_null=True)
    mother_name = serializers.CharField(max_length=100, required=False, allow_null=True)
    email = serializers.EmailField(required=False, allow_null=True)
    aadhar_number = serializers.CharField(max_length=12, required=False, allow_null=True)

    def validate_dob(self, value):
        if value:
            parsed_date = parse_date(value)
            if not parsed_date:
                raise serializers.ValidationError("Invalid date format. Use YYYY-MM-DD.")
            return parsed_date
        return None