# Auditoría de procedencia de casos — 24/11/2026

## Caso revisado con Meta

`CIV-2026-2667`: se consultaron por sus IDs exactos la publicación `275486829735525_1045723459378521` y el comentario `1045723459378521_1046064736011060`.

Meta devolvió ambos registros y el texto del comentario coincidió exactamente con el guardado. Se recuperaron el texto de la publicación, su URL y el comentario original en la captura local. La respuesta de Meta no incluyó imagen ni adjuntos. No se creó una foto, identidad ni publicación alternativa.

## Auditoría local reproducible

Ejecutar desde el backend: `python audit_case_provenance.py`. Solo lee datos; no llama a Meta ni elimina registros.

Resultado al realizar esta revisión (los conteos pueden variar con nuevas capturas):

| Evidencia local | Casos |
| --- | ---: |
| Texto de comentario coincide exactamente con captura e ID de origen | 1141 |
| Falta el identificador individual del comentario | 1115 |
| Publicación referenciada no está en la captura local | 394 |
| Publicación capturada, comentario referenciado ausente | 11 |
| Total auditado | 2661 |

También se compararon título y contenido completos con los **ocho casos** definidos como datos de ejemplo en `app/api/v1/seed.py`: no hubo coincidencias exactas. Esto no detecta todos los posibles datos ficticios ni prueba identidad de autores, exactitud de clasificaciones o atención realizada.

Los 1115 registros sin ID individual usan un formato histórico que conserva referencias de publicación. No se los debe declarar ficticios automáticamente, ni completar sus IDs mediante suposiciones por nombre o semejanza de texto.

## Reglas para continuar la limpieza

- Ausencia de captura no demuestra que un registro sea ficticio; impide confirmar su procedencia con esa captura.
- Un registro en PostgreSQL no demuestra por sí solo que provenga de Meta.
- Separar contenido capturado de título, categoría, emoción, prioridad y ubicación derivados. Las clasificaciones históricas requieren revisión.
- No rellenar desconocidos con números, fotos, coordenadas, autores o radicados de ejemplo.
- No eliminar registros reales por no poder verificarlos en una consulta. Marcar evidencia incompleta y recuperar por IDs exactos cuando sea posible.
- Esta auditoría cubre procedencia de **casos**; no certifica que Inicio, indicadores, contactos y todas las rutas estén libres de contenido de demostración. Permanecen los pendientes P0 del documento central.

## Cambios en la interfaz

El resumen del caso incluye texto y URL de su publicación de origen y un enlace al comentario cuando hay IDs completos. Si falta el origen, se indica explícitamente. Tener una publicación recuperada no implica que todos sus comentarios estén capturados. La imagen es opcional: el contexto de una publicación de texto no depende de una portada.
