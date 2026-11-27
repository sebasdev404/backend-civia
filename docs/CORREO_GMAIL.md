# Correo de recuperación: preparación y cambio de remitente

Actualizado: 26 de noviembre de 2026.

El envío usa variables privadas, por lo que el correo remitente puede configurarse ahora con una cuenta temporal real y cambiarse después por la definitiva **sin modificar el código**. El remitente y el correo de acceso de cada usuario son datos diferentes.

## Estado preparado

Las plantillas de configuración utilizan este perfil:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_TLS=true
SMTP_SSL=false
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
```

Los últimos tres campos de las plantillas permanecen vacíos: cada entorno debe añadir su cuenta privada. No son credenciales de prueba. La recuperación informa que no está disponible y no crea códigos ni anuncia envíos mientras falte configuración.

En el entorno local, la cuenta temporal ya quedó configurada privadamente y Gmail aceptó TLS y autenticación SMTP. El Administrador tiene vinculado su correo real con autorización del propietario; se revocaron sus sesiones anteriores y se comprobó el nuevo acceso. Sigue pendiente comprobar la recepción del código y el restablecimiento desde la interfaz. No se enviaron mensajes de prueba durante la validación SMTP.

## Cuando se disponga del correo

1. Activar la verificación en dos pasos en la cuenta Google y, si está disponible para esa cuenta, crear una contraseña de aplicación para Ordenemos a Neiva.
2. Completar en `backend-civia/.env`: `SMTP_USER` con la dirección Gmail, `SMTP_PASSWORD` con su contraseña de aplicación y `SMTP_FROM_EMAIL` con la misma dirección. Para otro remitente, verificar primero que la cuenta/proveedor autoriza esa dirección.
3. Reiniciar el backend para que lea los cambios. El frontend no necesita cambios ni una compilación nueva.
4. Confirmar que el usuario que solicita recuperación tiene un buzón real registrado y accesible. Una dirección escrita en Ordenemos a Neiva no demuestra que ese buzón exista.
5. Solicitar la recuperación desde la pantalla, comprobar la llegada del código y completar el restablecimiento. Un diagnóstico de configuración completa no acredita entrega; hay que probarla con un destinatario autorizado.

Google no ofrece contraseñas de aplicación para todas las configuraciones de cuenta. Su disponibilidad depende, entre otros factores, de la verificación en dos pasos y de las políticas de la cuenta. No usar la contraseña habitual de Gmail en `SMTP_PASSWORD`.

## Cambiar al correo definitivo

Si sigue siendo Gmail, cambiar los tres campos de cuenta/remitente y reiniciar el backend. Si cambia a otro proveedor que admita autenticación SMTP con usuario y contraseña, actualizar también host, puerto y transporte según sus instrucciones. Si exige exclusivamente OAuth, habrá que adaptar y comprobar esa autenticación antes de activar el envío: la conexión actual no implementa OAuth. Revocar la contraseña de aplicación de la cuenta temporal cuando deje de utilizarse.

En producción con Compose, actualizar el archivo privado `deploy/production.env` y **recrear** el servicio para recargar `env_file`:

```bash
docker compose --env-file compose.env up -d --force-recreate backend
```

Ese comando se ejecuta desde `backend-civia/deploy/`, una vez configurado el despliegue. Reiniciar un contenedor existente sin recrearlo no incorpora cambios de `env_file`.

Antes de sustituir una cuenta, revisar los correos pendientes en la bandeja: los reintentos usan la configuración vigente del trabajador. Cambiar el remitente no modifica correos de acceso, contraseñas, roles ni expedientes.

Las claves van únicamente en el entorno privado o el gestor de secretos del operador. No subir `.env` a Git ni pegar contraseñas de aplicación en el chat.

Referencias: [SMTP de Gmail](https://developers.google.com/workspace/gmail/imap/imap-smtp), [contraseñas de aplicación de Google](https://support.google.com/mail/answer/185833?hl=es).

## Diseño de los correos de seguridad

Recuperación y aviso de cambio de contraseña usan el logo del acceso, el lema «Ordenemos a Neiva» y la paleta negra, verde y dorada de la plataforma. El nombre visible del remitente y los asuntos también utilizan ese lema. Los mensajes conservan texto alternativo y el código sigue venciendo a los 15 minutos.

El aviso de contraseña actualizada presenta una confirmación destacada en verde, indicaciones para el siguiente acceso, el cierre de las sesiones anteriores y una advertencia dorada para cambios no reconocidos. Su diseño se comprobó entre 320 y 1440 px; los correos ya recibidos conservan su contenido original.

El logo viaja como PNG adjunto e insertado mediante Content-ID, sin enlaces a localhost ni imágenes remotas. Se incluye en `app/assets/email/` para que el backend pueda desplegarse independientemente. No se generan códigos fijos ni se alteran las validaciones del restablecimiento por cambiar el diseño.
