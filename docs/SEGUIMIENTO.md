# Ordenemos a Neiva — seguimiento de desarrollo

Actualizado: **26 de noviembre de 2026**.

Este archivo es la lista central de avance. Una tarea terminada se marca `[x]` y se tacha con `~~texto~~`. Las tareas parciales permanecen abiertas. «Terminado» significa implementado y comprobado en el alcance indicado; no implica aprobación para producción ni publicación en GitHub.

## Desarrollado y comprobado

- [x] ~~Enviar bienvenida con credenciales y botón de acceso al crear una cuenta.~~ Correo propio del nuevo usuario, contraseña inicial, rol, logo y colores de la plataforma. Cola cifrada, reintentos, comprobación de vigencia y estado consultable en Configuración. 289 pruebas de backend (1 omitida), build/lint y 18 comprobaciones de navegador. Ver [flujo y configuración](BIENVENIDA_USUARIOS.md).
- [ ] Configurar la URL pública del frontend en `PUBLIC_APP_URL` al desplegar. El botón de bienvenida apunta actualmente al acceso local; otros equipos necesitarán una dirección accesible.

- [x] ~~Aclarar y mejorar el asistente de borradores de Ciudadanos para envío manual.~~ Entrada vacía, sin ejemplos inventados ni generación automática al abrir; texto editable, revisión requerida y apertura explícita del chat. No acredita envío ni entrega. Build/lint sin errores.
- [ ] Envío automático/masivo de WhatsApp por categorías: no activado. El propietario confirmó uso por Johan/equipo político; la política de Meta prohíbe WhatsApp Business Platform para ese uso. Ver [alcance y restricción comprobada](MENSAJERIA_WHATSAPP_ALCANCE.md).

- [x] ~~Agregar ciudadanos individualmente y registrar origen y observación en cargas masivas e individuales.~~ Formulario, Censo, Familiar, Referido, Evento, Visita territorial, Llamada, WhatsApp y Otro; consulta de procedencias anteriores sin reemplazar los datos existentes. Botones y API sujetos a permisos.
- [x] ~~Unificar y proteger el teléfono contra duplicados, incluidos registros simultáneos.~~ Celulares y fijos colombianos de 10 dígitos, prefijo +57 normalizado, índice único y restricción en PostgreSQL. Se conservaron los 305 registros anteriores, incluidos 39 sin número. 280 pruebas de backend (1 omitida), build/lint, concurrencia real en base temporal y 27 comprobaciones de navegador. Ver [reglas y uso](CIUDADANOS_ORIGEN_TELEFONO.md).

- [x] ~~Mostrar porcentaje, total procesado y restantes en el análisis de opinión.~~ La captura de 2.972/6.664 corresponde a 44,6 %. Ese recorrido terminó en 100 %, con 6.622 clasificados y 42 señalados para revisión. El porcentaje expresa avance, no exactitud.
- [x] ~~Reestructurar Publicaciones como monitor de noticias de Neiva y Huila con clasificación de GPT-4o mini.~~ Dos vistas (noticias y redes conectadas), registro/pausa de medios, captura autorizada, clasificación con motivo, filtros, ordenación y paginación. Tres fuentes reales registradas. 274 pruebas de backend (1 omitida), build/lint y 25 comprobaciones de navegador aprobados. Ver [funcionamiento y evidencia](MONITOR_NOTICIAS_NEIVA_HUILA.md).
- [ ] Habilitar en Meta el acceso autorizado a Opa Noticias, Lucho Noticias Neiva y Neiva Noticias en Vivo. Las tres consultas reales devolvieron código 10; el módulo está preparado, pero todavía no recibió publicaciones de esos medios.

- [x] ~~Mantener GPT-4o mini como IA de clasificación integrada en la plataforma.~~ Restablecido por indicación del propietario después de evaluar otro modelo. El backend llama a la API de OpenAI y guarda sus respuestas; Codex interviene en el desarrollo del software. Cada trabajo conserva el modelo con el que se ejecutó y los resultados anteriores no se borran.

- [x] ~~Corregir el bloqueo de comentarios de videos y agregar análisis completo de opinión en segundo plano.~~ Auditoría inicial: 9.755 sin analizar por faltar transcripción y 53 analizados dudosos. Nuevo botón, clasificación con texto disponible, distinción entre pendientes y ambiguos, modelo de opinión actualizado, avance persistido, detención/reanudación y reintentos por comentario. 263 pruebas de backend (1 omitida), build/lint y 15 comprobaciones de navegador aprobados; el ensayo recorrió 80 comentarios sin límite de 20. Evaluación real de 14 ejemplos y tres comentarios capturados aprobada. El recorrido real está iniciado: su terminación se comprueba en el panel y no se presume por completar el desarrollo. Ver [funcionamiento, validación y límites](OPINION_ANALISIS_COMPLETO.md).

- [x] ~~Exigir mayúscula, minúscula, número y carácter especial en las contraseñas nuevas.~~ Mínimo 10 caracteres y máximo 72 bytes UTF-8. La regla se aplica en backend y formularios de Mi cuenta, recuperación y contraseña personalizada al crear usuarios; se conserva 1234 únicamente como contraseña inicial administrativa. El acceso de cuentas existentes sigue compatible. Validación: 253 pruebas de backend (1 omitida), compilación y lint sin errores y 35 comprobaciones en navegador; cambios de contraseña ensayados en una base temporal, sin enviar correos reales.

- [x] ~~Permitir que Administración cree usuarios con nombre, correo y rol, usando 1234 como contraseña inicial predeterminada.~~ Disponible en Configuración → Cuentas y permisos → Crear cuenta. El backend aplica el valor predeterminado si se omite la contraseña y la guarda con hash; una clave personalizada debe cumplir la política de contraseñas nuevas. El cambio solo afecta cuentas nuevas. Validación inicial: 43 pruebas de acceso, sesiones y recuperación aprobadas; build y lint del frontend sin errores; 12 comprobaciones de navegador, incluyendo creación y acceso con el rol seleccionado en base temporal aislada. La validación de la política ampliada se detalla arriba.

- [x] ~~Cambiar el nombre visible del software a Ordenemos a Neiva.~~ Navegación, acceso, ayuda, avisos, correos de seguridad e informes usan la nueva marca y el logo existente. Se conservan los IDs de expedientes, las claves técnicas de sesión, las rutas de repositorios y la evidencia histórica para mantener compatibilidad y trazabilidad. Validación local: build de producción y lint sin errores; 244 pruebas de backend (1 omitida) y 84 comprobaciones de marca y ajuste visual en navegador, con base temporal aislada. No se enviaron correos ni se modificaron expedientes reales para estas comprobaciones.

- [x] ~~Integrar la captura de publicaciones y comentarios de Facebook e Instagram mediante Meta.~~ Implementado; la disponibilidad depende de los permisos y del estado de cada fuente. No implica cobertura total del histórico.
- [x] ~~Separar captura de Meta y análisis en trabajos en segundo plano, con consulta de avance.~~ Implementado en el código actual; falta validar operación y recuperación en el despliegue de producción.
- [x] ~~Agregar Publicaciones y separar las fuentes externas del análisis sobre Johan.~~ Implementado; registrar una fuente no garantiza que Meta permita consultarla.
- [x] ~~Implementar análisis contextual de comentarios en Opinión sobre Johan.~~ Diferencia emoción, destinatario y postura. No certifica exactitud de todas las clasificaciones; los videos requieren contexto aportado.
- [x] ~~Optimizar los listados de publicaciones y casos con paginación, miniaturas y detalle bajo demanda.~~ Validado localmente; el rendimiento de producción queda pendiente.
- [x] ~~Agregar apertura y cierre del sidebar en escritorio.~~ Implementado.
- [x] ~~Implementar importación masiva de ciudadanos desde Excel/CSV.~~ Vista previa, validación, conservación de columnas y deduplicación por identificadores; pruebas de importación aprobadas.
- [x] ~~Importar el Excel de contactos proporcionado.~~ Se importaron 300 contactos en esa operación. Es un hecho histórico, no el conteo actual del directorio.
- [x] ~~Agregar eliminación individual y múltiple de ciudadanos.~~ Con confirmación, permisos y transacción; los casos y comentarios se conservan.
- [x] ~~Guardar creación y asociación de comentarios a casos en PostgreSQL.~~ Reemplaza cambios que antes solo existían en la pantalla. Incluye IDs completos, copia del comentario y usuario que realizó la asociación.
- [x] ~~Evitar duplicados al repetir una operación de triaje.~~ Pruebas de idempotencia, conflicto y persistencia aprobadas; comprobación PostgreSQL revertida sin dejar registros de prueba.
- [x] ~~Retirar el auto-despacho ficticio, los IDs de ejemplo y los porcentajes no medidos de la bandeja de revisión.~~ «Crear caso» no asigna responsables ni acredita despacho externo.
- [x] ~~Reorganizar Revisar comentarios con acciones claras.~~ Crear/vincular por comentario, selección múltiple, filtros, páginas de 10 y acceso al caso guardado. Tipos, lint del componente y rutas comprobados; aceptación visual final pendiente.
- [x] ~~Eliminar las portadas genéricas como reemplazo de imágenes originales.~~ Se indica la ausencia de imagen y no se toma otra publicación para rellenarla.
- [x] ~~Retirar el panel vacío de impacto de las tarjetas y mostrar seguimiento y responsable.~~ No se inventan evaluaciones para completar campos vacíos.
- [x] ~~Mostrar el texto y enlace de la publicación junto al comentario cuando hay un origen disponible.~~ Los registros incompletos se identifican como tales.
- [x] ~~Verificar directamente con Meta el caso CIV-2026-2667 y recuperar su publicación.~~ Los IDs y el texto del comentario coincidieron. Esa verificación individual no se extiende automáticamente al resto de los casos.
- [x] ~~Realizar una auditoría inicial de procedencia de los 2661 casos existentes en la fecha de revisión.~~ Script reproducible e informe disponibles; la limpieza completa sigue pendiente.
- [x] ~~Crear documentación central de arquitectura, reglas de negocio y pendientes.~~ Enlaces desde los README y advertencias sobre documentación antigua de demo.
- [x] ~~Rediseñar el recorrido de gestión de casos para priorizar contenido y acciones.~~ Bandeja de trabajo, filtros desplegables, regreso con contexto, comentario como contenido principal y decisión contextual. Capturas y pruebas de navegación en navegador aislado, TypeScript, lint sin errores y build aprobados. Ver [alcance y evidencia](REDISENO_GESTION_CASOS_20261124.md).
- [x] ~~Corregir los recortes iniciales de controles, tablas y formularios.~~ 14 vistas en 12 tamaños (320–2560 px), 18 comprobaciones de paneles y formularios, menú móvil y tablas con teclado. Esta revisión inicial fue insuficiente para validar el aprovechamiento del ancho; la captura posterior del usuario mostró límites fijos que seguían abiertos.
- [x] ~~Corregir la distribución en escritorio amplio y adaptar las cuadrículas al ancho real del contenido.~~ Retirados límites de 1600/860 px, márgenes compartidos, raíz ajustada a la barra de desplazamiento y columnas según el contenedor. Matriz ampliada a 17 vistas/variantes en 17 tamaños (320–3840 px), 63 comprobaciones con sidebar plegado y 26 de paneles/formularios. TypeScript y build aprobados. Ver [evidencia y límites](RESPONSIVE_20261124.md).
- [x] ~~Publicar en GitHub la entrega anterior y excluir las imágenes de caché del backend.~~ Backend `6be67e8` y `1f106be`; frontend `966d86b`. Los cambios locales posteriores no quedan publicados por ese hecho.

## 1. Datos y trazabilidad — en curso

- [ ] Recuperar y verificar los orígenes históricos que faltan, utilizando IDs exactos.
- [x] ~~Revisar el lote de 1115 registros sin ID individual y recuperar únicamente coincidencias estrictas.~~ 871 recuperados de captura local; 244 señalados con motivo persistente. Ver [informe de recuperación](RECUPERACION_ORIGEN_20261124.md).
- [ ] Resolver los 244 registros señalados: 152 conflictos con otro caso, 87 autores discrepantes/no disponibles y 5 textos sin coincidencia. No fusionar ni completar identidades por suposición.
- [x] ~~Comparar los 152 conflictos con el caso que reclama el mismo comentario y guardar evidencia.~~ 151 pares con diferencias en los datos del expediente y 1 con seguimiento registrado; enlaces entre casos disponibles. Ver [revisión de conflictos](REVISION_CONFLICTOS_20261124.md).
- [x] ~~Implementar comparación visual y consolidación reversible de pares.~~ Elección de principal, motivo, usuario, evidencia, protección del seguimiento, exclusión del duplicado de la bandeja y reversión sin sobrescribir avances. 61 pruebas y ensayo PostgreSQL revertido aprobados. Ver [funcionamiento](CONSOLIDACION_REVERSIBLE.md).
- [ ] Revisar y confirmar decisiones reales para los 152 pares, conservando bitácoras, responsables e IDs. Empezar por CIV-2026-0004 / CIV-2026-1294. Ningún par se consolidó automáticamente durante la implementación; falta aceptación visual.
- [x] ~~Revisar el comentario, contexto y bitácoras del primer par.~~ En CIV-2026-0004 se encontró «Despacho de prueba»; el comentario coincidente expresa una crítica general sin solicitud concreta identificada. Ver [evidencia y límites](REVISION_PRIMER_PAR_20261124.md).
- [ ] Revisar la clasificación del primer par y decidir su tratamiento como solicitud o conversación general, antes de resolver su posible duplicidad. La retirada del despacho de prueba no resuelve esa clasificación ni equivale a cerrar el caso.
- [x] ~~Evaluar el comentario y el texto de la publicación del primer par después de retirar el despacho de prueba.~~ Revisión de solo lectura: crítica general, sin solicitud concreta identificada en el texto disponible; ubicaciones Estadio/Ipanema sin respaldo textual. Propuesta preparada para confirmar ambos como No requiere gestión; todavía no aplicada. Ver [evaluación y límites](REVISION_PRIMER_PAR_20261124.md#revisión-de-clasificación-posterior-a-la-corrección).
- [x] ~~Implementar la corrección auditada de despachos de prueba.~~ Retiro explícito de asignación, decisión entre pendiente de revisión u opinión sin solicitud, motivo, usuario, evidencia y reversión protegida. Ver [recorrido y validaciones](CORRECCION_DESPACHOS_PRUEBA.md).
- [x] ~~Retirar con autorización el despacho de prueba de CIV-2026-0004 y dejarlo Pendiente de revisión.~~ Confirmación explícita del usuario y aplicación por API con auditoría reversible. Responsable y dependencia retirados; comentario y notas conservados; CIV-2026-1294 intacto. Ver [resultado real](CORRECCION_DESPACHOS_PRUEBA.md#aplicación-real-autorizada).
- [ ] Revisar las publicaciones y comentarios referenciados que no aparecen en la captura local. Sus cantidades son una fotografía de la auditoría, no un conteo fijo.
- [ ] Identificar y retirar datos de demostración que se comprueben como tales en todo el proyecto, incluidos contactos y métricas. No eliminar registros solo por falta de evidencia.
- [x] ~~Mantener diferenciados: contenido capturado, datos verificados, clasificación inferida y datos no disponibles.~~ Corregidos ceros desconocidos, identidad histórica y mezcla de comentarios/expedientes; la evidencia depende de la captura disponible.
- [ ] Sustituir asociaciones antiguas por nombre/fallback por relaciones de origen explícitas.
- [ ] Revisar qué casos históricos realmente contienen una solicitud y cuáles son saludos, respuestas u opiniones.

## 2. Indicadores reales

- [x] ~~Eliminar el incremento fijo de `1280` y los indicadores simulados de Inicio.~~ Los cuatro perfiles consultan los agregados del backend, con alcance global explícito; se retiraron nombres, tiempos, capacidades y porcentajes de ejemplo del resumen.
- [x] ~~Calcular indicadores globales en backend, sin depender de una página limitada de casos.~~ Consulta sobre todo el histórico, con criterio de exclusión de duplicados consistente con la bandeja; prueba aislada con más de 500 registros.
- [x] ~~Separar conteos reportados por Meta, comentarios capturados, expedientes y análisis contextuales.~~ Conteos por red, IDs únicos por publicación y resultados contextuales vigentes; etiquetas históricas mostradas como sujetas a revisión.
- [x] ~~Mostrar fecha de consulta, modificación registrada y datos no medidos sin inventar resultados.~~ Tiempo de atención No disponible; errores y base vacía comprobados, con cero real conservado.
- [x] ~~Retirar la tendencia semanal y el informe con cifras simuladas.~~ PDF, CSV e impresión comparten las cifras de la pantalla; exportación y lectura visual comprobadas. Ver [definiciones y pruebas](INDICADORES_REALES_20261124.md).
- [x] ~~Instrumentar eventos de atención estructurados antes de calcular tiempos promedio, metas o cumplimiento.~~ Asignación, avances, borradores, cierre, reapertura y referencias externas conservan actor y fecha. No se reconstruyen tiempos históricos ausentes.

## 3. Seguridad y sesiones

- [x] ~~Preparar Gmail para añadir o cambiar después el remitente sin modificar código.~~ Host, puerto y TLS configurables. Ver [configuración y cambio de correo](CORREO_GMAIL.md).
- [x] ~~Configurar la cuenta temporal y su contraseña de aplicación en el entorno privado.~~ Gmail aceptó conexión TLS y autenticación SMTP. Correo del Administrador actualizado con autorización, accesos anteriores revocados y nuevo inicio de sesión comprobado. No se publicaron credenciales ni se enviaron mensajes de prueba.
- [x] ~~Aplicar a los correos de seguridad el logo, lema y colores actuales de la plataforma.~~ Recuperación y aviso de cambio de clave con «Ordenemos a Neiva», paleta negra/verde/dorada y logo PNG idéntico al acceso, adjunto por Content-ID. Retirado Ordenemos a Neiva de asunto, remitente y contenido visible. 39 pruebas de recuperación/sesiones/operación y ocho comprobaciones visuales entre 320 y 1440 px aprobadas; sin envíos de prueba.
- [ ] Confirmar los buzones reales de los demás usuarios y comprobar recepción del código y restablecimiento completo. Autenticación SMTP correcta no acredita llegada a la bandeja del destinatario.

- [x] ~~Retirar acceso automático, accesos de un clic, cambio de rol de presentación y aceptación de `demo-token-*`.~~ La pantalla espera la validación del servidor; no hay acceso local alternativo. Las cuentas existentes se conservan y requieren revisión de titulares y claves. Ver [alcance, permisos y evidencia](SEGURIDAD_SESIONES_20261125.md).
- [x] ~~Manejar sesión vencida o inválida: cerrar la sesión visual y permitir iniciar sesión nuevamente con un mensaje claro.~~ Regreso a la ruta original, reintento ante fallo de red y tratamiento separado de 401/403. 23 comprobaciones de navegador y 10 del cliente aprobadas; privacidad y eliminación de datos permanecen públicas.
- [x] ~~Aplicar autenticación y permisos por rol de forma uniforme a las rutas sensibles publicadas.~~ Política central, rol vigente consultado en PostgreSQL, administración solo ADMIN y actor real en notas/asignaciones/cierres. Inventario de operaciones protegido con pruebas; imágenes públicas y entradas de autenticación/webhook son excepciones explícitas.
- [x] ~~Deshabilitar seed y simulación de comentarios en la API publicada.~~ Responden 410 también para ADMIN; no se cargaron ni eliminaron datos históricos.
- [x] ~~Validar la firma de eventos POST del webhook antes de procesarlos.~~ HMAC sobre el cuerpo original; sin registrar secretos. Se retiró la exposición del OTP y el falso éxito de envío de recuperación.
- [x] ~~Completar deduplicación, procesamiento diferido y límites compartidos del webhook.~~ Bandeja PostgreSQL, firma, deduplicación, reintentos y límites probados; recepción real en el dominio definitivo pendiente.
- [ ] Confirmar titulares/correos/departamentos y cambiar las credenciales iniciales de las cuentas históricas. SMTP local configurado y autenticado; falta completar validación operativa y configuración del destino de producción.
- [x] ~~Proteger la sesión con cookie HttpOnly/Secure y revocación en el servidor.~~ Intermediario Next, registros de sesión, cierre actual o de todos y cambio/restablecimiento que invalida accesos anteriores. Mi cuenta y seguridad disponible para los cuatro roles. 27 pruebas de backend, 10 del intermediario y 14 de navegador aislado aprobadas; tipos, lint y build correctos. Backend local activado, usuarios y datos de negocio intactos. Ver [funcionamiento y límites](SEGURIDAD_SESIONES_20261125.md#mi-cuenta-y-revocación).
- [x] ~~Proteger OTP en almacenamiento y uniformar las respuestas de recuperación.~~ HMAC con nonce y vínculo a la cuenta/contraseña, 15 minutos, cinco errores, uso único y reenvío que sustituye el anterior. Mensajes condicionales iguales y búsqueda/envío posteriores a la respuesta. Sin SMTP, 503 igual para todos; envío real pendiente. Ver [funcionamiento y comprobaciones](SEGURIDAD_SESIONES_20261125.md#recuperación-y-configuración).
- [x] ~~Aplicar límites de autenticación compartidos entre procesos.~~ Contadores atómicos en PostgreSQL por conexión y por correo normalizado, Retry-After y claves HMAC. 40 pruebas de backend, ensayo PostgreSQL en tabla temporal y 12 comprobaciones de navegador aprobados; no se enviaron correos reales.
- [ ] Confirmar duración definitiva y retención de sesiones; configurar límites por IP real en el acceso público y la operación/reintentos del envío de correo. El intermediario concentra las conexiones a FastAPI; no sustituye el control por IP original en el proxy público.
- [x] ~~Confirmar el alcance de consulta por dependencia para Secretarías.~~ El usuario confirmó todos los expedientes de Ordenemos a Neiva; alcance global y permisos de actuación por rol.
- [x] ~~Implementar historial estructurado de las actuaciones de atención.~~ Creación manual o desde comentarios, vínculos, asignación, avances, borradores, decisiones y cierre conservan usuario, fecha y campos anteriores/posteriores en la misma transacción. No se inventaron eventos históricos. Ver [flujo y comprobaciones](FLUJO_ATENCION_20261125.md).
- [x] ~~Extender la auditoría estructurada a administración de cuentas, contactos y operaciones del sistema.~~ Actor, motivo cuando corresponde y trazabilidad; consulta en /audit sin credenciales.

## 4. Reglas de atención

- [x] ~~Unificar y validar las transiciones del flujo actual en backend.~~ Pendiente → En Gestión mediante asignación, En Gestión → Resuelto con soporte, y decisión motivada de conversación general desde pendiente. PATCH, creación manual y borradores desde Ciudadanos no saltan estas acciones; estados desconocidos o cerrados se rechazan para atención ordinaria.
- [x] ~~Completar las validaciones de responsables, evidencia y cierre en los caminos publicados de atención.~~ Revisión confirmada, persona/equipo, próxima actuación, referencia del soporte, actor real, versión revisada y protección del historial. 155 pruebas aprobadas, incluidas 29 del flujo; no se cerraron expedientes reales para probarlo.
- [x] ~~Implementar reapertura ordinaria con motivo, permisos y conservación del cierre anterior.~~ Administración/Secretaría, motivo y confirmación, versión vigente y bloqueo de duplicados. Resuelto/No requiere gestión → Pendiente, sin asignación, borrador ni solución activos; el cierre y sus soportes se conservan en Historial. No se puede simular por PATCH. 56 pruebas de backend y 19 de navegador aprobadas; tipos, lint y build correctos. Backend local activado, sin reaperturas reales. Ver [flujo de reapertura](FLUJO_ATENCION_20261125.md#reabrir-una-decisión).
- [x] ~~Separar códigos internos de cualquier radicado oficial externo.~~ Número, entidad, fecha, soporte y declaración de revisión; corrección/retirada conservan historial y no simulan recepción externa.
- [x] ~~Separar la creación de casos de las consultas de incidentes: una lectura no crea expedientes.~~ Retirada la conversión automática desde GET; incidente sin expediente devuelve 404. Prueba aislada verifica que un rol de consulta no pueda crear por esa vía ni alterar el incidente.
- [x] ~~Verificar con pruebas aisladas la consistencia entre caso, comentarios, mapa, seguimiento y cifras del informe.~~ El comentario y sus vínculos se conservan; el mapa y las métricas leen el estado del caso, y conversación general no se registra como solución. Falta aceptación con solicitudes reales en el bloque 5.

## 5. Validación integral

- [ ] Comprobar la adaptación en dispositivos físicos y Safari/iOS, incluyendo teclado virtual y orientación; completar aceptación visual del usuario. La matriz de Chromium no sustituye estas comprobaciones.
- [ ] Revisar contigo la interfaz reorganizada y confirmar que el recorrido resulta comprensible.
- [ ] Extender los criterios de jerarquía y acciones claras a Inicio, Opinión, Publicaciones, Indicadores y Ciudadanos, revisando cada tarea y su aceptación. El rediseño actual no acredita que toda la plataforma esté terminada.
- [ ] Probar el flujo completo con solicitudes reales: captura → revisión → caso → asignación → seguimiento → cierre.
- [x] ~~Completar pruebas de permisos, duplicados, fallos de red, sesiones vencidas y recuperación.~~ Suite de backend y pruebas aisladas de sesiones, intermediario y flujo HTTPS aprobadas. Entrega SMTP y aceptación externa siguen abiertas.
- [x] ~~Corregir expectativas antiguas de métricas y separar la comprobación en vivo de Meta de la suite local.~~ Suite completa aprobada.
- [x] ~~Ejecutar la prueba en vivo de Instagram y comprobar la publicación reciente contra Meta.~~ Ejecución separada aprobada; conexión lista sin permisos faltantes y publicación reciente presente. Lectura de Facebook también autorizada; webhook público pendiente.
- [ ] Evaluar calidad del análisis contextual con una muestra revisada y medir ambigüedad, sin convertir resultados del modelo en hechos sobre las personas.
- [x] ~~Revalidar tipos, build y pruebas de la entrega local.~~ Next 16.4.6/Node 24, TypeScript, cero errores de lint y 241 pruebas sin fallos (una validación Meta en vivo omitida). La publicación exacta requiere registrar ambas revisiones.

## 6. Preparación y salida a producción

- [ ] Definir alojamiento, dominio y responsables de operación.
- [ ] Configurar secretos, HTTPS, CORS y URLs del frontend/backend para ese entorno.
- [x] ~~Centralizar las llamadas que todavía tienen localhost escrito directamente.~~ Navegador usa /api/backend y /assets; URL privada de FastAPI y origen público configurables en el servidor.
- [x] ~~Preparar migraciones reproducibles y comprobarlas en PostgreSQL vacío y local existente.~~ Aplicación doble idempotente, ledger de huellas y comprobación de esquema. Ejecutarlas en el destino definitivo sigue pendiente.
- [x] ~~Preparar copias cifradas y probar una restauración completa.~~ 19 tablas y 2515 archivos restaurados físicamente en destino desechable; sobrescritura rechazada. Falta instalar programación, alertas y almacenamiento externo.
- [ ] Definir retención y tratamiento de datos personales y multimedia.
- [ ] Validar recuperación y reintentos de trabajos; revisar coordinación antes de usar múltiples procesos o réplicas.
- [ ] Configurar monitoreo, alertas y un procedimiento de reversión del despliegue.
- [x] ~~Revisar, agrupar y publicar esta entrega en ambos repositorios.~~ Publicados y verificados en `main` el 24/11/2026: backend `aed2eee`, frontend `bf251dc`. No equivale a desplegar en producción; futuros cambios necesitarán su propia publicación.
- [ ] Desplegar, ejecutar pruebas de aceptación en el entorno publicado y aprobar el inicio de operación.

## Cierre técnico de preparación — 25/11/2026

- [x] ~~Preparar despliegue Linux, comprobación de esquema, copias, importación a destino vacío y procedimiento de reversión.~~ Ver [paquete y evidencia](PREPARACION_PRODUCCION_20261125.md) y [manual del operador](../deploy/README.md).
- [x] ~~Retirar los datos del seed publicado, afirmaciones predefinidas de borradores y embeddings ficticios.~~ El endpoint antiguo devuelve 410; no se eliminaron expedientes reales sin evidencia.
- [x] ~~Comprobar el flujo HTTPS de radicado a reapertura y adaptación de 14 rutas entre 320 y 3840 px.~~ 147 comprobaciones aprobadas en la compilación de producción y PostgreSQL aislado; revisión visual de móvil y escritorio amplio. No sustituye Safari/dispositivos físicos.
- [ ] Instalar y validar imágenes Linux, SMTP real, dominio/certificado, copias externas y alertas en el destino confirmado.

## Registro de evidencias y cambios

| Fecha | Entrega / revisión | Evidencia y límites |
| --- | --- | --- |
| 25/11/2026 | Preparación de producción | Suite 241 sin fallos (1 Meta en vivo omitida), 12 del intermediario, 147 de navegador HTTPS, restauración de 19 tablas y 2515 archivos; usuarios y negocio conservados. Paquete operativo preparado; despliegue y servicios externos pendientes. |
| 13/11/2026 | Importación, eliminación, optimización inicial y publicación de código | Resultados históricos registrados en la conversación. No sustituyen pruebas de la versión local posterior. |
| 24/11/2026 | Documento central y revisión del estado real | Inspección de código; identificados restos de demo, problemas de indicadores y permisos. |
| 24/11/2026 | Triaje persistente | 10 pruebas aisladas, 8 de lectura de casos y 7 de flujo caso–mapa aprobadas; comprobación PostgreSQL con rollback. Dos fallos de la suite general de Meta registrados como pendientes. |
| 24/11/2026 | Reorganización de revisión de comentarios | TypeScript y lint de componentes aprobados; 10 pruebas de triaje aprobadas; respuesta HTTP y campos de origen comprobados. Inspección visual automatizada no disponible. |
| 24/11/2026 | Contexto de publicación y auditoría inicial | Verificación individual con Meta; 9 pruebas de lectura de casos aprobadas; el informe no certifica limpieza de toda la plataforma. |
| 24/11/2026 | Recuperación de referencias históricas | Lote de 1115 revisado; 871 IDs recuperados y 244 casos señalados; 12 pruebas aisladas y ensayo PostgreSQL con rollback; sin eliminación ni fusión de casos. |
| 24/11/2026 | Publicación de la entrega | Backend `aed2eee` y frontend `bf251dc` confirmados en GitHub. Credenciales, Excel, base de datos, caché e informes detallados locales excluidos. |
| 24/11/2026 | Comparación de 152 conflictos | 151 pares con diferencias de expediente y 1 con seguimiento; auditoría guardada sin cambios en casos o vínculos. 42 pruebas, TypeScript y lint aprobados; consolidación y aceptación visual pendientes. Esta entrega es posterior a la publicación anterior. |
| 24/11/2026 | Consolidación reversible | Flujo implementado, tabla local preparada y migración incluida. 61 pruebas y ensayo PostgreSQL con rollback aprobados; 2661 casos y 871 vínculos intactos. TypeScript y lint sin errores. Decisiones reales, aceptación visual y publicación de esta entrega pendientes. |
| 24/11/2026 | Revisión de negocio del primer par | Consulta de solo lectura: texto sin solicitud concreta identificada y nota explícita «Despacho de prueba». No se modificaron registros. La clasificación y el efecto operativo de esa prueba quedan pendientes de corrección auditada. |
| 24/11/2026 | Corrección auditada de despachos de prueba | Acción disponible con permisos, evidencia, motivo y reversión protegida. Ensayo PostgreSQL revertido, sin cambios persistentes en los casos. TypeScript y lint sin errores; confirmación del expediente real y aceptación visual pendientes. |
| 24/11/2026 | Rediseño del recorrido de casos | Bandeja y expediente reorganizados; navegación compartida compacta. Prueba de navegador con cero escrituras y errores de ejecución, regreso con filtros/página, capturas de escritorio/tableta/móvil y temas claro/oscuro revisadas. TypeScript, lint y build aprobados. Aceptación del usuario y demás secciones pendientes. |
| 24/11/2026 | Adaptación inicial de controles | 168 comprobaciones de tamaños y vistas, 18 de paneles/formularios, menú y tablas con teclado. TypeScript y build aprobados. La captura posterior del usuario demostró que faltaba validar la distribución amplia; se conserva esta limitación en la trazabilidad. |
| 24/11/2026 | Corrección de distribución amplia | Áreas de trabajo sin límites fijos a la izquierda, cuadrículas adaptadas al contenedor y revisión visual de escritorio amplio. Matriz de 289 comprobaciones, 63 con sidebar plegado y 26 de paneles/formularios. TypeScript y build aprobados. Pendientes dispositivos físicos, Safari/iOS y aceptación del usuario. |
| 24/11/2026 | Retirada autorizada del primer despacho de prueba | CIV-2026-0004 pasó a Pendiente, sin responsable ni dependencia; requiere revisión. Operación `413a0724-d529-42be-9c11-bf64c1542113`, con evidencia, motivo y reversión protegida. Comentario y notas intactos, par CIV-2026-1294 sin cambios; 2661 casos y 871 vínculos conservados. Diez pruebas aisladas de corrección aprobadas antes de aplicar. Clasificación y duplicidad pendientes. |
| 24/11/2026 | Evaluación de la clasificación del primer par | Comentario y texto de publicación revisados en transacción de solo lectura. No se identifica solicitud concreta; propuesta No requiere gestión para ambos pendiente de confirmación. Se detectaron ubicaciones históricas discrepantes sin respaldo textual. Sin modificación de casos o vínculos; no se inspeccionó el video ni se consultó nuevamente Meta. |
| 24/11/2026 | Cifras guardadas en Inicio, Indicadores e informes | Resumen común del backend, sin límite de página ni métricas simuladas. Separados expedientes/captura/conteos Meta/contexto; tiempo no medido explícito. 19 pruebas de indicadores y mapa, comprobación PostgreSQL de solo lectura, 37 comprobaciones de navegador, 34 de tamaños y exportaciones PDF/CSV/impresión verificadas. TypeScript, lint y build aprobados. Persisten pendientes de calidad histórica y seguridad. |
| 25/11/2026 | Sesiones registradas y Mi cuenta | Cookie HttpOnly/Secure, JWT fuera de localStorage/JavaScript, cierre con revocación y cambio de contraseña que invalida accesos anteriores. 27 pruebas de backend, 10 del intermediario y 14 de navegador; tipos, lint y build correctos. Backend local activado y huellas de usuarios/datos idénticas antes y después. Recuperación protegida, revisión integral y despliegue pendientes. |
| 25/11/2026 | Recuperación protegida y límites compartidos | HMAC de OTP, caducidad, cinco errores, uso único, mensajes uniformes y envío posterior a la respuesta. 40 pruebas de backend, ensayo PostgreSQL con tabla temporal/rollback y 12 de navegador aislado aprobados; tipos, lint y build correctos. Backend local actualizado, usuarios/contraseñas/datos intactos y tablas nuevas sin fixtures. SMTP real ausente; proveedor/remitente pendientes de definir. |
| 25/11/2026 | Reapertura auditada de expedientes | Acción con motivo, confirmación, roles y versión; vuelve a pendiente y conserva la decisión anterior. 56 pruebas de backend y 19 comprobaciones de navegador (incluidos 320–2560 px), tipos, lint y build correctos. Backend local activado; huellas de usuarios y datos intactas. Pruebas solo en SQLite temporal; sin reaperturas reales. |

Documentos de referencia:

- [Arquitectura y lógica de negocio](PROYECTO_CIVIA.md).
- [Auditoría inicial de datos](AUDITORIA_DATOS_20261124.md).
- Pruebas: `backend-civia/tests/`.

Al cerrar una tarea: marcarla, tachar su título y registrar fecha y evidencia. Si una comprobación falla, conservarla abierta. No usar porcentajes de avance sin un alcance y un criterio de medición definidos.
