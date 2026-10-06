from pydantic_settings import BaseSettings
from typing import List, Optional
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = str(BASE_DIR / ".env")

class Settings(BaseSettings):
    PROJECT_NAME: str = "CIVIA API - Plataforma de Inteligencia Ciudadana"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Configuración de Base de Datos (Supabase / PostgreSQL)
    DATABASE_URL: str = "postgresql://postgres:1234@localhost:5432/civia_db"
    
    # Configuración de Seguridad y CORS
    SECRET_KEY: str = "civia_secret_dev_key_2026_bogota_intelligence"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 días
    
    # Orígenes permitidos para CORS (Frontend)
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Configuración de Inteligencia Artificial (OpenAI)
    OPENAI_API_KEY: Optional[str] = None

    class Config:
        env_file = ENV_FILE
        case_sensitive = True

settings = Settings()
