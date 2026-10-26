# Matriz de paridad — MolChat nuevo vs interno (viva, Fase 2)

Fuente: `backend/services/ai/tools/*.py` (27 herramientas) + respondedores.
Estados: **hecho** (en este repo, con tests), **puente** (vía contrato/bridge
existente), **fase N** (planificado), **descartado** (justificado).

## Herramientas (27)

| Herramienta interna | Estado | Dónde / nota |
|---|---|---|
| `compute_properties` | hecho (fixtures) → fase 5 (API) | `conversation/tools.py` + fixtures RDKit reales; vía API de plataforma con CR-01 |
| `validate_smiles` | hecho (heurística) → fase 5 (API) | `intents.smiles_plausible` (estructural); validez química real, servidor |
| `check_druglikeness` | hecho (reglas+registrado) | `deterministic.build_druglikeness_response`; PAINS sin registro → abstención |
| `compare_molecules` | hecho | `deterministic.build_compare_response` (+ N-vías) sobre valores tipados |
| `rank_session_molecules` | hecho | Del agente: `build_rank_response` sobre memoria de sesión |
| `query_history` | hecho (sesión) → fase 3 (persistido) | Historial de sesión; persistido declarado no conectado |
| `query_evaluation_details` | fase 3 | Intento `evaluation` existe; detalles vía capacidades de informes |
| `run_docking` | fase 3 | Intento `docking` existe; propuestas con aprobación humana |
| `check_docking_status` | fase 3 | Vía `evaluation_status` |
| `get_rescoring` | fase 3 | Vía capacidades de rescoring |
| `check_preparation` | fase 3 | Intento `preparation` existe; informe vía `check_preflight` |
| `generate_analogs` | fase 5 | Intento `analog`/`suggest` existe; necesita CR-01/CR-05 |
| `explain_fragments` | fase 5 | Con análogos |
| `suggest_smiles` | fase 5 | Intento `suggest` existe (3 modos); necesita API |
| `predict_admet` | fase 5 | Necesita API de plataforma |
| `molgraph_*` (7) | fase 5 | Intento `molgraph` existe; decisión D-04 |
| `pubchem_lookup`, `pubchem_description`, `chembl_activity`, `search_pdb`, `search_similar`, `query_verified_source` | fase 5 | Intento `source` existe; consentimiento web + D-04 |

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
| `interpreter.py` | **Descartado como módulo**: narrativa IA de reportes; el patrón ("la IA transforma resultados verificados, no calcula") vive como regla en `evidence.py`/`prompts.py` |
| `limbic_system.py` | **Descartado**: gamificación de personalidad (XP/mood) sin valor científico ni necesidad demostrada |
| `red.py` | **Concepto portado, catálogo diferido**: huella `servicio@host` + offline ya viven en `providers/registry.py`; el catálogo web (PubChem/ChEMBL/RCSB) se decide en Fase 5 (D-04) |

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
