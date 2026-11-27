# Ordenemos a Neiva — API y operación

Proyecto independiente de escucha y gestión ciudadana en Neiva. Organiza publicaciones y comentarios de Meta, análisis sujetos a revisión y expedientes de atención. No acredita radicación oficial, envío de respuestas o recepción de una solicitud por otra entidad.

FastAPI, SQLAlchemy, PostgreSQL y Python 3.14 en el paquete de despliegue. Dependencias fijadas en `requirements.lock`; instalar con `pip install -r requirements.txt` dentro de un entorno virtual. Configurar el archivo `.env` privado usando `.env.example`, sin publicar sus valores.

## Desarrollo local

```bash
python manage.py migrate
python manage.py migrate --check
uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

El frontend corre como repositorio hermano. En desarrollo, las tablas ausentes pueden crearse al arrancar; en producción, la API solo comprueba el esquema y requiere migraciones explícitas. El servicio usa un coordinador único con bloqueo PostgreSQL: no lanzar otro proceso API sobre la misma base.

Las rutas sensibles requieren sesión y permisos. Secretaría consulta todos los expedientes por decisión del usuario; las actuaciones tienen permisos diferenciados. La API devuelve imágenes públicas en las rutas expresamente permitidas y recibe eventos de Meta solo con firma válida. La carga de demostración está retirada. No usar datos de ejemplo para inicializar producción.

## Verificación

```bash
python -m unittest discover -s tests -p 'test_*.py'
python -m pip check
```

Las pruebas de integración de lectura necesitan PostgreSQL con el esquema actualizado. Las escrituras de prueba se aíslan en fixtures, transacciones revertidas o bases desechables. La prueba que consulta Meta se omite salvo activación explícita con `CIVIA_LIVE_META_TESTS=1`; requiere credenciales y estado externo válidos. La configuración SMTP por sí sola no demuestra entrega.

## Documentación

- [Estructura y lógica de negocio](docs/PROYECTO_CIVIA.md).
- [Tareas terminadas y pendientes](docs/SEGUIMIENTO.md).
- [Flujo de atención](docs/FLUJO_ATENCION_20261125.md).
- [Seguridad de sesiones](docs/SEGURIDAD_SESIONES_20261125.md).
- [Preparar y cambiar el correo de recuperación](docs/CORREO_GMAIL.md).
- [Preparación de producción y evidencias](docs/PREPARACION_PRODUCCION_20261125.md).
- [Despliegue, importación de datos, copias y reversión](deploy/README.md).

`deploy/` contiene Compose, Caddy y archivos de configuración de ejemplo sin secretos. El despliegue público y su aceptación están pendientes del alojamiento, dominio, correo y comprobaciones en el destino definitivo.
