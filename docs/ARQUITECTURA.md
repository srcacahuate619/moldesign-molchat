# Arquitectura — MolChat Agent (v2, Fase 4)

Núcleo agnóstico + puertos + adaptadores. El núcleo habla de capacidades,
planes y artefactos; nunca de PDB, Vina o casos. Todo lo específico de
MolDesign vive detrás del puente HTTP y, desde la Fase 3, en tool-packs.

## Mapa del código

```text
src/molchat_agent/
  config.py        único lector de os.environ (tarea 1.6)
  plan.py          planes inmutables /1 y /2 (bindings), digest SHA-256
  executor.py      ejecución auditada con aprobación ligada al hash
  tools/           tool-packs: catalog.py + moldesign.py (23 capacidades)
  bridge.py        transporte HTTP loopback/HTTPS, sin redirecciones
  providers/       puerto LLMProvider: fake, meta, openai-compatible,
                   llama-server, ollama (+ consentimiento por destino)
  conversation/    turno: intenciones, respondedores, evidencia, memoria
  orchestration/   store, jobs con backoff, presupuestos (Fase 3)
  voice/           puerto SpeechToText + Whisper local de MolDesign (Fase 4)
  server/          sidecar: auth, app, executions, serve (Fase 4, extra server)
ui/                React+TS+Vite servida por el sidecar (Fase 4)
```

## Puerto `LLMProvider`

```python
class LLMProvider(Protocol):
    id: str                      # "meta", "openai-compatible",
                                 # "llama-server", "ollama", "fake"
    locality: Literal["local", "remote"]
    async def health(self) -> HealthCheckResult: ...
    async def plan(self, goal: str, catalog: list | None = None) -> Plan: ...
    async def chat(self, turn: TurnContext) -> AsyncIterator[ChatEvent]: ...
```

Reglas (PLAN §6.1, verificadas por tests):

- El planificador solo ve capacidades con riesgo `read` explícito
  (`read_only_catalog` en `base.py`); sin `risk: read` no hay herramienta.
- `plan()` filtra aunque el llamante pase el catálogo completo.
- `chat()` en streaming llega en la Fase 2; hoy levanta `NotImplementedError`
  explícito en todos los proveedores (frontera testeada).
- `fake` es el proveedor por defecto en tests y demos sin claves.

## Sidecar (Fase 4)

`server/` expone el núcleo por HTTP loopback (`molchat-agent serve`, extra
`server`): sesiones HMAC con permisos y caducidad (`auth.py`), API `/v1/*`
con guard de Host/Origen (`app.py`), ejecuciones en segundo plano con
cancelación explícita (`executions.py`) y cableado standalone (`serve.py`).
`ui/` (React+TS+Vite) se sirve en el mismo origen; detalle operativo y API
en [`SIDECAR.md`](SIDECAR.md). `voice/` mueve aquí la transcripción local
(`bridge.transcribe_local` delega).

## Localidad y consentimiento

La localidad se calcula desde el destino resuelto, no desde el nombre: un
`openai-compatible` apuntado a loopback es local; uno sin URL es remoto
(fallo cerrado). Llama-server y Ollama rechazan URLs no-loopback al construirse.

Toda llamada remota exige consentimiento para la huella `proveedor@host`,
otorgado antes del primer byte y revocable por proveedor. Sin él, el registro
lanza `ConsentDenied` sin emitir nada — ni siquiera el sondeo de salud
(estado `no_consent`). `MOLCHAT_OFFLINE=1` manda sobre cualquier autorización.
Los otorgamientos viven en `~/.molchat/consents.json` (o
`MOLCHAT_CONSENTS_FILE`); el fichero no contiene secretos. En modo alojado
(MolDesign como host) el consentimiento es el de la cuenta, guardado en MolDesign:
este fichero no se usa.

Frontera de datos: un planificador remoto recibe el objetivo y el catálogo.
Resultados e historial no salen sin un consentimiento específico con vista
previa (§10.4; exigible desde el ciclo de hipótesis, Fase 5).

## Proveedores y claves

Los proveedores remotos son un catálogo fijo en la llave: `providers/catalogo.json`
(OpenAI primero como API genérica; DeepSeek sólo para DeepSeek; Anthropic, Gemini,
NVIDIA, Meta y los dos locales). Cada entrada dice su familia de protocolo, su URL
base y lo que sale de la máquina. La URL no la cambia el entorno. Un adaptador por
entrada: `providers/registry.py::construir`.

Modo alojado (MolDesign como host): el proveedor activo y su clave son de la cuenta.
Cada turno pide al host el activo (`GET /molchat-host/proveedores`) y, si es remoto,
la credencial para el host de este catálogo (`POST /molchat-host/credencial`). El host
la entrega sólo si la cuenta guardó la clave, autorizó `proveedor@host` y el host es el
suyo. La clave vive en un registro de UNA llamada (`providers/alojado.py`); el registro
base nunca la guarda. Sin autorización, la llamada no sale y se dice dónde resolverlo.

Fuera de MolDesign (sidecar independiente): las claves vienen del entorno
(`OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `NVIDIA_API_KEY`, `ANTHROPIC_API_KEY`,
`GEMINI_API_KEY`, `MODEL_API_KEY` para Meta) y el consentimiento es el de
`~/.molchat/consents.json`.

## Perfiles

- `default` (por defecto, el del producto): todo el catálogo permitido. Cada remoto
  exige su clave y su autorización.
- `hackathon` (sólo con `MOLCHAT_PROFILE=hackathon`): Meta Standard y los locales;
  el resto de remotos se deshabilitan (`ProviderDisabled`, no silencio).

`MOLCHAT_PROVIDER` fija el proveedor activo. Sin él no hay proveedor activo: la
respuesta conceptual lo dice en vez de usar otro en silencio.

## Política Meta (§6.1.1)

Modelo por defecto `muse-spark-1.3` Standard; cualquier variante `contributor`
se rechaza al construir el proveedor. `reasoning_effort` configurable
(`medium` por defecto; subirlo exige evidencia A/B en la quality suite).

## CLI

`molchat-agent plan --provider fake "objetivo"` planifica por el registro
(con gate de consentimiento). `molchat-agent doctor` informa de configuración
(redactada), proveedores, consentimientos y alcance del puente; `--consents`
detalla la frontera de datos; `--grant-consent proveedor@host` y `--revoke`
gestionan autorizaciones.

## Decisiones diferidas (no olvidadas)

- Claves por cuenta fuera de MolDesign (almacén propio del sidecar, cifrado y por
  usuario de sistema). Hoy el sidecar independiente lee el entorno.
- Multi-cuenta dentro de un mismo proceso: el sidecar sigue fijado a la primera
  cuenta (PD-04 del ADR 100). Las claves ya son por cuenta en MolDesign.
- Cifrado de la clave maestra con DPAPI (hoy se deriva de `~/.moldesign/secret_key`).
- Listado de modelos desde el proveedor (`/models`) y API Responses para los modelos
  Codex: sin implementar.
- Handshake de contrato + catálogo vivo servido por la plataforma (CR-04).
  Hoy el catálogo es local y la suite de contrato lo valida.
