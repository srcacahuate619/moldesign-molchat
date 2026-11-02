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

Cuando el usuario pide un receptor al azar, `pick_random_receptor` lee todo el
catálogo accesible para la cuenta, excluye los receptores no disponibles y los
identificadores ambiguos, y devuelve una elección aleatoria con su sección.
La elección no modifica el caso: el agente solicita la asignación mediante
`assign_case_receptor` y espera la confirmación del host. El filtro de
verificados solo se aplica cuando el usuario lo ha pedido.

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

### Iniciar una evaluación

`evaluate_case` solicita al host iniciar la evaluación del caso indicado solo
cuando el usuario lo pide. MolDesign conserva las validaciones del botón, el
preflight y el registro del trabajo. `started` significa que el backend aceptó
la tarea y que se registró en el caso; no significa que haya terminado. Si el
resultado es incierto, no se reintenta automáticamente.

### Sugerencias contextuales

`suggest_next_actions` permite al modelo proponer de cero a tres peticiones
breves como botones, sin ejecutarlas. El texto visible es exactamente el que
se envía al chat si el usuario pulsa el botón. Las sugerencias se guardan con
la respuesta y solo se muestran las de la respuesta más reciente. La referencia
y el tipo de comparación o verificación permiten descartar esas acciones si
ya se completaron en el turno; las demás peticiones se ofrecen como sugerencias
generales y siguen pasando por las herramientas y validaciones disponibles.

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

## Explicar un resultado terminado

`explain_evaluation` es de solo lectura: lee `GET /evaluation/status/{task_id}` con la sesión de la cuenta y devuelve cuatro
hechos, cada uno con la condición y el límite que MolDesign declara:

- **Afinidad de Vina**, con versión, exhaustividad, número de poses, semilla y receptor. Es la energía de la mejor pose; no es
  una energía libre, un Ki ni actividad.
- **Calibración del receptor**, con su nivel, el resumen, la advertencia y el motivo tal como llegan. Si el receptor está
  calibrado, también la ρ, el intervalo del 95 %, el n, el panel y el ensayo, y si el intervalo excluye el cero (lo calcula el
  código, no el modelo). Una ρ escrita en la fila del receptor sin esa medida se informa aparte y no concede calibración.
- **Avisos científicos**, con su código, severidad y texto.
- **Vigencia del protocolo**: si la corrida es comparable con la receta y la calibración de hoy.

Cómo se mantiene honesto:

1. **Lista de campos permitidos.** El resultado se construye eligiendo campos, no filtrando: una ruta local, el índice compuesto
   heredado o cualquier campo que MolDesign añada después no llegan al modelo hasta que alguien decida que deben llegar.
2. **Ausente no es bueno.** Un campo que la corrida no declara (las anteriores a la calibración congelada, por ejemplo) sale en
   `absent` y con una nota; nunca como «calibrado».
3. **Los números los respalda la herramienta.** Todo número que devuelve se registra solo, y la respuesta debe citarlo con las
   cifras con que llega. Un número cercano pero distinto (una ρ de 0,3 cuando es 0,39) se oculta. **Límite:** el verificador
   comprueba que el número exista entre los hechos, no que esté asignado a la magnitud correcta; un 0,5 que coincide con el
   0,54 del límite superior del intervalo pasa aunque el modelo lo atribuya a la ρ.
4. **MolDesign tiene la última palabra sobre la calibración.** Tras la respuesta, el host añade la calibración tal como la
   declara MolDesign, también cuando el modelo dice otra cosa. El texto del modelo no se corrige: queda leído junto a la
   declaración.

**Medido y corregido el 2026-11-02, en MolDesign.** `GET /evaluation/status/{task_id}` volvía a calcular `target_calibracion`
con el receptor de hoy y pisaba la que la corrida guardó al terminar (reproducido con el código real: guardada
`curado_estructural`, devuelta `sin_curar`). Desde esa corrección el estado entrega la guardada. Una corrida anterior al
congelado no la tiene: MolDesign cae a la de hoy para no perder la advertencia, y esa calibración no es la de la fecha de la
corrida. Con un MolDesign anterior a la corrección la calibración que se explica puede ser la de hoy; `target_name`,
`target_hotspots` y `target_spearman_rho` siguen recalculándose en esa ruta.

Todavía no hay una herramienta para localizar la tarea de un resultado ya guardado: hace falta el `task_id` que devolvió
`evaluate_case` o que ya figura en la conversación.

## Guardar en Moldex y pedir un vídeo a Molcy

Son acciones con efecto, así que el modelo **propone y la persona confirma**. `save_to_moldex(task_id, name?)` y
`request_molcy_video(task_id, scene, format, …)` comprueban lo que se puede comprobar sin escribir nada (la corrida terminó con
éxito, si ya está en Moldex, que la escena figure entre `escenas_disponibles` de `GET /molcy/fuentes`, que `GET /molcy/renderizador`
declare Blender y GPU) y dejan una propuesta en la memoria del sidecar. La interfaz la muestra como tarjeta; el botón
«Confirmar» llama a `POST /v1/actions/{id}/confirm`, y solo entonces el sidecar llama a MolDesign con la sesión de la persona.

- **Por qué la confirmación vive aquí.** MolDesign acepta hoy la sesión del chat como la identidad completa de la cuenta en
  cualquier endpoint, sin comprobar los permisos de la sesión. Si la cerradura no distingue «el modelo» de «la persona», la
  llave tiene que hacerlo: el modelo no tiene ninguna herramienta que confirme.
- **Un vídeo sale de una corrida guardada.** Si no lo está, la propuesta lo dice («Se guardará primero en Moldex») y, al
  confirmar, guarda y después pide el vídeo; si el guardado falla, no se pide el vídeo.
- **Personalización.** Solo la receta que Molcy ya valida (`PresentacionMolcy`): título, colores `#RRGGBB`, receptor
  `automatico`/`visible`/`oculto`, muestra anterior, etiquetas y contactos. Se envía únicamente lo que la persona pidió. No hay
  campo para el cierre de MolDesign (obligatorio), ni para CPU, ni para el motor: el dispositivo es siempre `gpu` y un campo
  desconocido lo rechaza Molcy con 422.
- **Sin GPU o sin Blender no hay propuesta.** Se informa el motivo que declara Molcy; no se instala nada desde el chat.
- **Qué dice el turno.** Con propuestas, la respuesta la escribe el host («Dejé preparado … Todavía no se hizo nada»); sin
  ellas, una frase del modelo que afirme «guardé» o «generé el vídeo» se corrige. El resultado confirmado queda en la
  conversación para que el turno siguiente lo lea.
- **Resultado perdido.** Si no llega la respuesta de MolDesign al pedir el vídeo, el resultado es `unknown` («revisa la pestaña
  Molcy antes de reintentar»), nunca «no pasó nada». Un segundo clic sobre una propuesta ya resuelta devuelve el resultado
  guardado; no repite la acción.
- **Seguir el vídeo.** `get_molcy_video_status(job_id)` es de solo lectura y devuelve estado, fase, fotogramas y tiempo restante
  tal como los declara Molcy; el vídeo terminado se abre y se guarda desde la pestaña Molcy.

Límites declarados: las propuestas viven en memoria (15 minutos; un reinicio las pierde) y la tarjeta solo aparece en el turno
que la creó, no al reabrir la conversación. El texto de las tarjetas y de los resultados sale en español. El corrector de
frases cubre verbos en pasado (`guardó`, `generé`, `se inició el vídeo`), no cualquier paráfrasis.

## Seguir una evaluación aceptada

`get_evaluation_status` es de solo lectura: consulta `GET /evaluation/status/{task_id}`
con la sesión de la cuenta, para un `task_id` que `evaluate_case` devolvió. Informa
`task_status` y el progreso tal como llegan. Solo con `SUCCESS` devuelve la afinidad de
Vina (energía de la mejor pose, no una energía libre ni un Ki), la versión de Vina, el
receptor y la calibración que MolDesign declara, y cuántos avisos científicos hay. Una
tarea ajena o inexistente se informa como `not_found`; un estado incompatible o una
caída, como `unavailable`. No inicia, cancela ni reintenta nada.
