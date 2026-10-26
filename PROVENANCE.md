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
