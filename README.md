> **Documento central del proyecto:** [Estructura, lógica de negocio, limitaciones y pendientes](docs/PROYECTO_CIVIA.md), revisado el 24/11/2026.
>
> Este README contiene también instrucciones heredadas de demostración. Las referencias a una plataforma oficial, cuentas demo o carga de datos semilla no describen una configuración de producción aprobada. Consultar el documento central antes de instalar o desplegar.

# 🧠 CIVIA - Backend (Motor de Inteligencia Artificial y Gestión de Casos)

API RESTful de alto rendimiento para el sistema CIVIA de la Alcaldía de Neiva, desarrollada con **Python 3.10+**, **FastAPI**, **SQLAlchemy ORM**, **PostgreSQL** e integración con **OpenAI (GPT-4o-mini)** y **Meta Graph API (Facebook / Instagram)**.

## Publicaciones, actualización en segundo plano y fuentes externas

El apartado **Publicaciones** (`/publications`) permite consultar las capturas por fuente y abrir sus comentarios paginados, métricas e identidades disponibles de reacciones. Incluye las redes conectadas de Johan y la fuente aportada **Jorge Andrés Gechem** (`https://www.facebook.com/JorgeAndresGA`). Las capturas externas se guardan en `observed_posts`, separadas de los casos y del análisis de opinión sobre Johan. Registrar un enlace no concede acceso: un rechazo de Meta queda visible, con código y estado, sin contenido de ejemplo ni ceros inventados.

`POST /api/v1/meta/sync-live` responde **202** con un trabajo. `GET /api/v1/meta/sync-jobs/{id}` consulta su avance y resultado; `/api/v1/meta/sync-status?scope=connected` permite recuperar el último trabajo tras navegar. Los botones manuales y la tarea automática comparten una exclusión por fuente para evitar duplicar la misma captura. La ejecución normal consulta hasta **12 publicaciones recientes por red**, guarda primero los metadatos de Facebook y después sus comentarios y métricas. No espera descargas de portadas ni clasificación de cada comentario con IA. El análisis contextual se pone en una cola separada cuando termina la captura. Los scripts históricos mantienen sus opciones anteriores.

Los nombres visibles se conservan tal como los entrega Meta y pueden exportarse con los comentarios capturados a CSV. No son identidades verificadas. Las identidades de reacciones pueden ser parciales o estar restringidas aunque haya un conteo disponible. Las señales de repetición/frecuencia sirven para revisión; no confirman bots, personas reales, granjas ni afinidad política. El endpoint antiguo de detección devuelve estado indeterminado cuando no hay evidencia y no calcula probabilidades a partir de críticas o datos ausentes.

Las tablas nuevas se crean al arrancar; también existe `migrations/20261113_publications_sync_jobs.sql`. Un reinicio marca los trabajos pendientes previos como interrumpidos y permite reintentarlos. La coordinación actual está diseñada para el servidor local de un solo proceso.

## Opinión sobre Johan y contexto de publicaciones

El sidebar incluye **Opinión sobre Johan** (`/opinion`, con redirección desde `/conversation`). Consulta todos los comentarios capturados de Facebook, incluidas respuestas con su comentario padre cuando esté disponible. Distingue emoción, postura frente a Johan, destinatario, tema y motivo. Una denuncia de la ciudad no implica crítica a Johan; el enojo que respalda su denuncia se cuenta como apoyo.

Para videos, selecciona la publicación y guarda un resumen o una transcripción del contenido hablado. Actualmente no se descarga ni escucha el video automáticamente. La descripción y la portada por sí solas no se consideran contexto suficiente para un video. Para publicaciones de texto/imagen se utiliza el texto de la publicación. El origen del contexto queda visible en cada análisis.

**Analizar pendientes (20)** procesa hasta 20 comentarios del período/publicación seleccionados. La sincronización de Facebook también procesa hasta 20 pendientes por ciclo. Las clasificaciones quedan en tablas independientes de las capturas de Meta y se reutilizan; si cambia el contexto, el comentario, su padre o la versión del clasificador, vuelven a estar pendientes. Los comentarios ya analizados con ambigüedad permanecen en revisión hasta contar con un contexto que la resuelva. Los resultados con baja confianza, ambiguos o sin contexto no se suman como apoyos ni críticas. Las cifras de Meta pueden diferir de los comentarios capturados por respuestas, restricciones y disponibilidad.

Las tablas `post_contexts` y `comment_analyses` se crean al iniciar el backend; también se incluye `migrations/20261113_contextual_conversation.sql` para despliegues con migración explícita. Reinicia backend y frontend tras actualizar. Los endpoints `/api/v1/conversation` requieren sesión y no hacen publicaciones ni envían respuestas a Facebook.

Validación aislada (sin llamadas de pago ni escritura en datos reales):

```bash
python -m unittest discover -s tests -p test_conversation.py -v
```

Evaluación opcional con cuatro ejemplos sintéticos contra el proveedor de IA configurado (consume una llamada):

```bash
python tests/eval_conversation_live.py
```

La confianza del modelo es orientativa; no garantiza exactitud ni representa una afinidad política del autor. La vista Análisis conserva métricas de emoción de casos, diferenciadas de la postura contextual que muestra Conversación Facebook.

---

## 🚀 Requisitos Previos

- **Python**: 3.10, 3.11 o superior.
- **PostgreSQL**: 14+ instalado y en ejecución en el puerto 5432 (o base de datos remota).
- Base de datos creada: `civia_db` (o el nombre que configures).

---

## 📦 Instalación y Configuración

1. **Crear y activar el entorno virtual:**
   ```bash
   # En Windows PowerShell o CMD:
   python -m venv venv
   .\venv\Scripts\activate

   # En Linux / macOS:
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar Variables de Entorno (`.env`):**
   Copia el archivo `.env.example` como `.env`:
   ```bash
   cp .env.example .env
   ```
   Ajusta las credenciales de tu base de datos local:
   ```env
   DATABASE_URL=postgresql://postgres:TU_PASSWORD@localhost:5432/civia_db
   SECRET_KEY=civia_secret_dev_key_2026_bogota_intelligence
   ACCESS_TOKEN_EXPIRE_MINUTES=11520
   BACKEND_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
   OPENAI_API_KEY=tu-api-key-de-openai
   ```

4. **Crear tablas y poblar datos semilla iniciales:**
   ```bash
   # Inicializar base de datos y usuarios base (Alcalde, Operador, Admin):
   python -m app.api.v1.seed

   # Poblar incidentes geolocalizados del mapa de Neiva:
   python populate_map_incidents.py

   # Sincronizar casos consolidados y publicaciones 2026:
   python sync_all_2026_data.py
   ```

---

## 🏃‍♂️ Ejecución del Servidor

Con el entorno virtual activado:
```bash
uvicorn main:app --port 8000 --reload
```

- **API Base:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Documentación Interactiva Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Documentación ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 🔐 Cuentas Semilla Preconfiguradas

| Correo | Rol | Contraseña | Funcionalidad |
| :--- | :--- | :--- | :--- |
| `alcalde@civia.gov.co` | `ALCALDE` | `123456` | Acceso a métricas globales, índice de confianza y mapas |
| `operador@civia.gov.co` | `OPERADOR` | `123456` | Bandeja de triaje, supervisión de excepciones y despacho |
| `admin@civia.gov.co` | `ADMIN` | `123456` | Configuración técnica, webhooks y parámetros de IA |

---

## 📡 Módulos y Endpoints Principales

- **Autenticación (`/api/v1/auth`):**
  - `POST /login`: Inicio de sesión y generación de token JWT.
  - `GET /me`: Obtener perfil y rol del usuario en sesión.
- **Gestión de Casos (`/api/v1/cases`):**
  - `GET /`: Listado filtrado por estado, prioridad, comuna, canal o búsqueda de texto.
  - `GET /{id}`: Detalle 360 del caso e historial de trazabilidad.
  - `PATCH /{id}/status`: Actualización de estado y despacho institucional.
- **Incidentes y Mapa Territorial (`/api/v1/incidents`):**
  - `GET /`: Listado de incidentes georreferenciados con coordenadas WGS84 para el mapa térmico de Leaflet.
- **Integración Meta (`/api/v1/meta`):**
  - `GET /posts`: Listado de publicaciones de Facebook / Instagram con conteos de comentarios, likes y compartidos.
  - `POST /sync-live`: Sincronización forzada en tiempo real con Meta Graph API.
  - `GET /webhook` / `POST /webhook`: Escucha de eventos en vivo desde Meta Webhooks.
- **Servicio de Inteligencia Artificial (`/api/v1/ai`):**
  - `POST /classify`: Clasificación semántica de comentarios y PQR con detección de sentimiento y prioridad automática.
