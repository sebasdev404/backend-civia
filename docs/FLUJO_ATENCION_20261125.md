# Flujo de atención y controles de guardado

Entrega local: **25 de noviembre de 2026**. Este bloque valida el recorrido con fixtures aisladas; no acredita que se haya atendido o cerrado una solicitud real.

## Recorrido de trabajo

1. **Revisar comentarios:** crear un expediente desde comentarios capturados o vincularlos a un expediente abierto. Se conservan sus IDs y texto; repetir una selección no duplica el caso, los vínculos ni el evento de creación.
2. **Asignar:** indicar entidad/equipo, persona responsable y próxima actuación; confirmar que se revisó el comentario y necesita atención. Solo ADMIN y SECRETARIO. Pasa de `Pendiente` a `En Gestión` y activa seguimiento. Reasignar un expediente abierto vuelve a registrar la actuación, sin borrar al responsable anterior del historial.
3. **Registrar avances:** ADMIN, SECRETARIO u OPERADOR pueden añadir una nota no vacía a un expediente abierto. No modifica el comentario original.
4. **Preparar respuesta:** guardar un borrador interno desde el expediente o desde Ciudadanos. Usa la misma validación y auditoría. No cambia el estado, no publica mensajes y no acredita envío ni radicación externa.
5. **Cerrar:** un expediente `En Gestión` debe tener entidad y persona. Se exige resultado de al menos 20 caracteres, referencia del soporte y confirmación de verificación. Se guarda quién cerró, se desactiva seguimiento y pasa a `Resuelto`.

Una referencia de soporte puede ser un documento, acta o enlace. CIVIA conserva lo declarado y la confirmación del usuario; no certifica automáticamente que el soporte sea auténtico o suficiente.

La alternativa **conversación general** requiere un expediente pendiente, sin persona asignada ni cierre, confirmación de revisión y un motivo de al menos 20 caracteres. Se conserva como `No requiere gestión`; no se cuenta como problema resuelto. Los expedientes cerrados no admiten notas, reasignación, nuevos borradores, cambios de prioridad o clasificación por estos caminos. La reapertura utiliza una acción específica; no se permite simularla mediante PATCH. Las correcciones históricas reversibles mantienen su flujo específico y su propia auditoría.

## Reabrir una decisión

Administración y Secretaría pueden usar **Reabrir para revisión** en un expediente `Resuelto` o `No requiere gestión`. Se exige motivo de entre 20 y 10.000 caracteres, confirmación de revisión y versión vigente. `POST /api/v1/cases/{id}/reopen` bloquea la fila, rechaza duplicados consolidados y estados abiertos/desconocidos, y registra al usuario autenticado. Reintentar con la versión anterior no repite la reapertura.

El expediente vuelve a **Pendiente**, con seguimiento requerido y sin responsable/equipo, solución ni borrador activos. Para cerrar de nuevo debe revisarse y asignarse otra vez. Se conservan ID, comentario, procedencia, clasificación, prioridad, vínculos y cualquier referencia institucional registrada. No se crean comunicaciones, radicados ni confirmaciones externas.

La reapertura guarda un evento `reopened` con motivo, autor, fecha y estados anterior/posterior en la misma transacción que el caso. El resultado, responsable y borrador anteriores permanecen en esa copia; las actuaciones anteriores y sus soportes no se modifican. Historial permite abrir **Decisión anterior conservada** y consultar el cierre original con su soporte. Para registros históricos sin eventos de cierre se conserva lo que exista en los campos anteriores, sin inventar una actuación ni una fecha retrospectiva.

Al actualizar un expediente reabierto por otra persona, la interfaz limpia los valores del ciclo anterior y muestra los datos vigentes. Una recarga fallida después del guardado se informa por separado y no se presenta como una nueva acción pendiente de ejecutar.

## Protección del servidor

- La actualización general `PATCH /cases/{id}` solo admite clasificación. Se rechazan cambios directos de estado, responsable, bitácora, borrador, cierre, conteos o radicado. No se puede usar para sobrescribir el origen.
- Los casos manuales nacen pendientes. No aceptan asignaciones, bitácoras, cierres, radicados o prioridad especial precargados. Los IDs se generan sin depender del conteo y son internos. Ya no se asigna automáticamente la zona «centro» cuando falta información. Los datos históricos no se reescribieron por este cambio.
- Cada modificación revisa una huella del expediente recibido en la consulta y bloquea la fila antes de validar y guardar. Una versión antigua responde 409; una petición sin versión revisada responde 422. Esto evita sobrescribir una edición posterior o repetir la misma nota tras un reintento ambiguo.
- La interfaz permite actualizar el expediente ante un conflicto. Diferencia «se guardó pero falló la recarga» de un resultado que no pudo confirmarse; no inventa un guardado exitoso.
- Las escrituras usan el ID interno exacto. Se retiró la conversión automática entre números `CASO-*` y `CIV-*`. Una referencia externa registrada puede localizar un expediente para consulta; si coincide con varios, se informa el conflicto y no se escoge uno arbitrariamente.
- Los duplicados consolidados conservan su protección. Un expediente con actuaciones auditadas no se elimina; la relación de la tabla de eventos lo impide también a nivel de base de datos.

## Historial estructurado

Nueva tabla `case_workflow_events`, con migración [20261125_case_workflow_events.sql](../migrations/20261125_case_workflow_events.sql). Cada registro conserva tipo de actuación, ID del expediente, cuenta y nombre del autor, fecha UTC, nota, referencia del soporte cuando corresponde y campos anteriores/posteriores. Se guarda junto al expediente en la misma transacción; un fallo de commit revierte ambos.

Se registran creación manual, creación/vinculación desde comentarios, asignación, avances, borradores, cierre, conversación general, reapertura, clasificación y prioridad especial. El rol y usuario efectivos se validan en el servidor. No se usa el nombre enviado por el formulario para atribuir una actuación.

El detalle presenta los eventos en Historial y conserva aparte la bitácora anterior. No se generaron actores ni eventos retrospectivos para los expedientes históricos. La bitácora textual permanece disponible; los textos nuevos no pueden insertar etiquetas técnicas que sustituyan IDs de origen.

En desarrollo, el arranque actual crea la tabla faltante. Para producción debe aplicarse y comprobarse la migración explícita; `create_all` no reemplaza un sistema de migraciones revisado.

## Ciudadanos y procedencia

El historial de contactos dejó de asociar publicaciones por imágenes, coincidencias parciales de nombre o una primera publicación arbitraria. Solo muestra expedientes con coincidencia exacta de nombre/usuario y canal; se advierte que esto **no certifica identidad**, con un máximo de 15 resultados. Los nombres genéricos protegidos por Meta no se consideran una identidad enlazada. Los contactos importados sin perfil vinculado no reciben asociaciones supuestas.

El origen se obtiene de la referencia almacenada. Cuando falta, se indica; no se completa con un post, fecha o portada genéricos. Abrir el historial no llama a IA ni genera respuestas automáticamente. Guardar desde Ciudadanos conserva la revisión del expediente, autor y estado; la ruta antigua ya no permite cerrar o avanzar casos al guardar un borrador.

## Evidencia de validación

- **155 pruebas aprobadas**: 29 nuevas del flujo HTTP y regresiones de autenticación, triaje, métricas, procedencia, consolidación, corrección, publicaciones, conversación y caso–mapa. SQLite con claves foráneas en las pruebas del flujo.
- Se probó captura → revisión → creación → asignación → avance → cierre; conservación literal del comentario/vínculo, reintentos, versiones antiguas, payloads que intentan saltarse acciones, soporte faltante, identidades de autor, perfiles protegidos, fallo de commit y preservación de auditoría.
- Mapa y métricas consultan el estado del expediente tras un cierre; no se fabrican posiciones exactas ni se contabiliza conversación general como solución.
- **20 comprobaciones funcionales en navegador y 32 de adaptación aprobadas**: asignación, avances, borrador, soporte obligatorio, cierre persistente, conversación general, conflicto entre ediciones, permisos, historial desde Ciudadanos y formularios/historial en 320–3840 px. Se inspeccionaron las capturas de móvil y escritorio. El resultado final está en `artifacts/workflow-ui-result.json`.
- TypeScript, compilación Next y ESLint del componente del expediente y cliente común. Queda una advertencia por imagen nativa y advertencias Sass heredadas. No se declara limpia la totalidad del código anterior de Ciudadanos por esta revisión.

La prueba de navegador usa una instancia temporal con SQLite y redirige todas sus llamadas de API a esa instancia. No carga fixtures en PostgreSQL, no llama a Meta/IA ni envía mensajes. Las huellas de expedientes, vínculos, correcciones, consolidaciones y contactos coincidieron antes/después de activar el código local. La tabla nueva de auditoría quedó vacía: no se agregaron actuaciones de prueba ni se reescribió el historial de los casos existentes. El resultado está en los artefactos privados de QA.

## Comprobaciones de reapertura

- **56 pruebas de backend aprobadas**: 39 del flujo de atención (incluidas 10 nuevas de reapertura) y 17 de acceso. Motivo, confirmación, roles, versiones, reintento, duplicados, rollback conjunto, ciclos sucesivos y cierres históricos; mapa y métricas vuelven a leer el estado pendiente. Fixtures SQLite, sin reaperturas reales.
- **19 comprobaciones de navegador aprobadas** sobre una copia temporal de Next y API con SQLite: apertura/cancelación, validación, conservación del cierre/soporte, borrador nuevo vacío, conversación general, actualización tras otra reapertura y permisos de Operador. Formulario revisado a 320, 390, 768, 1440 y 2560 px; captura móvil inspeccionada y alineación de confirmación corregida. Resultados en `artifacts/reopen-browser-result.json`.
- TypeScript, lint de los archivos modificados y build de Next con Webpack aprobados. Se mantienen la advertencia previa de imagen nativa y advertencias Sass heredadas. Backend local actualizado; huellas de usuarios y datos de negocio idénticas antes/después. No se reabrieron expedientes reales.
- La nueva acción usa `case_workflow_events`; no requiere otra tabla ni modifica actuaciones históricas al activar el código. Continúa siendo necesaria la migración existente de historial en un entorno nuevo.

## Límites y siguiente trabajo

Quedan pendientes la aceptación del flujo con solicitudes reales, validación operativa de soportes, decisiones de procedencia histórica y validación de los radicados externos con sus soportes reales. No se debe usar un cierre o una reapertura de prueba en un expediente real para dar por terminadas esas validaciones.

El almacenamiento protegido, revocación de sesiones, OTP protegido y límites de base de datos están implementados; ver [seguridad y pendientes](SEGURIDAD_SESIONES_20261125.md). La preparación de migraciones, copias/restauración y límites por identidad del cliente está implementada y comprobada localmente. Antes de exponer la aplicación siguen pendientes cuentas definitivas, SMTP real y revisión del destino. Ver el paquete de despliegue y las evidencias en PREPARACION_PRODUCCION_20261125.md.

## Radicación externa con soporte

Administración y Secretaría pueden registrar número, entidad emisora, fecha del documento, referencia verificable del soporte, motivo de al menos 20 caracteres y confirmación de cotejo. El servidor valida la versión y conserva actor y fecha. No admite una fecha futura ni el ID interno del expediente como supuesto radicado externo.

`POST /cases/{id}/registration` añade un registro; corregir conserva los anteriores. `POST /cases/{id}/registration/cancel` retira la referencia vigente con motivo y conserva su soporte. Una referencia antigua no se reactiva automáticamente. Una referencia histórica que no tenga registro documental se identifica como tal.

El panel está en **Datos y origen → Radicación externa**. Registrar o retirar la referencia no cambia el estado del caso ni envía correspondencia. El historial muestra las dos operaciones y se conserva al reabrir.
