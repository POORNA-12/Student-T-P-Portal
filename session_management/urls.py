from django.urls import path
from .views import RegisterCheckView, OTPVerifyView, SetPasswordView, LoginView, StudentView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('verify-register/', RegisterCheckView.as_view()),
    path('verify-otp/', OTPVerifyView.as_view()),
    path('set-password/', SetPasswordView.as_view()),
    path('refresh/', TokenRefreshView.as_view()),
    path('login/', LoginView.as_view()),
    path('student/', StudentView.as_view(), name='student-api'),
]
