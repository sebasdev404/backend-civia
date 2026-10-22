import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.v1 import api_v1_router
from app.core.database import engine, Base, SessionLocal

logger = logging.getLogger("civia.autosync")

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

# Crear directorio estático para carátulas locales y multimedia
os.makedirs("static/covers", exist_ok=True)

async def periodic_meta_sync_loop():
    """
    Tarea en segundo plano que mantiene la bandeja de casos y publicaciones
    siempre sincronizadas con Meta Graph API de forma autónoma.
    """
    # Esperar 20 segundos antes del primer ciclo para permitir arranque completo
    await asyncio.sleep(20)
    while True:
        try:
            from sync_live_service import sync_facebook_live_posts, sync_instagram_publications
            db = SessionLocal()
            try:
                # Sincronizar en un hilo para no bloquear el bucle de eventos asíncrono
                await asyncio.to_thread(sync_facebook_live_posts, db)
                await asyncio.to_thread(sync_instagram_publications, db)
            finally:
                db.close()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Error en auto-sincronización periódica de Meta: {e}")
        
        # Esperar 3 minutos entre sincronizaciones automáticas
        await asyncio.sleep(180)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Iniciar auto-sync en segundo plano
    sync_task = asyncio.create_task(periodic_meta_sync_loop())
    yield
    sync_task.cancel()

app = FastAPI(
    title="CIVIA API",
    description="Plataforma de Inteligencia Ciudadana y Política",
    version="1.0.0",
    lifespan=lifespan
)

# Montar archivos estáticos para carátulas permanentes que nunca expiren
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS para comunicación con Next.js (puerto 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "¡Bienvenido a la API de CIVIA!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
