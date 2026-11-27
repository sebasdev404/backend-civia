# WhatsApp y asistente de atención: alcance actual

Revisión del 26 de noviembre de 2026. El propietario confirmó que Johan o su equipo político sería titular y usuario del número de envío.

## Restricción que determina la integración

La [Política de mensajes de WhatsApp Business](https://whatsappbusiness.com/es-la/policy/), actualizada el 23 de septiembre de 2026, prohíbe WhatsApp Business Platform para políticos, candidatos, partidos y campañas políticas. Por este uso confirmado no se implementó ni se activó una integración de envíos automáticos o masivos por esa API. Esto describe la restricción de ese producto de Meta; no constituye una prohibición general de toda comunicación por WhatsApp.

No se configuró otro proveedor ni automatización de WhatsApp Web para sustituir esa integración.

## Lo disponible en Ciudadanos

- Asistente de borradores de atención ciudadana mediante `gpt-4o-mini`, con revisión humana. El prompt del backend excluye propaganda y adaptación a posturas políticas o perfiles.
- Apertura sin comentarios inventados, sin consulta pagada al abrir y sin inferir que las notas del contacto sean un mensaje recibido.
- El operador introduce el mensaje real o las indicaciones y solicita la generación explícitamente. No se envían al modelo clasificaciones sociales ni métricas del perfil desde este formulario.
- Borrador editable, con indicación de revisión requerida. Se eliminó la etiqueta que lo presentaba como un argumento verificado.
- Para un contacto con enlace móvil válido, **Abrir WhatsApp con borrador** prepara el chat. El operador revisa y decide el envío manual dentro de WhatsApp, sujeto a las normas de uso aplicables.
- Abrir el enlace no acredita envío, entrega, lectura ni respuesta. No hay confirmación de entrega ni conexión activa a WhatsApp Business Platform.
- Los fijos no generan un enlace de WhatsApp automáticamente. Los resultados de una solicitud anterior no se aplican al abrir otro destinatario.

## Solicitud de grupos y envíos desde la plataforma

El propietario solicitó destinatarios individuales y selección de grupos por categorización. El envío automático o masivo no está implementado ni debe marcarse como terminado para el uso confirmado. Las categorías de procedencia (censo, formulario, etc.) organizan contactos; no prueban consentimiento para mensajes ni afiliación política.

Una integración de mensajería necesita primero elegibilidad del titular y uso en el proveedor. Además requeriría cuenta y número habilitados, credenciales privadas, permisos, recepción segura de estados, trazabilidad, exclusiones y consentimiento de los destinatarios. La política exige consentimiento para contacto, respeto de bajas y las reglas aplicables a plantillas y ventana de atención. Tener una base de teléfonos importados no cumple por sí solo esos requisitos.

## Validación del ajuste

Frontend: compilación de producción y lint sin errores. No se realizaron envíos ni se generaron respuestas de pago para probar este ajuste. El backend y la base de ciudadanos no se modificaron por esta revisión.
