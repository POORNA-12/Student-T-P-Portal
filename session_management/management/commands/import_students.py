import pandas as pd
from django.core.management.base import BaseCommand
from session_management.models import Student
from datetime import datetime
from student_portal.utils import *
from session_management.models import ErrorLogs



class Command(BaseCommand):
    help = 'Import students from an Excel file with register_number, name, and phone_number only.'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the Excel file')

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']
        try:
            df = pd.read_excel(file_path)

            # Adjust these keys to match your exact Excel column headers
            column_mapping = {
                'Reg.No': 'register_number',
                'Name of the Student': 'name',
                'Student No': 'phone_number',
            }

            df.rename(columns=column_mapping, inplace=True)

            # Check all required columns
            required_fields = ['register_number', 'name', 'phone_number']
            for field in required_fields:
                if field not in df.columns:
                    self.stderr.write(self.style.ERROR(f"❌ Missing column: {field}"))
                    return

            for _, row in df.iterrows():
                student, created = Student.objects.get_or_create(
                    register_number=row['register_number'],
                    defaults={
                        'name': row['name'],
                        'phone_number': str(row['phone_number']),
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'✅ Added: {student.register_number}'))
                else:
                    self.stdout.write(self.style.WARNING(f'⚠️ Exists: {student.register_number}'))

        except Exception as e:
            return log_exception(e)
