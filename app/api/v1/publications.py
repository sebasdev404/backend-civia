from app.core.assets import asset_base
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
import csv
from io import StringIO
from sqlalchemy.orm import Session
from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.publication import PublicationSource
from app.services import publications
from app.services.meta_sync_jobs import start_job
from pydantic import BaseModel, Field, StrictBool
from app.models.publication import NewsSource
from app.services import news_monitor

router = APIRouter(prefix="/publications", tags=["Publicaciones"], dependencies=[Depends(get_current_user)])


class NewsSourceInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    url: str = Field(min_length=10, max_length=350)


class NewsSourceState(BaseModel):
    enabled: StrictBool


def require_news_manager(user=Depends(get_current_user)):
    if user.role not in ('ADMIN', 'SECRETARIO'):
        raise HTTPException(403, 'Administración o Secretaría puede registrar y pausar medios.')
    return user


@router.get('/news/sources')
def news_sources(db: Session = Depends(get_db)):
    return news_monitor.list_sources(db)


@router.post('/news/sources', status_code=201)
def register_news_source(payload: NewsSourceInput, db: Session = Depends(get_db), actor=Depends(require_news_manager)):
    identity = news_monitor.register_source(db, payload.name, payload.url, actor)
    return next(source for source in news_monitor.list_sources(db) if source['id'] == identity)


@router.patch('/news/sources/{source_id}')
def update_news_source(source_id: str, payload: NewsSourceState, db: Session = Depends(get_db), actor=Depends(require_news_manager)):
    from app.services.audit import record
    source = db.get(NewsSource, source_id)
    if source is None:
        raise HTTPException(404, 'Medio no encontrado.')
    source.enabled = payload.enabled
    record(db, actor, 'news_source_state_changed', source_id, enabled=source.enabled)
    db.commit()
    return {'id': source_id, 'enabled': source.enabled}


@router.get('/news')
def news_feed(source_id: str | None = None, search: str | None = Query(None, max_length=200),
              priority: str | None = Query(None, pattern='^(Alta|Media|Baja|Fuera de foco|Por revisar)$'),
              territory: str | None = Query(None, pattern='^(Neiva|Huila|Fuera de la región|Sin ubicación confirmada)$'),
              topic: str | None = Query(None, max_length=100), offset: int = Query(0, ge=0),
              limit: int = Query(12, ge=1, le=100), order: str = Query('relevance', pattern='^(relevance|recent)$'), db: Session = Depends(get_db)):
    return news_monitor.feed(db, source_id=source_id, search=search, priority=priority,
                             territory=territory, topic=topic, order=order, offset=offset, limit=limit)


@router.post('/news/update', status_code=202)
def update_news(db: Session = Depends(get_db), actor=Depends(get_current_user)):
    from app.services.audit import record
    job = start_job(db, 'news-monitor')
    if not job.get('already_running'):
        record(db, actor, 'news_monitor_requested', job['id'])
        db.commit()
    return job


def require_source(db, source_id):
    if db.get(PublicationSource, source_id) is None:
        raise HTTPException(404, "Fuente no encontrada")


@router.get("/sources")
def sources(db: Session = Depends(get_db)):
    return publications.sources(db)


@router.post("/sources/{source_id}/sync", status_code=202)
def sync_source(source_id: str, db: Session = Depends(get_db)):
    require_source(db, source_id)
    return start_job(db, "connected" if source_id == "johan" else f"source:{source_id}")


@router.get("")
def list_posts(request: Request, source_id: str = "johan", search: str | None = Query(None, max_length=200),
               network: str | None = Query(None, pattern="^(all|Facebook|Instagram)$"), limit: int = Query(12, ge=1, le=100),
               offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    require_source(db, source_id)
    return publications.list_publications(db, source_id=source_id, search=search, network=network, limit=limit, offset=offset,
                                         asset_base=asset_base(request))


@router.get("/{source_id}/{post_id}")
def detail(source_id: str, post_id: str, request: Request, offset: int = Query(0, ge=0), limit: int = Query(5, ge=1, le=50),
           reactions_offset: int = Query(0, ge=0), search: str | None = Query(None, max_length=200), signals_only: bool = False,
           db: Session = Depends(get_db)):
    require_source(db, source_id)
    result = publications.publication_detail(db, source_id, post_id, offset=offset, limit=limit,
                reactions_offset=reactions_offset, search=search, signals_only=signals_only, asset_base=asset_base(request))
    if result is None:
        raise HTTPException(404, "Publicación no encontrada para esta fuente")
    return result


@router.get("/{source_id}/{post_id}/comments.csv")
def export_comments(source_id: str, post_id: str, db: Session = Depends(get_db)):
    require_source(db, source_id)
    post = publications.find_post(db, source_id, post_id)
    if post is None:
        raise HTTPException(404, "Publicación no encontrada para esta fuente")
    rows = publications.parse_rows(post.raw_comments_json)
    evidence = publications.comment_signals(rows)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID comentario", "Nombre visible recibido", "Nombre restringido", "Comentario", "Me gusta del comentario", "Senales observables", "Identidad verificada"])
    def cell(value):
        value = str(value) if value is not None else ""
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
    for row in rows:
        writer.writerow([cell(row["id"]), cell(row.get("author")), "Sí" if row.get("author_is_protected") else "No / sin comprobar",
                         cell(row["content"]), row.get("likes_count", ""), cell(" | ".join(evidence[row["id"]]["signals"])), "No"])
    return Response(content=("\ufeff" + output.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="comentarios-capturados.csv"'})


@router.post("/{source_id}/{post_id}/refresh", status_code=202)
def refresh(source_id: str, post_id: str, db: Session = Depends(get_db)):
    require_source(db, source_id)
    if publications.find_post(db, source_id, post_id) is None:
        raise HTTPException(404, "Publicación no encontrada para esta fuente")
    return start_job(db, f"post:{source_id}:{post_id}")
