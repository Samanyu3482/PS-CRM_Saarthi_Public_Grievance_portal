from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "PS-CRM"
    MONGODB_URI: str
    DATABASE_URL: str = "postgresql://neondb_owner:npg_vjwoAI8qQYy5@ep-fragrant-surf-ao0nt2ie-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    FRONTEND_ORIGINS: str = "http://localhost:5173"
    # Firebase Configuration (defaults to "" so server can start without them)
    FIREBASE_API_KEY: str = ""
    FIREBASE_AUTH_DOMAIN: str = ""
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_STORAGE_BUCKET: str = ""
    FIREBASE_MESSAGING_SENDER_ID: str = ""
    FIREBASE_APP_ID: str = ""
    FIREBASE_MEASUREMENT_ID: str = ""
    # Meta WhatsApp Cloud API
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_TO_NUMBER: str = ""  # default recipient for testing
    # Ngrok tunnel (for exposing WhatsApp webhook locally)
    NGROK_AUTH_TOKEN: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings()

# Sync keys to os.environ so modules that use os.getenv() (e.g. agent_service) pick them up
if settings.OPENAI_API_KEY:
    os.environ.setdefault("OPENAI_API_KEY", settings.OPENAI_API_KEY)