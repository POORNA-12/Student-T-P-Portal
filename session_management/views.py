import random
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Student, OTP
from .serializers import RegisterNumberSerializer, OTPVerifySerializer, SetPasswordSerializer
from twilio.rest import Client
from django.contrib.auth.hashers import make_password
from decouple import config
from student_portal.utils import *


account_sid = config('TWILIO_ACCOUNT_SID')
auth_token = config('TWILIO_AUTH_TOKEN')
twilio_phone = config('TWILIO_PHONE')
twilio_client = Client(account_sid, auth_token)

class RegisterCheckView(APIView):
    def post(self, request):
        serializer = RegisterNumberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reg_no = serializer.validated_data['register_number']

        try:
            student = Student.objects.get(register_number=reg_no)
            recent_otp = OTP.objects.filter(
                student=student, created_at__gte=timezone.now() - timedelta(minutes=1)
            ).exists()
            if recent_otp:
                return Response({"error": "Please wait before requesting a new OTP."}, status=429)

            otp = str(random.randint(100000, 999999))
            OTP.objects.create(student=student, otp=otp)

            twilio_client.messages.create(
                body=f"Your OTP is {otp}",
                from_=twilio_phone,
                to=student.phone_number
            )

            # ✅ Include phone number in response
            return Response({
                "message": "OTP sent successfully",
                "phone_number": student.phone_number
            }, status=200)

        except Student.DoesNotExist:
            return Response({"error": "Register number not found"}, status=404)
        except Exception as e:
            return log_exception(e)

class OTPVerifyView(APIView):
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reg_no = serializer.validated_data['register_number']
        otp_input = serializer.validated_data['otp']

        try:
            student = Student.objects.get(register_number=reg_no)
            otp_obj = OTP.objects.filter(student=student).latest('created_at')

            if otp_obj.otp != otp_input:
                return Response({"error": "Invalid OTP"}, status=400)

            if timezone.now() - otp_obj.created_at > timedelta(minutes=5):
                return Response({"error": "OTP expired"}, status=400)

            return Response({"message": "OTP verified"}, status=200)
        except Exception as e:
            return log_exception(e)
        except:
            return Response({"error": "Verification failed"}, status=400)

class SetPasswordView(APIView):
    def post(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reg_no = serializer.validated_data['register_number']
        password = serializer.validated_data['password']

        try:
            student = Student.objects.get(register_number=reg_no)
            student.password = make_password(password)
            student.save()

            refresh = RefreshToken.for_user(student)
            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "name": student.name
            }, status=200)
        except Exception as e:
            return log_exception(e)
        except:
            return Response({"error": "Failed to set password"}, status=400)
