# Contrato MolChat ↔ MolDesign (v2, `moldesign.molchat/1`, Fase 3)

Toda comunicación agente↔plataforma es HTTP con este contrato. El catálogo
vivo servido por la plataforma (CR-04) no existe aún: el catálogo es local
(`tools/moldesign.py`, 23 capacidades) y la suite de contrato lo valida
contra un MolDesign instalado.

## Capacidades (23)

| Capacidad | Endpoint | Riesgo | Notas |
|---|---|---|---|
| `list_targets` | `GET /targets/` | read | — |
| `check_preflight` | `POST /evaluation/preflight` | read | `smiles`, `target_pdb_id`, `chain?`, `docking_engine?` |
| `list_evaluations` | `GET /history/evaluations` | read | `page?`, `page_size?`, `target_pdb_id?` |
| `evaluation_status` | `GET /evaluation/status/{task_id}` | read | `PENDING\|STARTED\|SUCCESS\|FAILURE\|RETRY` |
| `get_docking_proposal` | `GET /ai/proposals/{proposal_id}` | read | `{id, estado, expira_en_s, hash, resumen}` |
| `approve_docking_proposal` | `POST /ai/proposals/{proposal_id}/approve` | approval_required | Revalida hash+estado; devuelve `{task_id, …}` |
| `list_engines` | `GET /evaluation/engines` | read | Inventario de motores |
| `get_evaluation_result` | `GET /evaluation/result/{molecule_id}` | read | `molecule_id` UUID; `?task_id=` opcional (MP-05) |
| `get_interactions` | `GET /evaluation/interactions/{molecule_id}` | read | `pose_rank?` 1–20 |
| `get_gnn_attention` | `GET /evaluation/gnn-attention/{molecule_id}` | read | SVG on-demand; `?task_id=` opcional |
| `stream_evaluation` | `GET /evaluation/stream/{task_id}` | read | SSE; espera de progreso (el sondeo decide) |
| `cancel_evaluation` | `POST /evaluation/cancel` | write | `{"task_id"}`; terminal FAILURE tras cancelar |
| `batch_status` | `GET /evaluation/batch/{batch_id}` | read | `running\|cancelling\|completed\|cancelled` |
| `cancel_batch` | `POST /evaluation/batch/{batch_id}/cancel` | write | — |
| `export_batch` | `GET /evaluation/batch/{batch_id}/{export,csv}` | read | Binario (bytes); solo lote completado |
| `get_ai_report` | `POST /evaluation/ai-report/{molecule_id}` | read | POST verificado (genera+cachea); clase `inference` |
| `stream_ai_report` | `GET /evaluation/ai-report/{molecule_id}/stream` | read | SSE |
| `get_case_dossier` | `POST /dossier/{molecule_id}/{preview,package}` | read | Binario; proyección mínima generada |
| `get_sar` | `GET /sar/{molecule_id}` | read | `?task_id=` opcional |
| `get_history_stats` | `GET /history/stats` | read | Contadores propios |
| `save_molecule` | `POST /history/save/{molecule_id}` | write | `?name=`, `?task_id=` |
| `rescoring_health`, `rescoring_info`, `rescoring_ram` | `GET /rescoring/…` | read | Estado del servicio |

Reglas: sin redirecciones; tope 5 MB por respuesta; loopback por defecto y
remoto solo HTTPS con `MOLDESIGN_ALLOW_REMOTE=1`. El servidor impone identidad
y revalida `proposal_hash` y estado antes de ejecutar. `check_preflight`
expone `technical_blockers` (lista), `warnings` y `not_evaluated`: con
bloqueantes, el ejecutor se detiene (`blocked`), nunca aprueba.

No es herramienta del modelo: `POST /evaluation/submit` (entrada directa).
Las propuestas se crean en el flujo de MolDesign y aquí solo se leen/aprueban.

Excluidas con motivo (abstención por ausencia, no simulación):

- `create_docking_proposal`: crear propuestas es in-process
  (`propuestas_de_docking.proponer`, vía `run_docking` interno); no existe
  `POST /ai/proposals`. La creación HTTP de propuestas está propuesta como
  contrato adicional, pendiente de aceptación en la revisión interna.
- `start_batch`: `POST /evaluation/batch` exige multipart con fichero; el
  agente no tiene bytes de fichero legítimos en Fase 3. `batch_status`,
  `cancel_batch` y `export_batch` sí existen (por id).
- `dossier/preparacion`: endpoint en desarrollo (`readiness FEP`); solo
  `preview` (PDF) y `package` (ZIP).

## Peticiones de contrato a MolDesign (CR-01…CR-05, formales desde Fase 3)

| ID | Petición | Motivación | Estado |
|---|---|---|---|
| CR-01 | API versionada de propiedades/preparación (RDKit) con identidad impuesta por el servidor | Habilita Fase 5 sin duplicar RDKit en el agente | Pendiente |
| CR-02 | Creación y consulta de **casos** como recurso (hoy el caso vive como proyección del cliente) | «Crear casos» desde MolChat exige un recurso direccionable | Pendiente |
| CR-03 | Endpoint de eventos (SSE/WebSocket) de cambio de estado de evaluaciones y trabajos de Molcy | Jobs sin polling ciego; el polling es el fallback implementado | Pendiente |
| CR-04 | Handshake de agente: versión de contrato + catálogo de capacidades servido por la plataforma | Evita catálogos duplicados que divergen | Pendiente |
| CR-05 | Superficie versionada de análogos/ADMET/MolGraph | Fase 5 completa | Pendiente |

Cada CR, cuando MolDesign la implemente, entra como capacidad con sus tests
de contrato. Hasta entonces la capacidad **no existe**: el agente se abstiene.

## Suite de contrato (27 peticiones)

```bash
MOLDESIGN_BASE_URL=http://127.0.0.1:8000 MOLDESIGN_TOKEN=<cuenta-de-pruebas> \
  python -m pytest tests/contract/ -m contract -o addopts=""
```

Cuenta de pruebas: cuenta propia de MolDesign, sin datos privados; PDB/SMILES
públicos (`1HSG`, `CCO`, aspirina). La suite salta —no falla— sin backend o
sin token válido; una vez alcanzable, los fallos son veredictos reales.
`MOLCHAT_CONTRACT_MOLECULE_ID` (UUID con resultado) habilita los positivos
por molécula; sin él esos casos saltan.

| # | Petición | Esperado |
|---|---|---|
| 1 | `list_targets` | Colección JSON |
| 2 | `check_preflight` CCO/1HSG | `technical_blockers` como lista |
| 3 | `check_preflight` aspirina/1HSG | Idem |
| 4 | `check_preflight` con SMILES inválido | `BridgeError` o bloqueantes (nunca pase silencioso; endurecer tras la primera corrida en vivo) |
| 5–7 | `list_evaluations` (+ paginación, + filtro `target_pdb_id`) | Colección JSON |
| 8 | `evaluation_status` de tarea inexistente | `BridgeError` |
| 9 | `get_docking_proposal` inexistente | `BridgeError` |
| 10 | `approve_docking_proposal` inexistente | `BridgeError` (el servidor revalida) |
| 11–13 | `list_engines`, `get_history_stats`, rescoring ×3 | Formas documentadas |
| 14–20 | Lecturas con UUID inexistente (result, interactions, gnn, sar, ai-report ×2, dossier) | `BridgeError` (stream vacío también vale) |
| 21 | Batch inexistente (status/cancel/export) | `BridgeError` |
| 22 | `cancel_evaluation` inexistente | `BridgeError` o negativo limpio |
| 23 | `save_molecule` inexistente | `BridgeError` (sin escrituras) |
| 24 | `stream_evaluation` inexistente | `BridgeError` o lista de eventos |
| 25–27 | Positivos por molécula (con `MOLCHAT_CONTRACT_MOLECULE_ID`) | Dict o 404 limpio; dossier bytes o 404 |

## Paridad de planificadores (puerta de la Fase 1)

El mismo objetivo produce planes válidos de solo lectura con `fake`, un
proveedor local y Meta: `tests/providers/test_parity.py` (mocks). La
confirmación en vivo (llama-server corriendo + Meta con clave y
consentimiento) es un paso manual pre-release:

```bash
molchat-agent doctor --grant-consent meta@api.meta.ai
molchat-agent plan --provider fake "¿Qué receptores tengo?" --out plan.json
molchat-agent plan "¿Qué receptores tengo?" --out plan.json  # Meta (activo)
```

## Registro de corridas en vivo

| Fecha | Commit MolChat | Backend MolDesign | Resultado |
|---|---|---|---|---|
| 2026-10-26 | cierre de Fase 1 (supervisor) | Instancia de escritorio en `127.0.0.1:18017` (app 1.0.4, modo DESKTOP, worktree `video-prep`; no el commit de referencia `66ff5243`) | **Contrato 10/10** con cuenta de pruebas registrada para la ocasión. Paridad en vivo: Meta (`muse-spark-1.3`, consentimiento otorgado) produjo el plan válido esperado de 1 paso; llama-server local con **Bonsai-8B-Q1_0** produjo un plan formalmente válido (con sobre-alcance semántico: pasos e identificadores inventados que la Fase 2 debe medir); Qwen2.5-1.5B fue **rechazado** por el validador en 3/3 intentos (argumentos fuera de contrato e ID inventados: la abstención correcta). Primera corrida sin sesión: 4/10 con fallos de arnés (pool de conexiones entre loops) y 401 en historial; corregido el arnés, 10/10 |
