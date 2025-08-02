
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
    name = models.CharField(max_length=100, null=False, blank=False, default="Unknown")
    phone_number = models.CharField(max_length=15, null=False, blank=False, default="0000000000")
    dob = models.DateField(null=False, blank=False, default=make_aware(datetime(2000, 1, 1)))
    gender = models.CharField(max_length=20, null=False, blank=False, default="Not Specified")
    father_name = models.CharField(max_length=100, null=False, blank=False, default="Unknown")
    mother_name = models.CharField(max_length=100, null=False, blank=False, default="Unknown")
    email = models.EmailField(null=False, blank=False, default="example@example.com")
    aadhar_number = models.CharField(max_length=12, null=False, blank=False, default="000000000000")
    password = models.CharField(max_length=128, null=True, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.register_number})"

class OTP(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
