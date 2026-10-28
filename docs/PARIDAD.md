# Matriz de paridad — MolChat nuevo vs interno (final al corte, Fase 6.6)

> Registro del corte: la integración local posterior añade propiedades por
> contrato con MolDesign. Las demás filas y su evidencia conservan el estado
> medido en ese corte; no certifican el instalador ni la paridad completa.

Fuente: `backend/services/ai/tools/*.py` (27 herramientas) + respondedores.
Estados: **hecho** (en este repo, con tests), **puente** (vía contrato/bridge
existente), **ausente (CR-XX)** (final: sin superficie en plataforma, el
agente se abstiene y lo dice; reaparece como capacidad cuando la CR exista),
**descartado** (justificado).

## Herramientas (27)

| Herramienta interna | Estado | Dónde / nota |
|---|---|---|
| `compute_properties` | puente local `properties/1` | MolDesign valida y calcula; si el contrato está ausente, el agente se abstiene. La parte de preparación de CR-01 sigue pendiente. |
| `validate_smiles` | hecho (heurística + servidor) | `intents.smiles_plausible` (estructural); validez química real en preflight |
| `check_druglikeness` | hecho (reglas+registrado) | `deterministic.build_druglikeness_response`; PAINS sin registro → abstención |
| `compare_molecules` | hecho | `deterministic.build_compare_response` (+ N-vías) sobre valores tipados |
| `rank_session_molecules` | hecho | Del agente: `build_rank_response` sobre memoria de sesión |
| `query_history` | hecho (sesión + plataforma) | Historial de sesión + `list_evaluations` persistido |
| `query_evaluation_details` | puente | `get_evaluation_result` + historial |
| `run_docking` | puente | Crear→aprobar→trabajo con CR-07/CR-06 y aprobación humana |
| `check_docking_status` | puente | `evaluation_status` + seguimiento de jobs |
| `get_rescoring` | puente | Capacidades `rescoring_*` |
| `check_preparation` | puente | Intento `preparation`; informe vía `check_preflight` |
| `generate_analogs` | ausente (CR-05) | Sin superficie; el agente se abstiene y lo dice |
| `explain_fragments` | ausente (CR-05) | Con análogos |
| `suggest_smiles` | ausente (CR-05) | Intento `suggest` existe (3 modos); sin API no hay capacidad |
| `predict_admet` | ausente (CR-05) | Necesita API de plataforma |
| `molgraph_*` (7) | ausente (CR-05) | Intento `molgraph` existe; decisión D-04 (plataforma) |
| `pubchem_lookup`, `pubchem_description`, `chembl_activity`, `search_pdb`, `search_similar`, `query_verified_source` | ausente (D-04) | Intento `source` existe; sin camino web por decisión (plataforma o nada) |

## Respondedores y turno

| Pieza interna | Estado |
|---|---|
| `intent_classifier.py` | hecho: `conversation/intents.py` (mismo orden de reglas + 3 fixes) |
| `deterministic_responder.py` (rank/compare) | hecho tipado + fixes de dirección |
| `deterministic_responder.py` (props/history) | hecho |
| `conversation_state.py` | hecho: `memory.Conversation` + compresión |
| `memory_store.py` | hecho parcial: conversaciones + moléculas + búsqueda LIKE por dueño; sin embeddings/FTS |
| `chat_service.py` (turno) | hecho parcial: `engine.py` (determinista + conceptual verificado); sin tool-loop del modelo |
| Bloque de evidencia | hecho: mismo marcador `FIN_DE_EVIDENCIA`, clase+fuente por bloque |
| Verificación numérica (guard) | hecho: `evidence.verify_numbers` + retención con nota |

## Inventario 2.1: veredictos pendientes

| Fichero | Veredicto |
|---|---|
| `interpreter.py` | **Plataforma (reubicado, Fase 6.6)**: narrativa IA de reportes vive en `services/evaluation/`; el patrón ("la IA transforma resultados verificados, no calcula") además vive como regla en `evidence.py`/`prompts.py` |
| `limbic_system.py` | **Descartado**: gamificación de personalidad (XP/mood) sin valor científico ni necesidad demostrada |
| `red.py` | **Plataforma (reubicado, Fase 6.6)**: puerta de red + identidad en `services/red.py`; el concepto vive además en `providers/registry.py` |

## Fixes deliberados vs el original (con prueba)

1. `suggest` no roba "dame las propiedades de X" (interno: B03→suggest).
2. "qué son" es conceptual (interno: K03→invalid_smiles).
3. "y la X?" es anáfora (interno: A02→chemical; mismo desenlace, mejor ruta).
4. "mejor/peor afinidad" por calidad, no por valor (interno responde al revés).
5. Default MW solo con comparativos mayor/menor (interno: "mas puentes"→MW).
6. Valores tipados en vez de parsear texto de tools (adiós inversión nombre↔valor).
7. Verificación numérica cita ordinales y eco de consulta (F2-C1/C3: el Qwen
   local cita "12345" y enumera "1." — ni cita ni viñeta son fabricación).

## Gate adversarial: 18 → 16

Portadas las 4 frentes. No aplica `test_la_configuracion_de_proveedor_no_cruza_cuentas`
(sidecar monousuario: el fichero de consentimientos no tiene dimensión de
cuenta) ni el sondeo PubChem offline (sin camino web en Fase 2); ambas se
revisan al llegar multi-cuenta (no planeado) y Fase 5 respectivamente.
