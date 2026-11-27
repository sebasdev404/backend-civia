from app.core.authentication import get_current_user
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.case import Case
from app.models.case_consolidation import CaseConsolidation
from sqlalchemy import select
from typing import Annotated
from app.services.ai_classifier import ai_classifier

router = APIRouter(prefix="/ai", tags=["Inteligencia Artificial y NLP"])

class CommentClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000, description="Texto del comentario del ciudadano a analizar")

class MatchCasesRequest(CommentClassifyRequest):
    candidate_ids: List[Annotated[str, Field(min_length=1, max_length=50)]] = Field(min_length=1,max_length=20)

class SimilarityRequest(BaseModel):
    text_a: str = Field(min_length=1,max_length=20000)
    text_b: str = Field(min_length=1,max_length=20000)

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
            detail="No se pudo completar el análisis; revisa la configuración privada."
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
            detail="No se pudo comparar los textos; revisa el servicio de análisis."
        )

@router.post("/match-cases", response_model=List[MatchCaseItem])
def match_comment_against_open_cases(
    payload: MatchCasesRequest,
    db: Session = Depends(get_db)
):
    """
    Compara hasta 20 candidatos elegidos explícitamente; nunca asocia por sí sola.
    """
    clean_text = payload.text.strip()
    if not clean_text:
        return []

    try:
        duplicates=select(CaseConsolidation.duplicate_case_id).where(CaseConsolidation.undone_at.is_(None))
        open_cases = db.query(Case).filter(Case.id.in_(payload.candidate_ids),Case.status.in_(("Pendiente","En Gestión")),~Case.id.in_(duplicates)).order_by(Case.id).all()
        if not open_cases:return []
        comment_emb = ai_classifier.get_embedding(clean_text)
        
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
            detail="No se pudo completar la búsqueda de casos afines."
        )


@router.get("/credits")
def get_ai_credits_info(db: Session = Depends(get_db)):
    from app.core.config import settings
    from app.models.operations import SystemSetting
    item=db.get(SystemSetting,'ai_budget')
    values=item.value if item else {}
    return {
        'status':'Configurada; conexi\u00f3n no verificada' if settings.OPENAI_API_KEY else 'No configurada',
        'has_key':bool(settings.OPENAI_API_KEY),'quota_status':'Consultar facturaci\u00f3n del proveedor',
        'latency_ms':None,'cases_analyzed':None,'tokens_processed':None,'estimated_tokens':None,'estimated_cost_usd':None,
        'initial_budget_usd':values.get('initial_budget'),'remaining_usd':values.get('real_balance'),'consumed_usd':values.get('consumed_usd'),
        'percent_consumed':None,'percent_remaining':None,'model':'gpt-4o-mini',
        'masked_key':'Configurada' if settings.OPENAI_API_KEY else 'No configurada',
        'budget_source':'manual_record' if item else 'unavailable',
        'billing_url':'https://platform.openai.com/settings/organization/billing/overview',
        'detail':'El presupuesto es una declaraci\u00f3n administrativa. Ordenemos a Neiva no consulta el saldo del proveedor ni estima gasto a partir del n\u00famero de casos.'}


class BalanceSyncRequest(BaseModel):
    initial_budget: Optional[float] = Field(default=None,ge=0,le=1000000,allow_inf_nan=False)
    real_balance: Optional[float] = Field(default=None,ge=0,le=1000000,allow_inf_nan=False)
    consumed_usd: Optional[float] = Field(default=None,ge=0,le=1000000,allow_inf_nan=False)


@router.post("/sync-balance")
def sync_ai_balance(payload: BalanceSyncRequest, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    from app.models.operations import SystemSetting
    from app.services.audit import record
    values=payload.model_dump(exclude_none=True)
    if not values:raise HTTPException(422,'Indica los valores que deseas registrar.')
    item=db.query(SystemSetting).filter_by(key='ai_budget').with_for_update().first()
    if item is None:
        item=SystemSetting(key='ai_budget',value={},updated_by=actor.id);db.add(item)
    item.value={**item.value,**values};item.updated_by=actor.id
    record(db,actor,'budget_recorded','ai_budget',fields=list(values))
    db.commit()
    return {'success':True,'message':'Presupuesto declarado guardado. No acredita saldo del proveedor.'}


class SmartReplyRequest(BaseModel):
    comment_text: str = Field(..., min_length=1, max_length=20000, description="Texto del comentario o crítica del ciudadano")
    author_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    user_type: Optional[str] = "Negativo"

@router.post("/generate-smart-reply")
def generate_smart_reply(payload: SmartReplyRequest):
    """
    Genera un borrador de atención que requiere revisión humana y no se publica.
    """
    try:
        reply_data = ai_classifier.generate_smart_response(
            comment_text=payload.comment_text,
            context=None,
            user_type=payload.user_type
        )
        return reply_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo generar el borrador; revisa la configuración o redacta manualmente."
        )

class BotDetectRequest(BaseModel):
    comment_text: str = Field(..., min_length=1, max_length=20000, description="Texto del comentario")
    author_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

@router.post("/detect-bot")
def detect_bot_endpoint(payload: BotDetectRequest):
    """
    Devuelve señales para revisión sin certificar identidad, origen ni probabilidad de bot.
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
            detail="No se pudieron consultar las señales; no hay una conclusión confirmada."
        )
