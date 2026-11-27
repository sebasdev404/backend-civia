# Opinión sobre Johan: análisis completo y revisión

Actualizado: 26 de noviembre de 2026.

## Problema comprobado

La auditoría inicial encontró 11.837 comentarios de Facebook capturados: 9.755 sin analizar y 53 analizados pero dudosos. La pantalla sumaba ambos grupos en «Por revisar» (9.808). Los 9.755 pendientes pertenecían a videos sin resumen o transcripción: el servicio los descartaba antes de consultar a la IA. El botón síncrono también tenía un límite de 20 comentarios por solicitud.

Son cifras de esa auditoría, no un contador fijo: la captura y el análisis siguen modificando los totales.

## Funcionamiento actual

- **Analizar pendientes y dudosos** inicia un trabajo persistido, con respuesta HTTP 202. Recorre los comentarios sin análisis vigente y los resultados que necesitan revisión, dentro del período y la publicación seleccionados. La búsqueda, la postura y la página visible no reducen ese alcance.
- Los videos sin transcripción también se incluyen. Se entregan a la IA el texto disponible, el comentario y su padre cuando está capturado; no se presenta el texto de la publicación como una transcripción ni se inventa el contenido audiovisual.
- La IA distingue apoyo, crítica a Johan, postura mixta, ausencia de postura y ambigüedad. La emoción no decide la postura. Criticar a otro funcionario no equivale a criticar a Johan; una petición dirigida a Johan junto con críticas a terceros tampoco se convierte por ello en postura mixta.
- «Por revisar» separa **sin analizar** y **analizados que necesitan revisión**. Un mensaje neutral puede quedar correctamente clasificado sin aparecer como ambiguo.
- El modelo de opinión se configura con `OPINION_ANALYSIS_MODEL`, cuyo valor predeterminado es `gpt-4o-mini`, el mismo modelo que ya usa el clasificador institucional. Se usa salida JSON estructurada. La interpretación la ejecuta el modelo mediante la API de OpenAI; el backend envía los datos, valida la respuesta y guarda/agrupa sus resultados. Codex es la herramienta de desarrollo y no es el clasificador que opera dentro de la plataforma. El proveedor consume créditos según su uso; la configuración no acredita saldo disponible.
- Se usan hasta tres solicitudes concurrentes, con lotes de hasta 12 comentarios de una misma publicación. Las escrituras se realizan en un solo hilo y se confirman por lote.
- Los identificadores enviados al modelo son alias cortos del lote. Antes de guardar se verifica la correspondencia exacta y se recuperan los IDs originales de Meta, sin conversiones numéricas.
- Una salida incompleta se reintenta y, si hace falta, se subdivide. Si un comentario individual sigue sin recibir una respuesta válida, permanece pendiente y los demás continúan. Los errores de credenciales, cuota o conexión detienen el trabajo con el avance guardado.
- **Detener análisis** deja terminar y guardar las solicitudes ya enviadas. **Reanudar análisis guardado** usa el mismo trabajo y conserva el alcance inicial; evita repetir los resultados ya confirmados, incluidos los que aún son ambiguos.
- Salir de la pantalla no detiene el trabajo. El backend debe permanecer encendido. Tras reiniciar el servidor, un análisis interrumpido se reanuda desde el panel.

La operación no crea casos ciudadanos, no modifica los comentarios originales y no atribuye afiliación política a las personas. Las clasificaciones describen lo expresado en cada comentario y pueden requerir revisión humana.

## Rutas y persistencia

| Ruta | Uso |
| --- | --- |
| `GET /conversation/posts` | Selector ligero de publicaciones, sin reconstruir todos los comentarios. |
| `POST /conversation/analysis-jobs` | Iniciar o recuperar el trabajo activo, evitando duplicados. |
| `GET /conversation/analysis-jobs/latest` | Consultar avance, alcance, modelo y resultado. |
| `POST /conversation/analysis-jobs/{id}/cancel` | Solicitar detención. |
| `POST /conversation/analysis-jobs/{id}/resume` | Reanudar un trabajo detenido, parcial o interrumpido. |

Los trabajos usan `meta_sync_jobs` con alcance `opinion-analysis`. Los contadores de avance y los resultados del lote se guardan en la misma transacción. Las clasificaciones siguen en `comment_analyses`; los cambios de texto, padre o contexto invalidan su huella. La operación se registra en auditoría. No requiere una tabla nueva.

## Validación y límites

Se verificaron permisos, selección por período/publicación, procesamiento de más de 20 comentarios, exclusión de Instagram en este módulo, concurrencia, guardado por lotes, detención/reanudación, conservación de resultados y respuesta incompleta de un comentario sin bloquear los demás.

La evaluación con el proveedor real incluyó 14 ejemplos y tres comentarios capturados que habían mostrado errores de atribución. El modelo actualizado pasó esas comprobaciones. Esto no certifica exactitud perfecta de todo el histórico. Los resultados preliminares del primer recorrido se conservaron con copia cifrada y se marcaron para reevaluación, en lugar de presentarlos como clasificaciones confirmadas.

El ensayo de navegador procesó 80 comentarios marcados de prueba con un proveedor simulado y una base PostgreSQL temporal: creación del trabajo, detención, regreso a la pantalla, reanudación, recorrido completo y segunda pasada limitada a ocho ambiguos. Se verificó el ajuste de 320 a 3440 px. Ese ensayo no añadió datos ficticios a la base real.

El recorrido real fue iniciado por solicitud del propietario y se consulta desde el panel. Que el desarrollo esté terminado no significa que ese trabajo ya haya procesado todos los comentarios: su estado y contadores son la fuente de avance.

Por indicación del propietario se restableció GPT-4o mini después de evaluar otro modelo durante el desarrollo. Los trabajos conservan el modelo usado en su avance; los resultados ya guardados no se borran ni se atribuyen retrospectivamente al modelo nuevo. Cada recorrido nuevo registra su propio modelo.

Referencias del proveedor: [modelo y parámetros](https://developers.openai.com/api/docs/models/gpt-4o-mini), [salida estructurada](https://developers.openai.com/api/docs/guides/structured-outputs).
