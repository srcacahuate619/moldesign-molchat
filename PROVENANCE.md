# Procedencia — MolChat Agent

Ledger de porte desde MolDesign (PLAN §21). Ningún fichero entra desde
MolDesign sin una entrada aquí. Formato obligatorio por pieza portada: origen
exacto, commit fijado, autoría, transformación, licencia resultante y tests.

Commit de referencia de MolDesign fijado en la Fase 0:
`66ff524334267c56558b7a3cce94cb919edbad2e`, rama `codex/release-hygiene`,
verificado el 2026-10-26 en el árbol local de MolDesign (solo lectura).
Asunto del commit: `FEP-06-HUM: contacto para inscribirse y entregar`.
El árbol de MolDesign tenía cambios sin commitear al fijarlo (2 modificados,
1 sin seguimiento); la referencia es el commit, no el árbol de trabajo.

Nota de higiene: los orígenes futuros se escriben en forma repo-relativa
(`backend/services/ai/...` más el commit), sin letra de unidad, para que este
fichero —que sí se publica— nunca contenga rutas de máquina. La única
excepción tolerada por `scripts/check_secrets.py` son líneas `- Origen:` que
citen una ruta exacta exigida por una auditoría.

Titularidad: Johan Amezcua es el único titular del código de MolDesign
(historial de un solo autor, `CONTRIBUTORS.md` con el conjunto pre-CLA vacío),
por lo que puede relicenciar su código bajo GPL-3.0-or-later. Cada entrada de
porte futuro lo dejará constado.

Esto es ingeniería de procedencia, no asesoría jurídica.

## Entradas retroactivas del kit inicial (Fase 0)

Todo el kit inicial es **código nuevo**, sin porte desde MolDesign: ningún
módulo se copió de `backend/services/ai/`, de Molcy ni de ningún otro proyecto.
La auditoría de extracción (`docs/AUDITORIA.md`) documenta que la relación con
MolDesign es por API HTTP, no por copia de código.

### LICENSE

- Origen: texto estándar copiado sin cambios del `LICENSE` publicado en
  `https://github.com/srcacahuate619/moldesign-molcy` (verificado byte a byte,
  SHA-256 `8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903`)
- Commit de MolDesign: N/A (no procede de MolDesign)
- Autoría: Free Software Foundation (texto de la licencia); la decisión de
  aplicarla a este repo es de Johan Amezcua
- Transformación: ninguna (copia literal del texto estándar)
- Licencia resultante: GPL-3.0-or-later
- Tests: `scripts/check_provenance.py` (existencia y coherencia del ledger)

### src/molchat_agent/__init__.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (versión `0.1.0` del paquete)
- Licencia resultante: GPL-3.0-or-later
- Tests: suite general (`python -m pytest -q`)

### src/molchat_agent/bridge.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign;
  `docs/AUDITORIA.md` lo distingue del runtime de MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (cliente HTTP con guarda loopback/HTTPS)
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/test_bridge.py

### src/molchat_agent/capabilities.py

- Origen: código nuevo en este repositorio (contrato inspirado en
  `backend/services/ai/tool_registry.py`, sin copiarlo)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (allowlist de 6 herramientas HTTP)
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/test_capabilities.py

### src/molchat_agent/cli.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (CLI `plan → inspect → execute`)
- Licencia resultante: GPL-3.0-or-later
- Tests: ejecución manual de la CLI; cobertura vía tests de plan/executor

### src/molchat_agent/executor.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign;
  el servidor sigue siendo dueño de las propuestas, `propuestas_de_docking.py`
  se conserva en MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (aprobación por hash, freno por preflight)
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/test_executor.py

### src/molchat_agent/meta.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (planificador Muse Spark, solo lectura)
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/test_meta.py

### src/molchat_agent/plan.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (plan inmutable esquema /1, digest SHA-256)
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/test_executor.py (huella y aprobación)

### tests/test_bridge.py, tests/test_capabilities.py, tests/test_executor.py, tests/test_meta.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (29 tests, dobles HTTP, sin integración real)
- Licencia resultante: GPL-3.0-or-later
- Tests: son los tests (`python -m pytest -q`)

### docs/AUDITORIA.md, docs/HOJA_DE_RUTA.md, README.md, pyproject.toml, NOTICE.md, .gitignore

- Origen: documentos y metadatos nuevos de este repositorio (sin porte)
- Commit de MolDesign: N/A (las referencias a MolDesign son por URL pública
  y rutas de solo lectura, no copias de código)
- Autoría: Johan Amezcua
- Transformación: documentos nuevos; en Fase 0 la licencia declarada cambia
  de `GPL-3.0-only` a `GPL-3.0-or-later`
- Licencia resultante: GPL-3.0-or-later
- Tests: `scripts/check_provenance.py`, `scripts/check_secrets.py`

### tests/test_check_scripts.py

- Origen: código nuevo en este repositorio (pruebas de los checkers de la
  Fase 0, añadidas por el supervisor en la revisión de cierre de la fase)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (las sondas negativas de supervisión como
  tests permanentes de `scripts/check_secrets.py` y `check_provenance.py`)
- Licencia resultante: GPL-3.0-or-later
- Tests: es el test (`python -m pytest tests/test_check_scripts.py`)

### scripts/check_provenance.py, scripts/check_secrets.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (puertas de salida de la Fase 0)
- Licencia resultante: GPL-3.0-or-later
- Tests: se verifican a sí mismos en verde sobre el árbol actual
  (`python scripts/check_provenance.py`, `python scripts/check_secrets.py`)

## Entradas de la Fase 1 (fundación verificada e híbrido real)

### src/molchat_agent/config.py, tests/test_config.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tarea 1.6: configuración centralizada por
  entorno; sustituye el acceso disperso a `os.getenv` en `bridge.py` y `meta.py`)
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/test_config.py

### src/molchat_agent/providers/base.py, src/molchat_agent/providers/fake.py, src/molchat_agent/providers/__init__.py, tests/providers/test_port.py

- Origen: código nuevo en este repositorio; diseño del puerto inspirado en
  `backend/services/ai/providers/base.py` (commit de referencia) sin copiar código
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: reimplementado (tareas 1.2/1.3 parciales: puerto
  `LLMProvider`, estados de salud con `no_consent`, catálogo de solo lectura,
  proveedor determinista `fake`); sin acoplamiento a cuentas ni a MolDesign
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/providers/test_port.py

### src/molchat_agent/providers/registry.py, tests/providers/test_registry.py

- Origen: código nuevo en este repositorio; diseño del registro inspirado en
  `backend/services/ai/providers/registry.py` (commit de referencia) sin copiar código
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: reimplementado (tarea 1.2: registro con perfiles
  `hackathon`/`default`; sin persistencia por usuario, que vive en
  `config.py` y en el almacén de consentimientos)
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/providers/test_registry.py

### src/molchat_agent/providers/meta.py, src/molchat_agent/meta.py, tests/providers/test_meta_policy.py

- Origen: `src/molchat_agent/meta.py` de este repositorio (código nuevo del kit
  inicial, sin porte desde MolDesign); movido a `providers/meta.py`
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: movido al puerto `LLMProvider` (tareas 1.2/1.8) con
  `reasoning_effort` configurable (default `medium`), modelo Standard fijado y
  veto al nivel `contributor`; `meta.py` queda como shim una versión
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/test_meta.py (vía shim), tests/providers/test_meta_policy.py

### src/molchat_agent/providers/openai_compatible.py, tests/providers/test_openai_compatible.py

- Origen: código nuevo en este repositorio; diseño inspirado en
  `backend/services/ai/providers/openai_provider.py` (commit de referencia)
  sin copiar código
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: reimplementado (tarea 1.3): sin defaults de terceros,
  remoto exige HTTPS, localidad calculada desde la URL; `meta.py` reutiliza
  el nuevo `readonly_plan_schema` de `base.py`
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/providers/test_openai_compatible.py

### src/molchat_agent/providers/local_http.py, tests/providers/test_local_http.py

- Origen: código nuevo en este repositorio; diseño inspirado en
  `backend/services/ai/local_llm.py` y
  `backend/services/ai/providers/local_llm_provider.py` (commit de referencia)
  sin copiar código
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: reimplementado (tarea 1.3): proveedores `llama-server`
  (sobre `/v1`) y `ollama` (API nativa `/api/chat` + `/api/tags` con
  validación de modelo instalado) loopback-only; sin gestión del proceso
  servidor (Fase 5)
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/providers/test_local_http.py, tests/providers/test_ollama.py,
  tests/providers/test_parity.py

### tests/providers/test_ollama.py, tests/providers/test_parity.py

- Origen: código nuevo en este repositorio; diseño de Ollama inspirado en
  `backend/services/ai/providers/ollama_provider.py` (commit de referencia)
  sin copiar código
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: código nuevo (tarea 1.3): tests del proveedor `ollama` y
  prueba de paridad fake/local/Meta sobre el mismo objetivo
- Licencia resultante: GPL-3.0-or-later
- Tests: son los tests

### tests/providers/test_consent.py

- Origen: código nuevo en este repositorio; diseño del gate inspirado en
  `backend/services/ai/consent.py` (commit de referencia) sin copiar código
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: reimplementado (tarea 1.4): destino `proveedor@host`
  calculado, desconocido→remoto, revocación por proveedor, offline manda,
  `status()` sin sondear sin consentimiento; el CLI `plan` rutea por registro
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/providers/test_consent.py

### tests/test_doctor.py

- Origen: código nuevo en este repositorio; espíritu de
  `backend/services/ai/startup_detection.py` (commit de referencia)
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: código nuevo (tarea 1.5): `molchat-agent doctor` con
  `--consents`, `--grant-consent` y `--revoke`; transportes httpx perezosos y
  sondeos concurrentes
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/test_doctor.py

### tests/contract/test_live_moldesign.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tarea 1.1): suite de contrato en vivo, 10
  peticiones sobre las 6 capacidades, `@pytest.mark.contract`, excluida por
  defecto vía `addopts`; salta sin fallar sin backend/token
- Licencia resultante: GPL-3.0-or-later
- Tests: son los tests (manuales, pre-release)

### docs/ARQUITECTURA.md, docs/CONTRATO_MOLDESIGN.md

- Origen: documentos nuevos de este repositorio (sin porte)
- Commit de MolDesign: N/A (las referencias internas son por ruta de solo
  lectura con el commit fijado, no copias)
- Autoría: Johan Amezcua
- Transformación: documentos nuevos (tarea 1.7): arquitectura del puerto de
  proveedores y contrato `moldesign.molchat/1` con guía de la suite en vivo
- Licencia resultante: GPL-3.0-or-later
- Tests: N/A (documentación; la suite que describen es tests/contract/)

## Entradas de la Fase 2 (conversación determinista)

### scripts/record_fixtures.py, tests/quality/fixtures/properties.json

- Origen: código nuevo; valores computados con `services/ai/tools/rdkit_tools.py`
  (commit de referencia), no copiados de memoria
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: código nuevo (tarea 2.7, base): grabador reproducible
  (backend por argv, sin rutas de máquina) + 8 moléculas con descriptores RDKit
  reales y veredictos Lipinski/Veber/PAINS
- Licencia resultante: GPL-3.0-or-later
- Tests: validación de parseo en la propia grabación (falla si falta un campo)

### src/molchat_agent/conversation/intents.py, src/molchat_agent/conversation/__init__.py, tests/conversation/test_intents.py

- Origen: código nuevo en este repositorio; reglas reimplementadas desde
  `backend/services/ai/intent_classifier.py` (commit de referencia) sin copiar
  código; tabla mínima de 8 moléculas verificada contra `known_molecules.py`
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: reimplementado (tarea 2.2) con 3 fixes documentados vs el
  original (suggest no roba "dame las propiedades de X", "qué son" es
  conceptual, "y la X?" es anáfora); validación SMILES estructural sin RDKit
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/conversation/test_intents.py (consultas quality + regresiones)

### src/molchat_agent/conversation/deterministic.py, tests/conversation/test_deterministic.py

- Origen: código nuevo en este repositorio; semántica reimplementada desde
  `backend/services/ai/deterministic_responder.py` (commit de referencia) sin copiar código
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: reimplementado (tarea 2.3): ranking, comparación,
  propiedades, historial de sesión y drug-likeness con entradas tipadas en
  vez de parsear texto de tools; fixes vs original ("mejor/peor afinidad"
  por calidad, default MW solo con comparativos); tests de inversión
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/conversation/test_deterministic.py

### src/molchat_agent/conversation/evidence.py, src/molchat_agent/conversation/prompts.py, tests/conversation/test_evidence.py

- Origen: código nuevo en este repositorio; diseño reimplementado desde
  `backend/services/ai/tool_registry.py` (clases epistémicas, `FIN_DE_EVIDENCIA`)
  y la verificación numérica del guard (commit de referencia), sin copiar código
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: código nuevo (tarea 2.4): bloques de evidencia con clase y
  fuente, abstención sin números, verificación numérica contra valores
  verificados, prompts versionados sin datos de usuario
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/conversation/test_evidence.py

### src/molchat_agent/conversation/memory.py, tests/conversation/test_memory.py

- Origen: código nuevo en este repositorio; diseño reimplementado desde
  `backend/services/ai/memory_store.py` y `conversation_state.py` (commit de
  referencia) sin copiar código
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: reimplementado (tarea 2.5): conversaciones + moléculas de
  sesión por propietario, fallos de persistencia ruidosos, búsqueda LIKE por
  dueño, compresión determinista; sin embeddings ni FTS (cuando una tool los pida)
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/conversation/test_memory.py (incluye aislamiento Alice/Mallory)

### tests/providers/test_chat.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tarea 2.6, base): `chat()` no-streaming en
  los 5 proveedores para el camino conceptual verificado; `fake` responde
  texto canned sin dígitos
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/providers/test_chat.py

### src/molchat_agent/conversation/engine.py, src/molchat_agent/conversation/tools.py, tests/conversation/test_engine.py, tests/conversation/test_engine_llm.py

- Origen: código nuevo en este repositorio; flujo reimplementado desde el
  patrón v3 de `docs/34_MOLCHAT_V3.md` y la descomposición de `chat_service.py`
  (commit de referencia), sin copiar el monolito
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: código nuevo (tarea 2.6): turno clasifica→herramienta→
  determinista | LLM verificado, con backend tipado, evidencia por turno,
  consentimiento antes de chat remoto, abstención sin números y streaming
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/conversation/test_engine.py, tests/conversation/test_engine_llm.py

### tests/quality/runner.py, tests/quality/test_quality.py, tests/quality/cases.json, tests/quality/__init__.py

- Origen: consultas verbatim de `backend/quality_suite.py` (commit de
  referencia); runner y validadores reimplementados, no copiados
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: portados (tarea 2.7): 43 casos a JSON + runner con
  validadores sobre fixtures tipados (coherencia por construcción);
  pata local vía `MOLCHAT_QUALITY_PROVIDER`; gate de latencia 300 ms
- Licencia resultante: GPL-3.0-or-later
- Tests: son los tests (43/43 con `fake` al cierre)

### tests/adversarial/test_gate.py, tests/adversarial/__init__.py

- Origen: casos adaptados de `backend/tests/test_gate_molchat_adversarial.py`
  (commit de referencia); tests reescritos contra el motor nuevo
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: portados (tarea 2.7): 16 pruebas en 4 frentes (inyección,
  fuga, tool-calls inválidos, alucinación); config por-cuenta no aplica
  (sidecar monousuario) y se documenta en `docs/PARIDAD.md`
- Licencia resultante: GPL-3.0-or-later
- Tests: son los tests

### scripts/ab_reasoning.py, docs/PARIDAD.md, docs/SEGURIDAD.md

- Origen: código y documentos nuevos (sin porte); matriz levantada sobre
  `backend/services/ai/tools/*.py` y `docs/34_MOLCHAT_V3.md`, `docs/67_GATE_MOLCHAT.md`
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: nuevo (tareas 2.1/2.8/2.9): matriz de paridad viva con
  veredictos de inventario, modelo de amenazas, corredor A/B por el gate
  de consentimiento (ejecución pendiente de clave Meta)
- Licencia resultante: GPL-3.0-or-later
- Tests: N/A (docs + script manual; el A/B exige API real)

### tests/conversation/test_engine_failures.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (corrección F2-C1 del supervisor): regresión
  de los 4 `_abstain` doblemente envueltos en `engine.py`; cada camino de
  fallo devuelve `str`; voseo a neutro (F2-C2); robustez ante proveedor
  deshabilitado en el camino conceptual
- Licencia resultante: GPL-3.0-or-later
- Tests: son los tests

### tests/quality/small_model_goals.json, scripts/measure_small_models.py, docs/MEDICION_MODELOS_PEQUENOS.md

- Origen: código y documentos nuevos (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (corrección F2-C5 del supervisor): medición
  formal de modelos pequeños (métrica "válido y sin inventados y sin pasos
  extra", 4 objetivos, corredor reproducible, resultados Qwen 0/4 y Bonsai
  0/4 con llama-server CUDA local)
- Licencia resultante: GPL-3.0-or-later
- Tests: N/A (medición manual con servidor local; ver documento)
