# Rediseño del recorrido de gestión de casos

Entrega local del **24/11/2026**, a partir de la revisión del usuario sobre pantallas repetitivas y acciones difíciles de encontrar. El alcance implementado comprende la bandeja, el detalle del expediente y la navegación compartida. No implica que se haya rediseñado o aceptado toda la plataforma.

## Cambios de interacción

### Bandeja

- La vista inicial es una lista de trabajo: comentario literal, estado, responsable y enlace para abrir el caso.
- Casos y seguimiento aparece primero; revisión de comentarios y publicaciones quedan disponibles como recorridos distintos.
- Estados frecuentes accesibles directamente: todos, pendientes, en gestión, resueltos y sin solicitud.
- Búsqueda visible y filtros adicionales desplegables. Se conservan las vistas alternativas.
- Al abrir y volver desde un caso se conservan búsqueda, filtros, página y modo de visualización.
- No se presenta un cero como conteo de publicaciones o comentarios que todavía no se han cargado.
- La actualización de fuentes es una acción secundaria; el nombre no promete una captura instantánea completa.

### Expediente

- El comentario es el contenido principal. El título histórico y las clasificaciones inferidas pasan a Datos y origen, claramente identificados como datos por revisar.
- Una columna de decisión muestra la siguiente acción según el estado: decidir si requiere atención, registrar avance, revisar un despacho de prueba, consultar un cierre o abrir el principal de un duplicado.
- La decisión de conversación general tiene un paso explícito de confirmación antes de guardar. Elegir que requiere atención lleva a asignación; esa selección por sí sola no escribe en la base.
- La publicación de origen es desplegable y conserva texto, imagen disponible y enlace. No se inventan fotos de perfil o portadas.
- Atención divide asignación, borrador de respuesta y solución/cierre. Solo presenta el formulario elegido.
- Historial separa actuaciones de referencias técnicas; la bitácora original completa sigue disponible.
- Datos y origen conserva las herramientas de procedencia, corrección y consolidación. Sus consultas se difieren hasta abrir esta sección, y el estado de los formularios se conserva al cambiar de pestaña.
- No aparece un panel de duplicidad vacío cuando el expediente no tiene relaciones.
- Se eliminan las instrucciones y etapas repetidas que desplazaban el comentario hacia abajo.

### Navegación y adaptación

- Sidebar más compacto, con descripción de la sección activa.
- El expediente utiliza su propio regreso a la bandeja y código del caso, sin duplicar una segunda barra de navegación.
- Ancho de lectura limitado y alineado al inicio del área de trabajo para evitar el gran espacio vacío junto al sidebar en pantallas amplias.
- En móvil, las pestañas quedan visibles y un acceso directo lleva a la decisión o a la revisión del despacho de prueba.
- Navegación de pestañas por teclado, foco al cambiar de tarea, mensajes de resultado accesibles y respeto de movimiento reducido para los desplazamientos.

## Validación

- TypeScript aprobado y lint de componentes modificados sin errores; continúa la advertencia sobre la imagen nativa de la publicación.
- Build completo `next build --webpack` aprobado. Durante la validación se corrigieron dos bloqueos anteriores: selector global de impresión incompatible con CSS Modules y exports de funciones auxiliares incompatibles con los módulos de página de Next. No se cambiaron las reglas de los informes ni las funciones auxiliares.
- Navegador de prueba aislado con un usuario ADMIN existente. Se bloquearon todas las solicitudes de escritura al backend: **cero escrituras intentadas y cero errores de ejecución del navegador**.
- Comprobados: selección de conversación general y su confirmación sin guardar, paso a asignación con revisión conservada, historial, consulta de origen, ausencia del panel vacío, acceso a corrección de prueba, filtros, regreso con estado y página y acceso directo móvil.
- Revisadas capturas a 1600×1050, 1024×900 y 390×844. Sin desbordamiento horizontal del expediente en móvil o tableta. Tema claro y oscuro revisados.
- Evidencia local fuera de Git en la carpeta general `artifacts/`: `case_ux_validation.json`, `frontend-ux-build.log`, `case-ux-desktop-admin.png`, `cases-inbox-desktop.png`, `case-ux-mobile.png`, `case-ux-mobile-decision.png`, `case-ux-tablet.png` y `case-ux-light.png`.

Estas pruebas de interfaz no confirmaron correcciones, consolidaciones, asignaciones o cierres reales. La aceptación por el usuario y la revisión del resto de secciones siguen pendientes. Se mantienen las tareas existentes de datos, permisos, sesiones e indicadores antes de producción.
