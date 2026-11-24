from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.conversation import PostContext
from app.services.conversation import analyze_pending, context_for, facebook_posts, overview

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


def get_post(db, post_id):
    posts = facebook_posts(db, post_id=post_id)
    if not posts:
        raise HTTPException(404, "Publicación de Facebook no encontrada")
    return posts[0]


@router.get("")
def get_overview(month: str | None = None, post_id: str | None = None,
                 stance: str | None = Query(None, pattern="^(support|criticism|mixed|neutral|review)$"),
                 topic: str | None = None, narrative: str | None = None,
                 search: str | None = Query(None, max_length=200), offset: int = Query(0, ge=0),
                 limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    return overview(db, month=month, post_id=post_id, stance=stance, topic=topic,
                    narrative=narrative, search=search, offset=offset, limit=limit)


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
