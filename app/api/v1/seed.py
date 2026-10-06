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
        "author": "@JuanPerezCol",
        "priority": "Alta",
        "title": "No más abusos con el recibo del agua!",
        "content": "Llevamos 3 semanas sin suministro regular de agua en el barrio Los Pinos, la alcaldía no responde y los cobros siguen llegando altísimos. Si no solucionan hoy bloquearemos la vía principal.",
        "category": "Servicios Públicos",
        "sentiment": "Indignación",
        "location": "Los Pinos - Centro",
        "zone": "centro",
        "date_time": "15 Oct 2026, 14:30",
        "status": "Pendiente",
        "media_type": "video",
        "image_url": "https://images.unsplash.com/photo-1541888086725-3314f2e51927?q=80&w=600&auto=format&fit=crop",
        "impact_if_solved": "Alivia tensión comunitaria inmediata y previene bloqueo de vía arterial.",
        "impact_if_ignored": "Riesgo inminente de protesta social; capitalización por la oposición local.",
    },
    {
        "id": "CASO-002",
        "source": "Instagram",
        "author": "@MariaGomez_99",
        "priority": "Baja",
        "title": "Arreglo en la Carrera 5ta avanza muy bien",
        "content": "Me parece excelente que estén reparando los huecos de la carrera 5ta, ya era hora. Ojalá sigan así con el resto de la comuna central.",
        "category": "Infraestructura",
        "sentiment": "Aprobación",
        "location": "Centro - Carrera 5ta",
        "zone": "chapinero",
        "date_time": "15 Oct 2026, 09:15",
        "status": "En Gestión",
        "media_type": "image",
        "image_url": "https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?q=80&w=600&auto=format&fit=crop",
        "impact_if_solved": "Genera validación comunitaria positiva y confianza en obras públicas.",
        "impact_if_ignored": "Pérdida de oportunidad mediática para posicionar la gestión.",
    },
    {
        "id": "CASO-003",
        "source": "Twitter / X",
        "author": "@CiudadanoAlerta",
        "priority": "Media",
        "title": "Robo a plena luz del día en el parque principal",
        "content": "Robaron a otra persona en el parque principal a plena luz del día frente a los niños. ¿Dónde están los cuadrantes de policía?",
        "category": "Seguridad",
        "sentiment": "Preocupación",
        "location": "Parque Principal Usaquén",
        "zone": "usaquen",
        "date_time": "14 Oct 2026, 18:45",
        "status": "Pendiente",
        "media_type": "none",
        "image_url": None,
        "impact_if_solved": "Refuerza percepción de patrullaje y seguridad ciudadana inmediata.",
        "impact_if_ignored": "Aumento del miedo colectivo y desconfianza en la policía local.",
    },
    {
        "id": "CASO-004",
        "source": "WhatsApp",
        "author": "@LiderComunitarioKennedy",
        "priority": "Alta",
        "title": "Desbordamiento de alcantarillado e inundación de viviendas",
        "content": "Aguas servidas ingresaron a más de 12 casas tras fuertes aguaceros. Riesgo sanitario crítico para niños y adultos mayores.",
        "category": "Servicios Públicos",
        "sentiment": "Indignación",
        "location": "El Tintal - Kennedy",
        "zone": "kennedy",
        "date_time": "15 Oct 2026, 12:10",
        "status": "Pendiente",
        "media_type": "image",
        "image_url": "https://images.unsplash.com/photo-1544717305-2782549b5136?q=80&w=600&auto=format&fit=crop",
        "impact_if_solved": "Evita epidemia de salud pública y mitiga emergencia invernal barrial.",
        "impact_if_ignored": "Demandas por daños y perjuicios al acueducto distrital.",
    },
    {
        "id": "CASO-005",
        "source": "Facebook",
        "author": "@VeeduriaSaludSur",
        "priority": "Alta",
        "title": "Filas de 5 horas sin entrega de medicamentos para hipertensión",
        "content": "Abuelos esperando desde las 4 AM en el centro de salud de La Victoria. No hay medicamentos básicos desde hace 10 días.",
        "category": "Salud",
        "sentiment": "Alerta",
        "location": "La Victoria - San Cristóbal",
        "zone": "sancristobal",
        "date_time": "15 Oct 2026, 10:20",
        "status": "En Gestión",
        "media_type": "video",
        "image_url": "https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?q=80&w=600&auto=format&fit=crop",
        "impact_if_solved": "Restaura la atención primaria y apacigua el clamor de adultos mayores.",
        "impact_if_ignored": "Desencadena denuncias ante la superintendencia de salud.",
    },
    {
        "id": "CASO-006",
        "source": "Twitter / X",
        "author": "@MovilidadBogotaReal",
        "priority": "Media",
        "title": "Semáforos apagados en intersección de alta congestión",
        "content": "Cruce de la Calle 67 con Cra 7ma sin luces de tránsito. Ya van dos choques simples y trancón de más de 40 minutos.",
        "category": "Movilidad",
        "sentiment": "Alerta",
        "location": "Chapinero Norte",
        "zone": "chapinero",
        "date_time": "15 Oct 2026, 13:05",
        "status": "En Gestión",
        "media_type": "none",
        "image_url": None,
        "impact_if_solved": "Descongestiona el corredor oriental y previene accidentes fatales.",
        "impact_if_ignored": "Colapso de transporte público y reclamos masivos en redes.",
    },
    {
        "id": "CASO-007",
        "source": "Twitter / X",
        "author": "@SubaLimpiaYa",
        "priority": "Media",
        "title": "Escombros y basuras en separador escolar",
        "content": "Arrojo clandestino de deshechos de demolición frente al colegio distrital. Genera focos de roedores e inseguridad para estudiantes.",
        "category": "Medio Ambiente",
        "sentiment": "Preocupación",
        "location": "Rincón de Suba",
        "zone": "suba",
        "date_time": "14 Oct 2026, 16:30",
        "status": "Pendiente",
        "media_type": "image",
        "image_url": "https://images.unsplash.com/photo-1530587191325-3db32d826c18?q=80&w=600&auto=format&fit=crop",
        "impact_if_solved": "Recupera espacio público escolar y previene plagas.",
        "impact_if_ignored": "Consolidación de punto crítico de basura crónico.",
    },
    {
        "id": "CASO-008",
        "source": "Instagram",
        "author": "@VecinosTeusaquillo",
        "priority": "Baja",
        "title": "Luminarias reparadas en el Parkway",
        "content": "Agradecemos a la cuadrilla de alumbrado público por el cambio de bombillas en el sendero peatonal. Quedó muy iluminado.",
        "category": "Infraestructura",
        "sentiment": "Positivo",
        "location": "Parkway - Teusaquillo",
        "zone": "centro",
        "date_time": "14 Oct 2026, 21:00",
        "status": "Resuelto",
        "media_type": "image",
        "image_url": "https://images.unsplash.com/photo-1509114397022-ed747cca3f65?q=80&w=600&auto=format&fit=crop",
        "impact_if_solved": "Mayor seguridad nocturna y fidelización ciudadana.",
        "impact_if_ignored": "Sin riesgo inmediato.",
    },
]

INITIAL_INCIDENTS = [
    {
        "id": "CASO-001",
        "lat": 4.6097,
        "lng": -74.0817,
        "title": "No más abusos con el recibo del agua",
        "description": "Comunidad lleva 3 semanas sin suministro regular de agua y cobros excesivos. Amenaza de bloqueo de vía principal.",
        "category": "Servicios Públicos",
        "priority": "Alta",
        "sentiment": "Indignación",
        "source": "Facebook",
        "neighborhood": "Barrio Los Pinos",
        "zone": "centro",
        "status": "Pendiente",
        "reports_count": 42,
        "date_time": "Hace 25 min",
        "is_new": False,
    },
    {
        "id": "CASO-002",
        "lat": 4.6486,
        "lng": -74.0628,
        "title": "Obras y baches en la Carrera 5ta",
        "description": "Avanzan reparaciones de la malla vial, conductores reportan desvíos bien señalizados pero tráfico lento.",
        "category": "Infraestructura",
        "priority": "Baja",
        "sentiment": "Aprobación",
        "source": "Instagram",
        "neighborhood": "Centro - Cra 5ta",
        "zone": "chapinero",
        "status": "En Gestión",
        "reports_count": 15,
        "date_time": "Hace 2 horas",
        "is_new": False,
    },
    {
        "id": "CASO-003",
        "lat": 4.6763,
        "lng": -74.0483,
        "title": "Atraco a mano armada en parque vecinal",
        "description": "Vecinos solicitan patrullaje urgente tras asalto a comerciantes en la zona comercial del parque.",
        "category": "Seguridad",
        "priority": "Media",
        "sentiment": "Preocupación",
        "source": "Twitter / X",
        "neighborhood": "Parque Principal Usaquén",
        "zone": "usaquen",
        "status": "Pendiente",
        "reports_count": 28,
        "date_time": "Hace 45 min",
        "is_new": False,
    },
    {
        "id": "CASO-004",
        "lat": 4.6280,
        "lng": -74.1350,
        "title": "Desbordamiento de alcantarillado e inundación",
        "description": "Aguas servidas ingresaron a 12 viviendas tras fuertes lluvias. Riesgo de salubridad infantil.",
        "category": "Servicios Públicos",
        "priority": "Alta",
        "sentiment": "Indignación",
        "source": "WhatsApp",
        "neighborhood": "El Tintal - Kennedy",
        "zone": "kennedy",
        "status": "Pendiente",
        "reports_count": 56,
        "date_time": "Hace 10 min",
        "is_new": False,
    },
    {
        "id": "CASO-005",
        "lat": 4.5720,
        "lng": -74.0950,
        "title": "Escasez de insumos en puesto de salud",
        "description": "Filas de adultos mayores desde las 4 AM sin entrega de medicamentos vitales para hipertensión.",
        "category": "Salud",
        "priority": "Alta",
        "sentiment": "Alerta",
        "source": "Facebook",
        "neighborhood": "La Victoria - San Cristóbal",
        "zone": "sancristobal",
        "status": "En Gestión",
        "reports_count": 33,
        "date_time": "Hace 1 hora",
        "is_new": False,
    },
    {
        "id": "CASO-006",
        "lat": 4.7350,
        "lng": -74.0850,
        "title": "Botadero de escombros en separador vial",
        "description": "Carretilleros arrojan desechos de construcción bloqueando el paso peatonal escolar.",
        "category": "Medio Ambiente",
        "priority": "Media",
        "sentiment": "Preocupación",
        "source": "Twitter / X",
        "neighborhood": "Rincón de Suba",
        "zone": "suba",
        "status": "Pendiente",
        "reports_count": 19,
        "date_time": "Hace 3 horas",
        "is_new": False,
    },
    {
        "id": "CASO-007",
        "lat": 4.6550,
        "lng": -74.0580,
        "title": "Semáforos apagados en intersección crítica",
        "description": "Cruce de la Calle 67 con Carrera 7ma sin controladores viales, alta congestión y riesgo de colisión.",
        "category": "Movilidad",
        "priority": "Media",
        "sentiment": "Alerta",
        "source": "Twitter / X",
        "neighborhood": "Chapinero Norte",
        "zone": "chapinero",
        "status": "En Gestión",
        "reports_count": 22,
        "date_time": "Hace 35 min",
        "is_new": False,
    },
    {
        "id": "CASO-008",
        "lat": 4.6390,
        "lng": -74.0720,
        "title": "Luminarias recuperadas en plazoleta",
        "description": "Intervención exitosa de la empresa de energía restableció la iluminación tras reporte ciudadano.",
        "category": "Infraestructura",
        "priority": "Baja",
        "sentiment": "Positivo",
        "source": "Instagram",
        "neighborhood": "Parkway - Teusaquillo",
        "zone": "centro",
        "status": "Resuelto",
        "reports_count": 9,
        "date_time": "Hace 5 horas",
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
        if not db.query(Case).filter(Case.id == c["id"]).first():
            db.add(Case(**c))
            cases_added += 1

    for inc in INITIAL_INCIDENTS:
        if not db.query(Incident).filter(Incident.id == inc["id"]).first():
            db.add(Incident(**inc))
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

