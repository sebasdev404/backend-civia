# CIVIA — adaptación de pantallas

Fecha: **24 de noviembre de 2026**.

## Alcance comprobado

Se revisaron 14 vistas en Chromium aislado, con la aplicación local y datos existentes: Inicio, Opinión, Publicaciones, detalle de publicación, las tres bandejas de Gestión de casos, expediente, Ciudadanos, Indicadores, Mapa y las tres secciones de Configuración (usuarios, servicios y conexiones).

Tamaños en píxeles CSS:

| Ancho | Alto | Escenario |
| --- | --- | --- |
| 320 | 568 | Móvil estrecho |
| 360 | 740 | Móvil |
| 390 | 844 | Móvil |
| 640 | 800 | Pantalla intermedia |
| 768 | 1024 | Tableta vertical |
| 844 | 390 | Pantalla horizontal de poca altura |
| 1024 | 768 | Tableta horizontal |
| 1025 | 768 | Transición al sidebar de escritorio |
| 1280 | 800 | Portátil |
| 1440 | 900 | Escritorio |
| 1920 | 1080 | Escritorio amplio |
| 2560 | 1440 | Escritorio de alta resolución |

## Correcciones

- Los formularios de usuario e importación caben en pantallas pequeñas o bajas, con desplazamiento vertical y cierre accesible. Los campos dobles pasan a una columna cuando corresponde.
- El informe ejecutivo adapta título, acciones, hoja y firmas; sus tablas conservan desplazamiento propio. No se modificó el contenido de negocio del informe ni su hoja de impresión.
- Las cuatro opciones de visualización de casos caben en móvil. El selector de meses respeta el ancho disponible.
- Los filtros del panel de comentarios se distribuyen en varias filas. Su cabecera aprovecha el ancho disponible y conserva espacio para leer el contenido.
- Las tablas anchas de ciudadanos, usuarios y casos se desplazan dentro de su región, sin ensanchar la página. Se añadió foco por teclado, nombre accesible e indicación de desplazamiento en móvil.
- Los filtros territoriales del mapa son desplegables en pantallas intermedias y móviles. El mapa mantiene altura utilizable y recalcula sus dimensiones cuando cambia su contenedor.
- Las tarjetas de Inicio, rankings de Indicadores y estado de servicios evitan anchos mínimos que recortaban contenido.
- Los diálogos y paneles quedan por encima de los controles flotantes de ayuda.

## Evidencia

- **168 comprobaciones de vistas y tamaños**, sin desbordamientos horizontales no previstos. La detección incluye elementos recortados por sus contenedores; se permiten únicamente regiones de desplazamiento deliberadas, como tablas y pestañas, además del lienzo del mapa.
- **18 comprobaciones adicionales**: formularios de usuario e importación, informe y panel de comentarios en cuatro tamaños; comparación de expedientes y apertura de filtros del mapa en móvil.
- Menú móvil comprobado: cabe en pantalla y cierra con Escape.
- Tablas de ciudadanos y usuarios comprobadas con foco y flecha derecha: se desplazan sin mover toda la página.
- **Cero solicitudes de escritura intentadas al backend y cero errores de ejecución** durante las pruebas. La consulta de comparación de expedientes es de solo lectura. No se importaron, eliminaron, asignaron, consolidaron ni corrigieron registros.
- TypeScript y compilación de producción comprobados sobre esta entrega; el registro de seguimiento recoge el resultado final.

Los scripts y capturas locales se conservan fuera de los repositorios, en la carpeta general `artifacts/`: `verify_responsive.cjs`, `responsive-audit.json`, `verify_responsive_overlays.cjs`, `responsive-overlays.json`, capturas `responsive-*.png` y `frontend-responsive-build.log`. No contienen credenciales de sesión guardadas como evidencia.

## Pendiente

- [ ] Validar en dispositivos físicos y Safari/iOS, incluyendo teclado virtual y cambios de orientación reales.
- [ ] Revisar con el usuario la comodidad del recorrido y la lectura de las secciones restantes; corregir anchos no representados si aparecen problemas.
- [ ] Repetir la aceptación sobre la versión desplegada antes de producción.

La emulación de tamaños en Chromium no certifica todos los navegadores o dispositivos. Esta entrega adapta la interfaz y no resuelve los pendientes de datos, indicadores, autenticación ni operación de producción.

## Corrección de distribución tras la captura del usuario

La primera revisión detectaba recortes, pero no comprobaba el aprovechamiento del ancho. La captura posterior mostró un defecto real: Gestión de casos tenía un límite de 1600 px alineado a la izquierda, que dejaba una franja vacía considerable en escritorio amplio. Configuración conservaba un límite de 860 px. La validación inicial fue insuficiente para dar por buena la distribución visual.

Se corrigió la base de la interfaz:

- Las áreas de trabajo usan el ancho disponible después de descontar el sidebar y unos márgenes comunes de 16–40 px. Se retiraron los límites de ancho de Casos, Opinión, Configuración y expediente.
- El ancho raíz usa `100%`, en lugar de `100vw`, para respetar la barra de desplazamiento vertical. Se retiró la animación del ancho del área principal, que retrasaba el ajuste al cambiar entre escritorio y móvil.
- Las cuadrículas de publicaciones y casos calculan sus columnas a partir del contenedor y de un ancho mínimo legible de tarjeta. En 2560 px, la bandeja de publicaciones muestra seis columnas; en 2744 px, siete; en 3440 px, nueve. Son resultados medidos con sidebar abierto y la configuración actual, no cantidades fijas.
- Inicio, Indicadores y Ciudadanos cambian sus columnas de indicadores según el espacio del contenido, incluyendo el cambio al plegar el sidebar.
- Opinión distribuye los comentarios en columnas legibles; Configuración distribuye sus paneles sin reducir la tabla de usuarios a una columna estrecha.
- La revisión de comentarios puede usar varias columnas. El expediente separa comentario, contexto y decisión cuando el área de trabajo supera 1600 px.
- Se ajustaron la identidad del historial ciudadano y los campos del formulario de revisión en móvil, además de conservar la adaptación anterior de los demás diálogos.

### Validación ampliada

- Matriz de **17 vistas y variantes por 17 tamaños**: 289 comprobaciones. Incluye las cuatro presentaciones de casos y el detalle real de una publicación.
- Tamaños añadidos: 1366×768, 1536×864, 2744×1000, 3440×1440 y 3840×2160. Se conservan los 12 tamaños originales.
- **63 comprobaciones adicionales con sidebar plegado**: siete vistas en los nueve tamaños de escritorio.
- **26 comprobaciones de paneles y formularios**, incluyendo creación/vinculación de caso e historial ciudadano. Los dos formularios ajustados al final se comprobaron de nuevo.
- La matriz verifica desbordamiento y ancho ocupado por la página, y registra número de columnas y tamaño de las tarjetas. Se revisaron capturas amplias y móviles; no se consideró suficiente que el contenido no se saliera de pantalla.
- Las pruebas no guardaron decisiones ni modificaron registros del backend. TypeScript y build de producción aprobados.

La evidencia local ampliada está en `responsive-wide-final.log`, `responsive-audit.json`, `responsive-collapsed.json`, `responsive-collapsed-run.log`, `responsive-overlay-run.log`, `responsive-overlay-last.log`, `responsive-overlays-combined.json` y las capturas de 2560, 2744 y 3440 px de la carpeta general `artifacts/`. El informe combinado conserva las seis pruebas originales de paneles y sustituye los dos formularios ajustados por su última comprobación; no genera resultados nuevos. Las validaciones físicas y Safari/iOS siguen pendientes.
