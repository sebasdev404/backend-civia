# Corrección auditada de despachos de prueba

Implementada el **24/11/2026** a partir del [hallazgo del primer par](REVISION_PRIMER_PAR_20261124.md). La herramienta está disponible; durante su implementación no se corrigió ningún expediente real.

Posteriormente, tras autorización explícita del usuario, se retiró la asignación de prueba de CIV-2026-0004. El resultado se registra al final de este documento; no se marcó como opinión ni como resuelto.

## Recorrido

Abrir `CIV-2026-0004` y pulsar **Revisar y corregir** en la columna de siguiente acción. En **Datos y origen**, localizar **Despacho de prueba registrado** y pulsar **Corregir despacho de prueba**. En móvil también está el acceso **Revisar asignación**. Administración o Secretaría pueden guardar o revertir; los usuarios autenticados pueden consultar la evidencia.

La revisión muestra asignación actual, última nota de despacho, comentario, publicación y bitácora completa. Hay dos decisiones explícitas:

- **Dejar pendiente de revisión de la solicitud**: opción inicial. Retira responsable y dependencia de prueba, deja estado Pendiente y seguimiento por revisar. No clasifica el comentario como opinión automáticamente.
- **Marcar como opinión general sin solicitud concreta**: requiere confirmar esa revisión. Retira la asignación, cambia a No requiere gestión y desactiva el seguimiento requerido. No registra una solución ni un cierre como Resuelto.

Ambas requieren motivo y confirmación. El texto del comentario, origen, clasificación histórica y notas anteriores se conservan. Cambian únicamente estado, responsable, dependencia, necesidad de seguimiento y una nota nueva de auditoría. El registro independiente conserva el estado previo, la evidencia revisada, los campos posteriores, usuario y fecha.

## Protecciones

Se exige que la última nota de asignación/despacho contenga explícitamente «Despacho de prueba», con una asignación activa En Gestión. Una prueba antigua no habilita retirar una asignación posterior. Se verifica el comentario exacto en su captura local, sin completar identidades o datos por suposición.

No se admite la operación cuando existe respuesta, solución, responsable de cierre, radicado, prioridad especial, una consolidación activa u otra corrección activa. Estos escenarios requieren revisión adicional.

La confirmación verifica que casos y evidencia no hayan cambiado desde la vista previa. Bloquea publicación y caso en el mismo orden que el flujo de consolidación. Un ID de operación evita duplicar correcciones al reintentar.

**Revertir corrección** restaura únicamente los cuatro campos operativos modificados y agrega una nota; conserva las notas de corrección y reversión. Requiere un motivo y que no haya cambios posteriores ni una consolidación activa. Si existe seguimiento nuevo, devuelve conflicto y conserva los datos actuales para revisión manual. Los expedientes con historial de corrección no pueden eliminarse mediante la API de casos.

Esto corrige un efecto operativo de prueba; no acredita una atención real, la veracidad de denuncias ni la identidad del autor. Tampoco resuelve automáticamente duplicidades u otros registros históricos.

## Implementación y comprobación

- `GET /api/v1/case-corrections/case/{id}`: revisión e historial, sin escrituras.
- `POST /api/v1/case-corrections`: confirmación con motivo, revisión vigente, disposición e ID de operación.
- `POST /api/v1/case-corrections/{id}/undo`: reversión protegida.
- Tabla local `case_corrections`; migración `migrations/20261124_case_corrections.sql`.

**71 pruebas aprobadas** en el conjunto de corrección, consolidación, comparación, recuperación, lectura, triaje y flujo caso–mapa. Las pruebas aisladas cubren permisos, decisión explícita, fuente exacta, asignaciones posteriores, idempotencia, ambas disposiciones, reversión y protección del seguimiento posterior. Ensayo PostgreSQL sobre CIV-2026-0004 dentro de transacción externa revertida: **2661 casos y 871 vínculos intactos, sin correcciones reales añadidas**. TypeScript y lint sin errores; permanece la advertencia anterior sobre la imagen nativa de la publicación. Aceptación visual pendiente.

## Aplicación real autorizada

Después de comprobar nuevamente la evidencia, el usuario confirmó: **«Sí, retirar la prueba y dejar pendiente»**.

- Caso: **CIV-2026-0004**.
- Operación: `413a0724-d529-42be-9c11-bf64c1542113`, aplicada mediante `POST /api/v1/case-corrections` con la cuenta ADMIN existente y la revisión vigente.
- Decisión: `needs_review`. Estado posterior: **Pendiente**; responsable y dependencia: **sin asignar**; `requires_followup=true`.
- No se modificaron texto, autor, origen, categoría, emoción, ubicación ni los datos del caso relacionado **CIV-2026-1294**. Se conservaron las notas anteriores y se añadió la nota de corrección.
- La operación añadió un registro en `case_corrections`. Permanecen **2661 casos, 871 vínculos de comentarios y cero consolidaciones**.
- Las **10 pruebas aisladas de corrección** se ejecutaron de nuevo antes de aplicar y aprobaron. La revisión posterior comprobó los campos cambiados, conservación de notas, invariancia del par y conteos.
- Evidencia completa antes/después, comprobaciones y recibo en `artifacts/authorized_correction_0004_result.json`, fuera del repositorio. Solicitud con ID estable en `artifacts/authorized_correction_0004_request.json`; no se almacenó el token de acceso en esos archivos.

No se ejecutó una reversión sobre este caso real ni se confirmó una consolidación. La clasificación de negocio del comentario y del expediente relacionado continúa abierta. El siguiente paso es revisar si el contenido exige atención o es conversación general y registrar esa decisión sin convertir la asignación de prueba en una gestión real.
