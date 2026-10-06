from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from typing import List, Optional

from app.core.database import get_db
from app.models.case import Case
from app.schemas.case import CaseCreate, CaseUpdate, CaseResponse

router = APIRouter(prefix="/cases", tags=["Casos Ciudadanos"])

@router.get("", response_model=List[CaseResponse])
def get_cases(
    search: Optional[str] = Query(None, description="Búsqueda por texto en título, contenido o barrio"),
    priority: Optional[str] = Query(None, description="Filtrar por prioridad: Alta, Media, Baja"),
    category: Optional[str] = Query(None, description="Filtrar por categoría de problemática"),
    source: Optional[str] = Query(None, description="Filtrar por red social / canal"),
    status: Optional[str] = Query(None, description="Filtrar por estado: Pendiente, En Gestión, Resuelto"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(Case)

    if priority and priority != "all":
        query = query.filter(Case.priority == priority)

    if category and category != "all":
        query = query.filter(Case.category == category)

    if source and source != "all":
        query = query.filter(Case.source == source)

    if status and status != "all":
        query = query.filter(Case.status == status)

    if search:
        search_fmt = f"%{search.lower()}%"
        query = query.filter(
            or_(
                Case.title.ilike(search_fmt),
                Case.content.ilike(search_fmt),
                Case.location.ilike(search_fmt),
                Case.author.ilike(search_fmt),
                Case.id.ilike(search_fmt),
            )
        )

    return query.order_by(desc(Case.created_at)).offset(skip).limit(limit).all()

@router.get("/{case_id}", response_model=CaseResponse)
def get_case_by_id(case_id: str, db: Session = Depends(get_db)):
    case_item = db.query(Case).filter(Case.id == case_id).first()
    if not case_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Caso con id '{case_id}' no encontrado",
        )
    return case_item

@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(case_in: CaseCreate, db: Session = Depends(get_db)):
    # Generar ID si no viene especificado
    if not case_in.id:
        count = db.query(Case).count()
        generated_id = f"CASO-{str(count + 1).zfill(3)}"
    else:
        generated_id = case_in.id

    existing = db.query(Case).filter(Case.id == generated_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un caso con id '{generated_id}'",
        )

    case_data = case_in.model_dump()
    case_data["id"] = generated_id
    new_case = Case(**case_data)
    db.add(new_case)
    db.commit()
    db.refresh(new_case)
    return new_case

@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(case_id: str, case_update: CaseUpdate, db: Session = Depends(get_db)):
    case_item = db.query(Case).filter(Case.id == case_id).first()
    if not case_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Caso con id '{case_id}' no encontrado",
        )

    update_data = case_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(case_item, field, value)

    db.commit()
    db.refresh(case_item)
    return case_item

@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(case_id: str, db: Session = Depends(get_db)):
    case_item = db.query(Case).filter(Case.id == case_id).first()
    if not case_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Caso con id '{case_id}' no encontrado",
        )
    db.delete(case_item)
    db.commit()
    return None

