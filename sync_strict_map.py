"""
Sincroniza el mapa ÚNICAMENTE con casos que contengan ARGUMENTO Y EVIDENCIA TEXTUAL
real y verificable (mención explícita de barrio, comuna o vía en el comentario).
NUNCA asigna una ubicación arbitraria si el ciudadano no la mencionó.
"""
from app.core.database import SessionLocal
from app.models.case import Case
from app.models.incident import Incident
import re

COMUNA_DATA = {
    "comuna 1": {"name": "Comuna 1 (Norte)", "zone": "comuna-1", "lat": 2.9480, "lng": -75.2950},
    "comuna 2": {"name": "Comuna 2 (Noroccidente)", "zone": "comuna-2", "lat": 2.9420, "lng": -75.2850},
    "comuna 3": {"name": "Comuna 3 (Centro)", "zone": "comuna-3", "lat": 2.9340, "lng": -75.2820},
    "comuna 4": {"name": "Comuna 4 (Occidente)", "zone": "comuna-4", "lat": 2.9290, "lng": -75.2890},
    "comuna 5": {"name": "Comuna 5 (Oriente)", "zone": "comuna-5", "lat": 2.9320, "lng": -75.2720},
    "comuna 6": {"name": "Comuna 6 (Sur)", "zone": "comuna-6", "lat": 2.9050, "lng": -75.2850},
    "comuna 7": {"name": "Comuna 7 (Suroriente)", "zone": "comuna-7", "lat": 2.9180, "lng": -75.2680},
    "comuna 8": {"name": "Comuna 8 (Suroriente Alto)", "zone": "comuna-8", "lat": 2.9230, "lng": -75.2600},
    "comuna 9": {"name": "Comuna 9 (Norte Alto)", "zone": "comuna-9", "lat": 2.9550, "lng": -75.2870},
    "comuna 10": {"name": "Comuna 10 (Oriente Alto)", "zone": "comuna-10", "lat": 2.9380, "lng": -75.2650},
}

# Mapeo estricto de barrios reales a su comuna respectiva
BARRIOS_CATALOG = {
    # Comuna 1
    "cándido leguízamo": ("Comuna 1", "comuna 1", 2.9485, -75.2960),
    "cándido": ("Cándido Leguízamo", "comuna 1", 2.9485, -75.2960),
    "candido": ("Cándido Leguízamo", "comuna 1", 2.9485, -75.2960),
    "santa inés": ("Santa Inés", "comuna 1", 2.9450, -75.2930),
    "santa ines": ("Santa Inés", "comuna 1", 2.9450, -75.2930),
    "chicalá": ("Chicalá", "comuna 1", 2.9490, -75.2910),
    "chicala": ("Chicalá", "comuna 1", 2.9490, -75.2910),
    "camilo torres": ("Camilo Torres", "comuna 1", 2.9510, -75.2920),
    "el triángulo": ("El Triángulo", "comuna 1", 2.9430, -75.2970),
    "el triangulo": ("El Triángulo", "comuna 1", 2.9430, -75.2970),
    "los andes": ("Los Andes", "comuna 1", 2.9420, -75.2940),

    # Comuna 2
    "las granjas": ("Las Granjas", "comuna 2", 2.9415, -75.2862),
    "granjas": ("Las Granjas", "comuna 2", 2.9415, -75.2862),
    "san martín": ("San Martín", "comuna 2", 2.9440, -75.2820),
    "san martin": ("San Martín", "comuna 2", 2.9440, -75.2820),
    "álamos": ("Álamos Norte", "comuna 2", 2.9460, -75.2840),
    "alamos": ("Álamos Norte", "comuna 2", 2.9460, -75.2840),
    "virgilio barco": ("Virgilio Barco", "comuna 2", 2.9430, -75.2810),
    "villa del prado": ("Villa del Prado", "comuna 2", 2.9450, -75.2880),

    # Comuna 3
    "centro": ("Centro", "comuna 3", 2.9310, -75.2870),
    "quirinal": ("Quirinal", "comuna 3", 2.9358, -75.2795),
    "josé eustasio rivera": ("José Eustasio Rivera", "comuna 3", 2.9340, -75.2830),
    "la toma": ("Av. La Toma", "comuna 3", 2.9335, -75.2840),
    "av. la toma": ("Av. La Toma", "comuna 3", 2.9335, -75.2840),
    "chapinero": ("Chapinero", "comuna 3", 2.9320, -75.2850),

    # Comuna 4
    "el malecón": ("El Malecón", "comuna 4", 2.9285, -75.2935),
    "el malecon": ("El Malecón", "comuna 4", 2.9285, -75.2935),
    "malecón": ("El Malecón", "comuna 4", 2.9285, -75.2935),
    "la gaitana": ("La Gaitana", "comuna 4", 2.9275, -75.2940),
    "gaitana": ("La Gaitana", "comuna 4", 2.9275, -75.2940),
    "mártires": ("Mártires", "comuna 4", 2.9295, -75.2910),
    "estadio": ("Estadio Guillermo Plazas", "comuna 4", 2.9260, -75.2880),

    # Comuna 5
    "buganvillas": ("Buganvillas", "comuna 5", 2.9320, -75.2720),
    "jordán": ("Jordán", "comuna 5", 2.9310, -75.2740),
    "jordan": ("Jordán", "comuna 5", 2.9310, -75.2740),
    "monserrate": ("Monserrate", "comuna 5", 2.9330, -75.2700),
    "las catleyas": ("Las Catleyas", "comuna 5", 2.9300, -75.2710),

    # Comuna 6
    "canaima": ("Canaima", "comuna 6", 2.9062, -75.2848),
    "max duque": ("Max Duque", "comuna 6", 2.9030, -75.2860),
    "pozo azul": ("Pozo Azul", "comuna 6", 2.9020, -75.2870),
    "el limonar": ("El Limonar", "comuna 6", 2.9080, -75.2830),
    "limonar": ("El Limonar", "comuna 6", 2.9080, -75.2830),
    "puertas del sol": ("Puertas del Sol", "comuna 6", 2.9040, -75.2820),

    # Comuna 7
    "ipanema": ("Ipanema", "comuna 7", 2.9180, -75.2680),
    "el vergel": ("El Vergel", "comuna 7", 2.9190, -75.2650),
    "las brisas": ("Las Brisas", "comuna 7", 2.9160, -75.2690),
    "calixto leiva": ("Calixto Leiva", "comuna 7", 2.9210, -75.2670),

    # Comuna 8
    "las américas": ("Las Américas", "comuna 8", 2.9230, -75.2600),
    "las americas": ("Las Américas", "comuna 8", 2.9230, -75.2600),
    "acrópolis": ("Acrópolis", "comuna 8", 2.9240, -75.2580),
    "panorama": ("Panorama", "comuna 8", 2.9210, -75.2590),
    "alfonso lópez": ("Alfonso López", "comuna 8", 2.9250, -75.2610),

    # Comuna 9
    "luis carlos galán": ("Luis Carlos Galán", "comuna 9", 2.9550, -75.2870),
    "galán": ("Luis Carlos Galán", "comuna 9", 2.9550, -75.2870),
    "alberto galindo": ("Alberto Galindo", "comuna 9", 2.9580, -75.2890),
    "darío echandía": ("Darío Echandía", "comuna 9", 2.9530, -75.2850),

    # Comuna 10
    "las palmas": ("Las Palmas", "comuna 10", 2.9380, -75.2650),
    "palmas": ("Las Palmas", "comuna 10", 2.9380, -75.2650),
    "el pedregal": ("El Pedregal", "comuna 10", 2.9390, -75.2620),
    "pedregal": ("El Pedregal", "comuna 10", 2.9390, -75.2620),
    "víctor félix": ("Víctor Félix", "comuna 10", 2.9410, -75.2640),

    # Corregimientos
    "el caguán": ("Corregimiento El Caguán", "comuna 6", 2.8600, -75.2750),
    "caguán": ("Corregimiento El Caguán", "comuna 6", 2.8600, -75.2750),
    "fortalecillas": ("Corregimiento Fortalecillas", "comuna 1", 2.9900, -75.2800),
    
    # Vías
    "circunvalar": ("Avenida Circunvalar", "comuna 3", 2.9290, -75.2920),
    "carrera 2": ("Carrera 2da Comercial", "comuna 3", 2.9300, -75.2860),
    "carrera 5": ("Carrera 5ta Troncal", "comuna 3", 2.9330, -75.2830),
}

def sync_strict_evidence_incidents():
    db = SessionLocal()
    # 1. Limpiar incidentes anteriores
    db.query(Incident).delete()
    db.commit()

    cases = db.query(Case).all()
    print(f"Total casos a examinar con rigor argumental: {len(cases)}")

    saved_count = 0
    discarded_count = 0

    for c in cases:
        full_text = f"{c.location or ''} {c.title or ''} {c.content or ''}".lower()
        
        detected_barrio = None
        detected_comuna_key = None
        base_lat = None
        base_lng = None
        argument_evidence = None

        # 1. Buscar mención directa de barrios o vías reconocidas
        for keyword, (barrio_name, com_key, lat, lng) in BARRIOS_CATALOG.items():
            if re.search(r'\b' + re.escape(keyword) + r'\b', full_text):
                detected_barrio = barrio_name
                detected_comuna_key = com_key
                base_lat = lat
                base_lng = lng
                argument_evidence = f"Mención explícita en texto: '{keyword}'"
                break

        # 2. Si no menciona barrio pero menciona explícitamente el número de comuna:
        if not detected_barrio:
            m_comuna = re.search(r'\bcomuna\s*([1-9]|10)\b', full_text)
            if m_comuna:
                num = m_comuna.group(1)
                detected_comuna_key = f"comuna {num}"
                cfg = COMUNA_DATA.get(detected_comuna_key)
                if cfg:
                    detected_barrio = cfg["name"]
                    base_lat = cfg["lat"]
                    base_lng = cfg["lng"]
                    argument_evidence = f"Mención explícita en texto: 'Comuna {num}'"

        # REGLA ESTRICTA: Si NO hay argumento ni evidencia territorial en el texto, NO SE COLOCA EN EL MAPA.
        if not detected_barrio or not detected_comuna_key or not base_lat:
            discarded_count += 1
            continue

        cfg = COMUNA_DATA.get(detected_comuna_key, COMUNA_DATA["comuna 3"])
        
        # Pequeño jitter realista (para que casos del mismo barrio no queden montados encima)
        offset_lat = ((hash(f"{c.id}_lat") % 500) - 250) * 0.000008
        offset_lng = ((hash(f"{c.id}_lng") % 500) - 250) * 0.000008

        final_lat = round(base_lat + offset_lat, 5)
        final_lng = round(base_lng + offset_lng, 5)

        # Añadir al mapa con su argumento comprobable
        description_with_argument = f"{c.content}\n\n[Argumento Geográfico]: {argument_evidence} en {detected_barrio} ({cfg['name']})."

        inc = Incident(
            id=c.id,
            title=c.title,
            description=description_with_argument,
            category=c.category,
            priority=c.priority,
            sentiment=c.sentiment,
            source=c.source,
            neighborhood=f"{detected_barrio} ({cfg['name']})",
            zone=cfg["zone"],
            lat=final_lat,
            lng=final_lng,
            status=c.status,
            reports_count=c.comments_count or 1,
            date_time=c.date_time,
            is_new=(c.status == "Pendiente")
        )
        db.add(inc)
        saved_count += 1

    db.commit()
    print(f"\nRESULTADO DE RIGOR TERRITORIAL:")
    print(f"  Puntos georreferenciados CON EVIDENCIA COMPROBABLE: {saved_count}")
    print(f"  Casos generales excluidos del mapa por falta de mención barrial: {discarded_count}")
    
    # Muestra de verificación
    sample = db.query(Incident).limit(3).all()
    for s in sample:
        clean_desc = s.description.encode('ascii', 'ignore').decode('ascii')
        print(f"\n[{s.id}] {s.neighborhood}")
        print(f"  {clean_desc[:120]}...")
        
    db.close()

if __name__ == "__main__":
    sync_strict_evidence_incidents()

