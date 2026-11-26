# Consolidación reversible de expedientes

Implementación local del **24 de noviembre de 2026**, posterior a la [comparación de los 152 conflictos](REVISION_CONFLICTOS_20261124.md).

## Recorrido en la aplicación

1. Iniciar sesión con un usuario real. Administración o Secretaría pueden confirmar y revertir; los demás usuarios autenticados pueden consultar la comparación.
2. Abrir **Gestión de casos → Casos y seguimiento → un caso con conflicto**, por ejemplo `CIV-2026-0004`.
3. Abrir **Datos y origen**. En **Expedientes relacionados**, pulsar **Comparar expedientes** con el relacionado `CIV-2026-1294`. Si no hay relaciones, no se muestra un panel vacío.
4. Revisar el origen compartido, ambos textos, estados, responsables, respuestas, cierre, radicados, bitácoras completas y campos diferentes. El origen se valida nuevamente contra la captura local.
5. Elegir el principal, escribir el motivo y confirmar que se trata de la misma solicitud después de revisar ambos historiales. Coincidir con el mismo comentario no basta para tomar esa decisión.
6. Pulsar **Guardar consolidación reversible**. El historial identifica usuario, fecha y motivo, y permite **Deshacer consolidación** con un nuevo motivo.

El par inicial puede compararse, pero no se dejó consolidado como parte de la implementación. La decisión real requiere revisar su contenido y confirmar desde la pantalla. El expediente `CIV-2026-0004` conserva seguimiento; el sistema impide convertirlo en duplicado mientras lo tenga.

**Hallazgo posterior:** la [revisión del primer par](REVISION_PRIMER_PAR_20261124.md) encontró una nota explícita «Despacho de prueba» y una crítica general sin solicitud concreta identificada. Antes de confirmar una consolidación como solicitud, corresponde revisar su clasificación y corregir el efecto operativo de esa prueba, conservando el historial. El seguimiento registrado no debe interpretarse como atención real verificada.

## Conservación y efecto operativo

- Ambos casos y sus campos permanecen intactos. No se sobrescriben clasificación, responsable, estado, bitácora, respuesta o cierre.
- No se trasladan ni eliminan comentarios. El principal permite consultar también los vínculos del duplicado y señala el expediente que los conserva.
- Se guarda una relación separada en `case_consolidations`, con evidencia de la comparación, copias de los campos revisados, IDs, usuario y fecha.
- La bandeja habitual de casos y el listado compatible excluyen el duplicado. **Incluir duplicados vinculados** permite volver a mostrarlo; el detalle sigue accesible por su ID.
- Las rutas de modificación de casos y asociación de comentarios bloquean el duplicado activo. La eliminación de cualquiera de los expedientes con historial de consolidación queda bloqueada para preservar la auditoría.
- La procedencia mostrada para un conflicto activo pasa a **Duplicidad revisada: expedientes vinculados**. El filtro de origen pendiente lo excluye mientras la relación esté activa. El registro original de auditoría se conserva y vuelve a tener efecto al deshacer.
- Deshacer retira la relación activa y conserva su historial. No restaura versiones antiguas ni borra avances posteriores del principal. Ambos expedientes vuelven al listado con sus datos actuales.

Estos efectos corresponden a la gestión de casos. Los indicadores globales antiguos, el mapa y las vistas históricas de publicaciones tienen revisiones de consistencia pendientes en `SEGUIMIENTO.md`; no se certifica una deduplicación de toda la plataforma.

## Validaciones y límites del flujo

Solo se admiten pares con un único comentario compartido, coincidencia exacta en publicación, texto, autor registrado y fecha de la captura, sin comentarios estructurados adicionales ni terceros reclamantes. No se aceptan cadenas o grupos superpuestos.

Si uno tiene responsable, respuesta, cierre, radicado, prioridad especial o estado de atención avanzado, debe ser el principal. Si ambos tienen seguimiento, este flujo no permite consolidarlos: requieren una revisión adicional que defina cómo preservar ambos seguimientos. Las bitácoras siempre se muestran para revisión manual y se conservan.

Una huella de la comparación impide confirmar una revisión desactualizada por cambios en los casos, contexto, captura o vínculos. Las transacciones bloquean primero la publicación y después los casos en orden estable. Las modificaciones normales de casos usan el mismo bloqueo de fila; la relación se vuelve a comprobar antes de escribir.

Cada decisión lleva un identificador de operación: repetir una solicitud no crea otra relación. Repetir una reversión tampoco afecta una consolidación nueva. Las rutas nuevas requieren JWT válido de un usuario existente y activo; no admiten tokens de demostración.

## API, migración y comprobaciones

- `POST /api/v1/case-consolidations/compare`: comparación actual, sin escrituras.
- `GET /api/v1/case-consolidations/case/{id}`: historial de relaciones.
- `POST /api/v1/case-consolidations`: confirmación con motivo, revisión, principal, duplicado e ID de operación.
- `POST /api/v1/case-consolidations/{id}/undo`: reversión con motivo y usuario autenticado.
- `GET /api/v1/cases?include_duplicates=true`: incluir registros duplicados en la consulta; no cambia datos.
- Migración reproducible: `migrations/20261124_case_consolidations.sql`. Tabla preparada en la base local; sin decisiones reales insertadas.

Validación de la entrega: **61 pruebas** aprobadas de consolidación, comparación, recuperación, lectura, triaje y flujo caso–mapa. Las pruebas sintéticas usan SQLite aislado. Un ensayo PostgreSQL guardó, repitió y deshizo la relación del par inicial y comprobó conteos y campos, dentro de una transacción externa que se revirtió: **2661 casos y 871 vínculos sin modificaciones y cero decisiones reales añadidas**. El filtro pendiente volvió a 244.

TypeScript aprobado; lint de los componentes, cliente API y expediente sin errores, con la advertencia anterior de imagen nativa en el contexto de la publicación. La aceptación visual automatizada no estuvo disponible. Validar la interfaz con el usuario sigue pendiente; estas pruebas no constituyen aceptación de producción.
