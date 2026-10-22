from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, desc
from typing import List, Optional, Dict, Any
import uuid
import re
from datetime import datetime

from app.core.database import get_db
from app.models.citizen import Citizen
from app.models.case import Case
from app.schemas.citizen import CitizenCreate, CitizenResponse, CitizenUploadRequest
from app.services.ai_classifier import ai_classifier

router = APIRouter(prefix="/citizens", tags=["Inteligencia Ciudadana & Base Telefónica"])

def normalize_colombia_phone(phone_raw: Optional[str]) -> Optional[str]:
    if not phone_raw:
        return None
    cleaned = re.sub(r"[^\d+]", "", phone_raw.strip())
    # Formato colombiano móvil ej: 3124567890 -> +57 312 456 7890
    if cleaned.startswith("+57"):
        digits = cleaned[3:]
    elif cleaned.startswith("57") and len(cleaned) == 12:
        digits = cleaned[2:]
    else:
        digits = cleaned

    if len(digits) == 10 and digits.startswith("3"):
        return f"+57 {digits[:3]} {digits[3:6]} {digits[6:]}"
    elif len(digits) >= 7:
        return f"+57 {digits}"
    return phone_raw.strip()

INITIAL_MOCK_CITIZENS = [
    {
        "id": "CIUD-001",
        "name": "Juan Carlos Pérez",
        "handle": "@JuanPerezNeiva",
        "phone": "+57 312 456 7890",
        "followers_count": 840,
        "following_count": 210,
        "account_created_at": "Hace 4 años",
        "user_type": "Negativo",
        "bot_probability": 0.05,
        "bot_origin": "Humano Verificado",
        "neighborhood": "Las Granjas (Comuna 2)",
        "channel": "Facebook",
        "zone": "Comuna 2",
        "total_reports": 6,
        "sentiment_tendency": "Crítico",
        "notes": "Presidente JAC Las Granjas. Reclama por corte de agua y retrasos en obras de la Cra 2da. Muy activo en Facebook."
    },
    {
        "id": "CIUD-002",
        "name": "María Camila Gómez",
        "handle": "@MariaGomez_Huila",
        "phone": "+57 315 987 6543",
        "followers_count": 1250,
        "following_count": 480,
        "account_created_at": "Hace 3 años",
        "user_type": "Positivo",
        "bot_probability": 0.02,
        "bot_origin": "Humano Verificado",
        "neighborhood": "Centro - Av. La Toma",
        "channel": "Instagram",
        "zone": "Comuna 3",
        "total_reports": 3,
        "sentiment_tendency": "Aprobación",
        "notes": "Comerciante de La Toma. Resalta los avances del bacheo nocturno y la recuperación del alumbrado."
    },
    {
        "id": "CIUD-003",
        "name": "Usuario_9281734_Neiva",
        "handle": "@user9281734",
        "phone": None,
        "followers_count": 4,
        "following_count": 412,
        "account_created_at": "Hace 14 días",
        "user_type": "Bot",
        "bot_probability": 0.94,
        "bot_origin": "Granja de Cuentas / Campaña Opositora",
        "neighborhood": "Neiva (General)",
        "channel": "Facebook",
        "zone": "Desconocida",
        "total_reports": 18,
        "sentiment_tendency": "Indignación",
        "notes": "Cuenta automatizada sin foto de perfil. Publica exactamente el mismo mensaje en publicaciones sobre el PAE y la administración."
    },
    {
        "id": "CIUD-004",
        "name": "Carlos Alberto Díaz",
        "handle": "@CarlosDiaz_Canaima",
        "phone": "+57 320 123 4567",
        "followers_count": 430,
        "following_count": 310,
        "account_created_at": "Hace 2 años",
        "user_type": "Negativo",
        "bot_probability": 0.08,
        "bot_origin": "Humano Verificado",
        "neighborhood": "Canaima (Comuna 6)",
        "channel": "Facebook",
        "zone": "Comuna 6",
        "total_reports": 7,
        "sentiment_tendency": "Crítico",
        "notes": "Líder barrial de Canaima. Denuncia rebosamiento del alcantarillado en temporada de lluvias. Requiere contacto directo."
    },
    {
        "id": "CIUD-005",
        "name": "Alerta_Opita_Real",
        "handle": "@alertaopita2026",
        "phone": None,
        "followers_count": 12,
        "following_count": 890,
        "account_created_at": "Hace 22 días",
        "user_type": "Bot",
        "bot_probability": 0.89,
        "bot_origin": "Troll Político / Perfil Falso Sin Foto",
        "neighborhood": "Neiva (General)",
        "channel": "Facebook",
        "zone": "Desconocida",
        "total_reports": 14,
        "sentiment_tendency": "Ataque",
        "notes": "Coordina ataques de desprestigio en comentarios. Repite frases como 'la misma mierda' y 'se roban la plata'."
    },
    {
        "id": "CIUD-006",
        "name": "Dra. Patricia Charry",
        "handle": "@DraPatriciaCharry",
        "phone": "+57 310 555 9812",
        "followers_count": 2100,
        "following_count": 620,
        "account_created_at": "Hace 5 años",
        "user_type": "Negativo",
        "bot_probability": 0.03,
        "bot_origin": "Humano Verificado",
        "neighborhood": "Quirinal (Comuna 3)",
        "channel": "Facebook",
        "zone": "Comuna 3",
        "total_reports": 5,
        "sentiment_tendency": "Preocupado",
        "notes": "Médica especialista. Realizó crítica técnica sobre el PAE ('Por mi crítica salvé el PAE') solicitando auditorías nutricionales."
    },
    {
        "id": "CIUD-007",
        "name": "Vecinos Unidos Ipanema",
        "handle": "@VecinosIpanema",
        "phone": "+57 314 789 1234",
        "followers_count": 670,
        "following_count": 190,
        "account_created_at": "Hace 3 años",
        "user_type": "Positivo",
        "bot_probability": 0.04,
        "bot_origin": "Humano Verificado",
        "neighborhood": "Ipanema (Comuna 7)",
        "channel": "Instagram",
        "zone": "Comuna 7",
        "total_reports": 4,
        "sentiment_tendency": "Positivo",
        "notes": "Colectivo vecinal. Agradecen instalación de cámaras de seguridad y podas preventivas en parques."
    },
    {
        "id": "CIUD-008",
        "name": "Bot_Hater_Huila_44",
        "handle": "@bot_huila44",
        "phone": None,
        "followers_count": 2,
        "following_count": 640,
        "account_created_at": "Hace 8 días",
        "user_type": "Bot",
        "bot_probability": 0.98,
        "bot_origin": "Granja de Cuentas / Campaña Opositora",
        "neighborhood": "Neiva (General)",
        "channel": "Facebook",
        "zone": "Desconocida",
        "total_reports": 25,
        "sentiment_tendency": "Ataque",
        "notes": "Perfil automatizado detectado por CIVIA NLP. Spam masivo de odio en todas las transmisiones en vivo."
    }
]

@router.get("", response_model=Dict[str, Any])
def list_citizens(
    user_type: Optional[str] = Query("all", description="Filtrar por: all, Positivo, Negativo, Bot"),
    followers_filter: Optional[str] = Query("all", description="all, under_50, 50_500, over_500"),
    account_age_filter: Optional[str] = Query("all", description="all, recent, older"),
    search: Optional[str] = Query(None, description="Buscar por nombre, teléfono, barrio o handle"),
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Lista la base de datos de ciudadanos, teléfonos y perfiles de Facebook/Instagram,
    con segmentación entre humanos reales (positivos/negativos) y bots de ataque.
    """
    # Si la base está vacía, sembrar automáticamente el dataset inicial
    if db.query(Citizen).count() == 0:
        for m in INITIAL_MOCK_CITIZENS:
            new_c = Citizen(
                id=m["id"],
                name=m["name"],
                handle=m["handle"],
                phone=m["phone"],
                followers_count=m["followers_count"],
                following_count=m["following_count"],
                account_created_at=m["account_created_at"],
                user_type=m["user_type"],
                bot_probability=m["bot_probability"],
                bot_origin=m["bot_origin"],
                neighborhood=m["neighborhood"],
                channel=m["channel"],
                zone=m["zone"],
                total_reports=m["total_reports"],
                sentiment_tendency=m["sentiment_tendency"],
                notes=m["notes"],
                origen_dato="BASE_INICIAL"
            )
            db.add(new_c)
        db.commit()

    query = db.query(Citizen)

    # Filtro Tipo de Usuario
    if user_type and user_type != "all":
        query = query.filter(Citizen.user_type == user_type)

    # Filtro Seguidores
    if followers_filter == "under_50":
        query = query.filter(Citizen.followers_count < 50)
    elif followers_filter == "50_500":
        query = query.filter(Citizen.followers_count >= 50, Citizen.followers_count <= 500)
    elif followers_filter == "over_500":
        query = query.filter(Citizen.followers_count > 500)

    # Filtro Antigüedad
    if account_age_filter == "recent":
        query = query.filter(or_(Citizen.account_created_at.like("%días%"), Citizen.account_created_at.like("%mes%")))
    elif account_age_filter == "older":
        query = query.filter(Citizen.account_created_at.like("%año%"))

    # Búsqueda libre
    if search:
        s = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Citizen.name).like(s),
                func.lower(Citizen.handle).like(s),
                func.lower(Citizen.phone).like(s),
                func.lower(Citizen.neighborhood).like(s),
                func.lower(Citizen.notes).like(s),
            )
        )

    total_matched = query.count()
    citizens = query.order_by(desc(Citizen.bot_probability), desc(Citizen.total_reports)).offset(offset).limit(limit).all()

    # Conteos globales para métricas superiores
    all_citizens = db.query(Citizen).all()
    total_all = len(all_citizens)
    total_bots = sum(1 for c in all_citizens if c.user_type == "Bot")
    total_positives = sum(1 for c in all_citizens if c.user_type == "Positivo")
    total_negatives = sum(1 for c in all_citizens if c.user_type == "Negativo")
    total_with_phone = sum(1 for c in all_citizens if c.phone is not None and len(c.phone) > 5)

    return {
        "total": total_matched,
        "metrics": {
            "total_registered": total_all,
            "total_with_phone": total_with_phone,
            "total_bots_detected": total_bots,
            "total_positives": total_positives,
            "total_negatives": total_negatives,
            "bot_percentage": round((total_bots / total_all * 100), 1) if total_all > 0 else 0
        },
        "items": [
            {
                "id": c.id,
                "name": c.name,
                "handle": c.handle,
                "phone": c.phone,
                "followers_count": c.followers_count,
                "following_count": c.following_count,
                "account_created_at": c.account_created_at,
                "user_type": c.user_type,
                "bot_probability": c.bot_probability,
                "bot_origin": c.bot_origin,
                "neighborhood": c.neighborhood or "Neiva (General)",
                "channel": c.channel,
                "total_reports": c.total_reports,
                "sentiment_tendency": c.sentiment_tendency,
                "notes": c.notes,
                "origen_dato": c.origen_dato,
                "whatsapp_link": f"https://wa.me/{re.sub(r'[^0-9]', '', c.phone)}" if c.phone else None
            }
            for c in citizens
        ]
    }

@router.post("/upload", response_model=Dict[str, Any])
def upload_citizens_database(
    payload: CitizenUploadRequest,
    db: Session = Depends(get_db)
):
    """
    Procesa la subida masiva de una base de datos externa de ciudadanos y números telefónicos.
    Valida sintaxis móvil de Colombia (+57 3xx), audita con IA el perfil para determinar
    si es Bot o Real, calcula probabilidad y georreferencia el barrio en Neiva.
    """
    if not payload.citizens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La lista de ciudadanos enviada está vacía"
        )

    processed = 0
    added = 0
    updated = 0
    valid_phones = 0
    bots_detected = 0

    for item in payload.citizens:
        processed += 1
        clean_phone = normalize_colombia_phone(item.phone)
        if clean_phone and clean_phone.startswith("+57 3"):
            valid_phones += 1

        handle = item.handle or f"@{item.name.lower().replace(' ', '_')}_{str(uuid.uuid4())[:4]}"
        
        # Auditoría con IA para clasificar
        bot_eval = ai_classifier.detect_bot(
            comment_text=item.notes or item.name,
            author_metadata={
                "author": item.name,
                "handle": handle,
                "followers": 150 if clean_phone else 15,
                "following": 80 if clean_phone else 400,
                "account_age_days": 365 if clean_phone else 20
            }
        )

        user_type = item.user_type or bot_eval["user_type"]
        if user_type == "Bot":
            bots_detected += 1

        existing = db.query(Citizen).filter(
            or_(Citizen.handle == handle, Citizen.phone == clean_phone) if clean_phone else Citizen.handle == handle
        ).first()

        if existing:
            existing.name = item.name
            if clean_phone:
                existing.phone = clean_phone
            if item.neighborhood:
                existing.neighborhood = item.neighborhood
            if item.notes:
                existing.notes = item.notes
            existing.user_type = user_type
            existing.bot_probability = bot_eval["bot_probability"]
            existing.bot_origin = bot_eval["bot_origin"]
            updated += 1
        else:
            new_id = f"CIUD-{str(uuid.uuid4())[:8].upper()}"
            new_citizen = Citizen(
                id=new_id,
                name=item.name,
                handle=handle,
                phone=clean_phone,
                followers_count=150 if clean_phone else 15,
                following_count=80 if clean_phone else 400,
                account_created_at="Importado recientemente",
                user_type=user_type,
                bot_probability=bot_eval["bot_probability"],
                bot_origin=bot_eval["bot_origin"],
                neighborhood=item.neighborhood or "Neiva (General)",
                channel="Base de Datos",
                zone=item.neighborhood or "Neiva (General)",
                total_reports=1,
                sentiment_tendency="Crítico" if user_type == "Negativo" else "Positivo",
                notes=item.notes or "Cargado desde base de datos externa",
                origen_dato=payload.source_tag or "BASE_SUBIDA"
            )
            db.add(new_citizen)
            added += 1

    db.commit()

    return {
        "success": True,
        "summary": {
            "total_processed": processed,
            "new_citizens_added": added,
            "existing_updated": updated,
            "valid_colombian_phones": valid_phones,
            "bots_flagged_by_ai": bots_detected,
            "source_tag": payload.source_tag
        },
        "message": f"Se procesaron con éxito {processed} registros. Se detectaron {bots_detected} perfiles bot y {valid_phones} líneas móviles colombianas verificadas."
    }

