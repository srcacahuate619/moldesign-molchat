# Extending MolChat: the key and the lock

MolChat is the **key**: an agent that runs as its own program, talks to a model, and asks for things. The platform that runs it is the **lock**: it launches the key, decides what the key may do, and does it. MolDesign is the first lock, and anyone can **enlarge the key** or **build another lock**.

This guide shows how, with the files involved. The detailed contracts are in Spanish, in [`docs/`](../../docs/), and each section links to its own. This guide was last checked against MolChat `945c4d7`; when the code and this guide disagree, the code and its tests are right.

| You want to… | Read |
|---|---|
| Let MolChat read or propose something new | [2. Add a tool](#2-add-a-tool) |
| Let MolChat ask the platform window to act on screen | [3. Add a host action](#3-add-a-host-action) |
| Run MolChat on a platform that isn't MolDesign | [4. Build your own lock](#4-build-your-own-lock) |
| Put your version of MolChat inside MolDesign | [6. Ship your version inside MolDesign](#6-ship-your-version-inside-moldesign) |

## 1. The contract in one page

```text
model ──tool call──▶ MolChat sidecar ──HTTP, account's session──▶ platform API
                          │ SSE event
                          ▼
                  MolChat UI (iframe) ──postMessage──▶ platform window
                          ▲                               (checks, acts, answers)
                          └────────────postMessage─────────────┘
```

- **Two programs.** The sidecar is a Python process on loopback, with its own UI shown in an iframe. Neither imports the other's code. The platform launches the sidecar, checks its files against `molchat-manifest.json`, and waits for `GET /v1/health` to say `contract: moldesign.molchat/1`.
- **Sessions come from the lock.** The platform signs short-lived `mh1` tokens per account (HMAC-SHA256 with the shared `MOLCHAT_HOST_SECRET`, audience `molchat`, scopes, expiry; format in [`server/auth.py`](../../src/molchat_agent/server/auth.py)). It hands them to the iframe with a `molchat-host-session` message, never in a URL.
- **The platform API stays the platform's.** MolChat calls it with the account's session after checking `GET /molchat-host/contract`, and stops if a capability is missing or a version is unknown. Routes and limits: [`CONTRATO_MOLDESIGN.md`](../../docs/CONTRATO_MOLDESIGN.md) and [`PROTOCOLO_MOLDESIGN.md`](../../docs/PROTOCOLO_MOLDESIGN.md).
- **Actions on screen go through the window**, with closed message schemas: [`HOST_CONTRACT.md`](../../docs/HOST_CONTRACT.md).

Rules every change keeps:

1. **The model proposes, code checks, the lock decides.** A tool validates its arguments; the platform validates again.
2. **Numbers come from tools.** A number in an answer that no tool returned is hidden before the person sees it ([`redact_unverified`](../../src/molchat_agent/conversation/evidence.py)).
3. **Effects need a person.** Saving or rendering waits for a confirmation card. The one exception is an iteration plan approved once, bound to its SHA-256 digest ([`ITERACION_DE_MOLECULAS.md`](../../docs/ITERACION_DE_MOLECULAS.md)).
4. **`unknown` is not `failed`.** When an answer doesn't arrive, MolChat records `unknown` and never retries on its own: the platform may already have acted.

## 2. Add a tool

A tool is a [`Tool`](../../src/molchat_agent/conversation/tool_loop.py)`(name, description, parameters, execute)`: a JSON schema the model fills and an async function that runs it. [`get_evaluation_status`](../../src/molchat_agent/conversation/harness_tools.py) is a short read-only example; [`compare_poses`](../../src/molchat_agent/conversation/compare_poses.py) is a large one.

**Step 1. Write the tool.** Put small tools in `conversation/harness_tools.py` and larger ones in their own module. A skeleton:

```python
def my_tool(bridge: MolDesignBridge) -> Tool:
    async def run(args: dict[str, Any]) -> dict[str, Any]:
        response = await bridge.client.get(f"/your/route/{args['task_id']}",
                                           headers={"Authorization": f"Bearer {bridge.token}"})
        if response.status_code != 200:
            return {"status": "unavailable"}
        data = response.json()
        # Pick fields; never pass the platform's whole answer to the model.
        return {"status": "ok", "value": data.get("value"), "source": "Platform GET /your/route"}
    schema = {"type": "object", "properties": {"task_id": {"type": "string", "maxLength": 128}},
              "required": ["task_id"], "additionalProperties": False}
    return Tool("my_tool", "What it reads, that it is read-only, and how not to read the result.", schema, run)
```

The schema is enforced before your function runs ([`_arguments`](../../src/molchat_agent/conversation/tool_loop.py)):

- objects are closed (`additionalProperties: false`), with every required field present and no others;
- strings are non-empty, without control characters, at most `maxLength` long (120 by default), and within `enum` if you give one;
- numbers need both `minimum` and `maximum`; integers stay within their range; booleans must be real booleans;
- arrays stay within `minItems` and `maxItems` (3 by default);
- the whole argument string is at most 4096 characters.

Return a `status` from a small closed set, and only the fields you chose. Missing is not good: say what is absent instead of filling it in. Never return paths, sessions or secrets.

**Step 2. Register it.** The tools a turn may use are assembled in `_harness_turn` in [`server/app.py`](../../src/molchat_agent/server/app.py). Add yours to that `tools` list, and wrap `execute` so the numbers your tool returns go into the turn's `verified` set. Otherwise the answer can't quote them.

**Step 3. Tell the model when to use it**, in the guidance `_harness_turn` sends with each turn, next to the other tools' lines.

**Step 4. If the tool changes anything, don't do it in the tool.** Either leave a proposal the person confirms, like `save_to_moldex` and `request_molcy_video` (the card calls `POST /v1/actions/{action_id}/confirm`), or ask the platform window with a host action (section 3). The model has no tool that confirms.

**Step 5. Test it** without a real platform: unit tests for the function, and a chat test that scripts the model's calls against [`tests/conversation/fake_moldesign.py`](../../tests/conversation/fake_moldesign.py). [`tests/server/test_compare_poses_chat.py`](../../tests/server/test_compare_poses_chat.py) is a model to copy.

**Step 6. Record it.** Add an entry to [`PROVENANCE.md`](../../PROVENANCE.md) (CI fails without one) and describe the tool in [`CREACION_DE_HERRAMIENTAS.md`](../../docs/CREACION_DE_HERRAMIENTAS.md). Then run [the checks](#5-checks-before-you-share-a-change).

## 3. Add a host action

A host action asks the platform window to do something the person can see, such as loading a molecule into the editor or pressing Evaluate. It needs three pieces.

1. **Sidecar.** Add a pending-request registry to `ServerState` ([`server/state.py`](../../src/molchat_agent/server/state.py); `case_status_requests` is a small example). Emit an SSE event carrying a fresh `request_id`. Add the route `POST /v1/<kind>-requests/{request_id}/result` in `server/app.py`, which accepts the answer only from the session that asked, only once, and only in its closed schema.
2. **UI.** Add a bridge in `ui/src/lib/<kind>Host.ts`, for example [`caseStatusHost.ts`](../../ui/src/lib/caseStatusHost.ts). It forwards a `molchat-host-message` with your `kind` to the parent window, accepts only `molchat-<kind>-result` from the trusted parent origin, and posts it to the sidecar.
3. **Platform.** Implement the action in the window. MolDesign's side is public: [`MolChatHostMount.tsx`](https://github.com/srcacahuate619/moldesign-app/blob/main/frontend/components/ai-host/MolChatHostMount.tsx).

Then add the action's row to [`HOST_CONTRACT.md`](../../docs/HOST_CONTRACT.md): fields, reply type and every status. Test the server schema (like [`tests/server/test_case_host_action.py`](../../tests/server/test_case_host_action.py)), the UI bridge (like `ui/src/lib/caseStatusHost.test.ts`) and the fake platform. A platform that knows it did nothing must answer `failed`; only what it can't know is `unknown`.

Three messages carry state with no reply: `molchat-ui-status` (one line for the minimized panel's bubble), `molchat-ui-progress` (the running plan, for the autopilot view) and `notify_download` (an entry in the platform's activity panel). [`HOST_CONTRACT.md`](../../docs/HOST_CONTRACT.md) gives their exact fields.

## 4. Build your own lock

There are two depths, and the honest limit comes first: the chat's tools and host actions are shaped by MolDesign today. A new lock either serves the same routes and actions or adds its own tools (section 2).

**Plans over HTTP, without the chat.** MolChat's plan executor works with any HTTP API you describe as capabilities. Declare them with `Capability` and `register` from [`tools/catalog.py`](../../src/molchat_agent/tools/catalog.py), as [`tools/reference.py`](../../src/molchat_agent/tools/reference.py) does, and check them with the conformance kit:

```sh
python examples/reference_backend/server.py
python -m conformance.runner --adapter generic --register molchat_agent.tools.reference \
  --cases examples/reference_backend/cases --live --base-url http://127.0.0.1:8099
```

The walkthrough, including what a PASS does and doesn't prove, is in [`ADAPTADORES.md`](../../docs/ADAPTADORES.md). There is no adapter selector in the CLI or the UI yet: you register your capabilities in your own process and give the executor a `MolDesignBridge` built with `require_contract=False`.

**The whole agent inside your app.**

1. **Launch** `python -m molchat_agent serve` with `MOLCHAT_HOST_SECRET` (the secret you sign sessions with) and `MOLDESIGN_BASE_URL` pointing at your API. Loopback is the default; a remote API needs HTTPS and `MOLDESIGN_ALLOW_REMOTE=1`. Wait for `GET /v1/health`.
2. **Sign sessions** per account in the `mh1` format and send each to the iframe with `molchat-host-session`. Use the sidecar's origin as the target, never `*`.
3. **Serve the routes** the tools call, starting with `GET /molchat-host/contract`. A tool whose route is missing answers `unavailable`; it doesn't make anything up.
4. **Implement the host actions** you want. The iteration plan needs `create_case`, `load_case_smiles`, `assign_case_receptor`, `evaluate_case` and `case_status`; `audit_case_preparation` and `molcy_render` are optional, and the notebook declares what's absent.
5. **Model keys.** The sidecar asks the platform for a key on each call (`POST /molchat-host/credencial`), for a provider host from the catalogue that the account authorized. Without a platform, `molchat-agent serve` runs standalone with `MOLCHAT_PROVIDER` ([`SIDECAR.md`](../../docs/SIDECAR.md)).

## 5. Checks before you share a change

```sh
python -m pytest -q
python -m conformance.runner
python scripts/check_provenance.py
python scripts/check_secrets.py
npm --prefix ui test
npm --prefix ui run build
python scripts/check_ui_build.py
```

CI runs these on Python 3.11 and 3.12 from a clean clone ([`ci.yml`](../../.github/workflows/ci.yml)). `check_secrets` also reads untracked files, so a test token or a local path left in your working folder fails it; run it in a clean clone before you push.

## 6. Ship your version inside MolDesign

MolDesign keeps a copy of the key in `tools/molchat/` and pins it in `backend/data/molchat_fijacion.json`: commit, repository, version and the SHA-256 of the manifest. Before launching, it checks every file against the manifest, the contract name and the pin, and it refuses to start a copy that doesn't match. MolDesign works without MolChat; the key is optional.

From a MolDesign checkout, with your MolChat commit's UI already built:

```powershell
.\python-embed\python.exe scripts\stage_molchat.py --fuente <your-molchat-clone> --write
.\python-embed\python.exe scripts\stage_molchat.py --check
```

Only committed code is staged. A fork is pinned with `oficial: false`, and MolDesign shows it as unofficial. To try a version without touching the pinned copy, stage it with `--destino` and set `MOLDESIGN_MOLCHAT_DIR` and `MOLCHAT_PERMITIR_EXTERNO=1` ([Getting started](GETTING_STARTED.md#use-a-newer-molchat)). The full rules for the copy and the pin are in [`LLAVE_Y_CERRADURA.md`](../../docs/LLAVE_Y_CERRADURA.md) and [`DESARROLLO_Y_VERSION_PROPIA.md`](../../docs/DESARROLLO_Y_VERSION_PROPIA.md).

**License.** MolChat is GPL-3.0-or-later. If you distribute a modified version, you must offer its source to those who receive it. MolDesign is under PolyForm Noncommercial; the two talk over HTTP and neither imports the other. This is engineering and provenance, not legal advice.
