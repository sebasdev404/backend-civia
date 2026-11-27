# Abrir Ordenemos a Neiva en otro portátil

Guía actualizada el 27 de noviembre de 2026. Los dos repositorios contienen el código, las migraciones y las plantillas de configuración. La base de datos, las credenciales y los archivos descargados se trasladan por un canal privado.

## 1. Requisitos y código

Instalar Git, Node.js 24, Python 3.14 y PostgreSQL 18. Crear una carpeta de trabajo y ejecutar en PowerShell:

```powershell
git clone https://github.com/sebasdev404/backend-civia.git
git clone https://github.com/sebasdev404/frontend-civia.git
```

Las carpetas deben quedar una al lado de la otra. Si ya existen como clones, ejecutar `git pull --ff-only` dentro de cada una después de guardar los cambios locales.

## 2. Preparar el backend

```powershell
cd backend-civia
py -3.14 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Editar el `.env` privado: configurar `DATABASE_URL` con la base del portátil, una `SECRET_KEY` aleatoria y las credenciales reales de las integraciones que se vayan a utilizar. Generar un secreto nuevo con:

```powershell
.\venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Para desarrollo local usar `ENVIRONMENT=development` y `PUBLIC_APP_URL=http://localhost:3000`. Mantener `AUTO_ANALYZE_ENABLED=false` y poner `AUTO_SYNC_ENABLED=false` mientras se prepara y valida el traslado. No iniciar dos servidores sobre la misma base. No publicar `.env`, tokens, copias de datos ni contraseñas en GitHub.

### Conservar los datos actuales

Antes de ejecutar migraciones o iniciar la API, trasladar y restaurar la base PostgreSQL y el directorio `static` mediante una copia privada. El procedimiento cifrado, la comprobación de restauración y la importación sobre un destino vacío se explican en [deploy/README.md](../deploy/README.md). Conservar también las claves privadas necesarias para recuperar la copia y los datos cifrados de la aplicación; no reemplazarlas a ciegas durante un traslado.

Clonar el código no copia ciudadanos, usuarios, comentarios, análisis ni imágenes descargadas. Las credenciales de acceso existentes solo estarán disponibles si se restaura su base de datos. Si se conecta el portátil a una base remota existente, coordinar el cierre del otro servidor antes de arrancar.

### Instalación vacía

Crear una base PostgreSQL vacía con el nombre y usuario configurados en `DATABASE_URL`. Después ejecutar:

```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py migrate --check
.\venv\Scripts\python.exe manage.py bootstrap-admin --email CORREO_REAL --name "NOMBRE_REAL"
```

Sustituir el correo y el nombre. El último comando solicita una contraseña privada y solo se usa si todavía no existe administración activa. Para una base restaurada, ejecutar las dos órdenes de migración después de restaurar y conservar las cuentas existentes.

No ejecutar los antiguos instaladores de la carpeta raíz que llaman a `seed`, `populate_map_incidents.py` o `sync_all_2026_data.py`: contienen instrucciones históricas y no son el procedimiento actual de traslado.

## 3. Preparar el frontend

En otra terminal, desde la carpeta de trabajo:

```powershell
cd frontend-civia
npm ci
if (!(Test-Path .env.local)) { Copy-Item .env.example .env.local }
```

Mantener `CIVIA_BACKEND_API_URL=http://127.0.0.1:8000/api/v1`. Dejar `CIVIA_PUBLIC_ORIGIN` sin definir para desarrollo local.

## 4. Arrancar y comprobar

En la terminal de `backend-civia`:

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

En la terminal de `frontend-civia`:

```powershell
npm run dev
```

Abrir `http://localhost:3000/login`, acceder con una cuenta activa y comprobar ciudadanos, publicaciones y expedientes. Revisar también `http://127.0.0.1:8000/docs`. Las funciones de Meta, IA y correo necesitan credenciales y permisos válidos; las noticias de medios siguen sujetas al acceso concedido por Meta.

La instalación queda comprobada cuando ambos servidores arrancan en el portátil y las consultas funcionan con la base elegida. La publicación del código en GitHub por sí sola no verifica ese entorno.
