from django.urls import path
from .views import (
    ForgotPasswordView, RegisterCheckView, OTPVerifyView, SendStudentOTPView, SetPasswordView,
     LoginView, StudentView, RefreshTokenView, UpdateStudentView
)
from rest_framework_simplejwt.views import TokenBlacklistView

urlpatterns = [
    path('verify-register/', RegisterCheckView.as_view(), name='verify-register'),
    path('verify-otp/', OTPVerifyView.as_view(), name='verify-otp'),
    path('set-password/', SetPasswordView.as_view(), name='set-password'),
    path('login/', LoginView.as_view(), name='login'),
    path('student/', StudentView.as_view(), name='student'),
    path('refresh/', RefreshTokenView.as_view(), name='token_refresh'),
    path('logout/', TokenBlacklistView.as_view(), name='token_blacklist'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('send-student-otp/', SendStudentOTPView.as_view(), name='send-student-otp'),
    path('update-student/', UpdateStudentView.as_view(), name='update-student'),
]