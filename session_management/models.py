
from django.db import models
class ErrorLogs(models.Model):
    error = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"{self.id}, {self.error}"