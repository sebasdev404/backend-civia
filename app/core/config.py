import os
from pydantic_settings import BaseSettings
from typing import List, Optional

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENV_PATH = os.path.join(_BASE_DIR, ".env")

class Settings(BaseSettings):
    PROJECT_NAME: str = "CIVIA API - Plataforma de Inteligencia Ciudadana"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Configuración de Base de Datos (Supabase / PostgreSQL)
    DATABASE_URL: str = "postgresql://postgres:1234@localhost:5432/civia_db"
    
    # Configuración de Seguridad y CORS
    SECRET_KEY: str = "SUPER_SECRET_KEY_REEMPLAZAR_EN_PRODUCCION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 días
    
    # Orígenes permitidos para CORS (Frontend)
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Configuración de Inteligencia Artificial (OpenAI)
    OPENAI_API_KEY: Optional[str] = None

    class Config:
        env_file = _ENV_PATH
        case_sensitive = True

settings = Settings()
