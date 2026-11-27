# Identidad del correo

`logo.png` es una copia exacta de `frontend-civia/public/logo.png`, incluida en este repositorio porque el backend se despliega independientemente del frontend. Si cambia el logo de la plataforma, actualizar esta copia con el mismo archivo.

Los correos lo adjuntan como imagen PNG con Content-ID para que no dependa de un dominio, un enlace a localhost o una descarga externa. El envío utiliza `multipart/related` y conserva alternativas de texto y HTML.

La plantilla está en `app/services/email_templates.py` y usa el lema y los colores actuales del acceso. No contiene credenciales ni códigos fijos. Las vistas de prueba se generan fuera del código publicado.
