# Arquitectura — MolChat Agent (v1, Fase 1)

Núcleo agnóstico + puertos + adaptadores. El núcleo habla de capacidades,
planes y artefactos; nunca de PDB, Vina o casos. Todo lo específico de
MolDesign vive detrás del puente HTTP y, desde la Fase 3, en tool-packs.

## Mapa del código

```text
src/molchat_agent/
  config.py        único lector de os.environ (tarea 1.6)
  plan.py          planes inmutables esquema /1, digest SHA-256
  executor.py      ejecución auditada con aprobación ligada al hash
  capabilities.py  allowlist de 6 herramientas HTTP (migra a tools/ en Fase 3)
  bridge.py        transporte HTTP loopback/HTTPS, sin redirecciones
  meta.py          shim obsoleto → providers.meta (se borra en 0.2)
  providers/
    base.py             puerto LLMProvider + salud + catálogo de solo lectura
    registry.py         registro, perfiles y gate de consentimiento
    fake.py             determinista, sin red (tests y demo sin claves)
    meta.py             Muse Spark 1.3 Standard, reasoning configurable
    openai_compatible.py cualquier endpoint estilo OpenAI (nube o loopback)
    local_http.py       llama-server (:8400/v1) y Ollama (:11434), solo loopback
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

## Localidad y consentimiento

La localidad se calcula desde el destino resuelto, no desde el nombre: un
`openai-compatible` apuntado a loopback es local; uno sin URL es remoto
(fallo cerrado). Llama-server y Ollama rechazan URLs no-loopback al construirse.

Toda llamada remota exige consentimiento para la huella `proveedor@host`,
otorgado antes del primer byte y revocable por proveedor. Sin él, el registro
lanza `ConsentDenied` sin emitir nada — ni siquiera el sondeo de salud
(estado `no_consent`). `MOLCHAT_OFFLINE=1` manda sobre cualquier autorización.
Los otorgamientos viven en `~/.molchat/consents.json` (o
`MOLCHAT_CONSENTS_FILE`); el fichero no contiene secretos.

Frontera de datos: un planificador remoto recibe el objetivo y el catálogo.
Resultados e historial no salen sin un consentimiento específico con vista
previa (§10.4; exigible desde el ciclo de hipótesis, Fase 5).

## Perfiles

- `hackathon` (por defecto): Meta Standard + proveedores locales. El resto de
  remotos están deshabilitados (`ProviderDisabled`, no silencio).
- `default`: todo lo registrado está permitido (sigue exigiendo consentimiento).

`MOLCHAT_PROVIDER` fija el proveedor activo; sin él, el activo es `meta`.

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

- Almacén cifrado de claves por usuario (diseño de `provider_config_store`):
  hoy las claves viven solo en entorno/memoria. Fase 2/5.
- `chat()` en streaming con el motor conversacional. Fase 2.
- Handshake de contrato + catálogo vivo servido por la plataforma (CR-04).
  Hoy el catálogo es local y la suite de contrato lo valida.
- Clases epistémicas y `epistemic_class` obligatoria en capacidades (§6.2).
  Fase 3, con la migración a `tools/`.
