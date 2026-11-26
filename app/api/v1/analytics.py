from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.analytics import DashboardSummaryResponse
from app.services import analytics as service

router = APIRouter(prefix='/analytics', tags=['Métricas y Análisis'])


@router.get('/overview')
def get_overview(db: Session = Depends(get_db)):
    return service.overview(db)


@router.get('/summary', response_model=DashboardSummaryResponse)
def get_dashboard_summary(db: Session = Depends(get_db)):
    cases = service.case_counts(db)
    categories = cases['categories']
    return DashboardSummaryResponse(total_cases=cases['total'], critical_cases=cases['critical_open'],
        in_progress_cases=cases['in_progress'], resolved_cases=cases['resolved'],
        active_territorial_alerts=None, primary_category=max(categories, key=categories.get) if categories else 'Sin clasificar',
        categories_distribution=categories, sentiment_distribution=cases['emotions'], channel_distribution=cases['channels'])


@router.get('/kpis')
def get_analytics_kpis(db: Session = Depends(get_db)):
    data = service.overview(db)
    return {'generated_at': data['generated_at'], 'total_mentions': data['capture']['captured_comments'],
        'tension_index': None, 'tension_level': 'No medido', 'net_sentiment': None, 'avg_reaction_time': None,
        'channels': data['capture']['channels'], 'top_terms': data['capture']['top_terms'],
        'scope': data['scope']}


@router.get('/top-barrios')
def get_top_problematic_barrios(db: Session = Depends(get_db)):
    return service.territorial_counts(db)['locations']
