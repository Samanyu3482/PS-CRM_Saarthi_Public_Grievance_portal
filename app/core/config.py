from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "PS-CRM"
    MONGODB_URI: str
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

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings()
