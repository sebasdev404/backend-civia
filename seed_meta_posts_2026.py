import json
from datetime import datetime
from app.core.database import SessionLocal, Base, engine
from app.models.meta_post import MetaPost
from app.models.case import Case

Base.metadata.create_all(bind=engine)

SAMPLE_POSTS_2026 = [
    # --- OCTUBRE 2026 ---
    {
        "id": "POST-2026-1001",
        "month_key": "2026-10",
        "published_at": "13 Oct 2026, 10:44 AM",
        "created_time": "2026-10-13T10:44:00+0000",
        "title": "Intervención de controladores viales y semaforización en la Avenida La Toma",
        "message": "Supervisamos en terreno el nuevo sistema de controladores inteligentes para mitigar los trancones en las horas pico. Neiva avanza hacia una movilidad más digna y segura.",
        "media_type": "video",
        "cover_image": "https://images.unsplash.com/photo-1541888086725-3314f2e51927?q=80&w=700&auto=format&fit=crop",
        "permalink_url": "https://facebook.com/johansteed/posts/1001",
        "likes_count": 342,
        "views_count": 4820,
        "shares_count": 67,
        "raw_comments": [
            {"id": "RC-101", "author": "@carlos_neiva", "message": "Aguántese un semáforo al mediodía en la toma con 5ta, es imposible pasar.", "time": "13 Oct 2026, 11:00 AM", "is_meaningful": True},
            {"id": "RC-102", "author": "@maritza_rivera", "message": "Por favor sincronizar los de la carrera 7ma también, excelente gestión.", "time": "13 Oct 2026, 11:25 AM", "is_meaningful": True},
            {"id": "RC-103", "author": "@veedor_vial", "message": "Falta cuadrilla técnica permanente para atender fallas por lluvias.", "time": "13 Oct 2026, 11:50 AM", "is_meaningful": True}
        ],
        "cases": [
            {
                "id": "CIV-2026-1001",
                "institutional_radicado": "RAD-MOV-2026-0001",
                "source": "Facebook Oficial - Johan Steed",
                "author": "Carlos Mendoza",
                "priority": "Alta",
                "title": "Movilidad: Desincronización crítica de semáforos en la Toma con Cra 5ta",
                "content": "Aguántese un semáforo al mediodía en la toma con 5ta, es imposible pasar y los trancones llegan hasta la carrera 2da.",
                "category": "Movilidad",
                "sentiment": "Crítico",
                "location": "Centro - Av. La Toma con Cra 5ta (Comuna 3)",
                "zone": "comuna-3",
                "date_time": "13 Oct 2026, 10:44 AM",
                "status": "Pendiente",
                "media_type": "video",
                "impact_if_solved": "Optimización del flujo vehicular y reducción de tiempos de espera en un 35%.",
                "impact_if_ignored": "Riesgo de colapso en la arteria central de Neiva y accidentes viales.",
                "assigned_department": "Secretaría de Movilidad y Tránsito",
                "assigned_to": "Técnicos de Semaforización Neiva",
                "priority_action": True,
                "comments_count": 3
            }
        ]
    },
    {
        "id": "POST-2026-1002",
        "month_key": "2026-10",
        "published_at": "11 Oct 2026, 04:30 PM",
        "created_time": "2026-10-11T16:30:00+0000",
        "title": "Plan de Choque de Repavimentación y Parcheo en Comunas 2 y 6",
        "message": "Maquinaria pesada activa en Las Granjas y Canaima. Estamos recuperando las vías que por años estuvieron en el olvido.",
        "media_type": "image",
        "cover_image": "https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?q=80&w=700&auto=format&fit=crop",
        "permalink_url": "https://facebook.com/johansteed/posts/1002",
        "likes_count": 512,
        "views_count": 6200,
        "shares_count": 94,
        "raw_comments": [
            {"id": "RC-201", "author": "@vecino_lasgranjas", "message": "En la calle 64 con 2da hay un cráter que ya tumbó a dos motociclistas.", "time": "11 Oct 2026, 05:10 PM", "is_meaningful": True},
            {"id": "RC-202", "author": "@lina_fernanda", "message": "Excelente alcalde, pero no olviden la entrada a Los Andes Norte.", "time": "11 Oct 2026, 05:40 PM", "is_meaningful": True}
        ],
        "cases": [
            {
                "id": "CIV-2026-1002",
                "institutional_radicado": "RAD-INF-2026-0045",
                "source": "Facebook Oficial - Johan Steed",
                "author": "Comunidad Las Granjas",
                "priority": "Alta",
                "title": "Infraestructura: Hueco profundo en vía arterial Calle 64 con Cra 2da",
                "content": "En la calle 64 con 2da hay un cráter que ya tumbó a dos motociclistas, solicitamos intervención con mezcla asfáltica inmediata.",
                "category": "Infraestructura",
                "sentiment": "Indignación",
                "location": "Las Granjas (Comuna 2)",
                "zone": "comuna-2",
                "date_time": "11 Oct 2026, 04:30 PM",
                "status": "En Gestión",
                "media_type": "image",
                "impact_if_solved": "Previene siniestros viales de motociclistas y restablece transitabilidad.",
                "impact_if_ignored": "Alta probabilidad de bloqueo comunal en acceso a la Comuna 2.",
                "assigned_department": "Secretaría de Infraestructura y Vías",
                "assigned_to": "Ing. Mauricio Perdomo - Cuadrilla Malla Vial",
                "priority_action": True,
                "comments_count": 4
            }
        ]
    },
    # --- SEPTIEMBRE 2026 ---
    {
        "id": "POST-2026-0901",
        "month_key": "2026-09",
        "published_at": "24 Sep 2026, 09:15 AM",
        "created_time": "2026-09-24T09:15:00+0000",
        "title": "Modernización de Redes de Acueducto con Las Ceibas E.S.P.",
        "message": "Instalación de nuevas válvulas de presión para estabilizar el suministro continuo en los sectores altos de Neiva.",
        "media_type": "image",
        "cover_image": "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?q=80&w=700&auto=format&fit=crop",
        "permalink_url": "https://facebook.com/johansteed/posts/0901",
        "likes_count": 420,
        "views_count": 5100,
        "shares_count": 45,
        "raw_comments": [
            {"id": "RC-301", "author": "@alvaro_corte", "message": "Llevamos 3 días con baja presión en Ipanema Comuna 7.", "time": "24 Sep 2026, 10:00 AM", "is_meaningful": True}
        ],
        "cases": [
            {
                "id": "CIV-2026-0901",
                "institutional_radicado": "RAD-ESP-2026-0120",
                "source": "Facebook Oficial - Johan Steed",
                "author": "Álvaro Morales",
                "priority": "Alta",
                "title": "Servicios Públicos: Baja presión sostenida de agua en Barrio Ipanema",
                "content": "Llevamos 3 días con baja presión en Ipanema Comuna 7, no sube agua a los segundos pisos.",
                "category": "Servicios Públicos",
                "sentiment": "Preocupado",
                "location": "Ipanema (Comuna 7)",
                "zone": "comuna-7",
                "date_time": "24 Sep 2026, 09:15 AM",
                "status": "Resuelto",
                "media_type": "image",
                "impact_if_solved": "Garantiza acceso al mínimo vital de agua en 380 hogares.",
                "impact_if_ignored": "Cobro de tarifas sin prestación efectiva del servicio.",
                "assigned_department": "Las Ceibas - Empresas Públicas de Neiva E.S.P.",
                "assigned_to": "Cuadrilla 2 - Presión y Válvulas",
                "priority_action": False,
                "comments_count": 2
            }
        ]
    },
    # --- AGOSTO 2026 ---
    {
        "id": "POST-2026-0801",
        "month_key": "2026-08",
        "published_at": "18 Ago 2026, 07:00 PM",
        "created_time": "2026-08-18T19:00:00+0000",
        "title": "Iluminación LED y Seguridad en Parques de la Comuna 10 y Comuna 8",
        "message": "Cambiamos más de 120 luminarias de sodio por tecnología LED de alta potencia. Espacios más seguros para nuestras familias.",
        "media_type": "image",
        "cover_image": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?q=80&w=700&auto=format&fit=crop",
        "permalink_url": "https://facebook.com/johansteed/posts/0801",
        "likes_count": 680,
        "views_count": 7900,
        "shares_count": 112,
        "raw_comments": [
            {"id": "RC-401", "author": "@patricia_palmas", "message": "En Las Palmas parque principal quedaron 2 postes apagados.", "time": "18 Ago 2026, 08:30 PM", "is_meaningful": True}
        ],
        "cases": [
            {
                "id": "CIV-2026-0801",
                "institutional_radicado": "RAD-ALU-2026-0089",
                "source": "Facebook Oficial - Johan Steed",
                "author": "Junta Comunal Las Palmas",
                "priority": "Media",
                "title": "Alumbrado: Falla en luminarias LED sector polideportivo Las Palmas",
                "content": "En Las Palmas parque principal quedaron 2 postes apagados, la zona queda oscura después de las 7pm.",
                "category": "Alumbrado Público",
                "sentiment": "Preocupado",
                "location": "Las Palmas (Comuna 10)",
                "zone": "comuna-10",
                "date_time": "18 Ago 2026, 07:00 PM",
                "status": "Resuelto",
                "media_type": "image",
                "impact_if_solved": "Espacio seguro para deporte infantil y reactivación comunitaria.",
                "impact_if_ignored": "Punto ciego propicio para consumo y hurtos.",
                "assigned_department": "Alumbrado Público Neiva - ESIP",
                "assigned_to": "Cuadrilla Nocturna ESIP",
                "priority_action": False,
                "comments_count": 3
            }
        ]
    },
    # --- JULIO 2026 ---
    {
        "id": "POST-2026-0701",
        "month_key": "2026-07",
        "published_at": "12 Jul 2026, 11:30 AM",
        "created_time": "2026-07-12T11:30:00+0000",
        "title": "Consejo Extraordinario de Seguridad: Operativos en Comunas 1 y 9",
        "message": "Articulamos con Policía y Ejército patrullajes mixtos en los corredores críticos del norte de la ciudad.",
        "media_type": "video",
        "cover_image": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?q=80&w=700&auto=format&fit=crop",
        "permalink_url": "https://facebook.com/johansteed/posts/0701",
        "likes_count": 890,
        "views_count": 10400,
        "shares_count": 180,
        "raw_comments": [
            {"id": "RC-501", "author": "@candido_seguro", "message": "Necesitamos presencia constante en el puente peatonal del Chicalá.", "time": "12 Jul 2026, 12:15 PM", "is_meaningful": True}
        ],
        "cases": [
            {
                "id": "CIV-2026-0701",
                "institutional_radicado": "RAD-GOB-2026-0312",
                "source": "Facebook Oficial - Johan Steed",
                "author": "Veeduría Comuna 1",
                "priority": "Crítica",
                "title": "Seguridad: Solicitud de cuadrante fijo en puente peatonal Chicalá",
                "content": "Reiterados atracos a estudiantes en el puente peatonal del Chicalá sobre la carrera 1ra.",
                "category": "Seguridad",
                "sentiment": "Indignación",
                "location": "Chicalá (Comuna 1)",
                "zone": "comuna-1",
                "date_time": "12 Jul 2026, 11:30 AM",
                "status": "En Gestión",
                "media_type": "video",
                "impact_if_solved": "Protección de más de 1200 estudiantes universitarios y escolares diarios.",
                "impact_if_ignored": "Incremento de hurtos violentos en corredor educativo norte.",
                "assigned_department": "Secretaría de Gobierno y Convivencia",
                "assigned_to": "Coronel Silva - Cuadrante Policía Estación Norte",
                "priority_action": True,
                "comments_count": 5
            }
        ]
    },
    # --- JUNIO 2026 ---
    {
        "id": "POST-2026-0601",
        "month_key": "2026-06",
        "published_at": "20 Jun 2026, 03:00 PM",
        "created_time": "2026-06-20T15:00:00+0000",
        "title": "Fiestas de San Juan y San Pedro: Dispositivo de Tránsito y Control",
        "message": "Garantizamos rutas seguras para turistas y neivanos durante el desfile folclórico por la Avenida Circunvalar.",
        "media_type": "image",
        "cover_image": "https://images.unsplash.com/photo-1533174072545-7a4b6ad7a6c3?q=80&w=700&auto=format&fit=crop",
        "permalink_url": "https://facebook.com/johansteed/posts/0601",
        "likes_count": 1250,
        "views_count": 15600,
        "shares_count": 310,
        "raw_comments": [
            {"id": "RC-601", "author": "@turismo_huila", "message": "Muy buen dispositivo, pero controlar el parqueo indebido en la carrera 2da.", "time": "20 Jun 2026, 04:00 PM", "is_meaningful": True}
        ],
        "cases": [
            {
                "id": "CIV-2026-0601",
                "institutional_radicado": "RAD-MOV-2026-0420",
                "source": "Facebook Oficial - Johan Steed",
                "author": "Asociación Hotelera Neiva",
                "priority": "Media",
                "title": "Movilidad: Invasión de espacio público y parqueo indebido en el Malecón",
                "content": "Vehículos mal parqueados bloquean el acceso al Malecón del Río Magdalena.",
                "category": "Movilidad",
                "sentiment": "Neutral",
                "location": "El Malecón (Comuna 4)",
                "zone": "comuna-4",
                "date_time": "20 Jun 2026, 03:00 PM",
                "status": "Resuelto",
                "media_type": "image",
                "impact_if_solved": "Fluidez en corredor turístico y comercial de la ribera del Magdalena.",
                "impact_if_ignored": "Colapso vial y quejas del sector comercial ribereño.",
                "assigned_department": "Secretaría de Movilidad y Tránsito",
                "assigned_to": "Controladores Viales y Grúas",
                "priority_action": False,
                "comments_count": 2
            }
        ]
    },
    # --- MAYO 2026 ---
    {
        "id": "POST-2026-0501",
        "month_key": "2026-05",
        "published_at": "15 May 2026, 10:00 AM",
        "created_time": "2026-05-15T10:00:00+0000",
        "title": "Jornada de Limpieza y Recuperación Ambiental en Ronda del Río Las Ceibas",
        "message": "Retiramos más de 18 toneladas de escombros e iniciamos siembra de árboles nativos.",
        "media_type": "image",
        "cover_image": "https://images.unsplash.com/photo-1542601906990-b4d3fb778b09?q=80&w=700&auto=format&fit=crop",
        "permalink_url": "https://facebook.com/johansteed/posts/0501",
        "likes_count": 780,
        "views_count": 9200,
        "shares_count": 140,
        "raw_comments": [
            {"id": "RC-701", "author": "@eco_neiva", "message": "Instalar cámaras de fotomulta para los carromuleros que siguen botando escombros.", "time": "15 May 2026, 11:20 AM", "is_meaningful": True}
        ],
        "cases": [
            {
                "id": "CIV-2026-0501",
                "institutional_radicado": "RAD-AMB-2026-0210",
                "source": "Facebook Oficial - Johan Steed",
                "author": "Líderes Ambientales Comuna 5",
                "priority": "Alta",
                "title": "Medio Ambiente: Disposición clandestina de escombros en ronda hídrica",
                "content": "Carretas y volquetas descargan escombros en la ronda del río a la altura de Siete de Agosto.",
                "category": "Medio Ambiente",
                "sentiment": "Indignación",
                "location": "Siete de Agosto (Comuna 5)",
                "zone": "comuna-5",
                "date_time": "15 May 2026, 10:00 AM",
                "status": "Resuelto",
                "media_type": "image",
                "impact_if_solved": "Protección de la fuente abastecedora de agua de Neiva.",
                "impact_if_ignored": "Sedimentación de la bocatoma de Las Ceibas en temporada de lluvias.",
                "assigned_department": "Secretaría de Medio Ambiente y Desarrollo Rural",
                "assigned_to": "Patrulla Ambiental",
                "priority_action": False,
                "comments_count": 4
            }
        ]
    },
    # --- ABRIL 2026 ---
    {
        "id": "POST-2026-0401",
        "month_key": "2026-04",
        "published_at": "10 Abr 2026, 08:30 AM",
        "created_time": "2026-04-10T08:30:00+0000",
        "title": "Dotación de Centros de Salud en la Comuna 8 y Comuna 6",
        "message": "Nuevos equipos médicos e insumos para fortalecer la atención de urgencias y consulta externa.",
        "media_type": "image",
        "cover_image": "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?q=80&w=700&auto=format&fit=crop",
        "permalink_url": "https://facebook.com/johansteed/posts/0401",
        "likes_count": 620,
        "views_count": 7100,
        "shares_count": 89,
        "raw_comments": [
            {"id": "RC-801", "author": "@ana_panorama", "message": "Excelente dotación, hace falta agilizar la asignación de citas telefónicas.", "time": "10 Abr 2026, 09:40 AM", "is_meaningful": True}
        ],
        "cases": [
            {
                "id": "CIV-2026-0401",
                "institutional_radicado": "RAD-SAL-2026-0155",
                "source": "Facebook Oficial - Johan Steed",
                "author": "Comunidad Panorama",
                "priority": "Media",
                "title": "Salud: Demoras en asignación de citas de medicina general en centro de salud",
                "content": "Usuarios del centro de salud Panorama deben madrugar a las 4am por falta de canal digital.",
                "category": "Salud",
                "sentiment": "Preocupado",
                "location": "Panorama (Comuna 8)",
                "zone": "comuna-8",
                "date_time": "10 Abr 2026, 08:30 AM",
                "status": "Resuelto",
                "media_type": "image",
                "impact_if_solved": "Dignificación en el acceso a citas médicas para adultos mayores.",
                "impact_if_ignored": "Aglomeraciones y quejas ante Personería Municipal.",
                "assigned_department": "Secretaría de Salud Municipal",
                "assigned_to": "ESE Carmen Emilia Ospina",
                "priority_action": False,
                "comments_count": 3
            }
        ]
    },
    # --- MARZO 2026 ---
    {
        "id": "POST-2026-0301",
        "month_key": "2026-03",
        "published_at": "14 Mar 2026, 04:15 PM",
        "created_time": "2026-03-14T16:15:00+0000",
        "title": "Recuperación de Parques Infantiles y Zonas Verdes en el Oriente de Neiva",
        "message": "Entregamos el parque biosaludable de Buganvillas y Jardín para disfrute de los niños y jóvenes.",
        "media_type": "image",
        "cover_image": "https://images.unsplash.com/photo-1576013551627-0cc20b96c2a7?q=80&w=700&auto=format&fit=crop",
        "permalink_url": "https://facebook.com/johansteed/posts/0301",
        "likes_count": 540,
        "views_count": 6300,
        "shares_count": 78,
        "raw_comments": [
            {"id": "RC-901", "author": "@madres_buganvillas", "message": "Los juegos quedaron preciosos, gracias por cumplirle a los niños.", "time": "14 Mar 2026, 05:00 PM", "is_meaningful": True}
        ],
        "cases": [
            {
                "id": "CIV-2026-0301",
                "institutional_radicado": "RAD-INF-2026-0098",
                "source": "Facebook Oficial - Johan Steed",
                "author": "Madres Comunitarias Buganvillas",
                "priority": "Baja",
                "title": "Infraestructura: Mantenimiento preventivo a cerramiento de parque infantil",
                "content": "Se requiere soldar malla perimetral del parque para mayor seguridad de los niños.",
                "category": "Infraestructura",
                "sentiment": "Positivo",
                "location": "Buganvillas (Comuna 5)",
                "zone": "comuna-5",
                "date_time": "14 Mar 2026, 04:15 PM",
                "status": "Resuelto",
                "media_type": "image",
                "impact_if_solved": "Seguridad infantil en entorno recreativo comunitario.",
                "impact_if_ignored": "Deterioro acelerado de juegos infantiles recién instalados.",
                "assigned_department": "Secretaría de Infraestructura y Vías",
                "assigned_to": "Cuadrilla de Espacio Público",
                "priority_action": False,
                "comments_count": 2
            }
        ]
    },
    # --- FEBRERO 2026 ---
    {
        "id": "POST-2026-0201",
        "month_key": "2026-02",
        "published_at": "19 Feb 2026, 09:00 AM",
        "created_time": "2026-02-19T09:00:00+0000",
        "title": "Ruta Escolar Segura: Inicio de Calendario Académico en Colegios Oficiales",
        "message": "Acompañamos a nuestros estudiantes con señalización escolar y reguladores de tránsito en las entradas de las instituciones.",
        "media_type": "image",
        "cover_image": "https://images.unsplash.com/photo-1580582932707-520aed937b7b?q=80&w=700&auto=format&fit=crop",
        "permalink_url": "https://facebook.com/johansteed/posts/0201",
        "likes_count": 710,
        "views_count": 8100,
        "shares_count": 92,
        "raw_comments": [
            {"id": "RC-1001", "author": "@padres_ineem", "message": "Pintar los reductores de velocidad frente a la sede Santa Librada.", "time": "19 Feb 2026, 10:15 AM", "is_meaningful": True}
        ],
        "cases": [
            {
                "id": "CIV-2026-0201",
                "institutional_radicado": "RAD-MOV-2026-0062",
                "source": "Facebook Oficial - Johan Steed",
                "author": "Asociación de Padres de Familia",
                "priority": "Alta",
                "title": "Movilidad: Pintura termoplástica para reductores frente a colegio",
                "content": "Vehículos no frenan frente al colegio por falta de demarcación visible en el reductor.",
                "category": "Movilidad",
                "sentiment": "Preocupado",
                "location": "Centro - Cra 12 (Comuna 3)",
                "zone": "comuna-3",
                "date_time": "19 Feb 2026, 09:00 AM",
                "status": "Resuelto",
                "media_type": "image",
                "impact_if_solved": "Protección de 800 menores al ingreso y salida escolar.",
                "impact_if_ignored": "Alto riesgo de atropellamiento en zona escolar central.",
                "assigned_department": "Secretaría de Movilidad y Tránsito",
                "assigned_to": "Cuadrilla Señalización Vial",
                "priority_action": True,
                "comments_count": 3
            }
        ]
    },
    # --- ENERO 2026 ---
    {
        "id": "POST-2026-0101",
        "month_key": "2026-01",
        "published_at": "05 Ene 2026, 10:00 AM",
        "created_time": "2026-01-05T10:00:00+0000",
        "title": "Primeros 100 Días de Gobierno: Plan de Desarrollo Neiva Inteligente 2026-2029",
        "message": "Iniciamos mesas de participación ciudadana en las 10 comunas de Neiva para construir el futuro de nuestra capital.",
        "media_type": "video",
        "cover_image": "https://images.unsplash.com/photo-1497366216548-37526070297c?q=80&w=700&auto=format&fit=crop",
        "permalink_url": "https://facebook.com/johansteed/posts/0101",
        "likes_count": 1420,
        "views_count": 18200,
        "shares_count": 420,
        "raw_comments": [
            {"id": "RC-1101", "author": "@veeduria_neiva", "message": "Éxitos alcalde, que este gobierno sí escuche los reclamos de los barrios populares.", "time": "05 Ene 2026, 11:00 AM", "is_meaningful": True}
        ],
        "cases": [
            {
                "id": "CIV-2026-0101",
                "institutional_radicado": "RAD-GOB-2026-0001",
                "source": "Facebook Oficial - Johan Steed",
                "author": "Red de Veedurías Ciudadanas",
                "priority": "Media",
                "title": "General: Participación de ediles en formulación de presupuesto participativo",
                "content": "Solicitud de cronograma de mesas comunales con los ediles de las comunas 6, 8 y 10.",
                "category": "General",
                "sentiment": "Positivo",
                "location": "Neiva (General)",
                "zone": "comuna-6",
                "date_time": "05 Ene 2026, 10:00 AM",
                "status": "Resuelto",
                "media_type": "video",
                "impact_if_solved": "Gobernanza participativa y legitimidad institucional.",
                "impact_if_ignored": "Inconformidad de dignatarios de Juntas de Acción Comunal.",
                "assigned_department": "Secretaría de Gobierno y Convivencia",
                "assigned_to": "Dirección de Participación Comunitaria",
                "priority_action": False,
                "comments_count": 6
            }
        ]
    }
]

def seed_posts():
    db = SessionLocal()
    posts_added = 0
    cases_added = 0
    try:
        for p_data in SAMPLE_POSTS_2026:
            p_id = p_data["id"]
            existing_post = db.query(MetaPost).filter(MetaPost.id == p_id).first()
            raw_comms = p_data.get("raw_comments", [])
            cases_list = p_data.get("cases", [])
            
            if not existing_post:
                new_post = MetaPost(
                    id=p_id,
                    title=p_data["title"],
                    message=p_data["message"],
                    cover_image=p_data["cover_image"],
                    media_type=p_data["media_type"],
                    permalink_url=p_data["permalink_url"],
                    created_time=p_data["created_time"],
                    published_at=p_data["published_at"],
                    month_key=p_data["month_key"],
                    total_comments=max(len(raw_comms), len(cases_list) * 2, 4),
                    cases_count=len(cases_list),
                    likes_count=p_data["likes_count"],
                    views_count=p_data["views_count"],
                    shares_count=p_data["shares_count"],
                    raw_comments_json=json.dumps(raw_comms, ensure_ascii=False)
                )
                db.add(new_post)
                posts_added += 1
            else:
                existing_post.total_comments = max(len(raw_comms), len(cases_list) * 2, 4)
                existing_post.cases_count = len(cases_list)
                existing_post.raw_comments_json = json.dumps(raw_comms, ensure_ascii=False)
                posts_added += 1

            for c in cases_list:
                c_id = c["id"]
                existing_c = db.query(Case).filter(Case.id == c_id).first()
                # Attach post id to internal notes for matching in backend
                c_copy = dict(c)
                c_copy["internal_notes"] = f"[POST_ID:{p_id}] [Despacho Institucional] Caso clasificado y canalizado."
                c_copy["image_url"] = p_data["cover_image"]

                if not existing_c:
                    db.add(Case(**c_copy))
                    cases_added += 1
                else:
                    for k, v in c_copy.items():
                        setattr(existing_c, k, v)
                    cases_added += 1

        db.commit()
        print(f"EXITO: Se poblaron {posts_added} publicaciones en MetaPost (Enero a Octubre 2026) y {cases_added} casos vinculados.")
    except Exception as e:
        db.rollback()
        print("ERROR poblando posts:", e)
    finally:
        db.close()

if __name__ == "__main__":
    seed_posts()

