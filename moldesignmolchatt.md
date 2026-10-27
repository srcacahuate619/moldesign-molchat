# Lo que MolChat necesita de MolDesign

**Documento de petición formal del equipo MolChat (repo `moldesign-molchat`,
GPL-3.0-or-later) al equipo MolDesign (plataforma, PolyForm Noncommercial).**

| Campo | Valor |
|---|---|
| Fecha | 2026-10-26 |
| De | MolChat Agent — agente independiente, se comunica por HTTP versionado |
| Para | MolDesign — plataforma científica (motores, identidad, datos, autorización) |
| Contrato vigente | `moldesign.molchat/1` (ver `docs/CONTRATO_MOLDESIGN.md` del repo MolChat) |
| Regla de oro | Si una pieza calcula ciencia o decide permisos, es de MolDesign; si conversa, planifica o presenta, es de MolChat. Nada de lo pedido aquí mueve ciencia al agente |

## Resumen: las peticiones por prioridad

| ID | Petición | Prioridad | Sin esto, qué no puede hacer MolChat |
|---|---|---|---|
| **CR-07** | Creación HTTP de propuestas de docking | **Crítica** | Crear propuestas por sí mismo (hoy depende del chat interno de MolDesign para que exista una propuesta que aprobar) |
| **CR-06** | Idempotencia y reconciliación de operaciones con efectos | Alta | Reintentar con seguridad; una respuesta perdida puede duplicar un cálculo |
| **CR-04** | Handshake de agente: versión de contrato + catálogo servido | Alta | Saber qué puede pedir sin un catálogo local que diverge en silencio |
| **CR-02** | Casos como recurso (crear/consultar) | Alta | «Crear casos» desde el agente; hoy el caso es una proyección del cliente |
| **CR-08** | Estado de cancelación distinguible en jobs | Media | Distinguir «cancelado por el usuario» de «falló» sin parsear mensajes |
| **CR-01** | API versionada de propiedades/preparación (RDKit) | Media | Conversar de moléculas nuevas con propiedades reales (hoy, fixtures grabadas) |
| **CR-03** | Eventos de cambio de estado (evaluaciones y trabajos Molcy) | Media | Seguir trabajos sin sondeo; el sondeo funciona, pero es el fallback |
| **CR-05** | Superficie versionada de análogos/ADMET/MolGraph | Media | El ciclo de exploración de hipótesis completo |
| **CR-09** | Inicio de batch por JSON (sin multipart) | Baja | Lanzar cribados por lote desde el agente con idempotencia |

Además, la **Sección B** lista lo que MolChat necesita para vivir *dentro* de
MolDesign en la Fase 6 (host, vendorizado y ciclo de vida). No es API
científica: es el contrato de integración, espejo del que ya existe con Molcy.

---

## Sección A — Superficie de plataforma (API)

### Lo que ya existe y MolChat ya consume (no se pide: se agradece y se congela)

Verificado en vivo el 2026-10-26 contra una instancia real (contrato 27/27):

- `GET /targets/`, `POST /evaluation/preflight` (con `technical_blockers`,
  `warnings`, `not_evaluated`: ese contrato es exactamente el que el agente
  necesita; no cambiar su forma sin versionar).
- `GET /history/evaluations`, `GET /history/stats`,
  `POST /history/save/{molecule_id}`.
- `GET /evaluation/status/{task_id}`, `GET /evaluation/stream/{task_id}` (SSE),
  `POST /evaluation/cancel`, `GET /evaluation/engines`.
- `GET /evaluation/result/{molecule_id}` **con `task_id` opcional** (la
  identidad inmutable de corrida ya es citable; MolChat la usa, MP-05 hecho).
- `GET /evaluation/interactions/{molecule_id}`,
  `GET /evaluation/gnn-attention/{molecule_id}`, `GET /sar/{molecule_id}`,
  informes (`/evaluation/ai-report/...`), dossier de caso (`/dossier/...`),
  batch (`GET/POST /evaluation/batch/{batch_id}...`, export CSV/JSON),
  rescoring (`/rescoring/health|info|ram`).
- `GET /ai/proposals/{proposal_id}`, `POST /ai/proposals/{proposal_id}/approve`
  y `/reject`: lectura y decisión server-side con `proposal_hash` revalidado.
  **Esto está bien diseñado y MolChat lo conserva tal cual.**
- `POST /ai/speech-to-text` (Whisper local): el STT por defecto del agente.

Lo que sigue es solo lo que falta.

---

### CR-07 — Creación HTTP de propuestas de docking · CRÍTICA

**Necesidad.** Un endpoint que cree una **propuesta revisable sin lanzar el
cálculo**, análogo a lo que el servicio interno de propuestas ya hace dentro
del proceso, y que devuelva su identidad y huella:

```http
POST /ai/proposals
Authorization: Bearer <sesión del investigador>
Content-Type: application/json

{"smiles": "CC(=O)Oc1ccccc1C(=O)O", "target_pdb_id": "1HSG", "chain": "A"}
```

```json
{
  "proposal_id": "…",
  "proposal_hash": "sha256:…",
  "estado": "pendiente",
  "parametros_efectivos": {"motor": "vina", "exhaustividad": 8, "poses": 5, "semilla": 42, "caja": {}},
  "preflight": {"technical_blockers": [], "warnings": [], "not_evaluated": []},
  "caduca_en": "2026-…"
}
```

**Por qué (evidencia, 2026-10-26).** Hoy `/ai/proposals` solo permite leer,
aprobar y rechazar. La única vía de creación es el chat interno de MolDesign
(la herramienta `run_docking` dentro del proceso). Para demostrar la Fase 3,
el MolChat nuevo tuvo que pedirle al MolChat *interno* — el que va a
reemplazar — que creara la propuesta con su motor llama.cpp, y entonces
aprobarla él. Funcionó, pero la dependencia es exactamente la que el
desacoplamiento quiere eliminar. Sin CR-07, el agente puede aprobar trabajo,
pero no puede *iniciar* el flujo científico completo por sí mismo.

**Condiciones.**

- Nunca es un `submit` directo: crear la propuesta no encola ni ejecuta nada.
- La identidad la impone el servidor desde la sesión; ningún `user_id` en el
  cuerpo tiene efecto (invariante del gate interno de MolChat).
- La propuesta nace ligada a cuenta, ligando, receptor y huella de su
  preflight, con caducidad, y se consume una sola vez al aprobarla (todo esto
  ya es semántica del servicio interno: se pide exponerla, no reinventarla).
- Si el preflight trae bloqueantes técnicos, la creación responde con el
  preflight completo y **sin** propuesta aprobable (o con estado que la
  aprobación rechaza siempre).

**Aceptación.** Con una cuenta de pruebas: crear → leer (`GET`) → la huella
coincide → aprobar (`approve` existente) lanza exactamente una evaluación →
una segunda aprobación de la misma propuesta es rechazada → una propuesta
caducada no se puede aprobar → otra cuenta no puede leerla ni aprobarla.

---

### CR-06 — Idempotencia y reconciliación de operaciones con efectos · ALTA

**Necesidad.** Para toda operación que crea trabajo (aprobaciones que lanzan
evaluación, y en su día CR-07 y CR-09):

1. Aceptar una **clave de idempotencia** por cuenta (cabecera
   `Idempotency-Key` o campo del cuerpo), persistida por la plataforma.
2. Misma clave + mismos parámetros ⇒ devuelve la operación original (mismo
   `task_id`/`proposal_id`), sin crear otra.
3. Misma clave + parámetros distintos ⇒ `409` explícito.
4. Un modo de **reconciliar**: dada la clave, consultar qué operación y qué
   trabajo existen, aunque la respuesta original se haya perdido.

**Por qué.** MolChat persiste su intención y su clave *antes* de enviar
(ya implementado de su lado). Pero si la respuesta se pierde tras crear el
trabajo y la plataforma no puede reconciliar, el agente solo puede registrar
«ambiguo» y detenerse: correcto, pero el investigador se queda sin flujo.
Repetir a ciegas puede duplicar un cálculo costoso; no repetir deja el
trabajo huérfano. La deduplicación tiene que vivir donde vive el trabajo.

**Aceptación.** Respuesta perdida tras crear (simulada cortando el cliente),
dos envíos concurrentes con la misma clave, misma clave con otro cuerpo, y
reconciliación posterior: en ningún caso existe un segundo cálculo
inadvertido, y siempre se puede recuperar el `task_id` resultante.

---

### CR-04 — Handshake de agente · ALTA

**Necesidad.** Un endpoint pequeño y estable:

```http
GET /ai/agent/handshake
→ {
    "contract": "moldesign.molchat/1",
    "platform_version": "1.0.4",
    "capabilities": [ {"name": "check_preflight", "version": "1", "risk": "read", "epistemic_class": "calculation", "parameters": {…JSON Schema…} } ],
    "limits": {"max_polls_per_job": null}
  }
```

**Por qué.** Hoy el catálogo de capacidades vive duplicado en el repo de
MolChat (tipos, rangos, patrones). Cada cambio de contrato en MolDesign es
una divergencia silenciosa esperando ocurrir: la suite de contrato la caza
cuando se corre a mano, no cuando le pasa a un usuario. Con el handshake, el
agente valida su catálogo contra el servido al conectar y degrada con un
mensaje claro («esta plataforma ofrece el contrato X; este MolChat espera
Y») en vez de fallar a mitad de un plan.

**Condiciones.** El catálogo servido declara por capacidad: nombre, versión,
riesgo (`read`/`write`/`approval_required`) y clase epistémica, además del
esquema de parámetros. Sin clase epistémica declarada, el agente no la
ofrece al modelo (regla de su gate). El endpoint no requiere más privilegio
que el de leer el propio perfil.

**Aceptación.** MolChat arranca contra la plataforma y su `doctor` muestra
contrato compatible; si se renombra un parámetro en la plataforma, el agente
lo reporta en el handshake antes de ejecutar ningún plan.

---

### CR-02 — Casos como recurso · ALTA

**Necesidad.** Crear y consultar **casos** como recurso direccionable de la
plataforma, por ejemplo:

```http
POST /cases            {"nombre": "…", "descripcion": "…"}        → {"case_id": "…"}
GET  /cases/{case_id}                                             → proyección del caso
POST /cases/{case_id}/runs   {"task_id": "…"}                     → vincula una corrida existente
```

**Por qué.** Hoy el caso vive como proyección que el cliente compone y
devuelve por POST al pedir el dossier (`/dossier/...` lo recibe ya armado).
Eso funciona para la UI actual, pero un agente no puede «crear un caso»,
vincularle corridas ni citarlo por identidad: le falta el recurso. El
dossier, los vídeos de Molcy y el historial ya cuelgan del caso en la
práctica; se pide darle la identidad que el resto del sistema ya asume.

**Condiciones.** Propiedad por cuenta impuesta por el servidor, como el
resto de la superficie; vincular una corrida exige que la corrida sea del
mismo propietario (la plataforma ya valida esto en otras rutas).

**Aceptación.** El agente crea un caso, vincula la corrida de una
evaluación terminada y pide su dossier (`/dossier` existente) citando solo
el `case_id`; otra cuenta no puede leerlo ni vincularle corridas.

---

### CR-08 — Estado de cancelación distinguible · MEDIA

**Necesidad.** Que el estado de un job cancelado sea distinguible sin
parsear texto: `status: "CANCELLED"` (recomendado) o un campo
`"cancelled": true` junto al estado terminal.

**Por qué (evidencia, 2026-10-26).** Al cancelar en vivo una evaluación, la
plataforma respondió `{"cancelled": true}` en la llamada de cancelación —
bien — pero el estado posterior del job fue
`status: "FAILURE", error: "Cancelado por el usuario"`. Para el agente,
«lo paró el investigador» y «reventó el motor» son el mismo estado salvo que
parsing de un mensaje en lenguaje natural, que además puede cambiar de
idioma o de redacción. La distinción es semántica y debe ser de contrato.

**Aceptación.** Cancelar un job y consultarlo devuelve el estado/campo de
cancelación; un fallo genuino de motor no lo trae. Los estados existentes
(`SUCCESS`/`FAILURE`) no cambian de significado para los clientes actuales.

---

### CR-01 — Propiedades y preparación versionadas (RDKit) · MEDIA

**Necesidad.** Una superficie pequeña y versionada, con identidad impuesta
por el servidor:

```http
POST /chemistry/properties   {"smiles": "…"}   → descriptores tipados + procedencia
POST /chemistry/validate     {"smiles": "…"}   → validez estructural y motivo
POST /chemistry/compare      {"smiles": ["…", "…"]} → tabla tipada por molécula
```

(el nombre exacto de la ruta lo elige la plataforma; lo importante es el
contrato tipado y versionado).

**Por qué.** La conversación de MolChat responde hoy propiedades desde
*fixtures grabadas* de RDKit (declarado en su matriz de paridad). Para
hablar de una molécula nueva con números reales hace falta RDKit, y RDKit
vive en la plataforma: el agente no va a duplicar el motor científico para
esto (es la frontera fundacional del proyecto). Las herramientas internas
equivalentes ya existen dentro del proceso (`compute_properties`,
`validate_smiles`, `check_druglikeness`, `compare_molecules`,
`check_preparation`); se pide su contrato, no su código.

**Condiciones.** Sin RDKit disponible, la respuesta es abstención explícita,
nunca un negativo fabricado («sin alertas PAINS» solo si el catálogo PAINS
cargó: lección del gate interno). Cada valor declara su procedencia.

**Aceptación.** El agente pregunta por una molécula que no está en ninguna
fixture y obtiene los mismos descriptores que obtiene la UI de MolDesign
para ese mismo SMILES, con la misma precisión y unidades.

---

### CR-03 — Eventos de cambio de estado · MEDIA

**Necesidad.** Un canal de eventos (SSE es suficiente) con los cambios de
estado de evaluaciones y de trabajos de Molcy del propietario:
`evaluation.status_changed`, `molcy.job_changed`, con `task_id`/`job_id`,
estado nuevo y timestamp.

**Por qué.** El agente ya sigue trabajos por sondeo con backoff y funciona;
es el fallback correcto y se queda. Pero sondear cada pocos segundos durante
un docking de minutos es ruido para ambos lados, y la UI del agente
necesita reaccionar (fin de un trabajo, un vídeo listo) sin esperar al
siguiente sondeo. El SSE de progreso por evaluación ya existe
(`/evaluation/stream/{task_id}`); se pide el agregado por cuenta.

**Aceptación.** El agente recibe el evento de fin de una evaluación que no
inició él (lanzada desde la UI) sin sondear, y el sondeo sigue funcionando
como respaldo si el canal cae.

---

### CR-05 — Análogos, ADMET y MolGraph versionados · MEDIA

**Necesidad.** Exponer como API versionada lo que hoy son herramientas
dentro del proceso: generación de análogos y fragmentos
(`generate_analogs`, `explain_fragments`), sugerencias (`suggest_smiles`),
ADMET (`predict_admet`) y las consultas `molgraph_*` (vecinos, similares,
scaffolds, impacto, drug-likeness, ADMET del grafo).

**Por qué.** Es la superficie del ciclo de exploración de hipótesis de
MolChat (proponer análogos → propiedades → preflight → propuesta →
resultado → comparar). Sin ella, el ciclo se detiene tras el preflight. Son
motores y datos de la plataforma (MolGraph incluido): el agente los consume
o no existen.

**Aceptación.** El agente completa una iteración de hipótesis con aprobación
humana usando solo HTTP: análogos de una molécula semilla, propiedades de
los candidatos (CR-01), preflight del mejor y propuesta (CR-07).

---

### CR-09 — Inicio de batch por JSON · BAJA

**Necesidad.** Crear un batch-screening con los ligandos **en el cuerpo**
(lista de SMILES/nombre, receptor y parámetros), sin subida multipart de
ficheros, con clave de idempotencia (CR-06).

**Por qué.** El batch actual se inicia con un fichero; un agente no tiene
ficheros legítimos que subir — tiene listas que el investigador escribió o
que una capacidad anterior produjo. El resto del ciclo batch (estado,
cancelación, export) ya es consumible por el agente hoy.

**Aceptación.** El agente lanza un batch de 3 ligandos públicos por JSON,
lo sigue hasta terminar y exporta el CSV; repetir con la misma clave de
idempotencia no crea un segundo batch.

---

## Sección B — Lo que MolChat necesita para vivir dentro de MolDesign (Fase 6)

Esto no es API científica: es el contrato de hospedaje, espejo del que
MolDesign ya aplica con Molcy (ADR 92/95). MolChat lo respeta desde su lado;
de MolDesign se necesita construir su mitad cuando llegue la Fase 6:

| # | Necesidad en MolDesign | Espejo existente |
|---|---|---|
| B-1 | Script de vendorizado `scripts/stage_molchat.py` que materialice `tools/molchat/` desde un **commit** del repo público (leyendo blobs de git, árbol limpio) y genere `tools/molchat/molchat-manifest.json` (`schema: moldesign.molchat/1`: commit, URL pública, SHA-256 por fichero, contrato) | `scripts/stage_molcy_motor.py` + `tools/molcy/molcy-manifest.json` |
| B-2 | Verificación del manifiesto **antes de cada arranque** del sidecar; si no verifica, no arranca y la UI lo explica («reinstala») | `backend/services/molcy/motor.py` |
| B-3 | Supervisor del proceso: localizar el sidecar, levantarlo en loopback con puerto efímero al abrir el panel, salud/versión, apagarlo con la aplicación | Supervisor de trabajos de Molcy |
| B-4 | Router host mínimo: `GET /molchat-host/status` y `POST /molchat-host/session` que emita un token de sesión **con scopes y caducidad corta**, audiencia `molchat`, identidad impuesta por el servidor | Emisión de acceso a medios de Molcy (token caduco, sin JWT en URL) |
| B-5 | Hueco de UI que incruste la interfaz del sidecar y atienda solo estos deep links con esquema cerrado: abrir evaluación, abrir caso, abrir informe, abrir vídeo de Molcy, ir a aprobar en la plataforma | El reproductor de vídeo de Molcy como superficie embebida |
| B-6 | Test de frontera en ambos repos: MolDesign no importa `molchat_agent`; MolChat no importa MolDesign; la comunicación es solo el contrato HTTP | `backend/tests/test_frontera_motor_molcy.py` |
| B-7 | MolChat en el SBOM con su licencia y commit, y en las comprobaciones de bundle. Al ser **opcional en runtime**, no entra en herramientas críticas: MolDesign debe funcionar entero con MolChat ausente o corrupto | `scripts/generate_sbom.py`; `HERRAMIENTAS_CRITICAS` (sin MolChat) |
| B-8 | `.gitattributes`: `tools/molchat/** -text` para que git no altere los bytes hasheados | `tools/molcy/** -text` |
| B-9 | ADR propio de la decisión (siguiente número libre) que enlace este documento y los ADR 92/95 | ADR 95 para Molcy |

Del lado de MolChat, la contraparte ya está comprometida en su plan:
sidecar en loopback con autenticación del host, UI estática propia,
manifiesto verificable, y modo standalone/externo cuando no haya host.

---

## Sección C — Lo que MolChat NO pide (para que conste)

- **No** pide acceso a la base de datos, al sistema de ficheros científico ni
  a código de la plataforma: todo es HTTP con el contrato de arriba.
- **No** pide que `POST /evaluation/submit` sea herramienta del modelo: la
  entrada directa seguiría saltándose la revisión humana. El camino es
  propuesta (CR-07) → aprobación → la plataforma ejecuta.
- **No** pide mover RDKit, Vina, MolGraph ni ningún motor al agente. Si una
  capacidad no tiene superficie, el agente se abstiene y lo dice; no la
  simula ni la duplica.
- **No** pide relajar la identidad impuesta por el servidor, la revalidación
  de `proposal_hash` ni la caducidad de propuestas: son la parte del diseño
  actual que el agente considera correcta y sobre la que construye.
- **No** pide multiusuario de servidor: el sidecar es monousuario ligado a
  la identidad del host (su comportamiento ante cambio de cuenta y
  revocación se define en la Fase 4/6, necesidad B-4).

## Secuencia sugerida

1. **CR-07 + CR-06** — desbloquean el flujo científico completo del agente
   (es el trabajo que la demo de la Fase 3 ya demostró necesitar).
2. **CR-04 + CR-08** — contratos pequeños, riesgo bajo, valor inmediato de
   robustez para cualquier consumidor, no solo MolChat.
3. **CR-02** — cuando el agente empiece a organizar trabajo en casos.
4. **CR-01 → CR-05 → CR-03/CR-09** — la conversación con moléculas nuevas,
   el ciclo de hipótesis y la comodidad operativa, en ese orden.
5. **Sección B** — con la Fase 6 de MolChat, ni antes (no hay sidecar que
   hospedar todavía) ni después (es su puerta de entrada a la plataforma).

Cada CR implementada entra en el repo de MolChat como capacidad con sus
tests de contrato en la siguiente fase que la necesite, y este documento se
actualiza marcándola como entregada con su fecha y commit de MolDesign.

---

*Contraparte viva de este documento: `docs/CONTRATO_MOLDESIGN.md` en el repo
de MolChat (contrato vigente, registro de corridas en vivo y estado de cada
CR). La planificación completa del agente vive en su `PLAN.md` interno,
§7.4 (peticiones) y §15 (el lado MolDesign de la integración).*
