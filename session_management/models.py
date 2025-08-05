from django.db import models
from datetime import timedelta, datetime
from django.utils.timezone import now, make_aware, timezone
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin

class ErrorLogs(models.Model):
    error = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id}, {self.error}"

class StudentUserManager(BaseUserManager):
    def create_user(self, register_number, password=None, **extra_fields):
        if not register_number:
            raise ValueError("The Register Number must be set")
        register_number = register_number.upper()
        user = self.model(register_number=register_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, register_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(register_number, password, **extra_fields)

class Student(AbstractBaseUser, PermissionsMixin):
    register_number = models.CharField(max_length=20, unique=True, primary_key=True)  # ✅ Primary key
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, null=True, blank=True)
    father_name = models.CharField(max_length=100, null=True, blank=True)
    mother_name = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    aadhar_number = models.CharField(max_length=12, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'register_number'
    REQUIRED_FIELDS = ['name', 'phone_number']

    objects = StudentUserManager()

    def __str__(self):
        return f"{self.name} ({self.register_number})"


class OTP(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)