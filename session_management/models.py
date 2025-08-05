from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils.timezone import now, make_aware
from datetime import datetime, timedelta
import random

# ===============================
# Error Logs Model
# ===============================
class ErrorLogs(models.Model):
    error = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id}, {self.error}"

# ===============================
# Custom User Manager
# ===============================
class StudentManager(BaseUserManager):
    def create_user(self, register_number, password=None, **extra_fields):
        if not register_number:
            raise ValueError("Register number is required")
        student = self.model(register_number=register_number, **extra_fields)
        if password:
            student.set_password(password)
        else:
            student.set_unusable_password()
        student.save(using=self._db)
        return student

    def create_superuser(self, register_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(register_number, password, **extra_fields)

# ===============================
# Student Model (Custom User)
# ===============================
class Student(AbstractBaseUser, PermissionsMixin):
    register_number = models.CharField(max_length=20, unique=True, primary_key=True)
    name = models.CharField(max_length=100, default="Unknown")
    phone_number = models.CharField(max_length=15, default="0000000000")
    dob = models.DateField(default=make_aware(datetime(2000, 1, 1)))
    gender = models.CharField(max_length=20, default="Not Specified")
    father_name = models.CharField(max_length=100, default="Unknown")
    mother_name = models.CharField(max_length=100, default="Unknown")
    email = models.EmailField(default="example@example.com")
    aadhar_number = models.CharField(max_length=12, default="000000000000")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    # explicitly remove inherited field
    last_login = None

    objects = StudentManager()

    USERNAME_FIELD = 'register_number'
    REQUIRED_FIELDS = ['name', 'email']

    def __str__(self):
        return f"{self.name} ({self.register_number})"

# ===============================
# OTP Model
# ===============================
def generate_otp():
    return f"{random.randint(100000, 999999)}"

class OTP(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6, default=generate_otp)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def is_expired(self):
        return now() > self.created_at + timedelta(minutes=5)

    def __str__(self):
        return f"OTP for {self.student.register_number} - {self.otp}"
