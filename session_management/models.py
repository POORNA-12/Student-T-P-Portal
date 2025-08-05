from django.db import models
from datetime import timedelta, datetime
from django.utils.timezone import now, make_aware, timezone

class ErrorLogs(models.Model):
    error = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id}, {self.error}"

class Student(models.Model):
    register_number = models.CharField(max_length=20, primary_key=True, null=False, blank=False)
    name = models.CharField(max_length=100, null=False, blank=False)
    phone_number = models.CharField(max_length=15, null=False, blank=False)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, null=True, blank=True)
    father_name = models.CharField(max_length=100, null=True, blank=True)
    mother_name = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    aadhar_number = models.CharField(max_length=12, null=True, blank=True)
    password = models.CharField(max_length=128, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.register_number})"

class OTP(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)