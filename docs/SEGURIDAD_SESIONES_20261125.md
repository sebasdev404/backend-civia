# Acceso, sesiones y permisos de CIVIA

Revisión local: **25 de noviembre de 2026**. Esta entrega cierra los accesos de demostración y aplica controles de acceso; no certifica que el despliegue esté listo.

## Funcionamiento

- Abrir una vista protegida lleva a `/login`. Se conserva la ruta para continuar después de iniciar sesión.
- Se exige una cuenta activa y una contraseña válida. Se retiraron la cuenta automática, los botones de acceso de un clic, el cambio de rol de demostración y el acceso local cuando falla el servidor.
- La interfaz espera la validación de `/auth/me` antes de montar las vistas privadas. No considera válido el perfil guardado en el navegador. La validación tiene un límite de 15 segundos y permite reintentar si falla la conexión.
- Una respuesta **401** elimina la sesión local y muestra el aviso para volver a entrar. Una respuesta **403** informa de la falta de permisos y conserva la sesión. Una respuesta antigua no puede cerrar una sesión que se haya renovado mientras esperaba.
- El servidor comprueba firma, caducidad, `iat`, `sub`, existencia y estado de la cuenta y el registro de sesión `jti`. Lee el rol actual de PostgreSQL; cambiar el rol almacenado en el navegador o en una declaración antigua del token no concede permisos.
- El navegador utiliza `/api/backend` en Next. Este intermediario conserva el JWT en una cookie `HttpOnly`, `SameSite=Lax`, con `Secure` en producción y caducidad del token. Solo el servidor añade Bearer al llamar a FastAPI. Consultas, formularios y exportaciones usan este mecanismo sin caché; el perfil se valida con la API y queda en memoria. Se retiran los valores antiguos de `civia_token` y `civia_user` de localStorage y la cookie antigua.
- Login, restablecimiento y cambio de contraseña devuelven al JavaScript del navegador únicamente perfil, identificador de sesión y fecha de vencimiento. Las escrituras exigen el mismo origen; el identificador revisado impide guardar desde una pestaña que aún usa otra sesión. La consulta de perfil puede descubrir una sesión renovada por otra pestaña.

## Mi cuenta y revocación

En el menú del perfil, arriba a la derecha, **Mi cuenta y seguridad** abre `/account` para cualquiera de los cuatro roles. Permite cambiar la contraseña actual, consultar los accesos vigentes propios y cerrar todos con confirmación. No se atribuyen dispositivos ni ubicaciones que no se hayan medido.

Cada acceso tiene un registro en `auth_sessions`. Cerrar sesión revoca el acceso actual; cerrar todos revoca los de esa cuenta. Cambiar o restablecer la contraseña revoca los accesos previos y entrega una sesión nueva a la ventana que realizó el cambio. La comprobación adicional de la huella de la contraseña invalida accesos emitidos antes de una modificación del hash. Un fallo de red no se presenta como cierre confirmado.

La actualización requiere **volver a iniciar sesión**: los tokens antiguos sin registro ya no se aceptan. Se conservan las cuentas y contraseñas existentes. El plazo sigue definido por `ACCESS_TOKEN_EXPIRE_MINUTES`; no hay renovación automática que prolongue el acceso indefinidamente.

La tabla local se prepara de forma aditiva. Para otro entorno está incluida `migrations/20261125_auth_sessions.sql`; debe aplicarse antes de activar este código. En Next, `CIVIA_BACKEND_API_URL` configura la dirección privada de FastAPI. `NEXT_PUBLIC_API_URL` sigue disponible para recursos públicos y como compatibilidad de configuración; ninguna de estas variables debe contener credenciales. En producción el frontend necesita HTTPS para la cookie Secure. El JWT de FastAPI continúa siendo un secreto y su uso directo exige el registro vigente.

## Permisos aplicados en la API

| Operación | Roles |
| --- | --- |
| Consultar casos, métricas, mapa, publicaciones, conversación y contactos | Cuentas activas de los cuatro roles |
| Administrar usuarios, ver diagnóstico o ajustar presupuesto | ADMIN |
| Crear un caso manual, registrar notas o guardar borradores internos | ADMIN, SECRETARIO, OPERADOR |
| Asignar, modificar clasificación o cerrar un caso | ADMIN, SECRETARIO |
| Eliminar un caso | ADMIN, conservando las restricciones de consolidación existentes |
| Marcar prioridad especial | ADMIN, ALCALDE |
| Crear/vincular casos desde comentarios | ADMIN, ALCALDE, OPERADOR, según la regla de triaje existente |
| Confirmar o deshacer consolidaciones y correcciones | ADMIN, SECRETARIO |
| Importar o eliminar contactos | ADMIN, ALCALDE |
| Actualizar capturas, contexto o solicitar análisis/borradores | Los cuatro roles; no publica mensajes en redes |

La política común se aplica al router completo publicado por `main.py`. Las rutas nuevas de escritura sin una regla explícita quedan restringidas a ADMIN. Las notas, asignaciones y cierres registran al usuario autenticado; no aceptan como identidad la enviada por el formulario. La propia cuenta no se puede eliminar desde Gestión de usuarios.

**Excepciones públicas explícitas:** inicio de sesión y recuperación de contraseña; verificación y recepción del webhook; proxies de imágenes públicas de publicaciones. `/health`, la portada técnica de la API, sus esquemas y los archivos de imágenes de `/static` permanecen públicos. Ninguna de estas excepciones concede acceso al directorio de ciudadanos o a expedientes.

Seed y simulación de comentarios responden 410 incluso para ADMIN. Consultar un incidente sin expediente responde 404: se retiró la creación automática de casos desde una lectura, que permitía efectos de escritura a roles de consulta. Se conservan los registros existentes.

## Recuperación y configuración

El código de seis dígitos se guarda en `password_recoveries` mediante HMAC-SHA256 con secreto del servidor, nonce aleatorio y vínculo a la cuenta y su contraseña vigente. No se devuelve en HTTP, no se registra en logs ni se incluye en el asunto del correo. Caduca a los 15 minutos, admite cinco errores compartidos entre verificar/restablecer y solo puede consumirse una vez. Reenviar sustituye el anterior cuando SMTP acepta el nuevo mensaje; cambiar la contraseña invalida los códigos anteriores. Los campos heredados `users.reset_otp*` no se aceptan como evidencia. En el entorno local revisado no había códigos antiguos almacenados.

La solicitud pública devuelve el mismo mensaje condicional para cuentas activas, inactivas o inexistentes. La búsqueda y el envío se ejecutan después de esa respuesta para separar el tiempo de SMTP del resultado público. Si falta configuración de correo, todos los destinatarios reciben el mismo 503 y la pantalla conserva el formulario de solicitud. Un fallo posterior de SMTP se registra sin datos personales y revierte el nuevo código; la respuesta pública no afirma que el mensaje se entregó. La verificación inválida utiliza un único error para código incorrecto, agotado, usado, vencido o cuenta no disponible. Una cuenta inactiva no puede restablecer su clave. Las contraseñas nuevas deben tener al menos 10 caracteres y como máximo 72 bytes para bcrypt.

Los límites dejaron de depender de memoria local: `auth_rate_limits` guarda contadores atómicos compartidos por los procesos que usan la misma base. Por dirección de conexión: 30 intentos/minuto en login, 5 solicitudes/15 minutos para enviar y 10/15 minutos conjuntos para verificar/restablecer. También se limita cada correo normalizado, exista o no: 5 solicitudes y 10 verificaciones/restablecimientos por 15 minutos. Son ventanas fijas; se devuelve 429 con Retry-After. Solo se almacenan claves HMAC, sin correos ni IPs en claro. Se retiran hasta 100 contadores con más de un día de vencimiento por operación.

El gateway sobrescribe las cabeceras de identidad del visitante y autentica su comunicación con Next mediante un secreto privado. Next deriva una identidad HMAC sin enviar la IP a FastAPI y firma identidad, método, ruta y fecha. FastAPI comprueba la firma y una ventana de 60 segundos; sin firma válida usa la dirección de conexión. No se confía en X-Forwarded-For arbitrario. El paquete configura este circuito; falta verificarlo en el acceso público definitivo.

SMTP necesita `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` y `SMTP_FROM_EMAIL` privados, sin remitente institucional inventado. Configurar exactamente uno de `SMTP_TLS=true` (STARTTLS, habitualmente 587) o `SMTP_SSL=true` (TLS directo, habitualmente 465); el otro debe ser false. Se verifica el certificado TLS antes de autenticar. `SMTP_FROM_EMAIL` debe pertenecer al remitente autorizado por el proveedor. El restablecimiento confirmado intenta enviar un aviso de seguridad sin la contraseña. Se mantiene el inicio de sesión con cookie protegida tras un código válido y se revocan todos los accesos anteriores.

El envío se confirma primero en la bandeja PostgreSQL cifrada. BackgroundTasks acelera la entrega y un trabajador periódico retoma pendientes tras reiniciar. Hasta cinco intentos con espera creciente; el código mantiene su vencimiento de 15 minutos y un fallo SMTP conserva el código anterior. Correo y OTP no se guardan en claro. Las notificaciones de cambio de clave usan la misma bandeja. Aplicar todas las migraciones con manage.py antes de arrancar producción; SMTP real y su monitorización siguen pendientes.

Referencia para los criterios de mensajes uniformes, caducidad, uso único y protección de intentos: [OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html). La entrega no acredita una auditoría completa de seguridad.

Los eventos POST del webhook exigen HMAC-SHA256 del cuerpo original con `META_APP_SECRET` y comparación constante. La comprobación de firma ocurre antes de analizar el contenido o escribir. La verificación GET dejó de registrar los tokens recibidos y esperados. La bandeja persistente deduplica cuerpos, limita entradas y procesa posteriormente. Reintenta eventos cuyo origen todavía no se ha capturado, sin inventar publicaciones, crear expedientes ni llamar a IA.

`ENVIRONMENT=production` impide arrancar con las claves JWT de ejemplo conocidas, claves menores de 32 caracteres u orígenes CORS sin HTTPS/explícitos. CORS utiliza `BACKEND_CORS_ORIGINS`. Esto no cambia ni rota los secretos reales del entorno actual.

## Comprobaciones de acceso iniciales

- **126 pruebas de backend aprobadas**, incluidas 17 de acceso y regresiones de métricas, triaje, conversación, publicaciones, procedencia, consolidación, corrección y flujo caso–mapa. Fixtures de SQLite; no se cerraron ni asignaron casos reales.
- El inventario de rutas se comprueba contra OpenAPI: toda operación no incluida en la lista pública exige sesión antes de ejecutar su lógica. Comprobación adicional contra el servidor local: métricas sin sesión y `/auth/me` con token demo responden 401.
- **10 comprobaciones del cliente aprobadas**: credenciales, 401/403, fallo de conexión, exportación, respuesta antigua, rutas de regreso y respuesta 204.
- **23 comprobaciones de navegador aprobadas**: rechazo de demo/JWT inválido o vencido, error de credenciales, regreso a la ruta original, conexión caída y reintento, restricciones de administración, expiración durante una consulta, privacidad y eliminación de datos accesibles sin sesión, y formulario a 320, 390, 768, 1440, 2560 y 3840 px. Se inspeccionaron capturas de móvil y escritorio. La respuesta de login se simuló solo en el navegador; el login con contraseña se comprobó en SQLite. Las consultas de perfil y permisos usaron el backend local y cuentas existentes. Ninguna prueba del navegador escribió datos reales ni invocó análisis de pago.
- TypeScript, compilación de Next y ESLint de los archivos de autenticación/administración comprobados. Existe una advertencia de imagen nativa en el expediente y advertencias de Sass heredadas; no equivalen a una auditoría completa de accesibilidad o de dependencias.

Los scripts y resultados locales están en `artifacts/auth-*`, `artifacts/verify_auth_ui.cjs` y `artifacts/verify_session_client.cjs`, fuera de los repositorios. No guardan credenciales de sesión en los resultados. La suite general de integración con capturas Meta y la salida a producción no quedan certificadas por estas pruebas.

## Comprobaciones de las sesiones registradas

- **27 pruebas de backend aprobadas**: 10 específicas de registro, revocación, cambio/restablecimiento, expiración, huella y separación por cuenta, más 17 de acceso. Utilizan SQLite aislado.
- **10 comprobaciones del intermediario aprobadas**: atributos de cookie en producción, ausencia de JWT en el JSON público, origen, sesión desactualizada, respuesta 401, cierre vencido, cierre sin conexión, exportación, rutas inválidas y redirecciones rechazadas.
- **14 comprobaciones de navegador aprobadas** sobre una copia temporal de Next y API con SQLite: login, cambio de contraseña, revocación, dos pestañas, recarga, cierre actual y cierre de todos; formulario revisado a 390 px. Resultado en `artifacts/sessions-browser-result.json`. Las contraseñas de prueba pertenecen solo a esas cuentas temporales; no se invocan Meta, correo ni IA de pago.
- TypeScript y ESLint de los archivos modificados sin errores. Compilación de Next con Webpack aprobada sobre la copia del código final, sin interferir con el servidor de desarrollo principal; persisten advertencias heredadas de Sass.
- Backend local actualizado y tabla creada sin sesiones de prueba. Comprobación PostgreSQL de solo lectura antes/después: huellas de usuarios (incluidas sus claves), casos, vínculos, correcciones, consolidaciones, historial y ciudadanos idénticas. Login local disponible; perfil anónimo 401 y escritura desde origen ajeno 403.

Estas comprobaciones son acotadas a la función entregada. La revisión integral de la versión final sigue pendiente. Los resultados históricos de la sección anterior no representan una nueva ejecución de toda la suite.

## Comprobaciones de recuperación protegida

- **40 pruebas de backend aprobadas**: 13 de recuperación, SMTP y límites, más las 27 de acceso/sesiones adaptadas al nuevo contrato. SQLite temporal, incluido consumo concurrente del límite mediante ocho conexiones.
- PostgreSQL: incremento atómico, rechazo y renovación del límite ejecutados en una tabla temporal exclusiva de la conexión, con rollback; no se alteraron contadores reales. No representa una prueba de carga de múltiples réplicas.
- **12 comprobaciones de navegador aprobadas** en Next y API temporales: mensajes uniformes, error de código, reenvío, formulario a 390 px, restablecimiento con cookie HttpOnly, revocación previa, rechazo de reutilización y aviso de SMTP no disponible. Correo simulado únicamente en la fixture; no se enviaron mensajes reales ni se cambiaron claves reales.
- TypeScript, lint del formulario y compilación de Next con Webpack aprobados. Backend local activado; tablas nuevas vacías al cerrar esta entrega. Huellas de usuarios, contraseñas y datos de negocio idénticas antes/después. SMTP local sigue sin configurar y se verificó su ausencia sin imprimir credenciales.
- Evidencias locales en `artifacts/recovery-*`, `check_recovery_browser.cjs` y `check_recovery_postgres.py`. La revisión integral y el envío real siguen pendientes.

## Estado tras el cierre técnico de preparación

- Secretaría consulta todos los expedientes de CIVIA, según confirmación del usuario; se mantienen permisos diferenciados para actuar.
- Auditoría administrativa en `/audit`: cuentas, importación/eliminación de contactos, presupuesto y reintentos. El historial ciudadano permanece en cada expediente.
- Webhook y correo usan bandejas durables. Se añadieron migraciones verificadas, coordinador PostgreSQL único y herramientas de copia/importación/restauración.
- La configuración de producción limita sesiones a entre 30 y 1440 minutos; el paquete usa 480. Limpieza técnica de sesiones caducadas a 30 días, pendiente de confirmar con la política del responsable.
- Suite completa de 241 pruebas sin fallos (una validación Meta en vivo omitida), 12 del intermediario y 147 de navegador HTTPS aprobadas. Ver [evidencia y límites](PREPARACION_PRODUCCION_20261125.md).

Pendientes externos: titulares/correos y cambio de claves iniciales, SMTP real, alojamiento/dominio, certificados públicos, alertas, almacenamiento externo de copias, política de datos y aceptación operativa. No se cambiaron claves ni cuentas reales durante las pruebas. La preparación local no acredita un despliegue público.

El flujo asignación → avance → cierre con soporte, reapertura y radicado externo están implementados; ver [flujo de atención](FLUJO_ATENCION_20261125.md) y [manual operativo](../deploy/README.md).
