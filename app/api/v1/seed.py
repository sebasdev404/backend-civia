from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.case import Case
from app.models.incident import Incident
from app.models.citizen import Citizen
from app.models.user import User
from app.core.security import get_password_hash

router = APIRouter(prefix="/seed", tags=["Inicialización de Datos"])

INITIAL_CASES = [
    {
        "id": "CASO-001",
        "source": "Facebook",
        "author": "@JuanPerezNeiva",
        "priority": "Alta",
        "title": "No más abusos con el recibo del agua y cortes de Las Ceibas!",
        "content": "Llevamos 4 días sin suministro regular de agua en el barrio Las Granjas (Comuna 2), Las Ceibas E.S.P. no responde y los cobros siguen llegando altísimos. Si no solucionan hoy bloquearemos la Carrera 2da con Calle 64.",
        "category": "Servicios Públicos",
        "sentiment": "Indignación",
        "location": "Las Granjas - Comuna 2",
        "zone": "comuna-2",
        "date_time": "15 Oct 2026, 14:30",
        "status": "Pendiente",
        "media_type": "video",
        "image_url": "https://images.unsplash.com/photo-1541888086725-3314f2e51927?q=80&w=600&auto=format&fit=crop",
        "impact_if_solved": "Alivia tensión comunitaria inmediata y previene bloqueo de vía arterial norte en Neiva.",
        "impact_if_ignored": "Riesgo inminente de protesta social frente a la sede de Las Ceibas E.S.P.",
    },
    {
        "id": "CASO-002",
        "source": "Instagram",
        "author": "@MariaGomez_Huila",
        "priority": "Baja",
        "title": "Arreglo en Avenida La Toma avanza muy bien",
        "content": "Me parece excelente que la alcaldía esté reparando la calzada de la Avenida La Toma con Carrera 5ta, ya era hora. Ojalá sigan así con el resto de la comuna central.",
        "category": "Infraestructura",
        "sentiment": "Aprobación",
        "location": "Centro - Av. La Toma",
        "zone": "comuna-3",
        "date_time": "15 Oct 2026, 09:15",
        "status": "En Gestión",
        "media_type": "image",
        "image_url": "https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?q=80&w=600&auto=format&fit=crop",
        "impact_if_solved": "Genera validación comunitaria positiva y confianza en obras públicas de Neiva.",
        "impact_if_ignored": "Pérdida de oportunidad mediática para posicionar la gestión de infraestructura vial.",
    },
    {
        "id": "CASO-003",
        "source": "Twitter / X",
        "author": "@NeivaAlerta",
        "priority": "Media",
        "title": "Hurto a mano armada en el sendero del Malecón del Río Magdalena",
        "content": "Asaltaron a varios deportistas en el Malecón cerca del monumento a La Gaitana a plena luz del día. ¿Dónde están los cuadrantes de policía de la Comuna 4?",
        "category": "Seguridad",
        "sentiment": "Preocupación",
        "location": "El Malecón - Comuna 4",
        "zone": "comuna-4",
        "date_time": "14 Oct 2026, 18:45",
        "status": "Pendiente",
        "media_type": "none",
        "image_url": None,
        "impact_if_solved": "Refuerza percepción de patrullaje y seguridad en el principal eje turístico de Neiva.",
        "impact_if_ignored": "Aumento del temor en turistas y desconfianza en la seguridad urbana.",
    },
    {
        "id": "CASO-004",
        "source": "WhatsApp",
        "author": "@LiderCanaimaNeiva",
        "priority": "Alta",
        "title": "Rebosamiento de aguas residuales e inundación en canaleta barrial",
        "content": "Aguas negras ingresaron a más de 14 casas tras las fuertes lluvias de anoche en Canaima. Riesgo fitosanitario crítico para niños y adultos mayores.",
        "category": "Servicios Públicos",
        "sentiment": "Indignación",
        "location": "Canaima - Comuna 6",
        "zone": "comuna-6",
        "date_time": "15 Oct 2026, 15:10",
        "status": "Pendiente",
        "media_type": "image",
        "image_url": "https://images.unsplash.com/photo-1544717305-2782549b5136?q=80&w=600&auto=format&fit=crop",
        "impact_if_solved": "Despliegue de camión vactor de Las Ceibas y prevención de contingencia sanitaria.",
        "impact_if_ignored": "Protesta comunitaria y plantón sobre la Avenida Max Duque.",
    },
    {
        "id": "CASO-005",
        "source": "Facebook",
        "author": "@VeeduriaSaludHuila",
        "priority": "Alta",
        "title": "Colapso en urgencias del Hospital Universitario de Neiva",
        "content": "Pacientes y abuelos esperando más de 7 horas en el Hospital Hernando Moncaleano. No hay insumos suficientes ni camas para pacientes del sur del departamento.",
        "category": "Salud",
        "sentiment": "Alerta",
        "location": "Quirinal - Comuna 3",
        "zone": "comuna-3",
        "date_time": "15 Oct 2026, 11:20",
        "status": "En Gestión",
        "media_type": "video",
        "image_url": "https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?q=80&w=600&auto=format&fit=crop",
        "impact_if_solved": "Articulación con Secretaría de Salud Departamental para descongestionar el centro asistencial.",
        "impact_if_ignored": "Crisis hospitalaria y denuncias ante la Superintendencia Nacional de Salud.",
    },
    {
        "id": "CASO-006",
        "source": "Twitter / X",
        "author": "@NeivaSostenible",
        "priority": "Media",
        "title": "Botadero clandestino de escombros en ronda del Río Las Ceibas",
        "content": "Carretilleros y volquetas arrojan desechos de construcción en la ribera del Río Las Ceibas cerca al barrio San Martín. Afecta la cuenca y el entorno escolar.",
        "category": "Medio Ambiente",
        "sentiment": "Preocupación",
        "location": "San Martín / Río Las Ceibas",
        "zone": "comuna-2",
        "date_time": "14 Oct 2026, 16:30",
        "status": "Pendiente",
        "media_type": "image",
        "image_url": "https://images.unsplash.com/photo-1530587191325-3db32d826c18?q=80&w=600&auto=format&fit=crop",
        "impact_if_solved": "Protección de la fuente hídrica vital de Neiva y operativo conjunto con la CAM.",
        "impact_if_ignored": "Taponamiento del cauce hídrico y proliferación de vertederos ilegales.",
    },
    {
        "id": "CASO-007",
        "source": "Twitter / X",
        "author": "@MovilidadNeivaHoy",
        "priority": "Media",
        "title": "Semáforos apagados en intersección de la Avenida Circunvalar",
        "content": "Cruce de la Circunvalar con Calle 21 sin controladores viales. Trancón monumental hacia el norte y alto peligro de siniestros viales.",
        "category": "Movilidad",
        "sentiment": "Alerta",
        "location": "Cándido Leguízamo - Comuna 1",
        "zone": "comuna-1",
        "date_time": "15 Oct 2026, 12:00",
        "status": "En Gestión",
        "media_type": "none",
        "image_url": None,
        "impact_if_solved": "Restablecimiento de la fluidez en el corredor norte hacia el puente Santander.",
        "impact_if_ignored": "Colapso vehicular en hora pico y siniestros con motociclistas.",
    },
    {
        "id": "CASO-008",
        "source": "Instagram",
        "author": "@VecinosIpanema",
        "priority": "Baja",
        "title": "Alumbrado LED instalado en parque y ciclo-ruta",
        "content": "Agradecemos a la administración por el cambio a luminarias LED en las zonas verdes de Ipanema. El sector quedó mucho más seguro para hacer deporte en la noche.",
        "category": "Infraestructura",
        "sentiment": "Positivo",
        "location": "Ipanema - Comuna 7",
        "zone": "comuna-7",
        "date_time": "14 Oct 2026, 20:15",
        "status": "Resuelto",
        "media_type": "image",
        "image_url": "https://images.unsplash.com/photo-1509114397022-ed747cca3f65?q=80&w=600&auto=format&fit=crop",
        "impact_if_solved": "Incrementa la satisfacción ciudadana y el uso seguro de espacios deportivos nocturnos.",
        "impact_if_ignored": "Sin riesgo inmediato.",
    },
]

INITIAL_INCIDENTS = [
    {
        "id": "CASO-001",
        "lat": 2.9415,
        "lng": -75.2862,
        "title": "Corte prolongado y sobrecostos en tarifa de acueducto Las Ceibas",
        "description": "Comunidad de Las Granjas lleva 4 días sin agua potable por falla en bocatoma del río Las Ceibas y recibos excesivos. Amenaza de bloqueo en la Cra 2da con Cll 64.",
        "category": "Servicios Públicos",
        "priority": "Alta",
        "sentiment": "Indignación",
        "source": "Facebook",
        "neighborhood": "Las Granjas - Comuna 2",
        "zone": "comuna-2",
        "status": "Pendiente",
        "reports_count": 58,
        "date_time": "Hace 20 min",
        "is_new": False,
    },
    {
        "id": "CASO-002",
        "lat": 2.9335,
        "lng": -75.2840,
        "title": "Repavimentación y bacheo en Avenida La Toma",
        "description": "Avanza a buen ritmo el plan de recuperación de la malla vial en La Toma con Cra 5ta. Flujo vehicular asistido por controladores.",
        "category": "Infraestructura",
        "priority": "Baja",
        "sentiment": "Aprobación",
        "source": "Instagram",
        "neighborhood": "Centro - Av. La Toma",
        "zone": "comuna-3",
        "status": "En Gestión",
        "reports_count": 18,
        "date_time": "Hace 1 hora",
        "is_new": False,
    },
    {
        "id": "CASO-003",
        "lat": 2.9285,
        "lng": -75.2935,
        "title": "Hurtos a deportistas y visitantes en el Malecón del Río Magdalena",
        "description": "Comerciantes y deportistas del sendero turístico de La Gaitana solicitan patrullaje policial continuo por robos en horas de la tarde.",
        "category": "Seguridad",
        "priority": "Media",
        "sentiment": "Preocupación",
        "source": "Twitter / X",
        "neighborhood": "El Malecón - Comuna 4",
        "zone": "comuna-4",
        "status": "Pendiente",
        "reports_count": 34,
        "date_time": "Hace 40 min",
        "is_new": False,
    },
    {
        "id": "CASO-004",
        "lat": 2.9062,
        "lng": -75.2848,
        "title": "Rebosamiento de aguas servidas en canaleta barrial",
        "description": "Lluvias torrenciales desbordaron el colector de aguas negras inundando 14 viviendas en Canaima. Riesgo fitosanitario para menores.",
        "category": "Servicios Públicos",
        "priority": "Alta",
        "sentiment": "Indignación",
        "source": "WhatsApp",
        "neighborhood": "Canaima - Comuna 6",
        "zone": "comuna-6",
        "status": "Pendiente",
        "reports_count": 62,
        "date_time": "Hace 12 min",
        "is_new": False,
    },
    {
        "id": "CASO-005",
        "lat": 2.9358,
        "lng": -75.2795,
        "title": "Sobrecupo de urgencias en Hospital Hernando Moncaleano",
        "description": "Largas filas y demoras de más de 6 horas en triaje y falta de medicamentos para usuarios crónicos remitidos de municipios vecinos.",
        "category": "Salud",
        "priority": "Alta",
        "sentiment": "Alerta",
        "source": "Facebook",
        "neighborhood": "Quirinal - Hospital Universitario",
        "zone": "comuna-3",
        "status": "En Gestión",
        "reports_count": 47,
        "date_time": "Hace 1 hora",
        "is_new": False,
    },
    {
        "id": "CASO-006",
        "lat": 2.9380,
        "lng": -75.2780,
        "title": "Disposición clandestina de escombros en ronda del Río Las Ceibas",
        "description": "Carretas y camiones arrojan desechos de obras a la orilla del río poniendo en riesgo el caudal hídrico y zonas verdes escolares.",
        "category": "Medio Ambiente",
        "priority": "Media",
        "sentiment": "Preocupación",
        "source": "Twitter / X",
        "neighborhood": "San Martín / Río Las Ceibas",
        "zone": "comuna-2",
        "status": "Pendiente",
        "reports_count": 26,
        "date_time": "Hace 2 horas",
        "is_new": False,
    },
    {
        "id": "CASO-007",
        "lat": 2.9460,
        "lng": -75.2970,
        "title": "Semáforos descalibrados en Avenida Circunvalar con Calle 21",
        "description": "Falla intermitente en semáforos del corredor norte causa congestión y alto riesgo de choque en el acceso hacia el puente Santander.",
        "category": "Movilidad",
        "priority": "Media",
        "sentiment": "Alerta",
        "source": "Twitter / X",
        "neighborhood": "Cándido Leguízamo - Comuna 1",
        "zone": "comuna-1",
        "status": "En Gestión",
        "reports_count": 29,
        "date_time": "Hace 30 min",
        "is_new": False,
    },
    {
        "id": "CASO-008",
        "lat": 2.9195,
        "lng": -75.2665,
        "title": "Renovación de iluminación LED en parque y ciclo-ruta",
        "description": "Instalación de luminarias LED completada en el sector residencial de Ipanema. Vecinos resaltan mayor visibilidad y seguridad.",
        "category": "Infraestructura",
        "priority": "Baja",
        "sentiment": "Positivo",
        "source": "Instagram",
        "neighborhood": "Ipanema - Comuna 7",
        "zone": "comuna-7",
        "status": "Resuelto",
        "reports_count": 11,
        "date_time": "Hace 4 horas",
        "is_new": False,
    },
]

DEFAULT_USERS = [
    {
        "id": "USR-001",
        "email": "alcalde@civia.gov.co",
        "full_name": "Johan Steed",
        "role": "ALCALDE",
        "department": "Despacho del Alcalde",
        "password": "civia2026",
    },
    {
        "id": "USR-002",
        "email": "secretario@civia.gov.co",
        "full_name": "Dra. Camila Morales",
        "role": "SECRETARIO",
        "department": "Secretaría de Movilidad y Servicios",
        "password": "civia2026",
    },
    {
        "id": "USR-003",
        "email": "operador@civia.gov.co",
        "full_name": "Carlos Mendoza",
        "role": "OPERADOR",
        "department": "Centro de Atención y Respuesta Ciudadana",
        "password": "civia2026",
    },
]

def run_seed(db: Session):
    cases_added = 0
    incidents_added = 0
    users_added = 0

    for u in DEFAULT_USERS:
        existing_user = db.query(User).filter(User.email == u["email"]).first()
        if not existing_user:
            hashed_pw = get_password_hash(u["password"])
            new_u = User(
                id=u["id"],
                email=u["email"],
                full_name=u["full_name"],
                role=u["role"],
                department=u["department"],
                hashed_password=hashed_pw,
                is_active=True,
            )
            db.add(new_u)
            users_added += 1

    for c in INITIAL_CASES:
        existing_case = db.query(Case).filter(Case.id == c["id"]).first()
        if not existing_case:
            db.add(Case(**c))
            cases_added += 1
        else:
            for k, v in c.items():
                setattr(existing_case, k, v)
            cases_added += 1

    for inc in INITIAL_INCIDENTS:
        existing_inc = db.query(Incident).filter(Incident.id == inc["id"]).first()
        if not existing_inc:
            db.add(Incident(**inc))
            incidents_added += 1
        else:
            for k, v in inc.items():
                setattr(existing_inc, k, v)
            incidents_added += 1

    db.commit()
    return {"cases_added": cases_added, "incidents_added": incidents_added, "users_added": users_added}

@router.post("", status_code=status.HTTP_200_OK)
def seed_database(db: Session = Depends(get_db)):
    result = run_seed(db)
    return {
        "status": "success",
        "message": f"Base de datos sembrada con éxito: {result['users_added']} usuarios, {result['cases_added']} casos, {result['incidents_added']} incidentes añadidos.",
        "details": result
    }

