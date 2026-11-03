# Contrato de acciones de host

Qué tiene que implementar una plataforma para que MolChat opere sobre ella. Este documento existe porque el código
del anfitrión de MolDesign (la «cerradura») no es público: sin él, un tercero no podría saber qué le pide MolChat ni qué
tiene que contestar. Describe lo que **MolChat envía y acepta**, verificado contra su código y sus pruebas; no describe
la ciencia de MolDesign.

> Estado: estas acciones **no forman parte** de `moldesign.molchat/1` ni del kit de conformidad
> ([`BASE_HARNESS_Y_PUENTE.md`](BASE_HARNESS_Y_PUENTE.md)). Son el contrato del modo alojado, con un anfitrión que
> incrusta la interfaz de MolChat en un `iframe`. Un servidor sin esa ventana no puede ejecutarlas.

## Por qué existe un puente

MolChat no ejecuta nada sobre la plataforma por su cuenta: **pide**, y el anfitrión, que conoce la cuenta, la
pantalla y el estado del producto, **hace o rechaza** y contesta con un estado. Es la misma frontera de
[`LLAVE_Y_CERRADURA.md`](LLAVE_Y_CERRADURA.md): la llave propone, la cerradura decide.

```text
modelo ──herramienta──▶ sidecar ──SSE: «case_create», …──▶ iframe (UI de MolChat)
                                                              │ postMessage
                                                              ▼
                                                      ventana del anfitrión
                                                      (valida, ejecuta, contesta)
                                                              │ postMessage
sidecar ◀──POST /v1/<tipo>-requests/{id}/result── iframe ◀────┘
```

1. El sidecar emite por SSE un evento con un `request_id` y los datos de la petición.
2. La interfaz lo reenvía a la ventana padre como `molchat-host-message` con un `kind`.
3. El anfitrión valida, ejecuta en su propia pantalla y contesta con `molchat-<tipo>-result`.
4. La interfaz entrega esa respuesta al sidecar, que despierta a quien esperaba (el turno del modelo o la iteración).

El sidecar **sólo acepta la respuesta de la sesión que hizo la petición**, una sola vez, y rechaza lo que no encaja
con el esquema cerrado de cada acción (campos de más, estados desconocidos, textos con caracteres de control).

## Apretón de manos y origen

| Mensaje | De → a | Contenido |
|---|---|---|
| `molchat-ui-ready` | iframe → anfitrión | La interfaz cargó y espera sesión. |
| `molchat-host-session` | anfitrión → iframe | `token` (sesión del sidecar), `locale`, `theme`. Se envía con el origen del sidecar como destino, nunca con `*`. |
| `molchat-host-hidden` | anfitrión → iframe | El panel se cerró; la interfaz deja de grabar voz. |

Reglas que el anfitrión debe cumplir y MolChat comprueba del otro lado:

- El anfitrión sólo atiende mensajes cuyo `event.source` es **su** iframe y cuyo origen es el del sidecar (loopback).
- La interfaz sólo acepta respuestas cuyo `event.source` es la ventana padre y cuyo origen es de confianza
  (`isTrustedHostOrigin`).
- La sesión no viaja nunca en una URL. Las descargas usan la cabecera `Authorization`.

## Acciones que piden algo y esperan respuesta

Todas llevan `type: "molchat-host-message"`, `kind` y `request_id`. **El mensaje tiene exactamente los campos de su fila,
ni uno más ni uno menos**; un campo extra o vacío invalida la petición completa. El anfitrión de MolDesign exige además
que `request_id` sean 32 caracteres hexadecimales y que `case_name` y `name` no pasen de 100 caracteres.

| `kind` | Campos | Respuesta (`type`) | Estados posibles |
|---|---|---|---|
| `create_case` | `name` | `molchat-case-result` | `created`, `exists`, `failed`, `unknown` |
| `load_case_smiles` | `case_name`, `smiles` | `molchat-smiles-result` | `applied`, `not_found`, `ambiguous`, `busy`, `failed`, `unknown` |
| `assign_case_receptor` | `case_name`, `pdb_id` | `molchat-receptor-result` | `applied`, `already_selected`, `case_not_found`, `case_ambiguous`, `receptor_not_found`, `receptor_ambiguous`, `unavailable`, `locked`, `busy`, `save_failed`, `failed`, `unknown` |
| `evaluate_case` | `case_name` | `molchat-evaluation-result` | `started`, `started_unregistered`, `case_not_found`, `case_ambiguous`, `busy`, `blocked`, `needs_review`, `failed`, `unknown` |
| `audit_case_preparation` | `case_name`, `task_id` | `molchat-preparation-result` | `audited`, `case_not_found`, `case_mismatch`, `not_auditable`, `audit_failed`, `busy`, `failed`, `unknown` |
| `case_status` | `case_name` | `molchat-case-status-result` | `idle`, `busy`, `not_found`, `ambiguous`, `failed`, `unknown` |
| `molcy_render` | `task_id`, `scene`, `format` | `molchat-molcy-result` | `started` (con `job_id`), `not_found`, `unavailable`, `busy`, `failed`, `unknown` |
| `read_editor` | `case_name`, `operation`, `revision` | `molchat-editor-result` | `ok`, `not_ready`, `not_found`, `ambiguous`, `changed`, `too_large`, `read_limit`, `failed`, `unknown` |

Cada respuesta repite el `request_id` de su petición y lleva `status`. Además:

- `evaluate_case` devuelve `task_id` **si y sólo si** el estado es `started` o `started_unregistered`
  (`^[A-Za-z0-9_.:-]{1,128}$`). Con cualquier otro estado, un `task_id` invalida la respuesta. Opcionalmente, `reason`
  (≤ 500 caracteres, sin caracteres de control).
- `read_editor` puede devolver `molfile` (≤ 256 KiB) y `revision` (≤ 100 caracteres); no admite ningún otro campo.
- `audit_case_preparation` con estado `audited` devuelve **exactamente** `molecule_id`, `estado` y `projection`
  (ver abajo). Con otro estado, sólo `status` y, opcionalmente, `reason` (≤ 300 caracteres, sin caracteres de control).

### Tiempos de espera: `unknown` no es `failed`

Si una petición no recibe respuesta a tiempo, MolChat registra `unknown` y **no la repite**. El motivo es que el
anfitrión pudo haber escrito antes de que se agotara la espera: reintentar duplicaría un caso o una evaluación. Un
anfitrión que sabe que no hizo nada debe contestar `failed`; sólo lo que no se sabe es `unknown`. La iteración de
moléculas aplica la misma regla: un `unknown` queda declarado en el cuaderno y el bucle sigue con la molécula siguiente.

### Estado del caso (`case_status`)

Pregunta de **sólo lectura**: ¿puede este caso recibir otra molécula ahora? `busy` significa que la ventana sigue cerrando
la corrida anterior (o atendiendo otra petición del chat); `idle`, que se puede cargar. Puede añadir `run_state` (el estado
de la última corrida del caso, `^[a-z_]{1,32}$`) y su `task_id`. No navega ni cambia nada. Un anfitrión sin espacio de
casos montado contesta `unknown`, nunca `idle`; con `unknown`, MolChat recurre a reintentar la carga mientras diga `busy`.

### Vídeo de Molcy (`molcy_render`)

El anfitrión lleva a la persona a la pestaña de Molcy, que **prepara el vídeo a la vista**: elige la corrida guardada en
Moldex (`task_id`), la escena y el formato, un paso tras otro, y pulsa su propio botón «Generar video» con sus propias
comprobaciones (GPU, Blender, espacio en disco). Devuelve el `job_id` que empezó o, si no pudo, por qué
(`not_found`: la corrida no está guardada; `unavailable`: falta GPU, Blender o espacio, con el motivo que enseña la
pestaña). MolChat no lanza el vídeo por detrás de la ventana cuando el anfitrión tiene esta acción, y un `unknown` no se
repite: la pestaña pudo empezar un render.

### Auditoría en Preparación (`audit_case_preparation`)

El anfitrión localiza la corrida (`task_id`) del caso (`case_name`), construye la **proyección del caso** con su propia
lógica y la devuelve junto con el estado que su auditoría dictó. MolChat **no** reconstruye ni modifica esa proyección:

- `estado` ∈ `BLOQUEADO`, `REVISION`, `TRANSFERIBLE`. MolChat los declara tal cual; nunca convierte `REVISION` en
  `TRANSFERIBLE`, y nunca inventa una decisión humana que el producto pide (aguas, protonación, tautómeros…).
- Si la corrida no corresponde al caso, la respuesta es `case_mismatch` y no hay auditoría.
- Con la proyección, el sidecar llama a la plataforma —con la sesión de la cuenta, no con la del anfitrión— para
  auditar (`POST /evaluation/dossier/{molecule_id}/preparacion`) y exportar (`POST …/package`). El estado que se
  registra es el que dicta **la plataforma**, no el que informó la ventana.
- El paquete exportado por la plataforma es determinista y entra **intacto** (byte a byte) en el ZIP de entrega de
  MolChat; MolChat no lo abre ni lo reescribe.

## Acciones que sólo navegan (sin respuesta)

| `kind` | Campos | Efecto esperado |
|---|---|---|
| `open_evaluation` | `molecule_id` | Abre la evaluación o su historial. |
| `open_report` | `molecule_id` | Abre el informe. |
| `open_case` | `case_id` | Abre el caso en Moldex. |
| `open_molcy` | `job_id` | Abre el trabajo de vídeo. |
| `request_platform_approval` | `proposal_id` | Si el anfitrión no tiene superficie de aprobación, muestra un aviso. |

No hay respuesta: son enlaces, no operaciones.

## Lo que el anfitrión no debe hacer

- **No decidir por la persona.** Una acción que requiere confirmación (guardar en Moldex, pedir un vídeo, acoplar con
  cómputo pesado) la confirma la persona en una tarjeta; el anfitrión sólo ejecuta lo que ya se confirmó. La única
  excepción es el plan de iteración aprobado de una vez, cuyo clic queda ligado al hash SHA-256 del plan:
  [`ITERACION_DE_MOLECULAS.md`](ITERACION_DE_MOLECULAS.md).
- **No contestar con más de lo que se pidió.** Los esquemas son cerrados a propósito: un campo desconocido en una
  respuesta es una respuesta rechazada.
- **No devolver rutas, sesiones ni secretos** en ningún campo.

## Qué cubre la suite pública

| Pieza | Prueba |
|---|---|
| Esquemas y estados de cada respuesta | `tests/server/test_case_host_action.py`, `tests/server/test_workflow_preparation.py` |
| Relevo de la iteración a la ventana | `ui/src/components/IterationCard.test.tsx` |
| Puente de Preparación (origen, forma, plazo) | `ui/src/lib/preparationHost.test.ts` |
| Plataforma simulada que contesta lo anterior | `tests/conversation/fake_moldesign.py` |

El anfitrión real de MolDesign (`MolChatHostMount`) tiene sus propias pruebas en el repositorio de MolDesign, que no
se publica. Lo que esta tabla no demuestra es la integración viva con una ventana real de Tauri: se ensaya a mano y se
declara en el vídeo.
