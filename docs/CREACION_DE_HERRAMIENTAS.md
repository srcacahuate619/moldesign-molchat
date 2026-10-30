# Creación de herramientas para MolChat y MolDesign

MolChat interpreta la petición y solicita una capacidad; MolDesign conserva la
operación real, los datos y la identidad. La guía completa de ambos lados vive
en `docs/CREACION_DE_HERRAMIENTAS_MOLCHAT.md` del repositorio MolDesign.

## Asignar un receptor a un caso

El ciclo de herramientas nativas actual ofrece `search_receptors` y
`assign_case_receptor`. MolChat selecciona la herramienta a partir de la
petición; para asignar requiere un identificador explícito o una búsqueda
inequívoca en el catálogo de la cuenta. El host valida la sesión, el caso,
la disponibilidad y el sistema estructural, aplica la selección mediante la
misma lógica del selector y confirma únicamente tras el guardado del caso.
La asignación no inicia una evaluación. Un error o una respuesta perdida no
demuestra que el caso se haya guardado: se debe revisar antes de reintentar.

## Primera herramienta: crear un caso (integración histórica)

En modo alojado, el servidor identifica una petición de caso y pide al proveedor
activo una selección JSON con `tool` y `name`. `case_selection.py` acepta solo
`create_case`, un esquema cerrado y un nombre presente en el mensaje original.
El modelo propone: no crea ni confirma nada.

El servidor envía el evento `case_create` con un identificador aleatorio y
espera una respuesta. La UI lo pasa al host por `postMessage`; el host valida
ventana, origen, forma y cuenta. MolDesign ejecuta su función de casos y devuelve
`created`, `exists`, `failed` o `unknown`. La UI entrega ese resultado al
servidor mediante la sesión autenticada. Solo `created` produce una afirmación
de éxito. Una respuesta perdida produce `unknown`: revisar antes de reintentar.

Esta primera integración no implementa llamadas nativas a herramientas ni un
enrutador general: solo las peticiones que el clasificador reconoce como
acciones de caso entran a este flujo. El resultado de `exists` no abre el caso,
no lo modifica y no prueba que dos nombres diferentes no apunten a la misma
carpeta. La verificación final de colisiones sigue en MolDesign.

## Para añadir otra capacidad

1. Definir en MolDesign la operación y sus resultados verificables, reutilizando
   sus validaciones y permisos existentes.
2. Versionar el contrato entre programas y describir explícitamente los datos,
   la identidad, los efectos, la autorización y las condiciones de error.
3. En MolChat validar la selección y argumentos sin confiar en el texto del
   modelo. Nunca informar éxito antes de recibir confirmación del host.
4. Cubrir éxito, entrada inválida, errores, identidad, mensajes ajenos,
   repetición, pérdida de respuesta y resultado incierto en ambos proyectos.
5. Ejecutar una prueba entre procesos y una prueba real en la app de escritorio;
   una prueba simulada no sustituye la ejecución con el proveedor y la UI reales.
6. Construir la UI, fijar un commit limpio, generar y verificar el manifiesto y
   actualizar la copia y fijación con `scripts/stage_molchat.py` en MolDesign.
   No editar a mano la copia vendorizada.

Los identificadores de solicitud actuales se deduplican en memoria del host;
no constituyen idempotencia durable entre reinicios. Las futuras operaciones
con efectos necesitan su propia política de recuperación y autorización.
