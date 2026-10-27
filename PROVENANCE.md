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

### docs/AB_REASONING.md, docs/ab_reasoning_20261026.json

- Origen: medición nueva con Muse Spark 1.3 Standard (clave temporal del
  propietario, solo para este experimento; ningún dato privado enviado)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: informe (tarea 2.9): A/B medium/high/xhigh sobre 30 metas,
  90/90 válidos, latencia monótona; default `medium` se mantiene con evidencia
- Licencia resultante: GPL-3.0-or-later
- Tests: N/A (informe de medición; corredor en scripts/ab_reasoning.py)

### src/molchat_agent/providers/registry.py, src/molchat_agent/plan.py, src/molchat_agent/providers/base.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: correcciones Enmienda 2026-10-26-B del supervisor:
  F2-C6 consentimiento de contenido (`huella+history`, chat remoto sin
  historial hasta otorgarlo), F2-C7 copia profunda en Plan (cierra la
  ventana de mutación durante `await`), F2-C8 `plan_from_content` valida
  contra el catálogo exacto enviado al proveedor
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/providers/test_consent.py, tests/test_executor.py,
  tests/providers/test_port.py (+ engine/doctor/chat)

## Entradas de la Fase 3 (orquestación real)

### src/molchat_agent/tools/catalog.py, src/molchat_agent/tools/moldesign.py, src/molchat_agent/tools/__init__.py, src/molchat_agent/capabilities.py, tests/tools/__init__.py, tests/tools/test_catalog.py, tests/tools/test_moldesign.py

- Origen: código nuevo en este repositorio; endpoints verificados uno por uno
  en `backend/api/routers/` (commit de referencia), sin copiar código
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: código nuevo (tarea 3.1): registro de capacidades con
  riesgo/clase epistémica/procedencia/salidas, 23 capacidades MolDesign
  verificadas, puente con query/body/bytes/SSE; `capabilities.py` queda
  como shim; `create_docking_proposal` y `start_batch` excluidos con motivo
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/tools/test_catalog.py, tests/tools/test_moldesign.py,
  tests/test_bridge.py (bytes/SSE/query-POST)

### tests/test_plan.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tarea 3.2): esquema /2 con bindings
  `{"$from": "sN.ruta"}` (forma, orden, cabeza declarada), resolución
  tipada en runtime, digest sobre la forma sin resolver, /1 intacto
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/test_plan.py

### src/molchat_agent/orchestration/store.py, src/molchat_agent/orchestration/budget.py, src/molchat_agent/orchestration/__init__.py, tests/orchestration/__init__.py, tests/orchestration/test_store.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tareas 3.3/3.5): estados persistentes con
  transiciones auditadas, outcomes y jobs reanudables, presupuestos que
  bloquean con motivo en vez de excepciones crudas
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/orchestration/test_store.py

### src/molchat_agent/orchestration/jobs.py, tests/orchestration/test_jobs.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tarea 3.4): seguimiento de evaluaciones
  (SUCCESS/FAILURE) y lotes (completed/cancelled) con backoff 2s→30s,
  una ventana SSE como espera (polling como veredicto), cancelación
  explícita y reanudación sobre la misma fila
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/orchestration/test_jobs.py

### src/molchat_agent/executor.py, tests/test_executor.py

- Origen: evolución de `executor.py` del kit inicial (código nuevo Fase 0)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tareas 3.2–3.5): resolución de bindings
  con tipado en runtime, seguimiento de jobs en pasos write, store/budget
  por inyección, bytes en reportes, `resume()` sin re-ejecución; sin
  store/jobs el comportamiento previo se conserva intacto
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/test_executor.py

### tests/contract/conftest.py, tests/contract/test_live_fase3.py, scripts/demo_fase3.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tareas 3.6/3.7 base): fixture de contrato
  compartida con sonda autenticada, 17 casos Fase 3 (errores seguros +
  positivos con id), script de demo operada A/B/C/D con SKIPs honestos
- Licencia resultante: GPL-3.0-or-later
- Tests: son los tests (manuales con backend real)

### src/molchat_agent/bridge.py, src/molchat_agent/orchestration/store.py, docs/CONTRATO_MOLDESIGN.md

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tareas 3.8/3.9, MP-04/MP-05 adoptados):
  `BridgeTransportError` distinto de error-respuesta, cabecera
  `X-Idempotency-Key`, tabla de claves con claim atómico, estado
  `ambiguous` sin reenvío, reporte con decisión humana enlazada,
  CR-06/CR-07 registradas
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/test_executor.py, tests/test_bridge.py,
  tests/orchestration/test_store.py

### src/molchat_agent/server/auth.py, src/molchat_agent/server/__init__.py, tests/server/__init__.py, tests/server/test_auth.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tarea 4.1, MP-06): sesiones de host firmadas
  HMAC con permisos, audiencia y caducidad verificables; sin secreto no se
  acuña ni se verifica nada
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/server/test_auth.py

### src/molchat_agent/server/app.py, src/molchat_agent/server/events.py, src/molchat_agent/server/state.py, tests/server/test_app.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tarea 4.1): API del sidecar (salud, catálogo,
  conversaciones, chat SSE) con guard ASGI de Host/Origen, sesiones por
  llamada y proceso monousuario ligado a la cuenta
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/server/test_app.py

### src/molchat_agent/server/executions.py, tests/server/test_executions.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tarea 4.1): propuesta de planes por proveedor
  y ejecuciones en segundo plano con snapshots SSE; la cancelación cancela
  los trabajos remotos y marca `cancelling` hasta que el runner aterriza
  `cancelled` con su reporte final
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/server/test_executions.py

### src/molchat_agent/voice/stt.py, src/molchat_agent/voice/moldesign_whisper.py, src/molchat_agent/voice/__init__.py, tests/voice/__init__.py, tests/voice/test_whisper.py, tests/server/test_transcribe.py

- Origen: `transcribe_local` migrado desde `bridge.py` (código nuevo Fase 0);
  puerto y endpoint nuevos en este repositorio
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tarea 4.3): puerto `SpeechToText`, backend
  Whisper local de MolDesign, `POST /v1/transcribe` con permiso `transcribe`
  y topes; devuelve texto para confirmar, nunca ejecuta
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/voice/test_whisper.py, tests/server/test_transcribe.py

### src/molchat_agent/voice/local_whisper.py, tests/voice/test_local_whisper.py

- Origen: código nuevo en este repositorio (completado por el supervisor al
  cerrar la Fase 4: la instancia de revisión respondía 501 sin
  faster-whisper en la plataforma)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo: STT local con faster-whisper (puerto
  `SpeechToText`, §12 «STT propio opcional») y `ChainSTT` — plataforma
  primero, local de respaldo; `serve` lo cablea tras el backend de MolDesign
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/voice/test_local_whisper.py

### src/molchat_agent/server/serve.py, tests/server/test_serve.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tarea 4.4): cableado standalone
  (config→registry→memoria→bridge→ejecuciones→STT), bind solo-loopback
  verificado, token standalone acuñado una vez, UI estática servida con
  anti-traversal; `molchat-agent serve`
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/server/test_serve.py

### scripts/check_ui_build.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tarea 4.5): puerta de demo que rehúsa un
  `ui/dist` ausente o más viejo que sus fuentes, con rebuild indicado
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/test_check_scripts.py

### src/molchat_agent/tools/moldesign.py, src/molchat_agent/bridge.py, src/molchat_agent/executor.py, src/molchat_agent/orchestration/store.py, tests/contract/test_live_cr.py

- Origen: código nuevo en este repositorio; endpoints verificados en la rama
  feat/molchat-plataforma-cr del repo de MolDesign (CR-06/CR-07), sin copiar código
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (Fase 5, adopción CR): capacidades
  `create_docking_proposal` (write, 409-bloqueantes→blocked) y
  `reconcile_operation`; cabecera verificada `Idempotency-Key`;
  `BridgeError` con status/detail; reconciliación al perder respuesta
  (COMPLETADA adopta, FALLIDA/PENDIENTE mantienen ambiguous) y `resume()`
  que reabre `ambiguous` vía `store.reopen()` solo al adoptar
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/test_executor.py, tests/test_bridge.py, tests/tools/,
  tests/orchestration/test_store.py, tests/contract/test_live_cr.py (vivo)

### src/molchat_agent/runtime/llama_server.py, src/molchat_agent/runtime/models.py, src/molchat_agent/runtime/__init__.py, tests/runtime/__init__.py, tests/runtime/test_llama_server.py, tests/runtime/test_models.py, tests/runtime/test_cli.py

- Origen: backend/services/ai/local_llm.py (brújula: cwd en el binario,
  creationflags literales, drenaje de stdout, probe sync, atexit) y
  backend/services/ai/model_registry.py (idea de catálogo); reimplementado
  sin ResourceManager, core.config/hardware ni structlog
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: código nuevo (tarea 5.4): ciclo de vida start/stop/health
  idempotente con GPU auto simplificada, argv builder inyectable, catálogo
  .gguf agnóstico de máquina y descarga https con tope y SHA-256
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/runtime/test_llama_server.py (subproceso stub real),
  tests/runtime/test_models.py

### src/molchat_agent/tools/molcy.py, tests/tools/test_molcy.py, tests/contract/test_live_molcy.py

- Origen: código nuevo en este repositorio; endpoints verificados en
  backend/api/routers/molcy.py de la rama feat/molchat-plataforma-cr
  (fuentes, trabajos, estado, procedencia, cancelar), sin copiar código
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tarea 5.1): tool-pack Molcy (descubrir,
  pedir render GPU, seguir trabajo, leer acta, cancelar); JobTracker y
  ejecutor siguen renders (en_cola/renderizando→completo/fallido/
  cancelado); el MP4 nunca pasa por el agente (deep link open_molcy)
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/tools/test_molcy.py, tests/orchestration/test_jobs.py,
  tests/test_executor.py, tests/contract/test_live_molcy.py (vivo)

### src/molchat_agent/providers/claude.py, src/molchat_agent/providers/gemini.py, tests/providers/test_claude.py, tests/providers/test_gemini.py

- Origen: backend/services/ai/providers/claude_provider.py y
  gemini_provider.py (brújula: modelos y salud por defecto, mapeo de roles
  Gemini, auth por cabecera); reimplementados sobre httpx sin el SDK de
  Anthropic ni acoplamientos, en la forma de la casa (plan/chat/salud)
- Commit de MolDesign: 66ff524334267c56558b7a3cce94cb919edbad2e
- Autoría: Johan Amezcua (único titular; puede relicenciar bajo GPL-3.0-or-later)
- Transformación: código nuevo (tarea 5.3): proveedores remotos solo-perfil
  default (hackathon los deshabilita, §6.1.1); plan pide JSON
  (responseMimeType en Gemini); sin claves en vivo aún, probados con mocks
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/providers/test_claude.py, tests/providers/test_gemini.py,
  tests/providers/test_registry.py

### src/molchat_agent/voice/cloud_stt.py, tests/voice/test_cloud_stt.py

- Origen: código nuevo en este repositorio (sin porte: la plataforma no
  tiene STT en nube; contrato público OpenAI-compatible /audio/transcriptions)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tarea 5.3): cliente multipart https con
  tope y forma verificada; opt-in triple (flag + URL/clave + permiso
  transcribe), exclusivo cuando activo (nunca fallback silencioso);
  `STTError` unifica errores de voz; `/v1/version` declara stt local/cloud/none
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/voice/test_cloud_stt.py, tests/server/test_serve.py,
  tests/server/test_transcribe.py, ui/src/components/Settings.test.tsx

### src/molchat_agent/voice/vocabulary.py, src/molchat_agent/voice/evaluate.py, tests/voice/test_vocabulary.py, scripts/eval_stt.py

- Origen: código nuevo en este repositorio (sin porte desde MolDesign)
- Commit de MolDesign: N/A
- Autoría: Johan Amezcua
- Transformación: código nuevo (tarea 5.5): lexicón químico es/en con
  initial_prompt para faster-whisper local (el endpoint de plataforma no
  admite prompt: sin sesgo, declarado); puntuación pura de recall de
  términos; script operador con SKIP honesto sin audios
- Licencia resultante: GPL-3.0-or-later
- Tests: tests/voice/test_vocabulary.py, tests/voice/test_local_whisper.py
