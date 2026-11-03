# Cribado automático con una sola aprobación

Una persona escribe una petición; el modelo la convierte en un **plan**; la persona lo aprueba **con un clic** y a partir
de ahí nada espera a nadie hasta que termina. Es la parte del agente que se construyó durante el hackathon
(27 oct – 4 nov 2026) sobre las acciones de host de [`HOST_CONTRACT.md`](HOST_CONTRACT.md).

Ejemplo de petición:

> investiga esta lista de moléculas y, si alguna pasa el umbral de −9,5 kcal/mol, guárdala en Moldex, genera un vídeo de
> búsqueda, hazle la auditoría en Preparación y al final prepárame todo en un único archivo

## Quién hace qué

| Quién | Hace | No hace |
|---|---|---|
| **El modelo** | Lee la petición y propone los parámetros (`propose_screening`): caso, receptor, moléculas, umbral, qué guardar. | No itera, no decide cuándo parar, no calcula, no escribe el cuaderno. |
| **MolChat (código)** | Valida el plan, lo muestra, ejecuta el bucle determinista, guarda el registro y escribe el cuaderno y el ZIP. | No calcula ninguna energía ni control: los lee de MolDesign. |
| **La persona** | Aprueba el plan una vez. Puede cancelar antes. | No necesita intervenir después. |
| **MolDesign** | Crea el caso, acopla con Vina, valida la pose (PoseBusters), guarda en Moldex, renderiza con Molcy, audita en Preparación. | — |

## El plan es un objeto cerrado

`ScreeningSpec` (`moldesign.molchat.screening/1`) se valida antes de mostrarse: entre 1 y 12 moléculas, umbral entre −30 y
0 kcal/mol, escenas y formatos de vídeo de una lista fija, tope por molécula (30–1800 s) y tope total (60–7200 s). Un
parámetro fuera de rango no se corrige: el plan se rechaza.

La tarjeta de aprobación enseña **todo** lo que se hará (caso, receptor, cada molécula, la regla, los topes). El clic
envía el **hash SHA-256 del plan**; el servidor sólo ejecuta si coincide con el plan que guardó. Un plan modificado
después de mostrarse no se ejecuta, y un segundo clic no lo ejecuta dos veces (devuelve el estado).

La petición original de la persona se copia literal al plan (`original_request`) y va al cuaderno: el modelo no puede
reescribir lo que se le pidió.

## La regla de parada

Una molécula **cumple** cuando se dan las dos cosas:

1. la energía de Vina de su mejor pose es **menor o igual** que el umbral, y
2. los controles físicos de esa pose (PoseBusters, según MolDesign) están en `passed`.

La energía sola **no basta**: una pose que Vina favorece y PoseBusters rechaza se registra como `near` y el bucle sigue.
La segunda condición se puede desactivar en el plan, pero entonces la tarjeta lo dice. `stop: first` se detiene en la
primera que cumple; `stop: all` evalúa toda la lista.

Es una regla de **priorización**. La energía de Vina no es una energía libre de unión ni una medida de actividad, y que
una molécula cumpla no significa que sea activa.

## El bucle no se rompe por una molécula

Cada molécula es un intento aislado con su propio estado: `evaluated`, `failed`, `timeout`, `unknown` o `skipped`.

- Un fallo se registra con su motivo y el bucle sigue con la siguiente.
- `busy` (MolDesign está ocupado) se reintenta con espera acotada.
- `unknown` (no se sabe si MolDesign llegó a hacer algo) **nunca se repite**: repetirlo podría duplicar una evaluación.
- Si se agota el tope total, el estado final es `budget_exhausted`, con lo evaluado hasta ahí.
- Si la ventana de MolDesign se cierra mientras corre, el plan se cancela.

## Lo que ocurre después de elegir

Cuando una molécula cumple, MolChat pide a MolDesign —con el plan ya aprobado— guardarla en Moldex y, si el plan lo
incluye, un vídeo de búsqueda. El vídeo lo renderiza Molcy y **siempre lleva su cierre de MolDesign**; MolChat sólo lo
pide y lo sigue. Mientras el vídeo se renderiza, en paralelo, se audita la corrida en Preparación.

### Preparación: se declara, no se decide

MolChat obtiene de MolDesign la auditoría de Preparación y su paquete exportado. El estado (`BLOQUEADO`, `REVISION`,
`TRANSFERIBLE`) es **el que dicta MolDesign**. MolChat no resuelve las decisiones humanas que Preparación pide (aguas,
protonación, tautómeros, metales…): si el resultado es `REVISION` o `BLOQUEADO`, así queda escrito en el cuaderno y en la
tarjeta. Un archivo que oculte una ambigüedad para parecer terminado sería un defecto, no una ventaja.

## Lo que se entrega

Siempre, en una carpeta de salida (`MOLCHAT_OUTPUT_DIR`; por defecto `~/MolDesign/MolChat/entregas`):

- **Cuaderno** (`cuaderno.json`, `cuaderno.md` y `cuaderno.pdf` si está `reportlab`): la petición literal, el plan
  aprobado con su hash, cada molécula con su estado, la energía y el control físico, lo que se guardó, el estado del
  vídeo y de Preparación, y las notas. Lo escribe el código con los datos del registro; el modelo no interviene.
  Con la misma entrada sale el mismo cuaderno (el PDF es determinista).
- **ZIP de entrega** (`entrega.zip`), sólo si el plan lo pide. Es una herramienta aparte: junta el cuaderno, el vídeo y el
  paquete de Preparación **tal cual lo entregó MolDesign** (se inserta byte a byte; MolChat no lo abre ni lo reescribe).
  Entradas ordenadas y marcas de tiempo fijas: la misma entrada da los mismos bytes. `MANIFEST.json` lleva el SHA-256 de
  cada pieza, quién la produjo (MolDesign o MolChat) y, en `missing`, lo que no está y por qué. Una pieza ausente se
  declara; nunca se sustituye por algo que se le parezca. `verify_deliverable` lo comprueba.

## Qué no es

- No es un cribado virtual a escala: son hasta 12 moléculas, una a una, con Vina y los tiempos que declara la tarjeta.
- No predice actividad biológica ni da consejo médico.
- No hace que un archivo «parezca listo»: lo que Preparación bloquea o pide revisar se conserva así.
- No es independiente de MolDesign: la ciencia, la identidad y el cómputo viven allí
  ([`LLAVE_Y_CERRADURA.md`](LLAVE_Y_CERRADURA.md)).

## Dónde está en el código y cómo se prueba

| Pieza | Código | Pruebas |
|---|---|---|
| Plan, regla y bucle | `src/molchat_agent/workflows/screening.py` | `tests/workflows/test_screening.py` |
| Cuaderno y ZIP | `workflows/notebook.py`, `workflows/deliverable.py` | `tests/workflows/test_notebook_and_deliverable.py` |
| Ejecución con la plataforma y la ventana | `workflows/service.py` | `tests/workflows/test_service.py`, `tests/server/test_workflow_chat.py`, `tests/server/test_workflow_preparation.py` |
| Herramienta del modelo | `workflows/tool.py` | `tests/server/test_harness_chat.py` |
| Tarjeta de aprobación y relevo al anfitrión | `ui/src/components/ScreeningCard.tsx`, `ui/src/lib/preparationHost.ts` | `ScreeningCard.test.tsx`, `preparationHost.test.ts` |

Las pruebas usan una plataforma simulada que responde como MolDesign (`tests/conversation/fake_moldesign.py`). **No
sustituyen** un ensayo con la plataforma real: ese ensayo, con el modelo real, se registra en el cuaderno de la demo y no en
este documento.
