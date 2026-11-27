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
TERMINAL = {"success", "partial", "failed", "interrupted", "cancelled"}
OPINION_SCOPE = 'opinion-analysis'
ANALYSIS_RETRY_DELAY = timedelta(minutes=5)


def job_data(job):
    if job is None:
        return {"id": None, "scope": None, "status": "idle", "progress": {}, "result": None, "error": None}
    return {"id": job.id, "scope": job.scope, "status": job.status, "progress": json.loads(job.progress_json or "{}"),
            "result": json.loads(job.result_json) if job.result_json else None, "error": job.error,
            "created_at": job.created_at, "updated_at": job.updated_at}


def latest_job(db, scope="connected"):
    return db.query(MetaSyncJob).filter(MetaSyncJob.scope == scope).order_by(MetaSyncJob.created_at.desc()).first()


def queue_pending_analysis(db):
    from app.services.conversation import ai_classifier, pending_by_post

    if not settings.AUTO_ANALYZE_ENABLED or ai_classifier.client is None:
        return
    if db.query(MetaSyncJob).filter(MetaSyncJob.active_key == OPINION_SCOPE).first():
        return
    last = latest_job(db, "analysis")
    if last and last.active_key:
        return
    if last and last.status in {"failed", "partial", "interrupted"} and last.updated_at:
        updated_at = last.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - updated_at < ANALYSIS_RETRY_DELAY:
            return
    if next(pending_by_post(db), None) is not None:
        start_job(db, "analysis")


def recover_jobs(db):
    # El servidor local usa un único proceso; una ejecución anterior no sobrevive al reinicio.
    resumed=[]
    for job in db.query(MetaSyncJob).filter(MetaSyncJob.active_key.is_not(None)):
        if job.scope in ('analysis', OPINION_SCOPE):
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
        if job.status != 'cancelling':
            job.status = "running"
        db.commit()
        progress = lambda **value: _progress(job_id, **value)
        try:
            if scope == "connected":
                result = _connected_sync(db, progress)
            elif scope == 'news-monitor':
                from app.services.news_monitor import run_monitor
                result = run_monitor(db, progress)
            elif scope == "analysis":
                from app.services.conversation import analyze_pending
                progress(stage="analysis", detail="Analizando comentarios por separado de la captura de publicaciones")
                result = analyze_pending(db, limit=20)
            elif scope == OPINION_SCOPE:
                from app.services.conversation import analyze_all
                saved = json.loads(job.progress_json or '{}')
                options = saved.get('filters', {})
                def cancelled():
                    with SessionLocal() as control_db:
                        control = control_db.get(MetaSyncJob, job_id)
                        return control.status == 'cancelling'
                def checkpoint(**value):
                    current = db.get(MetaSyncJob, job_id)
                    # The result rows and this cursor commit in the same transaction.
                    current.progress_json = json.dumps({**json.loads(current.progress_json or '{}'), **value}, ensure_ascii=False)
                result = analyze_all(db, month=options.get('month'), post_id=options.get('post_id'),
                                     include_review=options.get('include_review', True), review_before=job.created_at,
                                     previous=saved, progress=progress, should_cancel=cancelled, checkpoint=checkpoint, concurrency=3)
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
            db.refresh(job)
            job.status, job.result_json = result.get("status", "success"), json.dumps(result, ensure_ascii=False)
            job.progress_json = json.dumps({**json.loads(job.progress_json or '{}'), "stage": "done", "detail": result.get("detail", "Actualización terminada.")}, ensure_ascii=False)
        except Exception as exc:
            db.rollback()
            logger.warning("Actualización Meta no completada: %s", type(exc).__name__)
            job = db.get(MetaSyncJob, job_id)
            job.status, job.error = "failed", "No se pudo completar la actualización. Se conservan los datos capturados anteriormente."
        job.active_key = None
        db.commit()


def start_opinion_analysis(db, *, month=None, post_id=None, include_review=True, actor=None, resume_id=None):
    from fastapi import HTTPException
    from app.services.audit import record
    with _start_lock:
        active = db.query(MetaSyncJob).filter(MetaSyncJob.active_key.in_((OPINION_SCOPE, 'analysis'))).first()
        if active:
            if active.scope == OPINION_SCOPE:
                return {**job_data(active), 'already_running': True}
            raise HTTPException(409, 'Hay un lote automático de análisis en curso. Espera a que termine.')
        if resume_id:
            job = db.query(MetaSyncJob).filter_by(id=resume_id, scope=OPINION_SCOPE).populate_existing().with_for_update().first()
            if job is None:
                raise HTTPException(404, 'Trabajo de análisis no encontrado.')
            if job.status not in ('partial', 'failed', 'interrupted', 'cancelled'):
                raise HTTPException(409, 'Este trabajo no necesita reanudarse.')
            saved = json.loads(job.progress_json or '{}')
            job.progress_json = json.dumps({**saved, 'stage': 'queued', 'cancel_requested': False,
                                           'detail': 'Reanudando desde el último lote guardado.'}, ensure_ascii=False)
            job.status, job.error, job.result_json, job.active_key = 'queued', None, None, OPINION_SCOPE
        else:
            job = MetaSyncJob(id=str(uuid.uuid4()), scope=OPINION_SCOPE, active_key=OPINION_SCOPE, status='queued',
                              created_at=datetime.now(timezone.utc), progress_json=json.dumps({
                                  'stage': 'queued', 'completed': 0, 'classified': 0, 'uncertain': 0,
                                  'model': settings.OPINION_ANALYSIS_MODEL,
                                  'filters': {'month': month, 'post_id': post_id, 'include_review': include_review},
                                  'detail': 'Análisis completo en segundo plano. Puedes seguir navegando.'}, ensure_ascii=False))
            db.add(job)
        record(db, actor, 'opinion_analysis_resumed' if resume_id else 'opinion_analysis_started', job.id,
               period=month or 'all', selected_publication=post_id, review_uncertain=include_review)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            active = db.query(MetaSyncJob).filter_by(active_key=OPINION_SCOPE).first()
            if active:
                return {**job_data(active), 'already_running': True}
            raise
        result = {**job_data(job), 'already_running': False}
        _executor.submit(_run, job.id, OPINION_SCOPE)
        return result


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
