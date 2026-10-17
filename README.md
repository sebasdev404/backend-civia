# 🧠 CIVIA - Backend (Motor de Inteligencia Artificial y Gestión de Casos)

API RESTful de alto rendimiento para el sistema CIVIA de la Alcaldía de Neiva, desarrollada con **Python 3.10+**, **FastAPI**, **SQLAlchemy ORM**, **PostgreSQL** e integración con **OpenAI (GPT-4o-mini)** y **Meta Graph API (Facebook / Instagram)**.

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

