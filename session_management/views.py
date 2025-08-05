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
from .serializers import RegisterNumberSerializer, OTPVerifySerializer, SetPasswordSerializer, LoginSerializer, ForgotPasswordSerializer
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from django.contrib.auth.hashers import make_password, check_password
from decouple import config
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

            if student.password:
                return Response({"message": "Please enter your password."}, status=200)

            recent_otp = OTP.objects.filter(
                student=student, created_at__gte=timezone.now() - timedelta(minutes=1)
            ).exists()
            if recent_otp:
                return Response({"error": "Please wait before requesting a new OTP."}, status=429)

            otp = str(random.randint(100000, 999999))
            OTP.objects.create(student=student, otp=otp)

            phone_number = student.phone_number.strip().replace(' ', '')
            if not phone_number.startswith('+91'):
                phone_number = '+91' + phone_number.lstrip('0')

            try:
                twilio_client.messages.create(
                    body=f"Your OTP is {otp}",
                    from_=twilio_phone,
                    to=phone_number
                )
            except TwilioRestException as e:
                log_exception(e)
                return Response({"error": f"Twilio error: {str(e)}. Verify phone number in Twilio Console."}, status=400)

            return Response({
                "message": "OTP sent successfully",
                "phone_number": phone_number
            }, status=200)

        except Student.DoesNotExist:
            return Response({"error": "Register number not found"}, status=404)
        except Exception as e:
            log_exception(e)
            return Response({"error": str(e)}, status=500)

class OTPVerifyView(APIView):
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reg_no = serializer.validated_data['register_number'].upper()
        otp_input = serializer.validated_data['otp']

        try:
            student = Student.objects.get(register_number=reg_no)
            try:
                otp_obj = OTP.objects.filter(student=student).latest('created_at')
                if otp_obj.otp != otp_input:
                    log_exception(Exception(f"Invalid OTP provided: {otp_input}, expected: {otp_obj.otp}"))
                    return Response({"error": "Invalid OTP"}, status=400)

                if timezone.now() - otp_obj.created_at > timedelta(minutes=5):
                    log_exception(Exception(f"OTP expired: {otp_input}, created at: {otp_obj.created_at}"))
                    return Response({"error": "OTP expired"}, status=400)

                return Response({"message": "OTP verified"}, status=200)
            except OTP.DoesNotExist:
                log_exception(Exception(f"No OTP found for student: {reg_no}"))
                return Response({"error": "No OTP found for this student"}, status=400)
        except Student.DoesNotExist:
            return Response({"error": "Register number not found"}, status=404)
        except Exception as e:
            log_exception(e)
            return Response({"error": str(e)}, status=500)

class SetPasswordView(APIView):
    def post(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reg_no = serializer.validated_data['register_number'].upper()
        password = serializer.validated_data['password']

        try:
            student = Student.objects.get(register_number=reg_no)

            # ✅ Set and save hashed password
            student.password = make_password(password)
            student.save()

            # ✅ Generate JWT tokens
            refresh = RefreshToken.for_user(student)
            access = refresh.access_token

            return Response({
                "access": str(access),
                "refresh": str(refresh),
                "name": student.name,
                "register_number": student.register_number,
            }, status=status.HTTP_200_OK)

        except Student.DoesNotExist:
            return Response(
                {"error": "Student not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            log_exception(e)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reg_no = serializer.validated_data['register_number'].upper()
        password = serializer.validated_data['password']

        try:
            student = Student.objects.get(register_number=reg_no)

            if check_password(password, student.password):
                # ✅ Correct way to generate refresh and access tokens
                refresh = RefreshToken.for_user(student)
                access = refresh.access_token

                return Response({
                    "access": str(access),
                    "refresh": str(refresh),
                    "name": student.name,
                    "register_number": student.register_number,
                    "phone_number": student.phone_number,
                    "email": student.email or ""
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "Incorrect password"},
                    status=status.HTTP_401_UNAUTHORIZED
                )

        except Student.DoesNotExist:
            return Response(
                {"error": "Register number not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            log_exception(e)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class RefreshTokenView(APIView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"message": "Refresh token is required!"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)

            return Response(
                {
                    "access": access_token,
                    "refresh": str(refresh)
                },
                status=status.HTTP_200_OK,
            )

        except TokenError as e:
            return Response(
                {"message": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        except Exception as e:
            log_exception(e)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class StudentView(APIView):
    permission_classes = [IsAuthenticated]  # Use JWT globally via settings.py

    def get(self, request):
        reg_no = request.GET.get('register_number', '').upper()

        try:
            student = Student.objects.get(register_number=reg_no)
            data = {
                "register_number": student.register_number,
                "name": student.name,
                "phone_number": student.phone_number,
                "dob": student.dob.isoformat() if student.dob else None,
                "gender": student.gender or "",
                "father_name": student.father_name or "",
                "mother_name": student.mother_name or "",
                "email": student.email or "",
                "aadhar_number": student.aadhar_number or "",
                "updated_at": student.updated_at.isoformat() if student.updated_at else None
            }
            return Response(data, status=200)
        except Student.DoesNotExist:
            return Response({"error": "Student not found"}, status=404)

    def post(self, request):
        try:
            data = request.data
            reg_no = data.get("register_number", "").upper()
            otp = data.get("otp", "").strip()

            student = Student.objects.get(register_number=reg_no)

            # Format phone number
            phone_number = student.phone_number.strip().replace(' ', '')
            if not phone_number.startswith('+91'):
                phone_number = '+91' + phone_number.lstrip('0')

            # If OTP is not provided, generate and send one
            if not otp:
                generated_otp = str(random.randint(100000, 999999))
                OTP.objects.create(student=student, otp=generated_otp)

                try:
                    twilio_client.messages.create(
                        body=f"Your OTP is {generated_otp}",
                        from_=twilio_phone,
                        to=phone_number
                    )
                except Exception as e:
                    log_exception(e)
                    return Response({"error": f"Twilio error: {str(e)}"}, status=400)

                return Response({"message": "OTP sent to registered mobile number"}, status=200)

            # Validate OTP
            valid_otp = OTP.objects.filter(
                student=student,
                otp=otp,
                created_at__gte=timezone.now() - timedelta(minutes=5)
            ).order_by("-created_at").first()

            if not valid_otp:
                try:
                    latest_otp = OTP.objects.filter(student=student).latest('created_at')
                    if latest_otp.otp != otp:
                        return Response({"error": "Invalid OTP"}, status=400)
                    if timezone.now() - latest_otp.created_at > timedelta(minutes=5):
                        return Response({"error": "OTP expired"}, status=400)
                except OTP.DoesNotExist:
                    return Response({"error": "No OTP found for this student"}, status=400)

            # Update student details
            update_fields = ['dob', 'gender', 'father_name', 'mother_name', 'email', 'aadhar_number']
            for field in update_fields:
                value = data.get(field)
                if value:
                    setattr(student, field, parse_date(value) if field == 'dob' else value)

            student.save()
            return Response({"message": "Student data updated successfully"}, status=200)

        except Student.DoesNotExist:
            return Response({"error": "Student not found"}, status=404)
        except Exception as e:
            log_exception(e)
            return Response({"error": str(e)}, status=500)


class ForgotPasswordView(APIView):
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reg_no = serializer.validated_data['register_number'].upper()
        otp = serializer.validated_data.get('otp', '').strip()
        new_password = serializer.validated_data.get('new_password', '')

        try:
            student = Student.objects.get(register_number=reg_no)

            if not student.password:
                return Response(
                    {"error": "No password set for this account. Use registration process."},
                    status=400
                )

            phone_number = student.phone_number.strip().replace(' ', '')
            if not phone_number.startswith('+91'):
                phone_number = '+91' + phone_number.lstrip('0')

            # Step 1: Requesting OTP
            if not otp and not new_password:
                recent_otp = OTP.objects.filter(
                    student=student, created_at__gte=timezone.now() - timedelta(minutes=1)
                ).exists()

                if recent_otp:
                    return Response(
                        {"error": "Please wait before requesting a new OTP."},
                        status=429
                    )

                generated_otp = str(random.randint(100000, 999999))
                OTP.objects.create(student=student, otp=generated_otp)

                try:
                    twilio_client.messages.create(
                        body=f"Your password reset OTP is {generated_otp}",
                        from_=twilio_phone,
                        to=phone_number
                    )
                except TwilioRestException as e:
                    log_exception(e)
                    return Response(
                        {"error": f"Twilio error: {str(e)}. Verify phone number in Twilio Console."},
                        status=400
                    )

                return Response({
                    "message": "Password reset OTP sent successfully",
                    "phone_number": phone_number
                }, status=200)

            # Step 2: Resetting password
            if otp and new_password:
                valid_otp = OTP.objects.filter(
                    student=student,
                    otp=otp,
                    created_at__gte=timezone.now() - timedelta(minutes=5)
                ).order_by("-created_at").first()

                if not valid_otp:
                    try:
                        latest_otp = OTP.objects.filter(student=student).latest('created_at')
                        if latest_otp.otp != otp:
                            log_exception(Exception(f"Invalid OTP provided: {otp}, expected: {latest_otp.otp}"))
                            return Response({"error": "Invalid OTP"}, status=400)

                        if timezone.now() - latest_otp.created_at > timedelta(minutes=5):
                            log_exception(Exception(f"OTP expired: {otp}, created at: {latest_otp.created_at}"))
                            return Response({"error": "OTP expired"}, status=400)
                    except OTP.DoesNotExist:
                        log_exception(Exception(f"No OTP found for student: {reg_no}"))
                        return Response({"error": "No OTP found for this student"}, status=400)

                student.password = make_password(new_password)
                student.save()
                OTP.objects.filter(student=student).delete()

                # 🔐 Generate JWT tokens
                refresh = RefreshToken.for_user(student)
                refresh['register_number'] = student.register_number
                refresh['name'] = student.name
                access = refresh.access_token

                return Response({
                    "message": "Password reset successfully",
                    "access": str(access),
                    "refresh": str(refresh),
                    "name": student.name,
                    "register_number": student.register_number,
                    "phone_number": student.phone_number,
                    "email": student.email if student.email else ""
                }, status=200)

            return Response(
                {"error": "Both OTP and new password are required to reset password"},
                status=400
            )

        except Student.DoesNotExist:
            return Response({"error": "Register number not found"}, status=404)
        except Exception as e:
            log_exception(e)
            return Response({"error": str(e)}, status=500)