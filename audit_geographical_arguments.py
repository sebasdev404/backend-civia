from app.core.database import SessionLocal
from app.models.case import Case
import re

NEIVA_BARRIOS_CORREGIMIENTOS = [
    # Comuna 1
    "cándido leguízamo", "cándido", "candido", "santa inés", "santa ines", "chicalá", "chicala", "camilo torres", "el triángulo", "el triangulo", "los andes",
    # Comuna 2
    "las granjas", "granjas", "san martín", "san martin", "álamos norte", "alamos norte", "álamos", "alamos", "virgilio barco", "villa del prado", "gualanday",
    # Comuna 3
    "centro", "quirinal", "josé eustasio rivera", "jose eustasio", "el lago", "chapinero", "la toma", "av. la toma", "avenida la toma",
    # Comuna 4
    "el malecón", "el malecon", "malecón", "malecon", "mártires", "martires", "san pedro", "sevilla", "estadio", "la gaitana", "gaitana",
    # Comuna 5
    "buganvillas", "jordán", "jordan", "monserrate", "las catleyas", "catleyas", "siete de agosto", "7 de agosto", "kennedy",
    # Comuna 6
    "canaima", "max duque", "pozo azul", "san carlos", "santa isabel", "el limonar", "limonar", "puertas del sol", "encenillo",
    # Comuna 7
    "ipanema", "el vergel", "vergel", "calixto leiva", "calixto", "las brisas", "brisas", "san antonio", "prado alto",
    # Comuna 8
    "las américas", "las americas", "américas", "americas", "acrópolis", "acropolis", "panorama", "alfonso lópez", "alfonso lopez", "la florida",
    # Comuna 9
    "luis carlos galán", "galán", "galan", "alberto galindo", "galindo", "eduardo santos", "darío echandía", "dario echandia",
    # Comuna 10
    "las palmas", "palmas", "el pedregal", "pedregal", "víctor félix", "victor felix", "las camelias", "camelias", "oasis",
    # Corregimientos y Veredas
    "el caguán", "el caguan", "caguán", "caguan", "fortalecillas", "vegalarga", "guacirco", "río de las ceibas", "rio de las ceibas", "san antonio de anaconia",
    # Vías Principales
    "circunvalar", "avenida circunvalar", "carrera 2", "carrera 2da", "carrera 5", "carrera 5ta", "calle 8", "calle 21", "calle 26", "surabastos", "mercaneiva"
]

db = SessionLocal()
cases = db.query(Case).all()

cases_with_evidence = []
for c in cases:
    full_text = f"{c.location or ''} {c.title or ''} {c.content or ''}".lower()
    
    comuna_match = re.search(r'\bcomuna\s*([1-9]|10)\b', full_text)
    
    found_landmarks = []
    for landmark in NEIVA_BARRIOS_CORREGIMIENTOS:
        if re.search(r'\b' + re.escape(landmark) + r'\b', full_text):
            found_landmarks.append(landmark)
            
    if comuna_match or found_landmarks:
        cases_with_evidence.append({
            "id": c.id,
            "title": c.title,
            "content": c.content,
            "category": c.category,
            "comuna_match": comuna_match.group(0) if comuna_match else None,
            "landmarks": found_landmarks
        })

print(f"Total casos auditados: {len(cases)}")
print(f"Casos con EVIDENCIA TEXTUAL Y ARGUMENTAL EXPLÍCITA: {len(cases_with_evidence)}")

for item in cases_with_evidence[:8]:
    clean_content = item['content'].encode('ascii', 'ignore').decode('ascii')
    print(f"[{item['id']}] Categoria: {item['category']}")
    print(f"  Comentario real: \"{clean_content[:90]}...\"")
    print(f"  Evidencia argumental: Comuna: {item['comuna_match']} | Barrios/Hitos: {item['landmarks']}\n")

db.close()
