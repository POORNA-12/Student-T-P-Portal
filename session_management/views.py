import random
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .models import Student, OTP
from .serializers import RegisterNumberSerializer, OTPVerifySerializer, SetPasswordSerializer, LoginSerializer, ForgotPasswordSerializer
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from django.contrib.auth.hashers import make_password, check_password
from decouple import config
from student_portal.utils import *
import firebase_admin
from firebase_admin import auth as firebase_auth
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
            student.password = make_password(password)
            student.save()

            refresh = RefreshToken()
            refresh['register_number'] = student.register_number
            refresh['name'] = student.name
            access = refresh.access_token

            return Response({
                "access": str(access),
                "refresh": str(refresh),
                "name": student.name
            }, status=200)
        except Exception as e:
            log_exception(e)
            return Response({"error": str(e)}, status=500)

class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reg_no = serializer.validated_data['register_number'].upper()
        password = serializer.validated_data['password']

        try:
            student = Student.objects.get(register_number=reg_no)

            if check_password(password, student.password):
                refresh = RefreshToken()
                refresh['register_number'] = student.register_number
                refresh['name'] = student.name
                access = refresh.access_token

                return Response({
                    "access": str(access),
                    "refresh": str(refresh),
                    "name": student.name,
                    "register_number": student.register_number,
                    "phone_number": student.phone_number,
                    "email": student.email if student.email else ""
                }, status=200)
            else:
                return Response({"error": "Incorrect password"}, status=401)

        except Student.DoesNotExist:
            return Response({"error": "Register number not found"}, status=404)
        except Exception as e:
            log_exception(e)
            return Response({"error": str(e)}, status=500)

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

        except TokenError:
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
                "gender": student.gender if student.gender else "",
                "father_name": student.father_name if student.father_name else "",
                "mother_name": student.mother_name if student.mother_name else "",
                "email": student.email if student.email else "",
                "aadhar_number": student.aadhar_number if student.aadhar_number else "",
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

            phone_number = student.phone_number.strip().replace(' ', '')
            if not phone_number.startswith('+91'):
                phone_number = '+91' + phone_number.lstrip('0')

            if not otp:
                generated_otp = str(random.randint(100000, 999999))
                OTP.objects.create(student=student, otp=generated_otp)

                try:
                    twilio_client.messages.create(
                        body=f"Your OTP is {generated_otp}",
                        from_=twilio_phone,
                        to=phone_number
                    )
                except TwilioRestException as e:
                    log_exception(e)
                    return JsonResponse({"error": f"Twilio error: {str(e)}. Verify phone number in Twilio Console."}, status=400)

                return JsonResponse({"message": "OTP sent to registered mobile number"}, status=200)

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
                        return JsonResponse({"error": "Invalid OTP"}, status=400)
                    if timezone.now() - latest_otp.created_at > timedelta(minutes=5):
                        log_exception(Exception(f"OTP expired: {otp}, created at: {latest_otp.created_at}"))
                        return JsonResponse({"error": "OTP expired"}, status=400)
                except OTP.DoesNotExist:
                    log_exception(Exception(f"No OTP found for student: {reg_no}"))
                    return JsonResponse({"error": "No OTP found for this student"}, status=400)

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
            log_exception(e)
            return JsonResponse({"error": str(e)}, status=500)


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
                return Response({"error": "No password set for this account. Use registration process."}, status=400)

            phone_number = student.phone_number.strip().replace(' ', '')
            if not phone_number.startswith('+91'):
                phone_number = '+91' + phone_number.lstrip('0')

            if not otp and not new_password:
                recent_otp = OTP.objects.filter(
                    student=student, created_at__gte=timezone.now() - timedelta(minutes=1)
                ).exists()
                if recent_otp:
                    return Response({"error": "Please wait before requesting a new OTP."}, status=429)

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
                    return Response({"error": f"Twilio error: {str(e)}. Verify phone number in Twilio Console."}, status=400)

                return Response({
                    "message": "Password reset OTP sent successfully",
                    "phone_number": phone_number
                }, status=200)

            if otp and new_password:
                try:
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

                    refresh = RefreshToken()
                    refresh['register_number'] = student.register_number
                    refresh['name'] = student.name
                    access = refresh.access_token

                    return Response({
                        "message": "Password reset successfully",
                        "access": str(access),
                        "refresh": str(refresh),
                        "name": student.name
                    }, status=200)
                except Exception as e:
                    log_exception(e)
                    return Response({"error": str(e)}, status=500)

            return Response({"error": "Both OTP and new password are required to reset password"}, status=400)

        except Student.DoesNotExist:
            return Response({"error": "Register number not found"}, status=404)
        except Exception as e:
            log_exception(e)
            return Response({"error": str(e)}, status=500)