"""Trabajos durables; el HTTP inicia y consulta, nunca espera a Meta o a la IA."""
import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from sqlalchemy.exc import IntegrityError
from app.core.database import SessionLocal
from app.models.publication import MetaSyncJob
from app.core.config import settings

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="civia-sync")
_start_lock = threading.Lock()
TERMINAL = {"success", "partial", "failed", "interrupted"}


def job_data(job):
    if job is None:
        return {"id": None, "scope": None, "status": "idle", "progress": {}, "result": None, "error": None}
    return {"id": job.id, "scope": job.scope, "status": job.status, "progress": json.loads(job.progress_json or "{}"),
            "result": json.loads(job.result_json) if job.result_json else None, "error": job.error,
            "created_at": job.created_at, "updated_at": job.updated_at}


def latest_job(db, scope="connected"):
    return db.query(MetaSyncJob).filter(MetaSyncJob.scope == scope).order_by(MetaSyncJob.created_at.desc()).first()


def recover_jobs(db):
    # El servidor local usa un único proceso; una ejecución anterior no sobrevive al reinicio.
    resumed=[]
    for job in db.query(MetaSyncJob).filter(MetaSyncJob.active_key.is_not(None)):
        if job.scope=='analysis':
            job.status,job.active_key,job.error='interrupted',None,'El análisis se interrumpió. Revisa el avance antes de solicitarlo de nuevo.'
        else:
            job.status,job.error='queued',None
            job.progress_json=json.dumps({'stage':'queued','detail':'Captura recuperada después del reinicio.'})
            resumed.append((job.id,job.scope))
    db.commit()
    for job_id,scope in resumed:_executor.submit(_run,job_id,scope)


def _progress(job_id, **value):
    with SessionLocal() as db:
        job = db.get(MetaSyncJob, job_id)
        job.progress_json = json.dumps({**json.loads(job.progress_json or "{}"), **value}, ensure_ascii=False)
        db.commit()


def _connected_sync(db, progress):
    from sync_live_service import sync_facebook_live_posts, sync_instagram_publications
    errors, facebook, instagram = [], {}, {}
    progress(network="Facebook", stage="posts", detail="Consultando hasta 12 publicaciones recientes de Facebook")
    try:
        sync_facebook_live_posts(db, stats=facebook, max_posts=12, classify_cases=False,
                                 analyze_comments=False, cache_covers=False, progress=progress)
    except Exception as exc:
        db.rollback()
        errors.append(f"Facebook no completó la captura ({type(exc).__name__}). Se conserva lo ya guardado.")
    progress(network="Instagram", stage="posts", detail="Consultando hasta 12 publicaciones recientes de Instagram")
    try:
        sync_instagram_publications(db, stats=instagram, max_posts=12, progress=progress, cache_covers=False)
    except Exception as exc:
        db.rollback()
        errors.append(f"Instagram no completó la captura ({type(exc).__name__}).")
    errors += facebook.get("errors", []) + instagram.get("errors", [])
    return {"status": "partial" if errors else "success", "posts_updated": facebook.get("posts_updated", 0) + instagram.get("posts_updated", 0),
            "new_comments_captured": facebook.get("new_comments_captured", 0) + instagram.get("new_comments_captured", 0),
            "instagram_status": instagram.get("status"), "instagram_detail": instagram.get("detail"), "errors": errors,
            "timestamp": datetime.now(timezone(timedelta(hours=-5))).strftime("%I:%M:%S %p"),
            "detail": "Captura terminada. El análisis de opinión se realiza por separado; puedes seguir consultando las publicaciones.",
            "analysis_deferred": True}


def _run(job_id, scope):
    with SessionLocal() as db:
        job = db.get(MetaSyncJob, job_id)
        job.status = "running"
        db.commit()
        progress = lambda **value: _progress(job_id, **value)
        try:
            if scope == "connected":
                result = _connected_sync(db, progress)
            elif scope == "analysis":
                from app.services.conversation import analyze_pending
                progress(stage="analysis", detail="Analizando comentarios por separado de la captura de publicaciones")
                result = {"status": "success", **analyze_pending(db, limit=20)}
            elif scope.startswith("source:"):
                from app.services.publications import sync_external
                result = sync_external(db, scope.split(":", 1)[1], progress)
            elif scope.startswith("post:"):
                from app.services.publications import refresh_publication
                source_id, post_id = scope.split(":", 2)[1:]
                result = refresh_publication(db, source_id, post_id, progress)
            else:
                raise ValueError("Unknown job scope")
            job = db.get(MetaSyncJob, job_id)
            job.status, job.result_json = result.get("status", "success"), json.dumps(result, ensure_ascii=False)
            job.progress_json = json.dumps({"stage": "done", "detail": result.get("detail", "Actualización terminada.")}, ensure_ascii=False)
        except Exception as exc:
            db.rollback()
            logger.warning("Actualización Meta no completada: %s", type(exc).__name__)
            job = db.get(MetaSyncJob, job_id)
            job.status, job.error = "failed", "No se pudo completar la actualización. Se conservan los datos capturados anteriormente."
        job.active_key = None
        db.commit()
        if scope == "connected" and job.status in {"success", "partial"} and settings.AUTO_ANALYZE_ENABLED:
            # La captura ya está terminada y visible antes de poner la IA en su propia cola.
            start_job(db, "analysis")


def start_job(db, scope="connected"):
    with _start_lock:
        active = db.query(MetaSyncJob).filter(MetaSyncJob.active_key == scope).first()
        if active:
            return {**job_data(active), "already_running": True}
        job = MetaSyncJob(id=str(uuid.uuid4()), scope=scope, active_key=scope, status="queued",
                          progress_json=json.dumps({"stage": "queued", "detail": "Actualización en segundo plano. Puedes seguir navegando."}))
        db.add(job)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return {**job_data(db.query(MetaSyncJob).filter(MetaSyncJob.active_key == scope).one()), "already_running": True}
        _executor.submit(_run, job.id, scope)
        return {**job_data(job), "already_running": False}
