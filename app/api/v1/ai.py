from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.case import Case
from app.services.ai_classifier import ai_classifier

router = APIRouter(prefix="/ai", tags=["Inteligencia Artificial y NLP"])

class CommentClassifyRequest(BaseModel):
    text: str = Field(..., description="Texto del comentario del ciudadano a analizar")

class SimilarityRequest(BaseModel):
    text_a: str
    text_b: str

class MatchCaseItem(BaseModel):
    case_id: str
    title: str
    category: str
    location: str
    similarity_percent: float

@router.post("/classify", response_model=Dict[str, Any])
def classify_citizen_comment(payload: CommentClassifyRequest):
    """
    Analiza un comentario de ciudadano con OpenAI gpt-4o-mini
    extrayendo intención, toponimia comunal de Neiva, problema y prioridad sugerida.
    """
    clean_text = payload.text.strip()
    if not clean_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El texto del comentario no puede estar vacío"
        )
    
    try:
        result = ai_classifier.classify_comment(clean_text)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando análisis con OpenAI: {str(e)}"
        )

@router.post("/similarity")
def compare_similarity(payload: SimilarityRequest):
    """
    Compara dos textos mediante embeddings de OpenAI y retorna su similitud semántica (0 a 100%).
    """
    try:
        emb_a = ai_classifier.get_embedding(payload.text_a)
        emb_b = ai_classifier.get_embedding(payload.text_b)
        sim = ai_classifier.cosine_similarity(emb_a, emb_b)
        return {
            "similarity_score": round(sim, 4),
            "similarity_percent": round(sim * 100, 1),
            "match": sim >= 0.70
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculando similitud vectorial: {str(e)}"
        )

@router.post("/match-cases", response_model=List[MatchCaseItem])
def match_comment_against_open_cases(
    payload: CommentClassifyRequest,
    db: Session = Depends(get_db)
):
    """
    Evalúa un comentario entrante frente a todos los casos abiertos en Neiva
    para detectar posibles duplicados y sugerir asociación inmediata.
    """
    clean_text = payload.text.strip()
    if not clean_text:
        return []

    try:
        comment_emb = ai_classifier.get_embedding(clean_text)
        open_cases = db.query(Case).filter(Case.status != "Resuelto").all()
        
        matches: List[MatchCaseItem] = []
        for c in open_cases:
            case_text = f"{c.title}. {c.content or ''}. Ubicación: {c.location}. Categoría: {c.category}"
            case_emb = ai_classifier.get_embedding(case_text)
            sim = ai_classifier.cosine_similarity(comment_emb, case_emb)
            sim_percent = round(sim * 100, 1)

            if sim_percent >= 50.0:  # Umbral de afinidad
                matches.append(MatchCaseItem(
                    case_id=c.id,
                    title=c.title,
                    category=c.category,
                    location=c.location,
                    similarity_percent=sim_percent
                ))

        # Ordenar por mayor porcentaje de similitud
        matches.sort(key=lambda m: m.similarity_percent, reverse=True)
        return matches[:5]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error buscando casos afines: {str(e)}"
        )


@router.get("/credits")
def get_ai_credits_info(db: Session = Depends(get_db)):
    """
    Monitorea el estado de la API Key de OpenAI, conectividad en tiempo real,
    estimación de tokens y costo acumulado de los casos clasificados en CIVIA,
    e intenta obtener saldo si se dispone de token con scope de administración.
    """
    import os
    import time
    import urllib.request
    import urllib.error
    import json
    from app.core.config import settings

    api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "status": "No configurada",
            "has_key": False,
            "quota_status": "Sin llave API",
            "latency_ms": 0,
            "cases_analyzed": 0,
            "estimated_tokens": 0,
            "estimated_cost_usd": 0.0,
            "model": "Local / Heurístico",
            "masked_key": "No configurada",
            "billing_url": "https://platform.openai.com/settings/organization/billing/overview",
            "detail": "Configure OPENAI_API_KEY en backend-civia/.env"
        }

    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "sk-***"
    
    # 1. Contar casos analizados en PostgreSQL
    cases_analyzed = db.query(Case).count()
    # Cada caso consume aprox 350 tokens (prompt + respuesta JSON estructurada)
    estimated_tokens = cases_analyzed * 350
    # GPT-4o-mini cuesta aprox $0.15 por 1M tokens de entrada y $0.60 por 1M de salida -> promedio $0.25 / 1M
    estimated_cost_usd = round((estimated_tokens / 1_000_000) * 0.25, 4)

    # 2. Test en vivo a OpenAI para verificar saldo / conectividad / latencia
    status_msg = "Activo / Conectado"
    quota_status = "Cuota disponible (Operativo)"
    latency_ms = 0
    balance_amount = None
    currency = "USD"
    
    t0 = time.time()
    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            latency_ms = round((time.time() - t0) * 1000, 1)
            if resp.status == 200:
                status_msg = "Conectado / Operativo"
                quota_status = "Cuota disponible (Activa)"
    except urllib.error.HTTPError as e:
        latency_ms = round((time.time() - t0) * 1000, 1)
        if e.code == 429:
            status_msg = "Cuota Agotada"
            quota_status = "Alerta: Saldo o límite de cuota alcanzado (HTTP 429)"
        elif e.code == 401:
            status_msg = "No Autorizado"
            quota_status = "API Key no válida o revocada (HTTP 401)"
        else:
            status_msg = f"HTTP {e.code}"
            quota_status = f"Respuesta inesperada: HTTP {e.code}"
    except Exception as e:
        status_msg = "Error de Red"
        quota_status = f"No se pudo conectar a OpenAI: {str(e)}"

    # 3. Intentar consultar balance si se cuenta con llave de organización o admin
    admin_key = os.getenv("OPENAI_ADMIN_KEY") or api_key
    try:
        req_bal = urllib.request.Request(
            "https://api.openai.com/v1/organization/billing/credit_balance",
            headers={"Authorization": f"Bearer {admin_key}"}
        )
        with urllib.request.urlopen(req_bal, timeout=3) as resp_bal:
            bal_data = json.loads(resp_bal.read().decode())
            if "total_available" in bal_data:
                balance_amount = bal_data.get("total_available")
            elif "balance" in bal_data:
                balance_amount = bal_data.get("balance")
    except Exception:
        pass

    return {
        "status": status_msg,
        "has_key": True,
        "quota_status": quota_status,
        "latency_ms": latency_ms,
        "cases_analyzed": cases_analyzed,
        "estimated_tokens": estimated_tokens,
        "estimated_cost_usd": estimated_cost_usd,
        "model": "OpenAI GPT-4o-mini",
        "masked_key": masked_key,
        "balance_amount": balance_amount,
        "currency": currency,
        "billing_url": "https://platform.openai.com/settings/organization/billing/overview",
        "detail": (
            f"La llave de inferencia responde en {latency_ms} ms. "
            f"Se han analizado {cases_analyzed:,} incidentes territoriales en Neiva con una inversión acumulada estimada de ${estimated_cost_usd} USD."
        )
    }




class SmartReplyRequest(BaseModel):
    comment_text: str = Field(..., description="Texto del comentario o crítica del ciudadano")
    author_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    user_type: Optional[str] = "Negativo"

@router.post("/generate-smart-reply")
def generate_smart_reply(payload: SmartReplyRequest):
    """
    Genera una respuesta inteligente institucional contextual,
    desescalando críticas de odio, neutralizando bots o respondiendo técnicamente a temas
    como PAE ('Por mi crítica salvé el PAE'), Malla Vial, Acueducto o Seguridad.
    """
    try:
        reply_data = ai_classifier.generate_smart_response(
            comment_text=payload.comment_text,
            context=payload.user_type,
            user_type=payload.user_type
        )
        return reply_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando respuesta con IA: {str(e)}"
        )

class BotDetectRequest(BaseModel):
    comment_text: str = Field(..., description="Texto del comentario")
    author_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

@router.post("/detect-bot")
def detect_bot_endpoint(payload: BotDetectRequest):
    """
    Evalúa perfil y texto para detectar si es un bot, ratio seguidores/seguidos,
    antigüedad de cuenta, probabilidad de bot e identifica el origen.
    """
    try:
        bot_data = ai_classifier.detect_bot(
            comment_text=payload.comment_text,
            author_metadata=payload.author_metadata
        )
        return bot_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analizando detección de bot: {str(e)}"
        )
