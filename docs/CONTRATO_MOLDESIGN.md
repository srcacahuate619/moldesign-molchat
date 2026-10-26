# Contrato MolChat ↔ MolDesign (v1, `moldesign.molchat/1`)

Toda comunicación agente↔plataforma es HTTP con este contrato. El catálogo
vivo servido por la plataforma (CR-04) no existe aún: el catálogo es local
(`capabilities.py`) y esta suite lo valida contra un MolDesign instalado.

## Capacidades (6)

| Capacidad | Endpoint | Riesgo | Parámetros |
|---|---|---|---|
| `list_targets` | `GET /targets/` | read | — |
| `check_preflight` | `POST /evaluation/preflight` | read | `smiles` (≤2000), `target_pdb_id` (4–10), `chain?`, `docking_engine?` |
| `list_evaluations` | `GET /history/evaluations` | read | `page?`, `page_size?`, `target_pdb_id?` |
| `evaluation_status` | `GET /evaluation/status/{task_id}` | read | `task_id` |
| `get_docking_proposal` | `GET /ai/proposals/{proposal_id}` | read | `proposal_id` |
| `approve_docking_proposal` | `POST /ai/proposals/{proposal_id}/approve` | approval_required | `proposal_id`, `proposal_hash` (`sha256:` + 64 hex) |

Reglas: sin redirecciones; tope 5 MB por respuesta; loopback por defecto y
remoto solo HTTPS con `MOLDESIGN_ALLOW_REMOTE=1`. El servidor impone identidad
y revalida `proposal_hash` y estado antes de ejecutar. `check_preflight`
expone `technical_blockers` (lista), `warnings` y `not_evaluated`: con
bloqueantes, el ejecutor se detiene (`blocked`), nunca aprueba.

No es herramienta del modelo: `POST /evaluation/submit` (entrada directa).
Las propuestas se crean en el flujo de MolDesign y aquí solo se leen/aprueban.

## Suite de contrato (10 peticiones)

```bash
MOLDESIGN_BASE_URL=http://127.0.0.1:8000 MOLDESIGN_TOKEN=<cuenta-de-pruebas> \
  python -m pytest tests/contract/ -m contract -o addopts=""
```

Cuenta de pruebas: cuenta propia de MolDesign, sin datos privados; PDB/SMILES
públicos (`1HSG`, `CCO`, aspirina). La suite salta —no falla— sin backend o
sin token válido; una vez alcanzable, los fallos son veredictos reales.

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
