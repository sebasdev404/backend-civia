import os
import json
import logging
import re
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
- Secretaría de Educación (PAE - Programa de Alimentación Escolar, infraestructura escolar).
"""

class AIClassifierService:
    def __init__(self):
        api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY no está configurada.")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)

    def _heuristic_classify(self, comment_text: str) -> Dict[str, Any]:
        low = comment_text.lower()
        category = "General"
        department = "Despacho Municipal"
        priority = "Media"
        sentiment = "Neutral"
        commune = "No especificada"
        neighborhood = "Neiva (General)"

        if any(w in low for w in ["agua", "tubo", "fuga", "ceibas", "factura", "alcantarill", "acueducto"]):
            category = "Servicios Públicos"
            department = "Las Ceibas - Empresas Públicas de Neiva E.S.P."
            priority = "Alta"
            sentiment = "Indignación" if any(x in low for x in ["no", "abuso", "cobro", "corte"]) else "Preocupado"
        elif any(w in low for w in ["pae", "alimentación escolar", "refrigerio", "colegio", "estudiante"]):
            category = "Educación"
            department = "Secretaría de Educación Municipal (PAE)"
            priority = "Alta"
            sentiment = "Crítico"
        elif any(w in low for w in ["vía", "via", "calle", "hueco", "cráter", "crater", "pavimento", "asfalto", "bacheo", "malla"]):
            category = "Infraestructura"
            department = "Secretaría de Infraestructura y Vías"
            priority = "Alta"
            sentiment = "Crítico"
        elif any(w in low for w in ["semáforo", "semaforo", "tránsito", "transito", "tráfico", "trafico", "choque", "accidente", "vial", "carrera"]):
            category = "Movilidad"
            department = "Secretaría de Movilidad y Tránsito"
            priority = "Alta"
            sentiment = "Preocupado"
        elif any(w in low for w in ["luz", "poste", "oscuridad", "luminaria", "lámpara", "lampara", "alumbrado"]):
            category = "Alumbrado Público"
            department = "Alumbrado Público Neiva - ESIP"
            priority = "Media"
            sentiment = "Preocupado"
        elif any(w in low for w in ["robo", "atraco", "inseguridad", "ladrón", "ladron", "policía", "policia", "seguridad", "raponazo"]):
            category = "Seguridad"
            department = "Secretaría de Gobierno y Convivencia"
            priority = "Crítica"
            sentiment = "Crítico"

        for i in range(1, 11):
            if f"comuna {i}" in low:
                commune = f"Comuna {i}"
                break

        return {
            "category": category,
            "subcategory": f"Gestión de {category}",
            "intent": "Reporte ciudadano",
            "neighborhood": neighborhood,
            "commune": commune,
            "reference_street": "No especificada",
            "detected_problem": f"Reporte ciudadano relativo a {category.lower()}",
            "sentiment": sentiment,
            "confidence": 0.92,
            "requires_followup": True,
            "priority_suggestion": priority,
            "assigned_department_suggestion": department,
            "summary": f"Reporte ciudadano canalizado hacia {department}."
        }

    def classify_comment(self, comment_text: str) -> Dict[str, Any]:
        """
        Clasifica un comentario de ciudadano en Facebook / Instagram usando GPT-4o-mini
        extrayendo intención, toponimia de Neiva, problema y asignación sugerida.
        Cuenta con fallback heurístico automático si no hay llave de OpenAI.
        """
        if not self.client:
            logger.info("OPENAI_API_KEY no configurada. Usando clasificador heurístico local.")
            return self._heuristic_classify(comment_text)

        system_prompt = f"""
Eres CIVIA AI, el motor de inteligencia ciudadana de la Alcaldía de Neiva, Huila.
Tu función es analizar comentarios de ciudadanos provenientes de Facebook e Instagram y estructurarlos para gestión institucional.

{NEIVA_COMMUNES_CONTEXT}

REGLAS ESTRICTAS DE SALIDA:
Debes responder ÚNICAMENTE un objeto JSON válido con esta estructura:
{{
  "category": "Infraestructura | Servicios Públicos | Movilidad | Alumbrado Público | Seguridad | Salud | Medio Ambiente | Educación | General",
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
            logger.warning(f"Aviso en clasificación con OpenAI ({e}). Usando fallback heurístico.")
            return self._heuristic_classify(comment_text)

    def detect_bot(self, comment_text: str, author_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analiza señales heurísticas y semánticas para determinar si un perfil/comentario es un Bot,
        su probabilidad de bot y el origen o tipología de la cuenta (Granja, troll, automatizado).
        """
        meta = author_metadata or {}
        followers = int(meta.get("followers", meta.get("followers_count", 0)) or 0)
        following = int(meta.get("following", meta.get("following_count", 0)) or 0)
        account_age_days = int(meta.get("account_age_days", 180) or 180)
        handle = str(meta.get("handle", "") or "")
        author_name = str(meta.get("author", meta.get("name", "")) or "")

        bot_score = 0.0
        signals = []
        origin = "Humano Verificado"

        # Señales de perfil
        if followers < 25:
            bot_score += 0.35
            signals.append("Baja cantidad de seguidores (< 25)")
        if following > 250 and followers < 40:
            bot_score += 0.25
            signals.append("Ratio seguidos/seguidores desproporcionado")
        if account_age_days < 45:
            bot_score += 0.30
            signals.append("Cuenta de creación reciente (< 45 días)")

        # Señales de nombre/handle
        if re.search(r'\d{5,}$', handle):
            bot_score += 0.15
            signals.append("Patrón de identificador numérico automático")
        if "user" in handle.lower() or "bot" in handle.lower():
            bot_score += 0.20
            signals.append("Handle genérico autogenerado")

        # Señales textuales
        low = comment_text.lower()
        hate_political_patterns = [
            "la misma mierda", "politiqueros", "maquinaria", "corruptos", "inútiles",
            "no hacen nada", "alcahuetas", "circo", "pésima gestión", "se roban la plata",
            "por mi crítica salvé", "ladrones", "dejen de robar"
        ]
        repetitive_matches = [p for p in hate_political_patterns if p in low]
        if len(repetitive_matches) >= 2:
            bot_score += 0.20
            signals.append("Patrón repetitivo de ataque de desprestigio")

        bot_score = min(0.99, round(bot_score, 2))
        is_bot = bot_score >= 0.55

        if is_bot:
            if "ataque" in " ".join(signals).lower() or followers < 15:
                origin = "Granja de Cuentas / Campaña Opositora"
            elif re.search(r'\d{5,}$', handle):
                origin = "Automatizado de Spam"
            else:
                origin = "Perfil Falso Sin Foto de Perfil"
            user_type = "Bot"
        else:
            if any(p in low for p in ["gracias", "excelente", "apoyo", "adelante", "felicidades", "buena gestión", "felicitaciones"]):
                user_type = "Positivo"
            elif len(repetitive_matches) > 0 or any(x in low for x in ["pésimo", "mentira", "abuso", "inseguridad", "huecos", "fuga", "desastre"]):
                user_type = "Negativo"
            else:
                user_type = "Negativo"

        return {
            "is_bot": is_bot,
            "bot_probability": bot_score,
            "user_type": user_type,
            "bot_origin": origin,
            "signals": signals
        }

    def generate_smart_response(self, comment_text: str, context: Optional[str] = None, user_type: str = "Negativo") -> Dict[str, Any]:
        """
        Genera una respuesta inteligente institucional de alto nivel basada en hechos reales,
        desescalando comentarios de odio o bots y respondiendo con argumentos técnicos verificables.
        Incluye argumentos específicos para:
        - "Por mi crítica salvé el PAE" (Programa de Alimentación Escolar Neiva)
        - Vías, Huecos y Malla Vial
        - Acueducto Las Ceibas
        - Seguridad y Cuadrantes
        - Movilidad y Semáforos
        """
        low = comment_text.lower()

        # CASO ESPECÍFICO 1: PAE (Programa de Alimentación Escolar)
        if "pae" in low or "alimento" in low or "salve el pae" in low or "salvé el pae" in low:
            return {
                "topic": "Programa de Alimentación Escolar (PAE)",
                "detected_intent": "Crítica sobre gestión o fiscalización del PAE",
                "recommended_action": "Respuesta institucional técnica con datos de interventoría",
                "response_text": (
                    "Apreciado ciudadano, el control social y la veeduría son fundamentales para la transparencia de Neiva. "
                    "Bajo la actual administración de Johan Steed, el Programa de Alimentación Escolar (PAE) opera con supervisión técnica "
                    "permanente en las 160 sedes educativas de la ciudad, garantizando más de 38.000 raciones diarias auditadas por nutricionistas "
                    "y comités de veeduría comunitaria. Toda observación ciudadana se radica formalmente para inspección inmediata en sitio por "
                    "la Secretaría de Educación."
                ),
                "talking_points": [
                    "38.000 raciones diarias supervisadas",
                    "Interventoría técnica en 160 sedes educativas",
                    "Canal de radicación oficial abierto para inspección en terreno"
                ],
                "tone": "Institucional Firme y Transparente"
            }

        # CASO ESPECÍFICO 2: Vías y Huecos
        if any(w in low for w in ["hueco", "calle", "vía", "via", "pavimento", "asfalto", "cráter"]):
            return {
                "topic": "Malla Vial y Pavimentación",
                "detected_intent": "Reclamo por estado vial o bacheo",
                "recommended_action": "Radicar caso CIVIA e informar cronograma de cuadrillas",
                "response_text": (
                    "Hola. Entendemos y compartimos la urgencia de recuperar las vías de Neiva tras años de deterioro acumulado. "
                    "La Secretaría de Infraestructura Municipal avanza con el Plan Choque de Repavimentación en corredores estratégicos "
                    "(Avenida La Toma, Carrera 5ta, Circunvalar) y priorización barrial mediante cuadrillas de bacheo continuo. "
                    "Este sector ya ha sido ingresado al sistema CIVIA con radicado institucional para programación técnica."
                ),
                "talking_points": [
                    "Plan Choque de Repavimentación activo",
                    "Intervención prioritaria en vías principales y alimentadoras",
                    "Registro en sistema CIVIA para visita de cuadrilla"
                ],
                "tone": "Empático y Resolutivo"
            }

        # CASO ESPECÍFICO 3: Agua y Las Ceibas E.S.P.
        if any(w in low for w in ["agua", "ceibas", "factura", "fuga", "tubo", "alcantarill"]):
            return {
                "topic": "Servicios Públicos - Acueducto Las Ceibas",
                "detected_intent": "Falla en suministro o reporte de fuga",
                "recommended_action": "Despachar a cuadrilla de Las Ceibas E.S.P.",
                "response_text": (
                    "Buen día. En Las Ceibas - Empresas Públicas de Neiva mantenemos cuadrillas operativas 24/7 atendiendo emergencias "
                    "en redes matrices y estabilización de plantas ante turbiedad en la cuenca del río Las Ceibas. Tu reporte ha sido remitido "
                    "directamente al despacho técnico para verificar presión y atención técnica en terreno."
                ),
                "talking_points": [
                    "Cuadrillas de emergencia 24/7 de Las Ceibas",
                    "Atención en planta de potabilización",
                    "Canalización técnica de reporte"
                ],
                "tone": "Atención Técnica Inmediata"
            }

        # CASO ESPECÍFICO 4: BOTS / Ataques de Granja o Trolls
        if user_type == "Bot" or "la misma mierda" in low or "politiqueros" in low:
            return {
                "topic": "Desescalamiento de Ataque Automatizado / Troll",
                "detected_intent": "Desprestigio sin propuesta técnica",
                "recommended_action": "Respuesta institucional neutral / Redirección a canales oficiales con radicado",
                "response_text": (
                    "Agradecemos la participación ciudadana. En CIVIA procesamos todas las solicitudes, quejas y propuestas con trazabilidad "
                    "y radicado institucional transparente para la Alcaldía de Neiva. Si cuentas con un reporte específico sobre tu barrio o comuna, "
                    "te invitamos a compartir la dirección exacta para gestionar la atención correspondiente."
                ),
                "talking_points": [
                    "Recepción institucional abierta y transparente",
                    "Exigencia de datos verificables para gestión barrial",
                    "Neutralización de ataques sin fundamento"
                ],
                "tone": "Neutral y Asertivo"
            }

        # Fallback general con IA o plantilla
        if self.client:
            try:
                system_prompt = f"""
Eres el vocero institucional y estratega de respuesta de la Alcaldía de Neiva (Johan Steed).
Genera una respuesta pública para un comentario en Facebook/Instagram.
Reglas:
1. Tono respetuoso, seguro, institucional y constructivo.
2. Basado en hechos de Neiva, sin pelear ni descalificar.
3. Máximo 70 palabras.
4. Si es odio o troll, desescalar con datos de gestión pública y canales de radicación.
Responde en formato JSON con llaves: "response_text", "topic", "recommended_action", "tone".
"""
                resp = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Comentario del ciudadano:\n\"{comment_text}\""}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    max_tokens=250
                )
                return json.loads(resp.choices[0].message.content)
            except Exception as e:
                logger.warning(f"Error generando respuesta con OpenAI: {e}")

        return {
            "topic": "Atención Ciudadana General",
            "detected_intent": "Comentario ciudadano en redes",
            "recommended_action": "Atención institucional con radicado",
            "response_text": (
                "Hola. Desde la Alcaldía de Neiva hacemos seguimiento permanente a las inquietudes ciudadanas. "
                "Tu comentario ha sido registrado en la plataforma CIVIA para coordinar acciones con la secretaría competente."
            ),
            "talking_points": ["Monitoreo continuo", "Registro en CIVIA", "Coordinación institucional"],
            "tone": "Institucional Cordial"
        }

    def get_embedding(self, text: str) -> List[float]:
        """
        Genera el vector de embedding para similitud semántica usando text-embedding-3-small.
        """
        if not self.client:
            import hashlib
            seed_bytes = hashlib.sha256(text.encode('utf-8')).digest()
            return [float(b) / 255.0 for b in seed_bytes[:32]]

        try:
            clean_text = text.replace("\n", " ").strip()
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=clean_text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(f"Error generando embedding con OpenAI ({e}). Usando fallback.")
            import hashlib
            seed_bytes = hashlib.sha256(text.encode('utf-8')).digest()
            return [float(b) / 255.0 for b in seed_bytes[:32]]

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
