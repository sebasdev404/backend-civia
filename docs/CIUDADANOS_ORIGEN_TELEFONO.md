# Ciudadanos: registro, procedencia y teléfono único

Implementado y comprobado localmente el 26 de noviembre de 2026.

## Uso

En **Ciudadanos y contactos**, los roles Administrador y Alcalde/dirección pueden:

1. Pulsar **Agregar ciudadano** para registrar nombre, teléfono y origen. No se solicita cédula.
2. Pulsar **Importar ciudadanos** para cargar un Excel o CSV. Seleccionar el origen y agregar una observación opcional antes de revisar el archivo. Ambos datos se aplican a toda esa carga; separar archivos si las procedencias son diferentes.
3. Abrir **Origen y datos** para consultar la procedencia actual, las columnas originales y las procedencias anteriores conservadas.

Opciones: Formulario, Censo, Familiar, Referido, Evento, Visita territorial, Llamada, WhatsApp y Otro. La observación permite indicar el censo, evento, formulario o referencia concreta. No se deduce una relación familiar ni una postura política a partir del origen.

Secretaría y Operador conservan la consulta del directorio; no se ampliaron sus permisos de creación, importación o eliminación.

## Teléfonos

Se reciben teléfonos colombianos: celular nacional de 10 dígitos que comienza en `3`, o fijo de 10 dígitos que comienza en `60` e incluye un indicativo regional válido. En Huila el fijo incluye `608` y siete dígitos locales. Se acepta el prefijo `+57`, `57` o `0057`, así como espacios, guiones y paréntesis. Se almacena una representación canónica `+57` seguida de los diez dígitos nacionales.

No se completan automáticamente números locales de siete dígitos. Se rechazan letras, extensiones, dos números en una celda, formatos ambiguos, indicativos extranjeros y longitudes incorrectas. Esta validación comprueba estructura, no titularidad, existencia de la línea ni disponibilidad de WhatsApp.

Referencia: [CRC, marcación única nacional](https://www.crcom.gov.co/es/noticias/comunicado-prensa/desde-1-septiembre-cambia-forma-hacer-llamadas-en-colombia). Indicativos en [Resolución CRC 5826 de 2019](https://normograma.crcom.gov.co/crc/compilacion/docs/resolucion_crc_5826_2019.htm).

El teléfono es una clave de contacto única. El ID interno permanece estable para conservar relaciones. La normalización se aplica en el modelo y las rutas de registro/carga, con índice único y restricción de formato en PostgreSQL. Dos inserciones simultáneas no pueden guardar el mismo teléfono. El registro manual repetido responde con conflicto; la importación relaciona el número existente y conserva la nueva procedencia sin reemplazar el nombre o datos ya registrados. Un usuario de WhatsApp que contradiga el teléfono existente requiere revisión.

Se ofrece llamada para fijos; solo los celulares generan enlace a WhatsApp. El enlace no confirma que el número esté registrado en WhatsApp.

## Importación y conservación

- Excel `.xlsx` o CSV, hasta 10 MB y 10.000 filas; hoja `Contactos` si existe.
- Cada nueva fila necesita nombre y teléfono válido. Las filas sin teléfono se señalan para corregir; no se crean contactos nuevos únicamente por un nombre o usuario de WhatsApp.
- Los teléfonos repetidos dentro del mismo archivo se informan y se conserva la primera fila válida.
- La vista previa no escribe. Cambiar origen, observación o archivo invalida la vista previa anterior.
- Las filas válidas se guardan en una transacción. Un conflicto concurrente revierte la carga, con aviso para revisarla nuevamente.
- Se conservan las columnas originales, archivo, hoja, fila y huella del archivo. Una nueva procedencia conserva la anterior en `source_data.history`. Las operaciones nuevas guardan fecha y actor; el registro individual también genera auditoría dirigida al contacto.
- Repetir el mismo archivo con la misma procedencia no duplica contactos ni amplía su historial innecesariamente.
- No se inventan seguidores, interacciones, clasificación social ni asociaciones a perfiles de redes.

La revisión previa de la base local encontró 305 ciudadanos: 266 teléfonos válidos y ningún duplicado canónico; 39 contactos sin teléfono. La migración `20261126_citizen_contact_origin.sql` conservó los 305 registros. Los contactos anteriores sin número siguen disponibles. No se asignó una procedencia por suposición ni se recargó el Excel real.

Se guardó una copia cifrada privada antes de migrar; no forma parte de Git. Los datos y copias de seguridad deben permanecer fuera del código fuente.

## Evidencia

- Backend: 280 pruebas aprobadas, una omitida; 13 pruebas de importación/registro aprobadas tras el ajuste de trazabilidad.
- PostgreSQL temporal: migraciones repetibles, rechazo de formato por SQL directo y dos inserciones concurrentes del mismo teléfono (solo una aceptada).
- Frontend: compilación de producción y lint sin errores; 27 comprobaciones de navegador con BFF y base PostgreSQL temporal. Registro, conflicto, fijo, importación, historial, permisos y anchos 320, 390, 768, 1024, 1440, 2560 y 3440.
- Los contactos usados para probar se crearon exclusivamente en una base temporal y se retiró el entorno al finalizar. Ningún contacto ficticio se añadió al directorio real.
