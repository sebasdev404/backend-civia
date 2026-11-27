# Ordenemos a Neiva: estructura, funcionamiento y pendientes

Fecha de revisión: **26 de noviembre de 2026**.

La [preparación de producción](PREPARACION_PRODUCCION_20261125.md) documenta radicados con soporte, auditoría, correo persistente, webhook, migraciones, copias y despliegue. El [manual operativo](../deploy/README.md) distingue la verificación local de la salida pública pendiente.

**Lista de avance:** [tareas terminadas y pendientes](SEGUIMIENTO.md). Las completadas aparecen marcadas y tachadas, con alcance y evidencia.

Última revisión de datos: [comparación de 152 conflictos de origen](REVISION_CONFLICTOS_20261124.md). Resultados persistidos; decisiones de consolidación pendientes.

Disponible para revisión: [consolidación reversible de expedientes](CONSOLIDACION_REVERSIBLE.md), con elección del principal, auditoría y reversión. Su implementación no aplicó decisiones sobre los pares reales.

También está disponible la [corrección auditada de despachos de prueba](CORRECCION_DESPACHOS_PRUEBA.md), a partir del hallazgo explícito del primer par. La herramienta conserva el historial y requiere una decisión sobre el expediente real.

La [reorganización de la bandeja y el expediente](REDISENO_GESTION_CASOS_20261124.md) prioriza comentario, decisión y seguimiento, con datos históricos y herramientas de procedencia en una sección secundaria. Incluye alcance y validación visual; la aceptación del usuario y el resto del rediseño siguen pendientes.

La [adaptación de pantallas](RESPONSIVE_20261124.md) registra la corrección posterior de distribución en escritorio amplio, cuadrículas según el contenedor y pruebas entre 320 y 3840 px. Distingue la matriz local de la validación pendiente en dispositivos físicos y Safari/iOS.

Este es el documento central del proyecto. Describe el código inspeccionado, no una certificación de funcionamiento en producción. La entrega del 24/11/2026 se publicó en ambos repositorios; consultar `SEGUIMIENTO.md` y el historial Git para distinguirla de cambios posteriores. La revisión documental inicial no consultó Meta ni ejecutó análisis de pago; las verificaciones posteriores de procedencia se documentan por separado.

## 1. Qué es Ordenemos a Neiva

Ordenemos a Neiva es un proyecto independiente para escuchar conversaciones públicas, organizar solicitudes ciudadanas y dar seguimiento a su atención en Neiva. El código conserva nombres de roles y textos de una demostración institucional. Eso no acredita que sea una plataforma oficial de la Alcaldía, que exista integración con sus sistemas de radicación o que una dependencia haya recibido una solicitud.

Tiene tres funciones diferentes:

1. **Escuchar:** capturar publicaciones, comentarios y métricas disponibles de fuentes de Meta.
2. **Entender:** analizar el tema, la emoción y, con contexto suficiente, la postura expresada respecto de Johan.
3. **Atender:** identificar solicitudes concretas, registrar casos, asignar responsables y documentar su gestión.

Un comentario no equivale a un caso; un nombre de Facebook no acredita identidad; un contacto de WhatsApp no acredita relación con un perfil social; guardar una respuesta no significa enviarla.

## 2. Arquitectura y repositorios

| Capa | Implementación actual | Ubicación |
| --- | --- | --- |
| Interfaz | Next.js **16.4.6**, React **19.2.8**, TypeScript, SCSS Modules | `frontend-civia/src` |
| Navegación y ayudas | Menú por tareas, navegación de espacios y ayuda contextual | `src/lib/navigation.ts`, `src/lib/help.ts`, `src/components/ui` |
| API | FastAPI con rutas bajo `/api/v1` | `backend-civia/app/api/v1` |
| Persistencia | SQLAlchemy y PostgreSQL | `app/models`, `app/core/database.py` |
| Integraciones | Meta Graph API y proveedor de IA configurado | `app/services`, `sync_live_service.py` |
| Procesamiento diferido | Trabajos registrados en PostgreSQL y ejecutados en hilos del servidor | `app/services/meta_sync_jobs.py` |
| Multimedia | Portadas y miniaturas locales | `static/covers`, `static/thumbnails` |

La carpeta general contiene **dos repositorios Git independientes**. El frontend y el backend se versionan por separado. Este documento se guarda dentro del backend para poder versionarlo; no conviene mantener copias distintas del mismo documento.

Flujo técnico: interfaz → cliente `src/lib/api/client.ts` → rutas FastAPI → servicios → PostgreSQL. Los servicios de captura consultan Meta y los de análisis pueden consultar IA. La interfaz consulta el progreso de los trabajos sin esperar a que termine toda la captura en una única petición HTTP.

## 3. Pantallas y responsabilidad de cada una

| Pantalla | Ruta | Qué hace y qué debe distinguir |
| --- | --- | --- |
| Inicio | `/dashboard` | Resumen por rol y accesos. **Sus cifras necesitan revisión:** aún usa una carga limitada de casos y un incremento fijo en el total de reportes. |
| Opinión sobre Johan | `/opinion` | Análisis contextual de comentarios capturados de Facebook. `/conversation` redirige aquí. Distingue destinatario, tema, emoción y postura. |
| Publicaciones | `/publications` | Monitor regional de noticias clasificadas por IA y pestaña de redes conectadas. Medios aportados con acceso de Meta pendiente; no se presume lectura por registrar una URL. Ver [monitor de noticias](MONITOR_NOTICIAS_NEIVA_HUILA.md). |
| Gestión de casos | `/cases` | Publicaciones vinculadas, casos consolidados y bandeja de supervisión. La consulta está paginada; hay acciones de triaje todavía no persistidas. |
| Detalle de caso | `/cases/[id]` | Consulta, asignación, notas, prioridad, respuesta guardada y cierre. |
| Mapa de reportes | `/map` | Consulta incidentes y su evidencia territorial; no debe presentar una ubicación supuesta como exacta. |
| Indicadores | `/analytics` | Métricas de casos y emociones. No son equivalentes a la postura contextual de Opinión. |
| Ciudadanos y contactos | `/citizens` | Directorio, importación Excel/CSV, datos de origen y eliminación individual/múltiple. |
| Configuración | `/settings` | Usuarios, diagnósticos y parámetros expuestos por la aplicación. Requiere completar la revisión de permisos. |

Fuente del menú actual: `frontend-civia/src/lib/navigation.ts`. Los README antiguos que hablan solo de cuatro módulos o de Next.js 15 están desactualizados.

## 4. Datos principales y relaciones

| Tabla | Qué representa | Código |
| --- | --- | --- |
| `users` | Cuentas, rol y estado de acceso | `app/models/user.py` |
| `meta_posts` | Publicaciones conectadas de Facebook/Instagram y comentarios capturados en JSON | `app/models/meta_post.py` |
| `cases` | Expedientes de atención, asignación, notas y resolución | `app/models/case.py` |
| `case_workflow_events` | Actuaciones de atención con actor, soporte y datos anteriores/posteriores | `app/models/case_workflow.py` |
| `incidents` | Registros territoriales para el mapa | `app/models/incident.py` |
| `citizens` | Contactos y metadatos del archivo importado | `app/models/citizen.py` |
| `post_contexts` | Resumen o transcripción aportados para una publicación | `app/models/conversation.py` |
| `comment_analyses` | Análisis almacenados por publicación/comentario y huella del contenido/contexto | `app/models/conversation.py` |
| `publication_sources` | Fuentes registradas y estado de acceso | `app/models/publication.py` |
| `observed_posts` | Capturas de fuentes externas, separadas de los casos de Johan | `app/models/publication.py` |
| `publication_snapshots` | Métricas y reacciones disponibles de publicaciones | `app/models/publication.py` |
| `meta_sync_jobs` | Estado, avance y resultado de trabajos | `app/models/publication.py` |

**Limitación del modelo:** varias relaciones todavía son convenciones en texto o IDs, no relaciones protegidas por claves foráneas. Por ejemplo, los casos conservan `[Post ID]` y `[Comment ID]` en `internal_notes`. Hay que normalizar esa relación antes de ampliar la consolidación automática. Una coincidencia por nombre o una fotografía compartida no debe sustituir al identificador de origen.

## 5. Captura de publicaciones y comentarios

1. La sincronización manual solicita un trabajo mediante `POST /api/v1/meta/sync-live` y obtiene **202**, no un resultado terminado.
2. El cliente consulta `/api/v1/meta/sync-jobs/{id}`. `/meta/sync-status` permite recuperar el trabajo al volver a la pantalla.
3. El trabajo `connected` consulta hasta **12 publicaciones recientes por red**. Guarda la captura sin esperar a descargar portadas ni clasificar cada comentario como caso.
4. Al terminar, puede poner el análisis contextual en otro trabajo, con hasta 20 pendientes por ejecución.
5. La tarea del servidor espera 20 segundos al arrancar y solicita captura cada 180 segundos. Eso no equivale a una garantía de entrega en tiempo real ni a una sincronización de todo el histórico.
6. Los trabajos distinguen cola, ejecución, éxito, resultado parcial, fallo e interrupción. Al reiniciar se marcan como interrumpidos los trabajos activos anteriores.

El coordinador actual usa hilos y está concebido para **un solo proceso local**. Tener una tabla de trabajos no lo convierte en una cola distribuida. Antes de usar múltiples réplicas o workers hay que revisar exclusión, recuperación y reintentos.

Los scripts históricos siguen siendo una vía distinta. No se deben ejecutar como si fueran la actualización ligera: pueden recorrer mucho más histórico y, según sus opciones, clasificar y crear casos.

En Publicaciones existen las fuentes conectadas de Johan y una fuente externa de Jorge Andrés Gechem. Registrar su URL no concede permisos de Meta. Un error de acceso debe mostrarse, no reemplazarse por publicaciones de ejemplo. Las capturas externas no deben convertirse automáticamente en casos ni mezclarse con opinión sobre Johan.

Meta puede limitar comentarios, respuestas, autores, fotos y reacciones. Conteo reportado y comentarios efectivamente capturados son magnitudes distintas. No se promete cobertura del 100 %.

## 6. Análisis contextual

Servicio principal: `app/services/conversation.py`; API: `/api/v1/conversation`.

- Se separan **emoción**, **destinatario** y **postura expresada**. Enojo ante un problema urbano no implica una crítica a Johan.
- Los comentarios de videos también se analizan sin resumen o transcripción, usando el texto disponible y el padre de la respuesta. Si el sentido depende de lo hablado y falta esa evidencia, el resultado queda para revisión. El sistema no escucha ni transcribe automáticamente el video.
- El análisis se almacena con una huella del comentario, su contexto y la versión del clasificador. Los cambios relevantes lo vuelven pendiente.
- Resultados ambiguos, sin contexto o de baja confianza permanecen para revisión y no deben contarse como apoyo o crítica confirmados.
- Una clasificación describe un comentario en su contexto; no constituye una afinidad política permanente del autor ni una identidad verificada.
- Las señales de repetición o frecuencia se muestran para revisión. No prueban que alguien sea bot o pertenezca a una granja.

El análisis de opinión usa `OPINION_ANALYSIS_MODEL` (predeterminado `gpt-4o-mini`, restablecido por indicación del propietario); los clasificadores institucionales usan ese mismo modelo y los embeddings usan `text-embedding-3-small`. La clasificación de opinión la realiza la API de OpenAI desde el backend, no Codex: Codex desarrolla el código. La presencia de los nombres de modelo no demuestra que una llamada se haya ejecutado ni que haya saldo. Algunos caminos institucionales conservan heurísticas de respaldo; hay que identificar su origen y no presentarlas como análisis confirmado por el proveedor.

**Actualizado el 26/11/2026:** el botón «Analizar pendientes y dudosos» recorre toda la selección en un trabajo persistido, muestra avance y permite detener/reanudar; no se limita a los 20 comentarios del endpoint síncrono heredado. La pantalla separa pendientes y ambigüedad real. Ver [análisis completo, evaluación y límites](OPINION_ANALISIS_COMPLETO.md).

## 7. Flujo de atención de un caso

Flujo de negocio que se busca consolidar:

**Comentario capturado → revisión de solicitud → asociación a un caso existente o creación persistida → asignación → seguimiento → resolución documentada.**

Operaciones persistidas existentes en `/api/v1/cases`:

- Crear o modificar un caso.
- `/{id}/dispatch`: guardar dependencia/responsable y pasar a `En Gestión`.
- `/{id}/notes`: agregar una nota a la bitácora.
- `/{id}/resolve`: guardar resolución y responsable de cierre; pasar a `Resuelto`.
- `/{id}/reopen`: volver de `Resuelto` o `No requiere gestión` a `Pendiente`, con motivo, confirmación y permisos de Administración/Secretaría. Desactiva asignación, solución y borrador del ciclo anterior; conserva sus valores y actuaciones en el historial.
- `/{id}/public-response`: guardar texto de respuesta. **No lo publica en Facebook/Instagram.**
- `/{id}/priority-action`: alternar la prioridad de intervención.

**Actualizado el 25/11/2026:** las transiciones ordinarias se validan en `app/services/case_workflow.py`. Asignar exige revisión, persona, equipo y próxima actuación; cerrar exige gestión activa, resultado, soporte y confirmación. `No requiere gestión` es una decisión motivada desde pendiente y no cuenta como solución. PATCH no modifica estado, origen ni bitácora; todas las acciones exigen la versión revisada del expediente y guardan el actor autenticado. El detalle presenta `case_workflow_events` sin inventar eventos anteriores. Ver [flujo, pruebas y límites](FLUJO_ATENCION_20261125.md).

**Implementado el 24/11/2026 — primer paso de preparación:** el agrupamiento ahora abre una revisión explícita para crear un caso o asociar comentarios a un caso existente. `POST /api/v1/triage/consolidate` valida las capturas, exige sesión firmada y rol autorizado, bloquea publicaciones en orden estable y guarda los vínculos en una transacción. `case_comments` conserva IDs completos, copia del comentario y usuario que lo vinculó. Repetir una selección no duplica el caso ni sus conteos; una selección en conflicto se rechaza íntegramente. El detalle muestra los comentarios vinculados.

Se retiraron los IDs de ejemplo y los mensajes de auto-despacho/porcentajes no medidos de esa bandeja. «Seleccionar visibles» solo marca comentarios; no los clasifica ni asigna. La bandeja presenta hasta 50 comentarios sin caso de las 200 publicaciones capturadas más recientes; no representa todo el histórico ni acredita que sean solicitudes. Los casos nuevos quedan pendientes, sin responsable ni radicado externo inventado. Los casos históricos con referencia exacta se reutilizan; sus vínculos se normalizan cuando se revisan, sin un backfill masivo.

Reorganización posterior de la interfaz: la pestaña se llama **Revisar comentarios**, entre Publicaciones y Casos y seguimiento. Cada comentario permite **Crear caso** o **Vincular a un caso** directamente; las casillas sirven para revisar varios juntos y «Seleccionar esta página» sustituye la selección masiva destacada anterior. Se muestran 10 comentarios por página, con búsqueda local y filtros de red/publicación dentro de los hasta 50 cargados. Se retiraron los bloques de metadatos sin evaluar que hacían parecer que cada opinión era un problema detectado. Al guardar se ofrece abrir el caso para continuar su atención. No se descartan comentarios ni se crean casos por filtrar, seleccionar o navegar.

Migración: `migrations/20261124_case_comment_links.sql`. Pruebas aisladas: `tests/test_triage.py`. La comprobación con PostgreSQL real usó una transacción externa y se revirtió, sin dejar casos de prueba. La concurrencia distribuida no se ha probado como despliegue multirréplica.

Un identificador `CIV`/`CASO` es interno. No es un radicado oficial por sí solo. No hay que inventar un número de correspondencia ni confirmar atención en terreno a partir de un cambio en la pantalla.

Otra deuda: el detalle puede convertir un `Incident` existente a `Case` durante una lectura. Conviene separar esa creación en una operación explícita.

## 8. Ciudadanos, importación y eliminación

Servicio: `app/services/citizen_import.py`; API: `/api/v1/citizens`.

- Excel `.xlsx` o CSV, máximo 10 MB y 10.000 filas. Se usa la hoja `Contactos` cuando existe.
- Vista previa antes de guardar; validación por fila y conservación de columnas originales en `source_data`.
- Registro individual y carga con origen obligatorio y observación opcional; procedencias anteriores conservadas. Nuevos registros requieren nombre y teléfono colombiano válido, nunca similitud de nombre. Los contactos históricos sin teléfono se conservan.
- Teléfono canónico +57 y 10 dígitos nacionales, único también en PostgreSQL. Los fijos incluyen indicativo regional (608 en Huila). No se completan números locales por suposición. Ver [reglas, permisos y comprobaciones](CIUDADANOS_ORIGEN_TELEFONO.md).
- Los nuevos contactos quedan sin clasificación social, sin seguidores inventados y con cero interacciones nuevas.
- Reimportar el mismo archivo permite reconocer registros sin cambios y evita duplicarlos.
- Eliminar uno o varios requiere sesión firmada y rol `ADMIN` o `ALCALDE`. El lote valida todos los IDs y se aplica en una transacción. No elimina casos ni comentarios.
- La selección múltiple conserva registros entre páginas; cambiar filtros limpia la selección. El diálogo muestra los registros antes del borrado definitivo.
- Importar contactos no autoriza envíos de mensajes ni vincula automáticamente sus identidades sociales.

**Deuda de identidad:** la ruta de historial de algunos contactos sociales aún busca casos por nombre/handle y conserva un fallback a otra publicación. Hay que reemplazarlo por una relación explícita y retirar ese fallback. Los contactos de WhatsApp/Base de Datos ya tienen una salida sin asociación social inferida.

Los contactos importados viven en PostgreSQL, no en Git. El Excel original no se incluye en el repositorio. No se fija aquí un conteo de ciudadanos: puede cambiar por importaciones o eliminaciones legítimas.

## 9. Mapa, indicadores e imágenes

El mapa utiliza `incidents` y `app/services/map_evidence.py` para auditar evidencia. Hay que preservar la diferencia entre una referencia barrial, una ubicación aproximada y una coordenada comprobada. El estado de un caso debe tener una representación consistente en mapa y detalle; existe una suite dedicada a ese flujo.

Los listados de casos/publicaciones tienen paginación y detalle bajo demanda. `post_images.py` produce miniaturas de portadas reales y evita portadas genéricas. Las carpetas de caché están ignoradas en Git. Si no existe imagen original disponible, se indica; no se toma otra publicación para rellenar el espacio.

**Inicio e Indicadores corregidos:** consultan `/api/v1/analytics/overview`, con agregados sobre todo el histórico, exclusión de duplicados activa y separación de expedientes, captura, conteos reportados y análisis contextual. Se retiraron el incremento fijo de 1280, indicadores simulados por rol, serie semanal e informes de ejemplo. Las emociones conservan las etiquetas guardadas; no determinan apoyo/crítica contextual. Los tiempos sin instrumentación se muestran No disponible. Ver [definiciones, exportaciones y validación](INDICADORES_REALES_20261124.md). Los conteos exactos no certifican la calidad de las clasificaciones históricas.

## 10. Acceso y seguridad: estado real

Existen los roles `ADMIN`, `ALCALDE`, `SECRETARIO` y `OPERADOR`, pero la presentación de pantallas por rol no garantiza autorización en la API.

Pendientes antes de exponer el sistema públicamente:

- **Implementado el 25/11/2026:** retirados acceso automático, tokens demo y cambio de rol de presentación. API y exportaciones exigen sesión; la interfaz valida el perfil con el servidor, gestiona 401/403 y conserva la ruta de regreso. Política central por rol, administración solo ADMIN y seed/simulación deshabilitados. Ver [permisos, pruebas y pendientes](SEGURIDAD_SESIONES_20261125.md).
- **Implementado el 25/11/2026:** sesiones registradas y revocables, cookie HttpOnly/Secure mediante Next y pantalla Mi cuenta y seguridad. El JWT no se entrega al JavaScript del navegador ni se guarda en localStorage; cerrar sesión o cambiar/restablecer contraseña invalida los accesos correspondientes. La actualización exige iniciar sesión otra vez, con la contraseña existente. Migración `20261125_auth_sessions.sql` para otros entornos.
- **Implementado el 25/11/2026:** OTP protegido mediante HMAC, uso único, caducidad y presupuesto de errores; respuestas de recuperación uniformes y límites atómicos en base de datos. El envío se separa de la respuesta pública y requiere SMTP con TLS. Migración aditiva `20261125_password_recovery.sql` para otros entornos.
- Confirmar las cuentas históricas y sus credenciales definitivas; configurar y validar SMTP real, límites por IP original en el acceso público y operación/reintentos del envío. Las cuentas existentes no se eliminaron ni se cambiaron sus contraseñas durante estas entregas.
- La firma HMAC del webhook ya se comprueba antes de procesar el cuerpo. Faltan deduplicación, límite compartido de solicitudes y procesamiento diferido.
- La lectura de un incidente ya no crea un expediente. Debe existir un caso para abrirlo; la creación requiere un camino de escritura autorizado.
- Definir registro de auditoría estructurado: quién hizo qué, cuándo y sobre qué objeto. Las notas de texto no cubren por sí solas esa necesidad.
- Validar secretos, CORS, copias de seguridad, restauración, retención de datos y borrado de contactos según las decisiones del responsable del proyecto.

No se deben copiar claves reales, tokens de Meta, contraseñas ni datos personales a la documentación. Los nombres de roles heredados no acreditan cargos reales.

## 11. Pendientes priorizados y criterio de cierre

| Prioridad | Trabajo | Se considera terminado cuando… |
| --- | --- | --- |
| P0 | Retirar cifras y éxitos simulados | Inicio calcula sus totales desde SQL; ninguna acción declara guardado o despacho si no hubo persistencia. |
| P0 — implementado y probado localmente | Persistir consolidación/triaje | API transaccional y revisión explícita conectadas; pruebas de persistencia e idempotencia aprobadas. Falta la aceptación visual del usuario antes de liberar. |
| P0 | Unificar acceso y permisos | No hay entrada demo automática; peticiones no autenticadas o sin rol reciben 401/403 en todas las rutas sensibles. |
| P0 | Asegurar webhook y herramientas de prueba | Se validan eventos, se evita duplicación y no hay seed/simulación utilizables en producción. |
| P1 | Formalizar ciclo de atención | Hay transiciones validadas, responsables, requisitos de cierre y distinción entre código interno y radicado externo. |
| P1 | Corregir relaciones de origen e identidad | Casos/comentarios/publicaciones/contactos se enlazan por IDs explícitos; no se presta una publicación ni se infiere identidad por nombre. |
| P1 | Unificar indicadores y evidencia | Totales globales sin límites de página; mapas y reportes explican la procedencia y precisión de datos. |
| P1 | Validar opinión con contexto | Se revisa una muestra real, se mide ambigüedad y se identifica qué resultados siguen pendientes de contexto. |
| P1 | Preparar despliegue y recuperación | Migraciones reproducibles, copia y restauración probadas, configuración de producción y pruebas del flujo completo. |
| P2 | Escalar trabajos y multimedia | Workers y reintentos soportan reinicios/múltiples procesos; caché tiene almacenamiento y ciclo de vida definidos. |
| P2 | Mejoras opcionales | Transcripción automática y envío real de respuestas solo tras definir alcance, permisos, costos y confirmación del operador. |

Este backlog nace de la inspección del código; no representa compromisos de entrega ni una aprobación para enviar mensajes o publicar en redes.

## 12. Desarrollo y operación local

Backend, desde `backend-civia`, con PostgreSQL disponible y `.env` local configurado:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn main:app --port 8000 --reload
```

Frontend, desde `frontend-civia`:

```powershell
npm install
npm run dev
```

Interfaz: `http://localhost:3000`. API: `http://127.0.0.1:8000/api/v1`. Salud: `/health`. Documentación de endpoints: `http://127.0.0.1:8000/docs`.

La URL del frontend se configura con `NEXT_PUBLIC_API_URL`; las peticiones de las vistas usan el cliente común, incluidas las exportaciones y los borradores de IA. El backend configura base de datos, autenticación e integraciones mediante `app/core/config.py` y su entorno; no deben compartirse valores reales en este archivo. `ENVIRONMENT=production` exige clave JWT ajena a los ejemplos conocidos y orígenes CORS HTTPS explícitos.

`Base.metadata.create_all()` crea tablas ausentes, pero no reemplaza un sistema completo de migraciones de columnas existentes. Revisar `migrations/` antes de actualizar otro entorno. No ejecutar seed ni scripts históricos como paso automático de instalación de una base real.

`ARRANCAR_CIVIA.bat` es un lanzador heredado: elegir `npm run start` solo por la existencia de `.next` no garantiza que haya un build de producción válido. Sus mensajes y cuentas de demostración también necesitan actualización.

## 13. Pruebas y forma de mantener el documento

Las suites disponibles en `backend-civia/tests` cubren lectura de casos/Meta, importación y eliminación de ciudadanos, flujo caso–mapa, contexto conversacional, publicaciones y métricas. No todas tienen los mismos requisitos: algunas leen PostgreSQL real, otras usan aislamiento y la evaluación `eval_conversation_live.py` puede consumir proveedor de IA. Revisar cada archivo antes de ejecutarlo sobre datos reales.

Comprobación de tipos del frontend:

```powershell
npx tsc --noEmit --incremental false
```

La revisión documental del 24/11/2026 **no ejecutó las suites, no probó el despliegue ni certificó el estado de los servicios externos**. Los resultados de pruebas de sesiones anteriores no bastan para validar los cambios locales posteriores.

Validación posterior del primer paso, el mismo día: 10 pruebas aisladas de triaje aprobadas, 8 de lectura de casos y 7 de flujo caso–mapa aprobadas; comprobación PostgreSQL de creación/repetición/cola/vínculos revertida correctamente; TypeScript y ESLint del componente nuevo aprobados. La suite general de Meta tuvo 2 fallos: una expectativa antigua sobre métricas versus snapshots y la ausencia de la publicación más reciente de Instagram en la base consultada. Esos fallos quedan abiertos; no se declara toda la plataforma validada ni preparada para producción.

Actualizar este documento cada vez que cambie un módulo, una regla, el modelo de datos o una limitación. Por cada pendiente cerrado, registrar el cambio, la evidencia de prueba y la fecha. Mantener separados: funcionalidad implementada, funcionalidad comprobada y funcionalidad propuesta.

## 14. Archivos para orientarse

- Arranque y rutas: `main.py`, `app/api/v1/__init__.py`.
- Reglas de atención: `app/api/v1/cases.py`, `app/services/case_reads.py`.
- Captura y trabajos: `sync_live_service.py`, `app/services/facebook_graph.py`, `instagram_graph.py`, `meta_sync_jobs.py`.
- Fuentes y capturas externas: `app/services/publications.py`, `app/models/publication.py`.
- Análisis contextual: `app/services/conversation.py`, `app/models/conversation.py`.
- Contactos: `app/services/citizen_import.py`, `app/api/v1/citizens.py`.
- Mapa y evidencia: `app/services/map_evidence.py`, `app/api/v1/incidents.py`.
- Interfaz y API: `frontend-civia/src/lib/navigation.ts`, `frontend-civia/src/lib/api/client.ts`, `frontend-civia/src/app`.

Las rutas de backend de esta lista son relativas a `backend-civia`; las rutas con prefijo `frontend-civia` son relativas a la carpeta general del proyecto.
