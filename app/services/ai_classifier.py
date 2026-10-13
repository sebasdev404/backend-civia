import os
import json
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

NEIVA_COMMUNES_CONTEXT = """
Contexto Geográfico de Neiva, Huila:
- Comuna 1: Cándido Leguízamo, Santa Inés, Chicalá, Camilo Torres, El Triángulo.
- Comuna 2: Las Granjas, San Martín, Los Andes, Álamos Norte, Virgilio Barco, Villa del Prado.
- Comuna 3: Centro, Quirinal, José Eustasio Rivera, El Lago, Chapinero, La Toma.
- Comuna 4: El Malecón, Mártires, San Pedro, Sevilla, Estadio, La Gaitana.
- Comuna 5: Buganvillas, Jordán, Monserrate, Las Catleyas, Siete de Agosto.
- Comuna 6: Canaima, Max Duque, Pozo Azul, San Carlos, Santa Isabel, Encenillo, Puertas del Sol.
- Comuna 7: Ipanema, El Vergel, Calixto Leiva, Las Brisas, San Antonio, Prado Alto.
- Comuna 8: Las Américas, Acrópolis, Panorama, Alfonso López, La Florida.
- Comuna 9: Luis Carlos Galán, Alberto Galindo, Eduardo Santos, Darío Echandía.
- Comuna 10: Las Palmas, El Pedregal, Víctor Félix, Las Camelias, Oasis.
- Corregimientos: El Caguán, Fortalecillas, Vegalarga, Guacirco, Río de las Ceibas, San Antonio de Anaconia.

Dependencias Principales de Neiva:
- Las Ceibas - Empresas Públicas de Neiva E.S.P. (Acueducto, alcantarillado, fugas, facturación de agua).
- Secretaría de Infraestructura y Vías (Malla vial, pavimentación, huecos, bacheo, puentes).
- Secretaría de Movilidad y Tránsito (Semáforos, señalización, controladores viales, transporte público).
- Alumbrado Público Neiva - ESIP (Luminarias LED fundidas, postes, iluminación de parques).
- Secretaría de Salud Municipal (Hospital Universitario, centros de salud, urgencias, sanidad).
- Secretaría de Medio Ambiente (Manejo de escombros, rondas hídricas del río Las Ceibas y Magdalena, podas).
- Secretaría de Gobierno y Convivencia (Seguridad, espacio público, cuadrantes policiales).
"""

class AIClassifierService:
    def __init__(self):
        api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY no está configurada.")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)

    def classify_comment(self, comment_text: str) -> Dict[str, Any]:
        """
        Clasifica un comentario de ciudadano en Facebook / Instagram usando GPT-4o-mini
        extrayendo intención, toponimia de Neiva, problema y asignación sugerida.
        """
        if not self.client:
            raise ValueError("Cliente OpenAI no inicializado. Verifique OPENAI_API_KEY en .env")

        system_prompt = f"""
Eres CIVIA AI, el motor de inteligencia ciudadana de la Alcaldía de Neiva, Huila.
Tu función es analizar comentarios de ciudadanos provenientes de Facebook e Instagram y estructurarlos para gestión institucional.

{NEIVA_COMMUNES_CONTEXT}

REGLAS ESTRICTAS DE SALIDA:
Debes responder ÚNICAMENTE un objeto JSON válido con esta estructura:
{{
  "category": "Infraestructura | Servicios Públicos | Movilidad | Alumbrado Público | Seguridad | Salud | Medio Ambiente | General",
  "subcategory": "Texto descriptivo breve",
  "intent": "Reporte ciudadano | Queja / Reclamo | Solicitud de Información | Pregunta | Sugerencia | Agradecimiento / Apoyo | Felicitación | Otro",
  "neighborhood": "Nombre del barrio identificado o 'Neiva (General)'",
  "commune": "Comuna identificada (ej. 'Comuna 2') o 'No especificada'",
  "reference_street": "Dirección o referencia vial detectada (ej. 'Calle 39 con Cra 25') o 'No especificada'",
  "detected_problem": "Resumen conciso del problema específico (ej. 'Deterioro vial / hueco profundo')",
  "sentiment": "Crítico | Preocupado | Indignación | Neutral | Positivo",
  "confidence": 0.95,
  "requires_followup": true,
  "priority_suggestion": "Alta | Media | Baja | Crítica",
  "assigned_department_suggestion": "Nombre de la dependencia competente de Neiva",
  "summary": "Resumen institucional de una línea"
}}
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analiza este comentario de ciudadano:\n\n\"{comment_text}\""}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=400,
            )
            raw_content = response.choices[0].message.content
            parsed = json.loads(raw_content)
            return parsed
        except Exception as e:
            logger.error(f"Error en clasificación con OpenAI: {e}")
            raise e

    def get_embedding(self, text: str) -> List[float]:
        """
        Genera el vector de embedding para similitud semántica usando text-embedding-3-small.
        """
        if not self.client:
            raise ValueError("Cliente OpenAI no inicializado.")

        clean_text = text.replace("\n", " ").strip()
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=clean_text
        )
        return response.data[0].embedding

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Calcula la similitud de coseno entre dos vectores."""
        import math
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return max(0.0, min(1.0, dot / (norm_a * norm_b)))

ai_classifier = AIClassifierService()
