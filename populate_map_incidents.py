"""
Script para poblar la tabla incidents con incidentes georreferenciados realistas
distribuidos en las 10 comunas de Neiva y corregimientos.
"""
import random
from datetime import datetime, timedelta
from app.core.database import SessionLocal, engine, Base
from app.models.incident import Incident

Base.metadata.create_all(bind=engine)

COMUNAS_DATA = {
    'comuna-1': {
        'name': 'Comuna 1 (Norte)',
        'center': (2.9480, -75.2950),
        'barrios': ['Cándido Leguízamo', 'Santa Inés', 'Chicalá', 'Camilo Torres', 'El Triángulo', 'Los Andes'],
        'count': 13
    },
    'comuna-2': {
        'name': 'Comuna 2 (Noroccidente)',
        'center': (2.9420, -75.2850),
        'barrios': ['Las Granjas', 'San Martín', 'Los Andes Norte', 'Álamos Norte', 'Virgilio Barco', 'Villa del Prado'],
        'count': 14
    },
    'comuna-3': {
        'name': 'Comuna 3 (Centro)',
        'center': (2.9340, -75.2820),
        'barrios': ['Centro', 'Quirinal', 'José Eustasio Rivera', 'El Lago', 'Chapinero', 'Av. La Toma'],
        'count': 16
    },
    'comuna-4': {
        'name': 'Comuna 4 (Occidente)',
        'center': (2.9290, -75.2890),
        'barrios': ['El Malecón', 'Mártires', 'San Pedro', 'Sevilla', 'Estadio', 'La Gaitana'],
        'count': 12
    },
    'comuna-5': {
        'name': 'Comuna 5 (Oriente)',
        'center': (2.9320, -75.2720),
        'barrios': ['Buganvillas', 'Jordán', 'Monserrate', 'Las Catleyas', 'Siete de Agosto', 'Kennedy'],
        'count': 12
    },
    'comuna-6': {
        'name': 'Comuna 6 (Sur)',
        'center': (2.9050, -75.2850),
        'barrios': ['Canaima', 'Max Duque', 'Pozo Azul', 'San Carlos', 'Santa Isabel', 'El Limonar', 'Puertas del Sol'],
        'count': 15
    },
    'comuna-7': {
        'name': 'Comuna 7 (Suroriente)',
        'center': (2.9180, -75.2680),
        'barrios': ['Ipanema', 'El Vergel', 'Calixto Leiva', 'Las Brisas', 'San Antonio', 'Prado Alto'],
        'count': 13
    },
    'comuna-8': {
        'name': 'Comuna 8 (Suroriente Alto)',
        'center': (2.9230, -75.2600),
        'barrios': ['Las Américas', 'Acrópolis', 'Panorama', 'Alfonso López', 'La Florida'],
        'count': 12
    },
    'comuna-9': {
        'name': 'Comuna 9 (Norte Alto)',
        'center': (2.9600, -75.2920),
        'barrios': ['Luis Carlos Galán', 'Alberto Galindo', 'Eduardo Santos', 'Darío Echandía', 'Vicente Araújo'],
        'count': 11
    },
    'comuna-10': {
        'name': 'Comuna 10 (Oriente Alto)',
        'center': (2.9380, -75.2620),
        'barrios': ['Las Palmas', 'El Pedregal', 'Víctor Félix', 'Las Camelias', 'Oasis', 'Neiva Ya'],
        'count': 12
    },
    'caguan': {
        'name': 'Corregimientos',
        'center': (2.8600, -75.2750),
        'barrios': ['El Caguán Centro', 'Fortalecillas', 'Vegalarga', 'Ronda Río Las Ceibas'],
        'count': 8
    }
}

INCIDENT_TEMPLATES = [
    {
        'category': 'Infraestructura',
        'title': 'Deterioro vial severo y baches profundos',
        'description': 'Huecos de gran tamaño en la calzada vehicular dificultan el paso y han causado daños mecánicos en vehículos y caídas de motociclistas.',
        'priorities': ['Alta', 'Media'],
        'sentiments': ['Indignación', 'Preocupación'],
    },
    {
        'category': 'Infraestructura',
        'title': 'Hundimiento de calzada y alcantarilla colapsada',
        'description': 'Se presenta asentamiento del asfalto cerca a la red de drenaje pluvial con riesgo de socavación y colapso de la vía.',
        'priorities': ['Alta'],
        'sentiments': ['Alerta', 'Indignación'],
    },
    {
        'category': 'Servicios Públicos',
        'title': 'Fuga de agua potable en red matriz Las Ceibas',
        'description': 'Derrame de miles de litros de agua potable en plena vía pública desde hace más de 48 horas sin atención de la cuadrilla técnica.',
        'priorities': ['Alta'],
        'sentiments': ['Indignación', 'Alerta'],
    },
    {
        'category': 'Servicios Públicos',
        'title': 'Baja presión continua y cortes sin previo aviso',
        'description': 'Vecinos denuncian intermitencia en el suministro de agua y desabastecimiento en pisos altos durante las mañanas.',
        'priorities': ['Media', 'Baja'],
        'sentiments': ['Preocupación', 'Neutral'],
    },
    {
        'category': 'Servicios Públicos',
        'title': 'Rebosamiento de aguas servidas en colector barrial',
        'description': 'Malos olores y desbordamiento de aguas residuales sobre la vía afectando a viviendas y locales comerciales.',
        'priorities': ['Alta'],
        'sentiments': ['Indignación', 'Alerta'],
    },
    {
        'category': 'Movilidad',
        'title': 'Semáforos averiados en cruce principal',
        'description': 'Dispositivos semafóricos apagados o en amarillo intermitente generan fuerte congestión vehicular y riesgo inminente de colisión.',
        'priorities': ['Alta', 'Media'],
        'sentiments': ['Alerta', 'Preocupación'],
    },
    {
        'category': 'Movilidad',
        'title': 'Falta de señalización vial y reductores de velocidad',
        'description': 'Comunidad solicita instalación de reductores frente a parque y zona escolar por exceso de velocidad de automotores.',
        'priorities': ['Media', 'Baja'],
        'sentiments': ['Preocupación', 'Neutral'],
    },
    {
        'category': 'Seguridad',
        'title': 'Solicitud de patrullaje policial por hurtos recurrentes',
        'description': 'Comerciantes y residentes reportan atracos a mano armada en horas de la tarde y noche, exigiendo presencia de cuadrantes.',
        'priorities': ['Alta', 'Media'],
        'sentiments': ['Alerta', 'Indignación'],
    },
    {
        'category': 'Alumbrado Público',
        'title': 'Luminarias LED apagadas en parque comunitario',
        'description': 'Sector a oscuras por fallas en el circuito de alumbrado público, facilitando hechos de delincuencia y consumo de sustancias.',
        'priorities': ['Media', 'Baja'],
        'sentiments': ['Preocupación', 'Neutral'],
    },
    {
        'category': 'Medio Ambiente',
        'title': 'Arrojo clandestino de escombros y basuras',
        'description': 'Inescrupulosos convirtieron lote comunal en botadero a cielo abierto con proliferación de roedores y malos olores.',
        'priorities': ['Media'],
        'sentiments': ['Indignación', 'Preocupación'],
    },
    {
        'category': 'Salud',
        'title': 'Demoras en atención y triaje en centro de salud',
        'description': 'Pacientes reportan esperas de más de 4 horas para atención de urgencias y falta de medicamentos básicos.',
        'priorities': ['Media', 'Alta'],
        'sentiments': ['Preocupación', 'Alerta'],
    },
]

def generate_incidents():
    db = SessionLocal()
    # Limpiar tabla de incidents actual para regenerar completo
    db.query(Incident).delete()
    db.commit()

    total_created = 0
    idx = 1

    for zone_key, zone_info in COMUNAS_DATA.items():
        center_lat, center_lng = zone_info['center']
        barrios = zone_info['barrios']
        count = zone_info['count']

        for _ in range(count):
            tpl = random.choice(INCIDENT_TEMPLATES)
            barrio = random.choice(barrios)
            
            # Variación geográfica pequeña alrededor del centro de la comuna
            # ~0.007 grados es aprox 750 metros
            lat = round(center_lat + random.uniform(-0.006, 0.006), 5)
            lng = round(center_lng + random.uniform(-0.006, 0.006), 5)

            prio = random.choice(tpl['priorities'])
            sentiment = random.choice(tpl['sentiments'])
            source = random.choice(['Facebook', 'Facebook', 'Instagram'])
            status = random.choice(['Pendiente', 'Pendiente', 'En Gestión', 'Resuelto'])
            reports = random.randint(12, 85)

            mins_ago = random.randint(5, 720)
            if mins_ago < 60:
                time_str = f"Hace {mins_ago} min"
            elif mins_ago < 1440:
                time_str = f"Hace {mins_ago // 60} horas"
            else:
                time_str = "Ayer"

            inc_id = f"CASO-{str(idx).zfill(3)}"
            idx += 1

            inc = Incident(
                id=inc_id,
                lat=lat,
                lng=lng,
                title=f"{tpl['title']} en {barrio}",
                description=f"{tpl['description']} Sector: {barrio} ({zone_info['name']}).",
                category=tpl['category'],
                priority=prio,
                sentiment=sentiment,
                source=source,
                neighborhood=f"{barrio} ({zone_info['name']})",
                zone=zone_key,
                status=status,
                reports_count=reports,
                date_time=time_str,
                is_new=mins_ago < 60,
                created_at=datetime.now() - timedelta(minutes=mins_ago)
            )
            db.add(inc)
            total_created += 1

    db.commit()
    db.close()
    print(f"Exito: Se crearon {total_created} incidentes territoriales en todas las 10 comunas de Neiva.")

if __name__ == '__main__':
    generate_incidents()
