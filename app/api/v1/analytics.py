from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any

from app.core.database import get_db
from app.models.case import Case
from app.models.incident import Incident
from app.schemas.analytics import DashboardSummaryResponse

router = APIRouter(prefix="/analytics", tags=["Métricas y Análisis"])

@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(db: Session = Depends(get_db)):
    total_cases = db.query(Case).count()
    critical_cases = db.query(Case).filter(Case.priority == "Alta").count()
    in_progress = db.query(Case).filter(Case.status == "En Gestión").count()
    resolved = db.query(Case).filter(Case.status == "Resuelto").count()
    active_territorial_alerts = db.query(Incident).filter(Incident.priority == "Alta").count()

    # Categorías
    cat_results = db.query(Case.category, func.count(Case.id)).group_by(Case.category).all()
    categories_distribution = {cat: count for cat, count in cat_results}

    # Sentimientos
    sent_results = db.query(Case.sentiment, func.count(Case.id)).group_by(Case.sentiment).all()
    sentiment_distribution = {sent: count for sent, count in sent_results}

    # Canales
    chan_results = db.query(Case.source, func.count(Case.id)).group_by(Case.source).all()
    channel_distribution = {chan: count for chan, count in chan_results}

    # Categoría primaria con mayor incidencia
    primary_category = "Servicios Públicos"
    if cat_results:
        primary_category = max(cat_results, key=lambda x: x[1])[0]

    return DashboardSummaryResponse(
        total_cases=total_cases,
        critical_cases=critical_cases,
        in_progress_cases=in_progress,
        resolved_cases=resolved,
        active_territorial_alerts=active_territorial_alerts,
        primary_category=primary_category,
        categories_distribution=categories_distribution,
        sentiment_distribution=sentiment_distribution,
        channel_distribution=channel_distribution,
    )

