from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.conversation import PostContext
from app.services.conversation import analyze_pending, context_for, facebook_posts, overview
from app.services.meta_sync_jobs import latest_job
from app.services.meta_sync_jobs import OPINION_SCOPE, job_data, start_opinion_analysis
from app.models.publication import MetaSyncJob
from app.models.meta_post import MetaPost
from sqlalchemy import or_, desc

router = APIRouter(prefix="/conversation", tags=["Conversación Facebook"], dependencies=[Depends(get_current_user)])


class ContextInput(BaseModel):
    summary: str = Field(default="", max_length=6000)
    transcript: str = Field(default="", max_length=24000)

    @model_validator(mode="after")
    def non_empty(self):
        self.summary, self.transcript = self.summary.strip(), self.transcript.strip()
        if not self.summary and not self.transcript:
            raise ValueError("Escribe un resumen o una transcripción de la publicación")
        return self


class AnalysisInput(BaseModel):
    month: str | None = Field(default=None, pattern=r'^(all|[0-9]{4}-(0[1-9]|1[0-2]))$')
    post_id: str | None = Field(default=None, min_length=1, max_length=150)
    include_review: bool = True


def get_post(db, post_id):
    posts = facebook_posts(db, post_id=post_id)
    if not posts:
        raise HTTPException(404, "Publicación de Facebook no encontrada")
    return posts[0]


@router.get('/posts')
def post_options(month: str | None = None, db: Session = Depends(get_db)):
    # The selector must not rebuild every captured comment and analysis.
    query = db.query(MetaPost.id, MetaPost.title).filter(or_(MetaPost.source.ilike('%Facebook%'),
                    MetaPost.source.is_(None) & ~MetaPost.id.like('IG_%')))
    if month and month != 'all':
        query = query.filter(MetaPost.month_key == month)
    return [{'id': row.id, 'title': row.title} for row in query.order_by(desc(MetaPost.created_time), desc(MetaPost.id))]


@router.get("")
def get_overview(month: str | None = None, post_id: str | None = None,
                 stance: str | None = Query(None, pattern="^(support|criticism|mixed|neutral|review)$"),
                 topic: str | None = None, narrative: str | None = None,
                 search: str | None = Query(None, max_length=200), offset: int = Query(0, ge=0),
                 limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    data = overview(db, month=month, post_id=post_id, stance=stance, topic=topic,
                    narrative=narrative, search=search, offset=offset, limit=limit)
    job = latest_job(db, "analysis") if settings.AUTO_ANALYZE_ENABLED else None
    return {**data, "automatic_analysis": settings.AUTO_ANALYZE_ENABLED,
            "analysis_status": job.status if job else "idle",
            "analysis_model": settings.OPINION_ANALYSIS_MODEL,
            "analysis_job": job_data(latest_job(db, OPINION_SCOPE))}


@router.post('/analysis-jobs', status_code=202)
def start_analysis(payload: AnalysisInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if post_id := payload.post_id:
        get_post(db, post_id)
    return start_opinion_analysis(db, month=payload.month, post_id=payload.post_id,
                                  include_review=payload.include_review, actor=user)


@router.get('/analysis-jobs/latest')
def read_analysis_job(db: Session = Depends(get_db)):
    return job_data(latest_job(db, OPINION_SCOPE))


@router.post('/analysis-jobs/{job_id}/resume', status_code=202)
def resume_analysis(job_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return start_opinion_analysis(db, actor=user, resume_id=job_id)


@router.post('/analysis-jobs/{job_id}/cancel', status_code=202)
def cancel_analysis(job_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.services.audit import record
    job = db.query(MetaSyncJob).filter_by(id=job_id, scope=OPINION_SCOPE).populate_existing().with_for_update().first()
    if job is None:
        raise HTTPException(404, 'Trabajo de análisis no encontrado.')
    if job.active_key:
        job.status = 'cancelling'
        record(db, user, 'opinion_analysis_stop_requested', job.id)
        db.commit()
    return job_data(job)


@router.get("/posts/{post_id}/context")
def read_context(post_id: str, db: Session = Depends(get_db)):
    return context_for(get_post(db, post_id), db.get(PostContext, post_id))


@router.put("/posts/{post_id}/context")
def save_context(post_id: str, payload: ContextInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    post = get_post(db, post_id)
    saved = db.get(PostContext, post_id)
    if saved is None:
        saved = PostContext(post_id=post_id)
        db.add(saved)
    saved.summary, saved.transcript, saved.updated_by = payload.summary, payload.transcript, str(user.id)
    db.commit()
    return context_for(post, saved)


@router.post("/analyze")
def analyze(post_id: str | None = None, month: str | None = None,
            limit: int = Query(20, ge=1, le=50), db: Session = Depends(get_db)):
    if post_id:
        get_post(db, post_id)
    return analyze_pending(db, post_id=post_id, month=month, limit=limit)
