# Preparación de producción — 25/11/2026

El código tiene un paquete de despliegue y comprobaciones locales de producción. **No hay despliegue público acreditado**: faltan servidor, dominio, proveedor/remitente SMTP y validaciones en ese destino. El seguimiento central conserva esas tareas abiertas.

## Cambios de esta entrega

- Secretaría consulta todos los expedientes de CIVIA, por decisión explícita del usuario. Las actuaciones siguen limitadas por rol.
- Radicado externo con entidad, fecha, referencia del soporte, motivo y declaración de revisión. Corregir añade otro registro; retirar conserva el anterior. No equivale a enviar correspondencia ni cambia el estado del expediente.
- Edición de cuentas con motivo y control de versión; cambio de rol/activación revoca sesiones. Auditoría administrativa con actor real, sin contraseñas, cuerpos de comentarios ni tokens.
- Webhook firmado y limitado, recepción persistente y deduplicada, reintentos para origen pendiente. Captura comentarios; no crea expedientes ni consume IA automáticamente.
- Correo pendiente cifrado en PostgreSQL, reintentos y recuperación tras reinicio. Cambiar/restablecer contraseña invalida códigos y sesiones anteriores. Sin SMTP se informa indisponibilidad.
- Presupuesto administrativo persistente, incluido cero. No se presentan conteos de casos como gasto, tokens o saldo del proveedor. Diagnóstico muestra lo medido y distingue configuración de conexión verificada.
- Retirados borradores con afirmaciones políticas predefinidas y vectores aleatorios de similitud. Los borradores de IA requieren revisión; una ausencia/falla del proveedor no se anuncia como generación exitosa.
- Imágenes por un intermediario del mismo origen, limitado a rutas multimedia y formatos raster. Sin nombres internos de contenedores en el navegador. La lista de comentarios capturados no fabrica comentarios a partir de expedientes históricos.
- Métricas capturadas conservan ceros confirmados y valores desconocidos. Las asociaciones publicación–caso usan referencias explícitas; no se infieren por compartir portada. La identidad histórica no se reemplaza por otra sin coincidencia exacta de texto y autor.
- Migraciones con registro de huellas, comprobación de esquema, API sin DDL automático en producción y coordinador único por bloqueo PostgreSQL. Capturas interrumpidas se recuperan; análisis pagados requieren solicitud explícita.
- Dockerfiles, Compose, Caddy, variables privadas de ejemplo, copia cifrada, importación a destino vacío y procedimiento operativo en [deploy/README.md](../deploy/README.md).

## Evidencia comprobada

- Suite completa: **241 pruebas, sin fallos; una prueba en vivo de Meta omitida en la ejecución local**. Esa prueba se ejecutó después por separado y aprobó con las credenciales existentes: Instagram listo, sin permisos faltantes, última publicación consultada presente y lectura de Facebook autorizada. No se modificaron comentarios ni se publicaron mensajes. Pruebas de escritura en SQLite o PostgreSQL desechables; lecturas históricas en transacciones de solo lectura.
- Intermediario de sesiones: 12 comprobaciones, incluyendo cookie protegida, rechazo de origen ajeno, cambio de sesión, errores de red y origen público HTTPS detrás del proxy.
- TypeScript y compilación Next 16.4.6 con Node 24 aprobados. ESLint: cero errores, 46 advertencias de código heredado (variables sin uso, imágenes y una advertencia de refs en un hook), registradas sin afirmar que desaparecieron.
- Auditorías npm y Python sin vulnerabilidades conocidas en la consulta realizada. Actualizados Next y OpenTelemetry; versiones Python fijadas en `requirements.lock`. El resultado es una fotografía de la fecha y necesita repetirse para futuras publicaciones.
- Caddy 2.11.9: binario oficial contrastado con SHA-512 del proyecto; configuración de despliegue validada sin listeners públicos.
- Migraciones sobre PostgreSQL vacío ejecutadas dos veces y comprobadas; también aplicadas y verificadas sobre el esquema local existente.
- Copia cifrada inicial: 19 tablas; restauración completa de tablas y **2.515 archivos multimedia** en una base/directorio desechables, con comparación de huellas. Rechazados destino no confirmado y sobrescritura de una base con tablas. La prueba no importó sobre `civia_db`.
- Comprobación de huellas de usuarios/contraseñas, expedientes, vínculos, ciudadanos e historial antes/después de migrar: sin cambios de negocio. Los archivos de evidencia y copias permanecen privados en `artifacts/`, fuera de ambos repositorios.

La interfaz HTTPS pasó **147 comprobaciones** sobre Next standalone y PostgreSQL desechable: cookie protegida, permisos, radicado, asignación, borrador, cierre, reapertura, presupuesto cero, auditoría y recuperación sin SMTP. Incluye 14 rutas en 320, 390, 768, 1024, 1440, 2560, 3440 y 3840 px, sin desbordamiento horizontal ni excepciones JavaScript. Inspección visual de capturas móvil y escritorio amplio. No certifica dispositivos físicos o Safari/iOS.

## Pendientes que requieren el destino o una decisión humana

1. Servidor/alojamiento, dominio, responsables y SMTP reales; configurar secretos por canal privado.
2. Construir y arrancar las imágenes Linux en el destino, validar DNS/certificado, firewall, salud, alertas y almacenamiento de copias externo; ensayar la reversión allí.
3. Entrega SMTP real, recepción del webhook en el dominio público y aceptación del recorrido con una solicitud autorizada. La lectura real de Facebook e Instagram se comprobó; debe revalidarse con la configuración del destino.
4. Titulares/correos/claves de cuentas históricas, política de tratamiento/retención y aceptación en dispositivos previstos. No se cambian cuentas reales por suposición.
5. Decisiones sobre origen y clasificación histórica: los 244 registros señalados y conflictos conservan su evidencia y requieren revisión. No se borraron, fusionaron ni declararon verificados para cerrar una lista.

La instrucción de terminar el proyecto autoriza completar código y verificaciones; no permite inventar infraestructura ni decisiones sobre solicitudes ciudadanas.

Se retiraron credenciales incrustadas encontradas en dos utilidades históricas; ahora leen configuración privada y no ponen tokens en URLs ni imprimen respuestas de error del proveedor. No se reescribió el historial Git: rotar las credenciales expuestas antes de la operación pública.

La revisión final también comprobó creación y edición de roles desde Administración, sin usar cuentas reales. La búsqueda semántica exige hasta 20 candidatos explícitos para evitar recorrer y facturar embeddings de todo el histórico. El menú superior de casos recientes consulta cinco resúmenes solo al abrirse; se retiró el sondeo global de expedientes cada 25 segundos y su presentación como notificaciones sin leer.

Al cerrar: servidores y base PostgreSQL de QA retirados; aplicación local original disponible en localhost:3000 y API lista en 8000. Compilación de desarrollo separada en .next-dev para conservar la compilación de producción .next. Las copias privadas y su clave se conservan fuera de Git.
