from app.core.database import SessionLocal
from app.models.case import Case
from collections import Counter

def classify_rueda_sentiment(title: str, content: str, category: str, old_sentiment: str = "") -> str:
    text = f"{title or ''} {content or ''}".lower()
    
    # 1. ALEGRÍA
    if any(k in text for k in ["sampedro", "fiesta", "desfile", "comparsa", "gozar", "bailar", "concierto", "música", "folclor", "festival"]):
        return "Alegría: Diversión"
    if any(k in text for k in ["orgullo opita", "orgullo huilense", "mi tierra", "grande neiva", "tierra de promisión"]):
        return "Alegría: Orgullo"
    if any(k in text for k in ["innovador", "creativo", "novedoso", "buena idea", "creatividad", "gran iniciativa"]):
        return "Alegría: Creatividad"
    if any(k in text for k in ["energía", "con toda", "activos", "madrugando", "imparable", "fuerza"]):
        return "Alegría: Energía"
    if any(k in text for k in ["qué emoción", "emocionante", "felicidad total", "maravilla", "conmovedor"]):
        return "Alegría: Emoción"
    if any(k in text for k in ["felicitaciones", "felicidades", "excelente", "bravo", "éxitos", "adelante", "buena esa", "aplausos", "magnífico", "genial", "super bien"]):
        return "Alegría: Entusiasmo"

    # 2. PAZ O TRANQUILIDAD
    if any(k in text for k in ["muchas gracias", "mil gracias", "gracias alcalde", "dios lo bendiga", "bendiciones", "agradecimiento", "agradecido", "agradecemos"]):
        return "Paz o tranquilidad: Gratitud"
    if any(k in text for k in ["tranquilidad", "en calma", "orden y paz", "armonía", "serenidad", "despejado"]):
        return "Paz o tranquilidad: Serenidad"
    if any(k in text for k in ["con cariño", "amor por neiva", "de corazón", "te queremos"]):
        return "Paz o tranquilidad: Amor"
    if any(k in text for k in ["alivio", "descanso", "por fin respiro", "descansamos"]):
        return "Paz o tranquilidad: Relajación"
    if any(k in text for k in ["bienestar", "calidad de vida", "salud comunitaria", "ambiente sano"]):
        return "Paz o tranquilidad: Bienestar"
    if any(k in text for k in ["confianza", "fe en su gestión", "en buenas manos"]):
        return "Paz o tranquilidad: Confianza"

    # 3. PODER O FORTALEZA
    if any(k in text for k in ["reconocimiento", "hay que reconocer", "honor a quien honor", "admirable gestión"]):
        return "Poder o fortaleza: Reconocimiento"
    if any(k in text for k in ["quedó excelente", "obra entregada", "cumplieron", "satisfechos", "buen resultado", "se ve el cambio", "arreglado"]):
        return "Poder o fortaleza: Satisfacción"
    if any(k in text for k in ["liderazgo", "firmeza", "mano dura", "autoridad", "determinación", "con temple"]):
        return "Poder o fortaleza: Seguridad en sí mismo"
    if any(k in text for k in ["valoración", "dignidad", "nos sentimos respetados", "valoramos"]):
        return "Poder o fortaleza: Valoración personal"
    if any(k in text for k in ["seguridad de avanzar", "firme con johan", "apoyo total y firme"]):
        return "Poder o fortaleza: Confianza"

    # 4. MIEDO
    if any(k in text for k in ["atraco", "roban", "ladrones", "inseguridad", "peligro", "balacera", "fleteo", "droga", "olla", "miedo salir", "oscuras", "luz fundida", "poste"]):
        return "Miedo: Inseguridad"
    if any(k in text for k in ["accidente", "atropellan", "zozobra", "angustia", "temor", "asusta", "alarma", "emergencia", "riesgo de"]):
        return "Miedo: Ansiedad"
    if any(k in text for k in ["indefensos", "a merced", "desamparados", "nadie nos defiende", "impotencia ante"]):
        return "Miedo: Impotencia"
    if any(k in text for k in ["confusión", "desinformación", "no se entiende qué hacen", "descontrol"]):
        return "Miedo: Confusión"
    if any(k in text for k in ["niños en peligro", "ancianos en riesgo", "vulnerables", "debilidad"]):
        return "Miedo: Debilidad"
    if any(k in text for k in ["nos ignoran", "no nos escuchan", "cerraron puertas", "rechazo"]):
        return "Miedo: Rechazo"

    # 5. TRISTEZA
    if any(k in text for k in ["qué vergüenza", "pena ajena", "desprestigio", "vergüenza"]):
        return "Tristeza: Vergüenza"
    if any(k in text for k in ["qué tristeza", "da tristeza", "lamentable", "duele ver a neiva", "pesar", "lástima", "decadencia", "deterioro"]):
        return "Tristeza: Desánimo"
    if any(k in text for k in ["nos dejaron solos", "nadie viene", "olvidados de todos", "soledad"]):
        return "Tristeza: Soledad"
    if any(k in text for k in ["ya para qué", "no van a hacer nada", "siempre lo mismo da igual", "desinterés"]):
        return "Tristeza: Apatía"
    if any(k in text for k in ["la culpa es de nosotros", "votamos mal", "culpa"]):
        return "Tristeza: Culpa"
    if any(k in text for k in ["aburridos", "hartazgo", "tedio"]):
        return "Tristeza: Aburrimiento"

    # 6. ENOJO O IRA
    if any(k in text for k in ["ratas", "ladrones", "descarados", "corruptos", "sinvergüenzas", "vándalos", "desgraciados"]):
        return "Enojo o ira: Furia"
    if any(k in text for k in ["da rabia", "maldita", "incompetentes", "ineptos", "porquería", "mierda"]):
        return "Enojo o ira: Rabia"
    if any(k in text for k in ["politiqueros", "los mismos de siempre", "solo van a pedir votos", "promesas falsas", "mentirosos", "engañados", "se roban"]):
        return "Enojo o ira: Resentimiento"
    if any(k in text for k in ["para unos sí", "para otros nada", "preferencias", "rosca", "solo al norte"]):
        return "Enojo o ira: Celos"
    if any(k in text for k in ["fastidio", "jartera", "caos", "desorden", "invasión", "ruido", "estorbo"]):
        return "Enojo o ira: Irritación"
    if any(k in text for k in ["hueco", "cráter", "vía", "calle", "agua", "fuga", "tubo", "factura", "semáforo", "semáforos", "tráfico", "tránsito", "abuso", "cobro", "cansados", "hasta cuándo"]):
        return "Enojo o ira: Frustración"

    # Heurística según categoría o sentimiento previo
    if category in ["Seguridad", "Alumbrado Público"]:
        return "Miedo: Inseguridad"
    if category in ["Infraestructura", "Movilidad", "Servicios Públicos"]:
        return "Enojo o ira: Frustración"
    if "positiv" in (old_sentiment or "").lower():
        return "Alegría: Entusiasmo"
    if "indign" in (old_sentiment or "").lower():
        return "Enojo o ira: Frustración"
    if "crit" in (old_sentiment or "").lower():
        return "Enojo o ira: Rabia"
    
    return "Paz o tranquilidad: Serenidad"

def migrate_cases():
    db = SessionLocal()
    cases = db.query(Case).all()
    print(f"Iniciando actualización de {len(cases)} casos con la Rueda de Sentimientos...")
    
    updated = 0
    for c in cases:
        new_sent = classify_rueda_sentiment(c.title, c.content, c.category, c.sentiment)
        c.sentiment = new_sent
        updated += 1
        
    db.commit()
    print(f"¡Éxito! Se actualizaron {updated} casos en PostgreSQL.")
    
    # Verificar muestra
    sample = db.query(Case).limit(5).all()
    for s in sample:
        print(f"[{s.id}] {s.title[:40]} -> {s.sentiment}")
        
    db.close()

if __name__ == "__main__":
    migrate_cases()
