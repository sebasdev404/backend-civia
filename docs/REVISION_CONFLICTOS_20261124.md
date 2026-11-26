# Comparación de 152 conflictos de origen

Revisión del **24 de noviembre de 2026**. Continúa la [recuperación de referencias históricas](RECUPERACION_ORIGEN_20261124.md).

## Resultado guardado

Se compararon los 152 expedientes cuyo comentario candidato ya estaba reclamado por otro caso. En todos se encontró un único caso relacionado y coincidencia exacta en publicación, ID del comentario, texto completo, autor registrado y fecha de la captura local.

| Resultado | Pares | Decisión pendiente |
| --- | ---: | --- |
| Mismo origen, diferencias en datos del expediente | 151 | Revisar clasificación y bitácoras antes de elegir cómo conservar la información |
| Mismo origen, seguimiento registrado | 1 | Proteger responsable e historial antes de cualquier consolidación |

El segundo grupo corresponde a **CIV-2026-0004**, relacionado con **CIV-2026-1294**. El primero tiene responsable asignado y estado **En Gestión** en el momento de la revisión. Ese dato registrado no acredita por sí mismo una actuación externa.

Las diferencias incluyen título, fuente registrada, ubicación, categoría, prioridad, dependencia e impactos registrados. No se corrigió ni se dio por verdadera ninguna clasificación histórica. Coincidir con una captura local no verifica actualmente el contenido en Meta ni la identidad de una persona.

Los 152 resultados se guardaron en `case_provenance_reviews.evidence_json.conflict_review`, con casos relacionados, campos distintos, señales de seguimiento, huellas de los expedientes y de la captura, fecha y actor técnico. Las huellas permiten detectar cambios al repetir la comparación; no reemplazan una revisión del historial. El resultado representa el momento guardado y no se actualiza automáticamente al editar un caso.

## Qué cambió y qué falta

Se conservaron los 2661 casos y los 871 vínculos estructurados existentes. No se fusionaron ni eliminaron expedientes, no se reasignaron comentarios y no se modificaron campos, notas o estados de atención de los casos.

Los 152 siguen con `needs_review`. El total pendiente del lote continúa en **244**: estos 152 conflictos, 87 discrepancias de autor y 5 textos sin coincidencia. Comparar conflictos no equivale a resolverlos.

En **Gestión de casos → Casos y seguimiento → Procedencia: Origen pendiente de verificar**, abrir un caso señalado y desplegar **Ver comparación con el caso relacionado**. Allí aparecen los campos diferentes y un enlace al otro expediente. También está disponible en las tarjetas de detalle, cuadrícula y lista. La tabla conserva el indicador breve de procedencia; abrir el caso para consultar la comparación.

Siguiente decisión: revisar primero CIV-2026-0004 y CIV-2026-1294 y comparar evidencia y bitácoras. Actualización posterior: el [flujo de consolidación reversible](CONSOLIDACION_REVERSIBLE.md) está implementado y permite confirmar la relación conservando seguimiento e IDs. Ningún par real se consolidó automáticamente durante esa implementación.

## Validación y reproducción

- 42 pruebas aprobadas: comparación, recuperación, lectura y triaje. Las pruebas sintéticas usan SQLite aislado; las pruebas sobre la base del proyecto son de lectura.
- Ensayo PostgreSQL del lote completo con reversión externa: 2661 casos y 871 vínculos iguales antes y después, estados y motivos de auditoría conservados, segunda ejecución sin nuevas escrituras.
- Aplicación real: 152 comparaciones guardadas. API de listado y detalle comprobada contra el resultado persistido.
- Repetición real posterior: cero comparaciones reescritas y 244 registros todavía pendientes de decisión. Backend y frontend locales iniciados; detalle de CIV-2026-0004 respondió HTTP 200 en ambos, con el caso relacionado correcto en la API.
- TypeScript y lint del componente y cliente API aprobados. No se realizó aceptación visual automatizada de esta entrega.

Desde `backend-civia`, vista previa sin escrituras:

```powershell
.\venv\Scripts\python.exe review_case_conflicts.py --expect-count 152
```

`--apply` guarda únicamente auditoría; `--report <ruta>` exporta IDs, campos distintos y huellas, sin textos completos de comentarios ni credenciales. La recuperación histórica conserva la comparación fechada en futuras ejecuciones.

Evidencia local fuera de Git: `artifacts/case_conflicts_20261124_before.json` y `artifacts/case_conflicts_20261124_applied.json`, en la carpeta general del proyecto. El primero conserva los registros de auditoría previos, no una copia de seguridad completa de la base de datos.
