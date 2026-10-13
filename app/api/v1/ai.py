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

