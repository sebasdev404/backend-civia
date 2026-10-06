from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, func
from typing import List, Optional

from app.core.database import get_db
from app.models.incident import Incident
from app.schemas.incident import IncidentCreate, IncidentResponse

router = APIRouter(prefix="/map", tags=["Mapa Termómetro Ciudadano"])

@router.get("/incidents", response_model=List[IncidentResponse])
def get_map_incidents(
    priority: Optional[str] = Query(None, description="Prioridad: Alta, Media, Baja"),
    category: Optional[str] = Query(None, description="Categoría"),
    zone: Optional[str] = Query(None, description="Localidad / Comuna"),
    source: Optional[str] = Query(None, description="Red social / Canal"),
    search: Optional[str] = Query(None, description="Búsqueda por texto"),
    db: Session = Depends(get_db),
):
    query = db.query(Incident)

    if priority and priority != "all":
        query = query.filter(Incident.priority == priority)

    if category and category != "all":
        query = query.filter(Incident.category == category)

    if zone and zone != "all":
        query = query.filter(Incident.zone == zone)

    if source and source != "all":
        query = query.filter(Incident.source == source)

    if search:
        search_fmt = f"%{search.lower()}%"
        query = query.filter(
            or_(
                Incident.title.ilike(search_fmt),
                Incident.description.ilike(search_fmt),
                Incident.neighborhood.ilike(search_fmt),
                Incident.id.ilike(search_fmt),
            )
        )

    return query.order_by(desc(Incident.created_at)).all()

@router.post("/incidents", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def create_map_incident(incident_in: IncidentCreate, db: Session = Depends(get_db)):
    if not incident_in.id:
        count = db.query(Incident).count()
        generated_id = f"CASO-{str(count + 1).zfill(3)}"
    else:
        generated_id = incident_in.id

    inc_data = incident_in.model_dump()
    inc_data["id"] = generated_id
    new_inc = Incident(**inc_data)
    db.add(new_inc)
    db.commit()
    db.refresh(new_inc)
    return new_inc

@router.get("/zones")
def get_zones_summary(db: Session = Depends(get_db)):
    results = db.query(
        Incident.zone,
        func.count(Incident.id).label("total_incidents"),
        func.sum(Incident.reports_count).label("total_reports")
    ).group_by(Incident.zone).all()

    return [
        {
            "zone": r[0],
            "total_incidents": r[1],
            "total_reports": r[2] or 0
        }
        for r in results
    ]

