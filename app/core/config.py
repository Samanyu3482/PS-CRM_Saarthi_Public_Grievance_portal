from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    PROJECT_NAME: str = "Saarthi PS-CRM"
    # Required — must be set in .env, no hardcoded default for security
    DATABASE_URL: str
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    FRONTEND_ORIGINS: str = "http://localhost:5173"

    # Firebase Configuration (optional — used for citizen auth)
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
    WHATSAPP_TO_NUMBER: str = ""

    # Ngrok (optional, for local WhatsApp webhook testing)
    NGROK_AUTH_TOKEN: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()

# Expose keys to os.environ for legacy modules that use os.getenv()
if settings.OPENAI_API_KEY:
    os.environ.setdefault("OPENAI_API_KEY", settings.OPENAI_API_KEY)
if settings.GEMINI_API_KEY:
    os.environ.setdefault("GEMINI_API_KEY", settings.GEMINI_API_KEY)