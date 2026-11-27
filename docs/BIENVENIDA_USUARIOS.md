# Bienvenida y credenciales al crear usuarios

Implementado y comprobado el 26 de noviembre de 2026.

## Flujo

1. Administrador abre **Configuración → Cuentas y permisos → Crear cuenta**.
2. Registra nombre, correo, rol y contraseña inicial. Se conserva el valor inicial `1234` solicitado por el propietario; otra contraseña debe cumplir la política vigente.
3. Al guardar se crean la cuenta y un trabajo de bienvenida en la misma transacción. Una operación rechazada no deja una bienvenida huérfana.
4. El envío se procesa después de la respuesta HTTP y se recupera desde la cola persistente si el proceso se reinicia. Un fallo SMTP no elimina la cuenta creada.
5. El usuario recibe nombre, correo de acceso, contraseña inicial, rol y botón **Ingresar a la plataforma**, con alternativa de URL escrita. La plantilla usa el logo adjunto del proyecto, el lema Ordenemos a Neiva y los colores negro, verde y dorado. Incluye versión de texto plano.
6. El usuario puede ingresar y cambiar su clave desde **Mi cuenta y seguridad**, cumpliendo los requisitos de contraseña. La bienvenida recomienda cambiarla; este cambio no añade un bloqueo obligatorio del primer inicio de sesión.

El remitente es el correo SMTP del servidor. El destinatario es el correo registrado para la cuenta nueva. No se usa el correo personal de cada nuevo usuario como remitente.

## Estado del envío

La respuesta de creación indica que la bienvenida está en cola. En cada tarjeta de cuenta se muestra su estado disponible: pendiente, reintento, aceptada por el servidor o fallo. El botón **Actualizar** consulta el estado actual.

`delivered` en la cola significa aceptación por SMTP. No certifica llegada a la bandeja principal, entrega final ni lectura. Si el servidor rechaza el envío se reintenta hasta cinco veces, con espera creciente. La bienvenida vence a las 24 horas sin envío; una cuenta ya creada conserva su acceso.

La creación duplicada no reenvía ni crea otra cuenta. El correo no se reenvía al editar rol o nombre. No se enviaron bienvenidas retrospectivas a usuarios existentes.

## Enlace de acceso

`PUBLIC_APP_URL` define la URL base de la plataforma. Se agrega `/login` para el botón. Debe ser HTTPS, salvo HTTP en localhost durante desarrollo. Si no está definida se usa el primer origen del frontend en `BACKEND_CORS_ORIGINS`.

El servidor local actual resuelve `http://localhost:3000/login`. Ese enlace solo es útil desde el equipo donde corre la plataforma. Para destinatarios en otros equipos se necesita publicar el frontend y configurar su URL accesible. `deploy/production.env.example` incluye el parámetro para hacerlo.

La URL procede de la configuración del servidor, nunca de cabeceras proporcionadas por el solicitante. Se rechazan enlaces con protocolos no admitidos, credenciales, parámetros o fragmentos.

## Privacidad y vigencia

- Las contraseñas de acceso continúan guardadas como hash en `users`.
- La contraseña inicial solo permanece cifrada en el trabajo de correo mientras debe enviarse; no se devuelve en la respuesta HTTP, auditorías, estados ni registros del servidor.
- El contenido cifrado de la bienvenida se borra al aceptar SMTP o terminar por fallo, vencimiento, cancelación de credenciales o cuenta no disponible.
- Antes del envío se comprueban el ID de la cuenta, su estado y la vigencia de la contraseña. Un cambio de clave, cuenta eliminada o correo reutilizado evita enviar credenciales anteriores.
- Los campos se escapan en HTML. Las credenciales no se incluyen en el asunto, URL ni cabeceras del mensaje.
- Los estados de bienvenida se consultan en el listado de administración de usuarios, sujeto a sus permisos existentes.

## Comprobaciones

289 pruebas de backend aprobadas (1 omitida), incluidas nueve específicas de bienvenida y las de recuperación/sesiones. SMTP simulado: formato MIME, logo, texto/HTML, ausencia de credenciales en logs, reintentos, contraseña vigente, expiración y destinatario correcto. Compilación de producción y lint sin errores.

18 comprobaciones de navegador con BFF y PostgreSQL temporal: creación y acceso con las credenciales iniciales, rol, aviso de correo, estado de reintento, pantalla adaptable y plantilla de correo en 320–1440 píxeles. SMTP deshabilitado en ese entorno. No se crearon usuarios ficticios en la base real ni se enviaron correos reales para las pruebas.
