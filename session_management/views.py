import random
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.permissions import IsAuthenticated
from .models import Student, OTP
from .serializers import RegisterNumberSerializer, OTPVerifySerializer, SetPasswordSerializer, LoginSerializer
from twilio.rest import Client
from django.contrib.auth.hashers import make_password, check_password
from decouple import config
from student_portal.utils import *
import firebase_admin
from firebase_admin import auth as firebase_auth
from student_portal.utils import *
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from django.utils.dateparse import parse_date


account_sid = config('TWILIO_ACCOUNT_SID')
auth_token = config('TWILIO_AUTH_TOKEN')
twilio_phone = config('TWILIO_PHONE')
twilio_client = Client(account_sid, auth_token)

class RegisterCheckView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = RegisterNumberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reg_no = serializer.validated_data['register_number'].upper()

        try:
            print(f"[INFO] Looking up student: {reg_no}")
            student = Student.objects.get(register_number=reg_no)

            # If password is already set, ask for password
            if student.password:
                print(f"[INFO] Password already set for {reg_no}")
                return Response({"message": "Please enter your password."}, status=status.HTTP_200_OK)

            # Rate limit check (1 min)
            recent_otp = OTP.objects.filter(
                student=student,
                created_at__gte=timezone.now() - timedelta(minutes=1)
            ).exists()

            if recent_otp:
                print(f"[WARN] OTP recently sent to {reg_no}")
                return Response({"message": "Please wait before requesting a new OTP."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

            # Generate and store OTP
            otp = str(random.randint(100000, 999999))
            OTP.objects.create(student=student, otp=otp)

            # Format phone number
            phone_number = student.phone_number.strip().replace(' ', '')
            if not phone_number.startswith('+91'):
                phone_number = '+91' + phone_number.lstrip('0')

            print(f"[INFO] Sending OTP to: {phone_number} | OTP: {otp}")

            # Send SMS
            twilio_client.messages.create(
                body=f"Your OTP is {otp}",
                from_=twilio_phone,
                to=phone_number
            )

            print(f"[SUCCESS] OTP sent successfully to {phone_number}")

            return Response({
                "message": "OTP sent successfully.",
                "phone_number": phone_number
            }, status=status.HTTP_200_OK)

        except Student.DoesNotExist:
            print(f"[ERROR] Student not found: {reg_no}")
            return Response({"message": "Register number not found."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            print(f"[ERROR] Exception during register check: {e}")
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class OTPVerifyView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reg_no = serializer.validated_data['register_number'].upper()
        otp_input = serializer.validated_data['otp']

        try:
            student = Student.objects.get(register_number=reg_no)
            otp_obj = OTP.objects.filter(student=student).latest('created_at')

            if timezone.now() - otp_obj.created_at > timedelta(minutes=5):
                return Response({"message": "OTP expired."}, status=status.HTTP_400_BAD_REQUEST)

            if otp_obj.otp != otp_input:
                return Response({"message": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"message": "OTP verified."}, status=status.HTTP_200_OK)

        except Student.DoesNotExist:
            return Response({"message": "Student not found."}, status=status.HTTP_404_NOT_FOUND)
        except OTP.DoesNotExist:
            return Response({"message": "No OTP found. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SetPasswordView(APIView):
    def post(self, request, *args, **kwargs):
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
            }, status=status.HTTP_200_OK)

        except Student.DoesNotExist:
            return Response({"message": "Student not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RefreshTokenView(APIView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"message": "Refresh token is required!"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Attempt to decode and use the refresh token
            refresh = RefreshToken(refresh_token)

            # Create a new access token
            access_token = str(refresh.access_token)

            return Response(
                {
                    "access": access_token,
                    "refresh": str(refresh)  # Optional: return the same refresh token
                },
                status=status.HTTP_200_OK
            )

        except TokenError:
            return Response(
                {"message": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class LoginView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reg_no = serializer.validated_data['register_number'].upper()
        password = serializer.validated_data['password']

        try:
            student = Student.objects.get(register_number=reg_no)

            if not check_password(password, student.password):
                return Response({"message": "Incorrect password."}, status=status.HTTP_401_UNAUTHORIZED)

            refresh = RefreshToken.for_user(student)

            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "name": student.name,
                "phone_number": student.phone_number,
                "email": student.email
            }, status=status.HTTP_200_OK)

        except Student.DoesNotExist:
            return Response({"message": "Register number not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        

        
class StudentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        reg_no = request.GET.get('register_number', '').upper()

        if not reg_no:
            return Response(
                {"message": "Register number is required!"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            student = Student.objects.get(register_number=reg_no)
            data = {
                "register_number": student.register_number,
                "name": student.name,
                "phone_number": student.phone_number,
                "dob": student.dob.isoformat() if student.dob else None,
                "gender": student.gender,
                "father_name": student.father_name,
                "mother_name": student.mother_name,
                "email": student.email,
                "aadhar_number": student.aadhar_number,
                "updated_at": student.updated_at.isoformat() if student.updated_at else None
            }
            return Response(data, status=status.HTTP_200_OK)
        except Student.DoesNotExist:
            return Response(
                {"message": "Student not found."},
                status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request, *args, **kwargs):
        reg_no = request.data.get("register_number", "").upper()
        otp = request.data.get("otp", "").strip()

        if not reg_no:
            return Response(
                {"message": "Register number is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            student = Student.objects.get(register_number=reg_no)
        except Student.DoesNotExist:
            return Response(
                {"message": "Student not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Normalize phone number
        phone_number = student.phone_number.strip().replace(' ', '')
        if not phone_number.startswith('+91'):
            phone_number = '+91' + phone_number.lstrip('0')

        if not otp:
            # Send OTP
            generated_otp = str(random.randint(100000, 999999))
            OTP.objects.create(student=student, otp=generated_otp)

            try:
                twilio_client.messages.create(
                    body=f"Your OTP is {generated_otp}",
                    from_=twilio_phone,
                    to=phone_number
                )
                return Response(
                    {"message": "OTP sent to registered mobile number."},
                    status=status.HTTP_200_OK
                )
            except Exception as e:
                return Response(
                    {"message": "Failed to send OTP.", "error": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # OTP Validation
        valid_otp = OTP.objects.filter(
            student=student,
            otp=otp,
            created_at__gte=timezone.now() - timedelta(minutes=5)
        ).order_by("-created_at").first()

        if not valid_otp:
            return Response(
                {"message": "Invalid or expired OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update student data
        update_fields = ['dob', 'gender', 'father_name', 'mother_name', 'email', 'aadhar_number']
        for field in update_fields:
            value = request.data.get(field)
            if value:
                setattr(student, field, parse_date(value) if field == 'dob' else value)

        try:
            student.save()
            return Response(
                {"message": "Student data updated successfully."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"message": "Failed to update student data.", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )