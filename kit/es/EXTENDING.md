# Extender MolChat: la llave y la cerradura

> Traducción de [`kit/en/EXTENDING.md`](../en/EXTENDING.md), revisada el 2026-11-03. Si alguna vez no coinciden, manda la versión inglesa.

MolChat es la **llave**: un agente que corre como programa propio, habla con un modelo y pide cosas. La plataforma que lo ejecuta es la **cerradura**: arranca la llave, decide qué puede hacer y lo hace. MolDesign es la primera cerradura, y cualquiera puede **agrandar la llave** o **hacer otra cerradura**.

Esta guía explica cómo, con los archivos que intervienen. Los contratos de detalle están en [`docs/`](../../docs/), y cada apartado enlaza el suyo. Se comprobó por última vez contra MolChat `945c4d7`; si el código y esta guía no coinciden, mandan el código y sus pruebas.

| Quieres… | Lee |
|---|---|
| Que MolChat lea o proponga algo nuevo | [2. Añadir una herramienta](#2-añadir-una-herramienta) |
| Que MolChat pida a la ventana de la plataforma que haga algo a la vista | [3. Añadir una acción de anfitrión](#3-añadir-una-acción-de-anfitrión) |
| Usar MolChat en una plataforma que no es MolDesign | [4. Hacer tu propia cerradura](#4-hacer-tu-propia-cerradura) |
| Meter tu versión de MolChat dentro de MolDesign | [6. Meter tu versión dentro de MolDesign](#6-meter-tu-versión-dentro-de-moldesign) |

## 1. El contrato en una página

```text
modelo ──llamada──▶ sidecar de MolChat ──HTTP, sesión de la cuenta──▶ API de la plataforma
                          │ evento SSE
                          ▼
                 UI de MolChat (iframe) ──postMessage──▶ ventana de la plataforma
                          ▲                               (comprueba, actúa, contesta)
                          └────────────postMessage─────────────┘
```

- **Dos programas.** El sidecar es un proceso de Python en loopback, con su propia interfaz dentro de un iframe. Ninguno importa código del otro. La plataforma arranca el sidecar, comprueba sus archivos contra `molchat-manifest.json` y espera a que `GET /v1/health` diga `contract: moldesign.molchat/1`.
- **Las sesiones las da la cerradura.** La plataforma firma tokens `mh1` de vida corta para cada cuenta (HMAC-SHA256 con el secreto compartido `MOLCHAT_HOST_SECRET`, audiencia `molchat`, permisos y caducidad; el formato está en [`server/auth.py`](../../src/molchat_agent/server/auth.py)). Se los pasa al iframe con un mensaje `molchat-host-session`, nunca en una URL.
- **La API de la plataforma sigue siendo suya.** MolChat la llama con la sesión de la cuenta después de consultar `GET /molchat-host/contract`, y se detiene si falta una capacidad o una versión es desconocida. Rutas y límites: [`CONTRATO_MOLDESIGN.md`](../../docs/CONTRATO_MOLDESIGN.md) y [`PROTOCOLO_MOLDESIGN.md`](../../docs/PROTOCOLO_MOLDESIGN.md).
- **Lo que se hace en pantalla pasa por la ventana**, con esquemas de mensaje cerrados: [`HOST_CONTRACT.md`](../../docs/HOST_CONTRACT.md).

Reglas que todo cambio conserva:

1. **El modelo propone, el código comprueba y la cerradura decide.** Una herramienta valida sus argumentos y la plataforma vuelve a validarlos.
2. **Los números salen de las herramientas.** Una cifra de la respuesta que ninguna herramienta devolvió se oculta antes de que la persona la vea ([`redact_unverified`](../../src/molchat_agent/conversation/evidence.py)).
3. **Los efectos necesitan a una persona.** Guardar o renderizar espera a una tarjeta de confirmación. La única excepción es un plan de iteración aprobado una vez, ligado a su huella SHA-256 ([`ITERACION_DE_MOLECULAS.md`](../../docs/ITERACION_DE_MOLECULAS.md)).
4. **`unknown` no es `failed`.** Si una respuesta no llega, MolChat anota `unknown` y nunca reintenta por su cuenta: puede que la plataforma ya haya actuado.

## 2. Añadir una herramienta

Una herramienta es un [`Tool`](../../src/molchat_agent/conversation/tool_loop.py)`(name, description, parameters, execute)`: un esquema JSON que rellena el modelo y una función asíncrona que la ejecuta. [`get_evaluation_status`](../../src/molchat_agent/conversation/harness_tools.py) es un ejemplo corto y de sólo lectura; [`compare_poses`](../../src/molchat_agent/conversation/compare_poses.py), uno grande.

**Paso 1. Escribe la herramienta.** Las pequeñas van en `conversation/harness_tools.py` y las grandes en su propio módulo. Un esqueleto:

```python
def my_tool(bridge: MolDesignBridge) -> Tool:
    async def run(args: dict[str, Any]) -> dict[str, Any]:
        response = await bridge.client.get(f"/your/route/{args['task_id']}",
                                           headers={"Authorization": f"Bearer {bridge.token}"})
        if response.status_code != 200:
            return {"status": "unavailable"}
        data = response.json()
        # Elige campos; nunca pases al modelo la respuesta entera de la plataforma.
        return {"status": "ok", "value": data.get("value"), "source": "Platform GET /your/route"}
    schema = {"type": "object", "properties": {"task_id": {"type": "string", "maxLength": 128}},
              "required": ["task_id"], "additionalProperties": False}
    return Tool("my_tool", "Qué lee, que es de sólo lectura y cómo no leer el resultado.", schema, run)
```

El esquema se hace cumplir antes de que corra tu función ([`_arguments`](../../src/molchat_agent/conversation/tool_loop.py)):

- los objetos son cerrados (`additionalProperties: false`), con todos los campos obligatorios y ninguno más;
- los textos no pueden estar vacíos ni llevar caracteres de control, miden como mucho `maxLength` (120 por defecto) y, si das un `enum`, deben estar en él;
- los números necesitan `minimum` y `maximum`; los enteros, quedar dentro de su rango; los booleanos tienen que ser booleanos de verdad;
- las listas quedan entre `minItems` y `maxItems` (3 por defecto);
- los argumentos, en total, no pasan de 4096 caracteres.

Devuelve un `status` de un conjunto pequeño y cerrado, y sólo los campos que elegiste. Ausente no es bueno: di qué falta en vez de rellenarlo. Nunca devuelvas rutas, sesiones ni secretos.

**Paso 2. Regístrala.** Las herramientas de cada turno se reúnen en `_harness_turn`, en [`server/app.py`](../../src/molchat_agent/server/app.py). Añade la tuya a esa lista `tools` y envuelve `execute` para que las cifras que devuelve entren en el conjunto `verified` del turno. Si no, la respuesta no podrá citarlas.

**Paso 3. Dile al modelo cuándo usarla**, en la guía que `_harness_turn` envía en cada turno, junto a las líneas de las otras herramientas.

**Paso 4. Si la herramienta cambia algo, no lo hagas dentro de ella.** O deja una propuesta que la persona confirma, como `save_to_moldex` y `request_molcy_video` (la tarjeta llama a `POST /v1/actions/{action_id}/confirm`), o pídeselo a la ventana de la plataforma con una acción de anfitrión (apartado 3). El modelo no tiene ninguna herramienta que confirme.

**Paso 5. Pruébala** sin plataforma real: pruebas unitarias de la función y una prueba de chat que guioniza las llamadas del modelo contra [`tests/conversation/fake_moldesign.py`](../../tests/conversation/fake_moldesign.py). [`tests/server/test_compare_poses_chat.py`](../../tests/server/test_compare_poses_chat.py) es un buen modelo.

**Paso 6. Regístrala en los papeles.** Añade una entrada a [`PROVENANCE.md`](../../PROVENANCE.md) (sin ella, la CI falla) y describe la herramienta en [`CREACION_DE_HERRAMIENTAS.md`](../../docs/CREACION_DE_HERRAMIENTAS.md). Después pasa [las comprobaciones](#5-comprobaciones-antes-de-compartir-un-cambio).

## 3. Añadir una acción de anfitrión

Una acción de anfitrión pide a la ventana de la plataforma algo que la persona ve, como cargar una molécula en el editor o pulsar Evaluar. Necesita tres piezas.

1. **Sidecar.** Añade un registro de peticiones pendientes a `ServerState` ([`server/state.py`](../../src/molchat_agent/server/state.py); `case_status_requests` es un ejemplo pequeño). Emite un evento SSE con un `request_id` nuevo. Añade en `server/app.py` la ruta `POST /v1/<tipo>-requests/{request_id}/result`, que acepta la respuesta sólo de la sesión que preguntó, una sola vez y sólo con su esquema cerrado.
2. **Interfaz.** Añade un puente en `ui/src/lib/<tipo>Host.ts`, por ejemplo [`caseStatusHost.ts`](../../ui/src/lib/caseStatusHost.ts). Reenvía a la ventana padre un `molchat-host-message` con tu `kind`, acepta sólo `molchat-<tipo>-result` del origen de confianza de la ventana padre y lo entrega al sidecar.
3. **Plataforma.** Implementa la acción en la ventana. La de MolDesign es pública: [`MolChatHostMount.tsx`](https://github.com/srcacahuate619/moldesign-app/blob/main/frontend/components/ai-host/MolChatHostMount.tsx).

Después añade la fila de la acción a [`HOST_CONTRACT.md`](../../docs/HOST_CONTRACT.md): campos, tipo de respuesta y cada estado. Prueba el esquema en el servidor (como [`tests/server/test_case_host_action.py`](../../tests/server/test_case_host_action.py)), el puente de la interfaz (como `ui/src/lib/caseStatusHost.test.ts`) y la plataforma simulada. Una plataforma que sabe que no hizo nada contesta `failed`; sólo lo que no puede saber es `unknown`.

Tres mensajes llevan estado sin esperar respuesta: `molchat-ui-status` (una línea para la burbuja del panel minimizado), `molchat-ui-progress` (el plan en marcha, para la vista del piloto automático) y `notify_download` (una entrada en el panel de actividad de la plataforma). [`HOST_CONTRACT.md`](../../docs/HOST_CONTRACT.md) da sus campos exactos.

## 4. Hacer tu propia cerradura

Hay dos niveles, y el límite honesto va primero: hoy, las herramientas del chat y las acciones de anfitrión tienen la forma de MolDesign. Una cerradura nueva sirve las mismas rutas y acciones o añade sus propias herramientas (apartado 2).

**Planes por HTTP, sin el chat.** El ejecutor de planes de MolChat funciona con cualquier API HTTP que describas como capacidades. Decláralas con `Capability` y `register` de [`tools/catalog.py`](../../src/molchat_agent/tools/catalog.py), como hace [`tools/reference.py`](../../src/molchat_agent/tools/reference.py), y compruébalas con el kit de conformidad:

```sh
python examples/reference_backend/server.py
python -m conformance.runner --adapter generic --register molchat_agent.tools.reference \
  --cases examples/reference_backend/cases --live --base-url http://127.0.0.1:8099
```

El recorrido completo, incluido lo que un PASS demuestra y lo que no, está en [`ADAPTADORES.md`](../../docs/ADAPTADORES.md). Todavía no hay un selector de adaptador en la CLI ni en la interfaz: registras tus capacidades en tu propio proceso y le das al ejecutor un `MolDesignBridge` creado con `require_contract=False`.

**El agente completo dentro de tu aplicación.**

1. **Arranca** `python -m molchat_agent serve` con `MOLCHAT_HOST_SECRET` (el secreto con que firmas las sesiones) y `MOLDESIGN_BASE_URL` apuntando a tu API. Por defecto sólo admite loopback; una API remota necesita HTTPS y `MOLDESIGN_ALLOW_REMOTE=1`. Espera a `GET /v1/health`.
2. **Firma sesiones** por cuenta con el formato `mh1` y envía cada una al iframe con `molchat-host-session`. Usa como destino el origen del sidecar, nunca `*`.
3. **Sirve las rutas** que llaman las herramientas, empezando por `GET /molchat-host/contract`. Una herramienta cuya ruta falta contesta `unavailable`; no se inventa nada.
4. **Implementa las acciones de anfitrión** que quieras. El plan de iteración necesita `create_case`, `load_case_smiles`, `assign_case_receptor`, `evaluate_case` y `case_status`; `audit_case_preparation` y `molcy_render` son opcionales, y el cuaderno declara lo que falte.
5. **Claves del modelo.** El sidecar pide a la plataforma una clave en cada llamada (`POST /molchat-host/credencial`), para un proveedor del catálogo que la cuenta autorizó. Sin plataforma, `molchat-agent serve` funciona solo con `MOLCHAT_PROVIDER` ([`SIDECAR.md`](../../docs/SIDECAR.md)).

## 5. Comprobaciones antes de compartir un cambio

```sh
python -m pytest -q
python -m conformance.runner
python scripts/check_provenance.py
python scripts/check_secrets.py
npm --prefix ui test
npm --prefix ui run build
python scripts/check_ui_build.py
```

La CI las ejecuta con Python 3.11 y 3.12 desde un clon limpio ([`ci.yml`](../../.github/workflows/ci.yml)). `check_secrets` también lee los archivos sin versionar, así que un token de prueba o una ruta local olvidados en tu carpeta de trabajo lo hacen fallar: pásalo en un clon limpio antes de empujar.

## 6. Meter tu versión dentro de MolDesign

MolDesign guarda una copia de la llave en `tools/molchat/` y la fija en `backend/data/molchat_fijacion.json`: commit, repositorio, versión y SHA-256 del manifiesto. Antes de arrancarla comprueba cada archivo contra el manifiesto, el nombre del contrato y la fijación, y se niega a arrancar una copia que no coincide. MolDesign funciona sin MolChat: la llave es opcional.

Desde un clon de MolDesign, con la interfaz de tu commit de MolChat ya construida:

```powershell
.\python-embed\python.exe scripts\stage_molchat.py --fuente <tu-clon-de-molchat> --write
.\python-embed\python.exe scripts\stage_molchat.py --check
```

Sólo se prepara código commiteado. Un fork queda fijado con `oficial: false`, y MolDesign lo muestra como no oficial. Para probar una versión sin tocar la copia fijada, prepárala con `--destino` y define `MOLDESIGN_MOLCHAT_DIR` y `MOLCHAT_PERMITIR_EXTERNO=1` ([Primeros pasos](GETTING_STARTED.md#usar-un-molchat-más-nuevo)). Las reglas completas de la copia y la fijación están en [`LLAVE_Y_CERRADURA.md`](../../docs/LLAVE_Y_CERRADURA.md) y [`DESARROLLO_Y_VERSION_PROPIA.md`](../../docs/DESARROLLO_Y_VERSION_PROPIA.md).

**Licencia.** MolChat es GPL-3.0-or-later. Si distribuyes una versión modificada, debes ofrecer su código fuente a quien la reciba. MolDesign está bajo PolyForm Noncommercial; los dos se hablan por HTTP y ninguno importa al otro. Esto es ingeniería y procedencia, no asesoría jurídica.
