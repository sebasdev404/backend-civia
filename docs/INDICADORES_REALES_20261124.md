# Inicio, Indicadores e informes basados en datos guardados

Fecha: **24 de noviembre de 2026**.

## Resultado

Inicio e Indicadores consultan `GET /api/v1/analytics/overview`. Se retiraron el incremento fijo de 1280, los indicadores simulados por rol, las series semanales de ejemplo, los porcentajes de operación y los tiempos constantes. Todos los perfiles usan los mismos agregados globales; Inicio indica que el alcance incluye todas las dependencias. El acceso por rol y departamento se revisará en la etapa de seguridad, sin presentar un filtro de pantalla como autorización.

Las consultas no crean expedientes, no sincronizan Meta ni solicitan análisis a IA. Los gráficos reutilizan la respuesta del padre y muestran las distribuciones guardadas; ya no consultan de nuevo los totales ni completan categorías sin datos con valores de ejemplo.

## Definiciones

| Indicador | Fuente y alcance |
| --- | --- |
| Expedientes guardados | Conteo completo de `cases`. No está limitado a la página de 500 registros. |
| Expedientes en bandeja | Mismo criterio de exclusión de duplicados con consolidación activa que la bandeja de casos. Incluye los distintos estados del histórico; no acredita solicitudes confirmadas. |
| Pendientes o en gestión | Estados Pendiente, Nuevo y En Gestión. Los estados Resuelto y No requiere gestión se muestran aparte. |
| Prioridad alta o crítica pendiente | Expedientes abiertos con prioridad Alta o Crítica. Un caso cerrado de prioridad alta no se cuenta como urgente abierto. |
| Origen señalado para revisión | Señales persistentes de procedencia, excluidas las relaciones ya consolidadas. No certifica el origen de los demás registros. |
| Publicaciones | Registros de `meta_posts` de las redes conectadas. Una publicación compartida en Facebook e Instagram conserva dos registros. No incluye fuentes externas guardadas en `observed_posts`. |
| Comentarios capturados | IDs únicos dentro de cada publicación, incluidas respuestas. No se deduplican comentarios de publicaciones o redes diferentes por parecido de texto. Las entradas sin ID no se consideran identificadores verificados. |
| Comentarios reportados guardados | Suma de los conteos persistidos de Meta. Puede diferir de la captura por respuestas, disponibilidad o fecha. Se muestran publicaciones sin conteo disponible; los ceros heredados de la captura no permiten reconstruir si Meta entregó originalmente un dato ausente. |
| Análisis contextual | Comentarios de texto de publicaciones explícitamente identificadas como Facebook. Se valida la huella del contexto y comentario; un resultado obsoleto vuelve al conjunto pendiente. Apoyos y críticas excluyen análisis señalados para revisión. |
| Categorías, emociones y dependencias | Etiquetas almacenadas de los expedientes de la bandeja. No se corrigen ni verifican sus clasificaciones por mostrarlas. Las emociones desconocidas conservan su etiqueta y no se convierten en paz o apoyo. |
| Palabras frecuentes | Frecuencias textuales en comentarios capturados con ID; se excluyen palabras comunes. No representan gravedad ni solicitudes confirmadas. |
| Menciones territoriales | Mismo auditor de origen y lugar textual que utiliza el mapa. Se cuentan combinaciones únicas de publicación, comentario y lugar. Se muestran diez lugares con más menciones, sin inventar gravedad, categorías secundarias, puntajes o actuaciones. |
| Tiempo promedio de atención | `null`: no hay eventos estructurados suficientes para medirlo. Se presenta No disponible, sin un tiempo de respaldo ni una meta institucional inventada. |

La respuesta diferencia la fecha de consulta de la última modificación registrada. Esta última no equivale a una sincronización completa exitosa. En pantalla se usa la zona horaria `America/Bogota`.

## Estados de pantalla y exportación

- Carga: mensaje visible, sin cifras de ejemplo.
- Base vacía: se conserva el cero real y se informa que no hay distribuciones disponibles.
- Fallo de red/API: error con Reintentar; no se publican cifras de respaldo ni se permite exportar un resumen ausente.
- Actualizar cifras vuelve a consultar el resumen. No ejecuta una captura de redes.
- El informe usa el mismo objeto de datos que la pantalla y se identifica como histórico guardado. Se eliminaron autoridad, firmas, semana operativa, actuaciones territoriales y tablas de eficiencia de ejemplo.
- PDF, CSV e impresión se generan a partir de una única lista de indicadores y definiciones. El CSV conserva Unicode, escapa comillas y protege cadenas que podrían interpretarse como fórmulas.
- El PDF paginado incluye fecha de consulta y numeración. La impresión utiliza un portal fuera del contenedor de la aplicación para evitar recortes y páginas vacías; se fuerza fondo claro al imprimir desde el tema oscuro.

Las rutas anteriores `/analytics/summary`, `/analytics/kpis` y `/analytics/top-barrios` también se corrigieron: los campos sin medición se devuelven nulos y el ranking usa menciones con evidencia. La forma de `channels` en `/kpis` y de los elementos del ranking cambia; las vistas actuales usan `/overview`.

## Validación y fotografía de datos

La comprobación de solo lectura obtuvo **2661 expedientes, 1877 publicaciones, 13.859 comentarios capturados y 12.414 comentarios reportados guardados**. Facebook aporta 11.796 comentarios capturados e Instagram 2063. Son cifras de la comprobación, no constantes del código.

- 12 pruebas aisladas de indicadores: base vacía, total superior a 500, duplicados activos/revertidos, estados cerrados, respuestas, IDs repetidos, captura inválida, emociones desconocidas, análisis vigente/obsoleto, deduplicación territorial, fecha de modificación del contexto y ausencia de escrituras/llamadas IA.
- 19 pruebas aprobadas al combinar indicadores y flujo caso–mapa.
- Comprobación PostgreSQL dentro de una transacción de solo lectura: sumas coherentes y huellas de casos, vínculos, correcciones y consolidaciones intactas. Consultas locales medidas entre aproximadamente 0,73 y 0,86 s; no es una garantía de producción.
- 37 comprobaciones de navegador: los cuatro perfiles existentes, cifras del backend, actualización, descarga PDF/CSV, error de red y cero real. Cero solicitudes de escritura intentadas y cero errores de ejecución.
- 34 comprobaciones responsive de Inicio e Indicadores: 17 tamaños entre 320 y 3840 px. Informe comprobado en móvil, horizontal, portátil y escritorio amplio.
- 8 comprobaciones del generador de informe, incluidos cero, dato ausente y escape de CSV.
- PDF descargado de cinco páginas e impresión de seis páginas comprobados mediante extracción y renderizado. Las 75 filas exportadas aparecen en la impresión, sin bloques de texto fuera de página.
- TypeScript, lint de los archivos modificados y build de producción aprobados.

Evidencia local fuera de Git en `artifacts/`: `verify_real_analytics.json`, `analytics-map-tests.log`, `metrics-ui-result.json`, `metrics-responsive.log`, `metrics-pdf-checks.json`, `metrics-print-pdf-checks.json`, `metrics-exports/` y `frontend-metrics-build.log`.

## Pendientes que conserva esta entrega

- Calidad y clasificación de registros históricos: mostrar un conteo exacto no valida el contenido de cada registro.
- Instrumentar eventos de atención antes de publicar promedios o indicadores de cumplimiento.
- Ampliar las métricas a fuentes externas con una definición separada y explícita.
- Retirar los restantes datos de demostración de otras secciones, endurecer autenticación/permisos y completar la aceptación de producción.
