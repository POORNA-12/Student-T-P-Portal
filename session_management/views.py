import random
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Student, OTP
from .serializers import RegisterNumberSerializer, OTPVerifySerializer, SetPasswordSerializer, LoginSerializer
from twilio.rest import Client
from django.contrib.auth.hashers import make_password, check_password
from decouple import config
from student_portal.utils import *
import firebase_admin
from firebase_admin import auth as firebase_auth
from student_portal.utils import *


account_sid = config('TWILIO_ACCOUNT_SID')
auth_token = config('TWILIO_AUTH_TOKEN')
twilio_phone = config('TWILIO_PHONE')
twilio_client = Client(account_sid, auth_token)

# class RegisterCheckView(APIView):
#     def post(self, request):
#         serializer = RegisterNumberSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         reg_no = serializer.validated_data['register_number'].upper()
#         id_token = request.data.get('idToken')

#         if not id_token:
#             return Response({"error": "Firebase ID token missing."}, status=400)

#         try:
#             decoded_token = firebase_auth.verify_id_token(id_token)
#             phone_number = decoded_token.get('phone_number')

#             student = Student.objects.get(register_number=reg_no)

#             if student.phone_number != phone_number:
#                 return Response({"error": "Phone number does not match."}, status=403)

#             # OTP already verified on frontend, you can log or save verified status
#             return Response({
#                 "message": "OTP verified successfully",
#                 "phone_number": phone_number
#             }, status=200)

#         except firebase_auth.InvalidIdTokenError:
#             return Response({"error": "Invalid ID token."}, status=401)
#         except Student.DoesNotExist:
#             return Response({"error": "Register number not found"}, status=404)
#         except Exception as e:
#             return Response({"error": str(e)}, status=500)

class RegisterCheckView(APIView):
    def post(self, request):
        serializer = RegisterNumberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reg_no = serializer.validated_data['register_number'].upper()

        try:
            student = Student.objects.get(register_number=reg_no)

            # ✅ Check if password is set
            if student.password:
                return Response({"message": "Please enter your password."}, status=200)

            # ✅ Check for recent OTP within 1 minute
            recent_otp = OTP.objects.filter(
                student=student, created_at__gte=timezone.now() - timedelta(minutes=1)
            ).exists()
            if recent_otp:
                return Response({"error": "Please wait before requesting a new OTP."}, status=429)

            # ✅ Generate OTP and save
            otp = str(random.randint(100000, 999999))
            OTP.objects.create(student=student, otp=otp)

            # ✅ Format phone number to +91
            phone_number = student.phone_number.strip().replace(' ', '')
            if not phone_number.startswith('+91'):
                phone_number = '+91' + phone_number.lstrip('0')

            # ✅ Send OTP
            twilio_client.messages.create(
                body=f"Your OTP is {otp}",
                from_=twilio_phone,
                to=phone_number
            )

            return Response({
                "message": "OTP sent successfully",
                "phone_number": phone_number
            }, status=200)

        except Student.DoesNotExist:
            return Response({"error": "Register number not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class OTPVerifyView(APIView):
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reg_no = serializer.validated_data['register_number'].upper()
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
        reg_no = serializer.validated_data['register_number'].upper()
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


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reg_no = serializer.validated_data['register_number'].upper()
        password = serializer.validated_data['password']

        try:
            student = Student.objects.get(register_number=reg_no)

            if check_password(password, student.password):
                refresh = RefreshToken.for_user(student)
                return Response({
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "name": student.name,
                    "phone_number": student.phone_number,
                    "email": student.email
                }, status=200)
            else:
                return Response({"error": "Incorrect password"}, status=401)

        except Student.DoesNotExist:
            return Response({"error": "Register number not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)