# CIVIA — seguimiento de desarrollo

Actualizado: **24 de noviembre de 2026**.

Este archivo es la lista central de avance. Una tarea terminada se marca `[x]` y se tacha con `~~texto~~`. Las tareas parciales permanecen abiertas. «Terminado» significa implementado y comprobado en el alcance indicado; no implica aprobación para producción ni publicación en GitHub.

## Desarrollado y comprobado

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
- [x] ~~Publicar en GitHub la entrega anterior y excluir las imágenes de caché del backend.~~ Backend `6be67e8` y `1f106be`; frontend `966d86b`. Los cambios locales posteriores no quedan publicados por ese hecho.

## 1. Datos y trazabilidad — en curso

- [ ] Recuperar y verificar los orígenes históricos que faltan, utilizando IDs exactos.
- [x] ~~Revisar el lote de 1115 registros sin ID individual y recuperar únicamente coincidencias estrictas.~~ 871 recuperados de captura local; 244 señalados con motivo persistente. Ver [informe de recuperación](RECUPERACION_ORIGEN_20261124.md).
- [ ] Resolver los 244 registros señalados: 152 conflictos con otro caso, 87 autores discrepantes/no disponibles y 5 textos sin coincidencia. No fusionar ni completar identidades por suposición.
- [ ] Revisar las publicaciones y comentarios referenciados que no aparecen en la captura local. Sus cantidades son una fotografía de la auditoría, no un conteo fijo.
- [ ] Identificar y retirar datos de demostración que se comprueben como tales en todo el proyecto, incluidos contactos y métricas. No eliminar registros solo por falta de evidencia.
- [ ] Mantener diferenciados: contenido capturado, datos verificados, clasificación inferida y datos no disponibles.
- [ ] Sustituir asociaciones antiguas por nombre/fallback por relaciones de origen explícitas.
- [ ] Revisar qué casos históricos realmente contienen una solicitud y cuáles son saludos, respuestas u opiniones.

## 2. Indicadores reales

- [ ] Eliminar el incremento fijo de `1280` del total de reportes de Inicio.
- [ ] Calcular indicadores globales en backend, sin depender de una página limitada de casos.
- [ ] Separar conteos reportados por Meta, comentarios capturados, casos y análisis contextuales.
- [ ] Mostrar fecha de actualización y datos desconocidos sin convertirlos en resultados confirmados.

## 3. Seguridad y sesiones

- [ ] Retirar acceso automático, cuentas de presentación y aceptación de `demo-token-*` fuera del entorno aislado de pruebas.
- [ ] Manejar sesión vencida o inválida: cerrar la sesión visual y permitir iniciar sesión nuevamente con un mensaje claro.
- [ ] Aplicar autenticación y permisos por rol de forma uniforme a todas las rutas sensibles.
- [ ] Restringir seed, simuladores y herramientas de prueba en producción.
- [ ] Revisar autenticidad de eventos del webhook, deduplicación y límites de solicitudes.
- [ ] Definir auditoría estructurada de operaciones, además de las notas actuales.

## 4. Reglas de atención

- [ ] Unificar y validar las transiciones permitidas de estado en backend.
- [ ] Completar las validaciones de responsables, evidencia y cierre en todos los caminos de modificación.
- [ ] Separar códigos internos de cualquier radicado oficial externo.
- [ ] Separar la creación de casos de las consultas de incidentes: una lectura no debería crear expedientes.
- [ ] Verificar la consistencia entre caso, comentarios, mapa, seguimiento e informes.

## 5. Validación integral

- [ ] Revisar contigo la interfaz reorganizada y confirmar que el recorrido resulta comprensible.
- [ ] Probar el flujo completo con solicitudes reales: captura → revisión → caso → asignación → seguimiento → cierre.
- [ ] Completar pruebas de permisos, duplicados, fallos de red, sesiones vencidas y recuperación.
- [ ] Resolver los dos fallos detectados en la suite general de Meta: expectativa anterior de métricas y publicación reciente de Instagram ausente de la captura consultada.
- [ ] Evaluar calidad del análisis contextual con una muestra revisada y medir ambigüedad, sin convertir resultados del modelo en hechos sobre las personas.
- [ ] Revalidar tipos, build y pruebas sobre la versión exacta que se vaya a publicar.

## 6. Preparación y salida a producción

- [ ] Definir alojamiento, dominio y responsables de operación.
- [ ] Configurar secretos, HTTPS, CORS y URLs del frontend/backend para ese entorno.
- [ ] Centralizar las llamadas que todavía tienen `localhost` escrito directamente.
- [ ] Preparar y comprobar migraciones reproducibles sobre la base de destino.
- [ ] Configurar copias de seguridad y probar una restauración.
- [ ] Definir retención y tratamiento de datos personales y multimedia.
- [ ] Validar recuperación y reintentos de trabajos; revisar coordinación antes de usar múltiples procesos o réplicas.
- [ ] Configurar monitoreo, alertas y un procedimiento de reversión del despliegue.
- [x] ~~Revisar, agrupar y publicar esta entrega en ambos repositorios.~~ Publicados y verificados en `main` el 24/11/2026: backend `aed2eee`, frontend `bf251dc`. No equivale a desplegar en producción; futuros cambios necesitarán su propia publicación.
- [ ] Desplegar, ejecutar pruebas de aceptación en el entorno publicado y aprobar el inicio de operación.

## Registro de evidencias y cambios

| Fecha | Entrega / revisión | Evidencia y límites |
| --- | --- | --- |
| 13/11/2026 | Importación, eliminación, optimización inicial y publicación de código | Resultados históricos registrados en la conversación. No sustituyen pruebas de la versión local posterior. |
| 24/11/2026 | Documento central y revisión del estado real | Inspección de código; identificados restos de demo, problemas de indicadores y permisos. |
| 24/11/2026 | Triaje persistente | 10 pruebas aisladas, 8 de lectura de casos y 7 de flujo caso–mapa aprobadas; comprobación PostgreSQL con rollback. Dos fallos de la suite general de Meta registrados como pendientes. |
| 24/11/2026 | Reorganización de revisión de comentarios | TypeScript y lint de componentes aprobados; 10 pruebas de triaje aprobadas; respuesta HTTP y campos de origen comprobados. Inspección visual automatizada no disponible. |
| 24/11/2026 | Contexto de publicación y auditoría inicial | Verificación individual con Meta; 9 pruebas de lectura de casos aprobadas; el informe no certifica limpieza de toda la plataforma. |
| 24/11/2026 | Recuperación de referencias históricas | Lote de 1115 revisado; 871 IDs recuperados y 244 casos señalados; 12 pruebas aisladas y ensayo PostgreSQL con rollback; sin eliminación ni fusión de casos. |
| 24/11/2026 | Publicación de la entrega | Backend `aed2eee` y frontend `bf251dc` confirmados en GitHub. Credenciales, Excel, base de datos, caché e informes detallados locales excluidos. |

Documentos de referencia:

- [Arquitectura y lógica de negocio](PROYECTO_CIVIA.md).
- [Auditoría inicial de datos](AUDITORIA_DATOS_20261124.md).
- Pruebas: `backend-civia/tests/`.

Al cerrar una tarea: marcarla, tachar su título y registrar fecha y evidencia. Si una comprobación falla, conservarla abierta. No usar porcentajes de avance sin un alcance y un criterio de medición definidos.
