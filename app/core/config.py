import os
from pydantic_settings import BaseSettings
from typing import List, Optional, Literal
from pydantic import model_validator

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENV_PATH = os.path.join(_BASE_DIR, ".env")

class Settings(BaseSettings):
    ENVIRONMENT: Literal['development', 'test', 'production'] = 'development'
    PROJECT_NAME: str = "Ordenemos a Neiva API - Escucha y gestión ciudadana"
    VERSION: str = "1.0.0"
    PUBLIC_ASSET_BASE: str = '/assets'
    AUTO_SYNC_ENABLED: bool = True
    AUTO_ANALYZE_ENABLED: bool = False
    SESSION_RETENTION_DAYS: int = 30
    BACKUP_ENCRYPTION_KEY: Optional[str] = None
    BFF_PROXY_SECRET: Optional[str] = None
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
    OPENAI_INITIAL_BUDGET: float = 10.00
    OPENAI_CONSUMED_USD: Optional[float] = None
    OPENAI_REAL_BALANCE: Optional[float] = None

    # Configuración de Integración con Meta (Facebook & Instagram)
    META_APP_ID: Optional[str] = None
    META_APP_SECRET: Optional[str] = None
    META_VERIFY_TOKEN: str = "civia_meta_webhook_neiva_2026"
    META_PAGE_ACCESS_TOKEN: Optional[str] = None
    META_PAGE_ID: Optional[str] = "275486829735525"

    # Configuración de Servidor de Correos (SMTP / OTP)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = ""
    SMTP_TLS: bool = True
    SMTP_SSL: bool = False

    @model_validator(mode='after')
    def production_security(self):
        if self.ENVIRONMENT == 'production':
            from urllib.parse import urlsplit
            known = {'SUPER_SECRET_KEY_REEMPLAZAR_EN_PRODUCCION', 'civia_secret_dev_key_2026_bogota_intelligence'}
            if len(self.SECRET_KEY) < 32 or self.SECRET_KEY in known or self.SECRET_KEY.startswith('generate-'):
                raise ValueError('Configura una SECRET_KEY privada y aleatoria antes de iniciar producción.')
            if any(origin == '*' or not origin.startswith('https://') for origin in self.BACKEND_CORS_ORIGINS):
                raise ValueError('Producción requiere orígenes CORS HTTPS explícitos.')
            for origin in self.BACKEND_CORS_ORIGINS:
                parsed=urlsplit(origin)
                if not parsed.hostname or '*' in origin or parsed.path or parsed.query or parsed.fragment or parsed.username or 'REPLACE' in origin:
                    raise ValueError('Configura orígenes HTTPS reales, sin rutas, credenciales ni comodines.')
            if self.DATABASE_URL=='postgresql://postgres:1234@localhost:5432/civia_db' or 'REPLACE' in self.DATABASE_URL or not self.DATABASE_URL.startswith(('postgresql://','postgresql+psycopg://','postgres://')):
                raise ValueError('Configura la base PostgreSQL privada del despliegue.')
            if not 30<=self.ACCESS_TOKEN_EXPIRE_MINUTES<=1440:
                raise ValueError('Configura la duración de sesión entre 30 y 1440 minutos para producción.')
            if self.BFF_PROXY_SECRET and (len(self.BFF_PROXY_SECRET)<32 or self.BFF_PROXY_SECRET.startswith(('REPLACE','generate-'))):
                raise ValueError('Configura una clave privada para el intermediario de acceso.')
            if (self.META_APP_SECRET or self.META_PAGE_ACCESS_TOKEN) and (not self.META_VERIFY_TOKEN or self.META_VERIFY_TOKEN=='civia_meta_webhook_neiva_2026'):
                raise ValueError('Configura un verificador privado para el webhook antes de activarlo.')
        return self

    class Config:
        env_file = _ENV_PATH
        case_sensitive = True
        hide_input_in_errors = True

settings = Settings()
