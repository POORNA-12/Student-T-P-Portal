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
        

        
@method_decorator(csrf_exempt, name='dispatch')
class StudentView(APIView):
    def get(self, request):
        reg_no = request.GET.get('register_number', '').upper()

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
            return JsonResponse(data, status=200)
        except Student.DoesNotExist:
            return JsonResponse({"error": "Student not found"}, status=404)

    def post(self, request):
        try:
            data = json.loads(request.body)
            reg_no = data.get("register_number", "").upper()
            otp = data.get("otp", "").strip()

            student = Student.objects.get(register_number=reg_no)

            # Normalize phone number
            phone_number = student.phone_number.strip().replace(' ', '')
            if not phone_number.startswith('+91'):
                phone_number = '+91' + phone_number.lstrip('0')

            if not otp:
                # Send OTP
                generated_otp = str(random.randint(100000, 999999))
                OTP.objects.create(student=student, otp=generated_otp)

                twilio_client.messages.create(
                    body=f"Your OTP is {generated_otp}",
                    from_=twilio_phone,
                    to=phone_number
                )

                return JsonResponse({"message": "OTP sent to registered mobile number"}, status=200)

            # ✅ OTP Validation
            valid_otp = OTP.objects.filter(
                student=student,
                otp=otp,
                created_at__gte=timezone.now() - timedelta(minutes=5)
            ).order_by("-created_at").first()

            if not valid_otp:
                return JsonResponse({"error": "Invalid or expired OTP"}, status=400)

            # ✅ Update fields
            update_fields = ['dob', 'gender', 'father_name', 'mother_name', 'email', 'aadhar_number']
            for field in update_fields:
                value = data.get(field)
                if value:
                    setattr(student, field, parse_date(value) if field == 'dob' else value)

            student.save()
            return JsonResponse({"message": "Student data updated successfully"}, status=200)

        except Student.DoesNotExist:
            return JsonResponse({"error": "Student not found"}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)