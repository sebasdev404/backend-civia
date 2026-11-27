# Despliegue de Ordenemos a Neiva

Este paquete prepara un servidor Linux con Docker Engine y Compose v2. La aplicación se comprobó localmente con PostgreSQL y Next en modo producción. **Las imágenes Linux y el dominio definitivo deben verificarse en el servidor de destino; este archivo no acredita un despliegue público.**

Los repositorios deben quedar juntos: `backend-civia/` y `frontend-civia/`. El directorio de trabajo para los comandos siguientes es `backend-civia/deploy/`.

## Configuración privada

1. Copiar `compose.env.example` a `compose.env` y `production.env.example` a `production.env`. Ambos archivos están excluidos de Git.
2. Completar dominio sin protocolo/ruta, correo para TLS, versiones de imágenes y contraseña PostgreSQL. En `DATABASE_URL`, codificar caracteres reservados de la contraseña como URL; debe apuntar a `database:5432/civia`.
3. Generar tres secretos diferentes: `SECRET_KEY`, `CIVIA_PROXY_SECRET` y `BACKUP_ENCRYPTION_KEY`. Los dos primeros necesitan al menos 32 caracteres aleatorios; el último codifica exactamente 32 bytes aleatorios en base64 URL-safe. Guardarlos en el gestor privado del operador, sin pasarlos por el chat, Git ni capturas.
4. En `production.env`, configurar el origen HTTPS exacto en `BACKEND_CORS_ORIGINS`, Meta, OpenAI y SMTP con TLS o SSL, remitente autorizado y credenciales. No activar simultáneamente `SMTP_TLS` y `SMTP_SSL`.
5. `AUTO_ANALYZE_ENABLED=true` habilita el análisis pagado de comentarios con contexto en lotes de hasta 20, independiente de la captura. El valor de ejemplo lo deja desactivado. `AUTO_SYNC_ENABLED` controla la captura periódica.
6. Restringir lectura de los archivos privados al operador. Preparar `backups/` con acceso privado y almacenamiento persistente. Conservar la clave de las copias en un lugar independiente del servidor; una copia cifrada sin esa clave no se puede recuperar.

La infraestructura publicada expone solamente 80/443 mediante Caddy. PostgreSQL, FastAPI y Next permanecen en la red interna. El origen público del intermediario se configura desde `CIVIA_DOMAIN`; no se confía en cabeceras de origen aportadas por el visitante. La clave compartida entre Caddy, Next y FastAPI autentica la identidad opaca usada para limitar peticiones.

## Primera instalación

Definir una función de consola para evitar omitir el archivo privado:

```bash
dc() { docker compose --env-file compose.env "$@"; }
dc config --quiet
dc build backend frontend backup restore
dc run --rm --no-deps gateway caddy validate --config /etc/caddy/Caddyfile
dc up -d database
```

### Conservar la información existente

**Importar antes de ejecutar migraciones o iniciar la API**: la restauración exige una base vacía y un directorio multimedia vacío. No usar seeds, `--clean`, `down -v` ni borrar volúmenes para resolver un error.

En el origen, detener las escrituras mientras se prepara la copia final de traslado, incluidos sincronización, recepción de eventos y administración. Crear la copia con la herramienta `ops/backup.py`, usando las herramientas PostgreSQL 18 instaladas y la clave de cifrado del operador:

```bash
python ops/backup.py backup --output /ruta/privada/traslado.enc --media-root static
python ops/backup.py restore-test --archive /ruta/privada/traslado.enc
```

Transferir por un canal privado `traslado.enc`, `traslado.enc.media.enc` y `traslado.enc.manifest.json` a `deploy/backups/`. Configurar en el destino la misma clave **de copia** usada para cifrarlos; puede diferir del secreto de sesiones del nuevo entorno.

```bash
dc run --rm restore restore-empty --archive /backups/traslado.enc --confirm-database civia --media-target /media --media-owner 10001 10001
dc run --rm migrate
dc run --rm migrate python manage.py migrate --check
dc run --rm migrate python manage.py preflight
```

`restore-empty` autentica los dos archivos antes de importar, usa una transacción para PostgreSQL y verifica las huellas de las tablas y archivos. Rechaza una base con tablas. No vuelve a ejecutarse sobre un traslado parcial: conservar la evidencia y revisar el destino con el operador. La copia multimedia y la transacción SQL no son una única transacción distribuida.

Los usuarios, expedientes e historial existentes se conservan. No ejecutar `bootstrap-admin` si ya hay administración activa. Revisar los titulares/correos, retirar accesos que el responsable confirme y cambiar las claves iniciales desde Mi cuenta. Cambiar `SECRET_KEY` invalida sesiones y pendientes de recuperación cifrados con el secreto anterior; completar o cancelar esos pendientes antes del traslado.

Para una instalación expresamente vacía, ejecutar migraciones y crear el primer administrador real mediante `dc run --rm migrate python manage.py bootstrap-admin --email CORREO_REAL --name NOMBRE_REAL`; solicita la contraseña sin mostrarla. No crear cuentas de ejemplo.

### Encendido y comprobaciones externas

```bash
dc up -d backend frontend gateway
dc ps
dc logs --tail=100 backend frontend gateway
```

- DNS debe apuntar al servidor. Verificar certificado válido, redirección de HTTP a HTTPS y que 3000/5432/8000 no estén expuestos.
- Abrir `/login`, entrar con una cuenta real y comprobar cookie `Secure`/`HttpOnly`/`SameSite=Lax`. Probar salir y volver a entrar.
- Probar recuperación con el remitente real y un buzón autorizado; confirmar entrega, caducidad, uso único y aviso de cambio de contraseña. Una configuración escrita no demuestra entrega SMTP.
- Validar permisos de Meta y recepción de un evento firmado real. Revisar errores de sincronización; no convertir la ausencia de `from` o de métricas en datos supuestos.
- Con una solicitud real autorizada, revisar origen, crear/asociar el expediente, asignar, registrar avance, guardar borrador y cerrar con soporte. Conservar su historial y comprobar los perfiles ADMIN, SECRETARIO, OPERADOR y ALCALDE. Secretaría consulta **todos los expedientes**, según decisión del usuario.
- Confirmar la revisión visual y de navegación en los dispositivos previstos, incluidos Safari/iOS si forman parte de la operación.

La salida pública queda pendiente hasta completar estas comprobaciones y registrar quién acepta la operación. Los casos históricos sin evidencia o con clasificaciones dudosas se mantienen identificados para revisión humana.

## Copias, restauración y actualización

Crear copias con nombre único, incluyendo multimedia:

```bash
dc run --rm backup backup --output /backups/civia-FECHA-HORA.enc --media-root /media
dc run --rm backup restore-test --archive /backups/civia-FECHA-HORA.enc
```

Una verificación de restauración usa una base desechable y requiere permiso `CREATEDB`. No restaura encima de la base activa. El manifiesto contiene huellas y conteos, por lo que también debe mantenerse privado. Tras cada copia, enviarla a almacenamiento cifrado fuera del servidor y comprobar su existencia. Definir retención y responsables antes de automatizar eliminaciones; el paquete no borra copias automáticamente.

`backup.sh` y los ejemplos de systemd permiten programar una copia diaria en el host. Adaptar ruta, usuario, almacenamiento externo y alertas; instalar y habilitar el temporizador es una tarea del servidor definitivo, todavía pendiente.

Antes de actualizar: copia verificada, anotar las dos revisiones Git/versiones de imagen, detener backend/frontend/gateway durante migraciones, construir la versión nueva y ejecutar `migrate`, `migrate --check` y `preflight`. Después, arrancar y repetir la aceptación de acceso, consulta y una actuación. No arrancar dos coordinadores de API sobre la misma base: la entrega usa un proceso y un bloqueo PostgreSQL para evitar capturas duplicadas.

Para revertir código, recuperar las versiones anteriores de **ambas** imágenes si siguen siendo compatibles con el esquema. Las migraciones no tienen reversión automática. Si hay incompatibilidad de datos, detener escrituras, restaurar la copia en una **base nueva**, verificarla y cambiar la conexión; conservar la base anterior y revisar actuaciones posteriores a la copia antes de decidir su tratamiento.

## Vigilancia y límites

- Los servicios Docker tienen comprobaciones de salud y reinicio; la API separa `/health` de `/health/ready`. No son un sistema de alertas por sí solos.
- Configurar un monitor externo de HTTPS, alertas de contenedores no saludables, disco, antigüedad de la última copia, errores SMTP, eventos pendientes/fallidos y capturas interrumpidas. El proveedor y los destinatarios dependen del operador.
- `/audit` muestra actuaciones administrativas y estado del webhook sin exponer credenciales ni cuerpos completos. El historial de atención está en cada expediente.
- Sesión configurada: 480 minutos; limpieza técnica de sesiones caducadas: 30 días. Recuperación: 15 minutos; correo pendiente cifrado, hasta cinco intentos con espera creciente. Eventos procesados y correo tienen limpieza técnica a 30 días. Confirmar que estos valores cumplen la política del responsable antes de iniciar la operación.
- No se ha medido capacidad de producción ni disponibilidad porcentual. No usar réplicas/múltiples workers sin separar y validar antes la coordinación de trabajos.

Referencia de la configuración del proxy: [validación de Caddy](https://caddyserver.com/docs/command-line#caddy-validate). La configuración se valida sin iniciar certificados ni listeners públicos.
