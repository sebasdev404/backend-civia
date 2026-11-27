import os
import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.v1 import api_v1_router
from app.core.database import engine, Base, SessionLocal
from app.core.config import settings

logger = logging.getLogger("civia.autosync")

# Crear tablas si no existen
if settings.ENVIRONMENT != 'production':
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
            from app.services.meta_sync_jobs import start_job
            db = SessionLocal()
            try:
                # Comparte el mismo trabajo que el botón manual; no duplica la captura.
                await asyncio.to_thread(start_job, db, "connected")
            finally:
                db.close()
        except asyncio.CancelledError:
            break
        except Exception:
            logger.warning('No se pudo completar la captura periódica de Meta.')
        
        # Esperar 3 minutos entre sincronizaciones automáticas
        await asyncio.sleep(180)


async def periodic_conversation_analysis_loop():
    from app.services.meta_sync_jobs import queue_pending_analysis

    def queue():
        with SessionLocal() as db:
            queue_pending_analysis(db)

    while True:
        try:
            await asyncio.to_thread(queue)
        except Exception:
            logger.warning('No se pudo programar el análisis automático de opinión.')
        await asyncio.sleep(60)


async def inbox_loop():
    from app.services.webhooks import process_pending
    while True:
        try:
            def run():
                with SessionLocal() as db: process_pending(db)
                from app.services.mail_queue import process_outbox
                process_outbox(engine)
                from app.models.auth_session import AuthSession
                from app.models.password_recovery import PasswordRecovery
                from datetime import datetime,timezone,timedelta
                with SessionLocal() as db:
                    cutoff=datetime.now(timezone.utc)-timedelta(days=max(1,settings.SESSION_RETENTION_DAYS))
                    db.query(AuthSession).filter(AuthSession.expires_at<cutoff).delete(synchronize_session=False)
                    db.query(PasswordRecovery).filter(PasswordRecovery.expires_at<cutoff).delete(synchronize_session=False)
                    db.commit()
            await asyncio.to_thread(run)
        except asyncio.CancelledError:raise
        except Exception:logger.error('No se pudo procesar la bandeja de eventos.')
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.publications import ensure_sources
    from app.services.meta_sync_jobs import recover_jobs
    from sqlalchemy import text
    from app.core.schema import verify_schema
    coordinator=engine.connect()
    locked=False
    try:
        verify_schema(coordinator)
        if coordinator.dialect.name=='postgresql':
            if not coordinator.execute(text('SELECT pg_try_advisory_lock(1128879681)')).scalar():
                raise RuntimeError('Ya hay un coordinador de Ordenemos a Neiva activo. Este despliegue admite un proceso API.')
            locked=True
            coordinator.commit()
        with SessionLocal() as db:
            recover_jobs(db)
            ensure_sources(db)
        tasks=[asyncio.create_task(inbox_loop())]
        if settings.AUTO_SYNC_ENABLED:tasks.append(asyncio.create_task(periodic_meta_sync_loop()))
        if settings.AUTO_ANALYZE_ENABLED:tasks.append(asyncio.create_task(periodic_conversation_analysis_loop()))
        yield
    finally:
        for task in locals().get('tasks',[]):task.cancel()
        if locals().get('tasks'):await asyncio.gather(*tasks,return_exceptions=True)
        if locked:
            coordinator.execute(text('SELECT pg_advisory_unlock(1128879681)'))
            coordinator.commit()
        coordinator.close()
    # Iniciar auto-sync en segundo plano

app = FastAPI(
    title="Ordenemos a Neiva API",
    description="Plataforma de Inteligencia Ciudadana y Política",
    version="1.0.0",
    lifespan=lifespan
    ,docs_url=None if settings.ENVIRONMENT=='production' else '/docs'
    ,redoc_url=None if settings.ENVIRONMENT=='production' else '/redoc'
    ,openapi_url=None if settings.ENVIRONMENT=='production' else '/openapi.json'
)

# Montar archivos estáticos para carátulas permanentes que nunca expiren
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS para comunicación con Next.js (puerto 3000)
# IMPORTANTE: allow_credentials=True es incompatible con allow_origins=["*"]
# Se deben listar los orígenes explícitamente cuando se usan credenciales
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")


@app.middleware('http')
async def operational_headers(request,call_next):
    identity=str(uuid.uuid4());started=time.perf_counter()
    response=await call_next(request)
    response.headers['X-Request-ID']=identity
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    logger.info('request id=%s method=%s path=%s status=%s duration_ms=%.1f',identity,request.method,request.url.path,response.status_code,(time.perf_counter()-started)*1000)
    return response

@app.get("/")
def read_root():
    return {"message": "¡Bienvenido a la API de Ordenemos a Neiva!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get('/health/ready')
def readiness():
    from sqlalchemy import text
    from fastapi.responses import JSONResponse
    try:
        with SessionLocal() as db:db.execute(text('SELECT 1'))
        return {'status':'ready'}
    except Exception:return JSONResponse({'status':'not_ready'},status_code=503)
