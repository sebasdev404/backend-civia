# Monitor de noticias de Neiva y Huila

Actualizado: 26 de noviembre de 2026.

## Uso

Publicaciones abre **Noticias de Neiva y Huila**. La pestaña **Redes conectadas** conserva las publicaciones y comentarios de Johan y las fuentes sociales anteriores. Las noticias externas se guardan separadas: no se convierten en casos ciudadanos ni se mezclan con las opiniones sobre Johan.

**Actualizar noticias y clasificar** inicia un trabajo en segundo plano. Comprueba las fuentes activas, captura hasta 12 publicaciones recientes por medio y envía las noticias pendientes a GPT-4o mini. Muestra avance y observaciones; salir de la pantalla no detiene el trabajo. No consulta comentarios ni reacciones de los medios, porque no son necesarios para este análisis.

La IA devuelve resumen atribuido al medio, tema, territorio, lugar explícito, motivo de prioridad y señal de revisión. Las prioridades son Alta, Media, Baja, Fuera de foco y Por revisar. Se consideran afectación regional, servicios esenciales, actualidad y evidencia disponible. El nombre de un medio local no demuestra que todos sus sucesos ocurrieran en Neiva.

Las noticias aparecen por relevancia regional, con opción de ordenar por fecha. Hay filtros de medio, tema, territorio, prioridad y texto, además de paginación. Cada noticia conserva fecha, medio y enlace original. La clasificación no verifica los hechos ni acredita una emergencia o una actuación institucional.

Administración y Secretaría pueden registrar y pausar fuentes. Los demás roles pueden consultar y solicitar actualización. Pausar una fuente conserva sus capturas. Los enlaces se normalizan y validan como páginas de Facebook; se rechazan grupos, publicaciones individuales, dominios ajenos y duplicados.

## Fuentes reales solicitadas y acceso comprobado

| Medio registrado | Página aportada |
| --- | --- |
| Opa Noticias | https://www.facebook.com/opanoticias |
| Lucho Noticias Neiva | https://www.facebook.com/luchonoticiasneiva |
| Neiva Noticias en Vivo | https://www.facebook.com/neivanoticiasenvivo |

Las tres se registraron a petición del propietario. La consulta real a Meta devolvió **código 10** para cada una, por falta de acceso autorizado. Quedaron con estado `missing_permissions` y sin publicaciones capturadas. Registrar un enlace público no concede permiso de API. No se cargaron noticias ficticias para llenar la pantalla.

Para desbloquear la captura, el responsable de la aplicación debe obtener acceso permitido por Meta: autorización sobre la página consultada o la capacidad **Page Public Content Access**, cuando corresponda y Meta la apruebe. Un token de la página de Johan no habilita por sí solo la lectura de otros medios. La solicitud de revisión/aprobación de Meta no se presentó durante esta implementación.

Una vez autorizado el acceso, pulsar Actualizar noticias y clasificar vuelve a comprobar las fuentes. La vista muestra el estado y la última consulta por medio, diferenciando acceso pendiente de ausencia de noticias.

Referencia: [documentación oficial del feed de páginas de Meta](https://developers.facebook.com/docs/graph-api/reference/page/feed/).

## Persistencia y operación

- Migración aditiva: `migrations/20261126_news_monitor.sql`.
- `news_sources` relaciona el registro periodístico con `publication_sources`, su URL normalizada y su activación.
- Las publicaciones recibidas están en `observed_posts`; las respuestas de IA y su huella están en `news_analyses`.
- La huella depende del texto, fecha, modelo y día de referencia. Cambios relevantes dejan pendiente el análisis, y las capturas conservadas no se sustituyen por etiquetas inventadas si falla el proveedor.
- Se usa `gpt-4o-mini` mediante la API integrada, no Codex como clasificador. La actualización manual puede consumir créditos de OpenAI cuando existan noticias pendientes.
- Los trabajos usan `meta_sync_jobs` con alcance `news-monitor`; registro, pausa y solicitudes de actualización quedan auditados.
- Rutas: `GET/POST /publications/news/sources`, `PATCH /publications/news/sources/{id}`, `GET /publications/news` y `POST /publications/news/update`.

## Validación

274 pruebas de backend (una prueba viva omitida), compilación y lint sin errores. El lint conserva la advertencia sobre `<img>` de la vista social anterior. Se evaluó GPT-4o mini con tres noticias sintéticas: afectación local importante, noticia fuera de región y publicación sin texto suficiente; no se guardaron esos ejemplos en la base real.

El ensayo de navegador usó PostgreSQL temporal y un proveedor simulado: captura/clasificación, fuente bloqueada, enlaces, filtros, ordenación, alta y pausa de medios, conservación de la vista social y tamaños de 320, 390, 768, 1024, 1280, 1440, 1920, 2560 y 3440 px. Las 25 comprobaciones aprobaron; la base y los servicios temporales se retiran al terminar.

## Porcentaje de opinión

El trabajo de Opinión sobre Johan muestra porcentaje numérico, procesados, total y restantes. El porcentaje indica avance, no exactitud del modelo. En la captura aportada, 2.972 / 6.664 equivalía a 44,6 %. Ese trabajo terminó con 6.664 recorridos, 6.622 clasificados y 42 que necesitan revisión; los nuevos comentarios capturados después de su selección pueden formar otro trabajo.
