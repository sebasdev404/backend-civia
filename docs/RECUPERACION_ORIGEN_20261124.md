# Recuperación de los 1115 casos históricos sin ID individual

Fecha: **24/11/2026**. Lote: `legacy_missing_comment_id_20261124`.

## Resultado aplicado

| Resultado | Casos |
| --- | ---: |
| Identificador y vínculo recuperados de captura local | 871 |
| Pendientes: comentario candidato ya vinculado a otro caso | 152 |
| Pendientes: autor no coincidente o no disponible | 87 |
| Pendientes: texto sin coincidencia exacta en la captura | 5 |
| Total del lote revisado | 1115 |

Se conservaron **los 2661 casos existentes**. No se eliminó ni fusionó ninguno. No se alteraron texto, autor, fecha, prioridad, estado, ubicación, responsable ni conteo de comentarios. Los cambios de casos recuperados se limitan a agregar la referencia individual y la nota de auditoría; su fecha de actualización cambia por ese registro de auditoría.

## Criterio y límites

Se exigió una coincidencia **única y exacta** de publicación, texto completo, autor registrado y fecha, contra los comentarios capturados. No se normalizaron nombres, no se usó similitud semántica, no se asignaron IDs por posición y no se recurrió a IA. Si otro caso ya reclamaba ese comentario, no se trasladó el vínculo.

Esto demuestra coincidencia con una **captura local**; no equivale a consultar hoy todos esos comentarios en Meta ni a verificar la identidad real de sus autores. La categoría, emoción y necesidad de atención tampoco quedan validadas por recuperar el ID.

Cada comentario recuperado conserva una copia de la captura en `case_comments`. El actor es el identificador técnico `system:legacy-provenance-recovery`, no una persona inventada. `case_provenance_reviews` conserva resultado, motivo y huellas de evidencia para los 1115 casos, incluidos los 244 pendientes.

## Protección y comprobaciones

- Vista previa sin escrituras antes de aplicar.
- 12 pruebas aisladas de coincidencia, ambigüedad, conflicto, persistencia, conservación de campos e idempotencia aprobadas.
- Ensayo completo en PostgreSQL dentro de una transacción externa, revertido correctamente.
- Aplicación real condicionada a que siguieran existiendo exactamente 871 coincidencias recuperables.
- Revisión posterior sin nuevas escrituras: 871 recuperados y 244 pendientes.
- El ensayo de repetición añadió **cero** vínculos y no duplicó notas.

## Cómo consultarlo

En **Gestión de casos → Casos y seguimiento**, abrir **Filtros** y usar **Procedencia**:

- **Origen pendiente de verificar:** los 244 pendientes, con advertencia y motivo.
- **Origen recuperado de captura:** los 871 recuperados, con la limitación de verificación local.

El detalle del caso muestra el aviso contextual y la evidencia en **Datos y origen**. El resultado no modifica su estado de atención.

## Herramientas

- `recover_legacy_comment_ids.py`: vista previa por defecto; `--apply` solicita persistencia explícitamente y `--expect-recoverable` evita aplicar si cambió la captura respecto de la revisión.
- `audit_case_provenance.py`: auditoría general, solo lectura.
- `migrations/20261124_case_provenance_review.sql`: tabla de resultados.
- `tests/test_provenance_recovery.py`: pruebas aisladas sin red ni cambios en la base real.
- Informes de IDs/huellas, sin textos de comentarios ni credenciales: `artifacts/provenance_recovery_20261124_preview.json` y `artifacts/provenance_recovery_20261124_applied.json`, en la carpeta general del proyecto.

## Siguiente revisión

Actualización del 24/11/2026: [comparación de los 152 conflictos terminada](REVISION_CONFLICTOS_20261124.md), con resultado guardado y enlaces entre expedientes. Su consolidación sigue pendiente; no cambia el total de 244 casos por resolver.

Los 152 conflictos requieren revisar la posible duplicidad con el caso que ya tiene el comentario: no se aprueba una fusión automática. Los 87 autores discrepantes y los 5 textos ausentes necesitan evidencia adicional o recuperación autorizada de la fuente. Mantenerlos como no verificados mientras falte esa evidencia.

Fuera de este lote, la auditoría general posterior dejó 2012 casos con texto coincidente e ID de captura, 394 sin publicación local y 11 sin el comentario referenciado dentro de una publicación capturada. Esos grupos siguen abiertos; recuperar 871 IDs no certifica toda la plataforma.
