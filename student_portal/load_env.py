import os
from dotenv import load_dotenv

load_dotenv()


POSTGRESQL_PASSWORD = os.getenv("POSTGRESQL_PASSWORD")
SUPERUSER_PASSWORD = os.getenv("SUPERUSER_PASSWORD")
SECRET_KEY = os.getenv('SECRET_KEY')
DB_PORT = os.getenv("DB_PORT", '5432')

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")