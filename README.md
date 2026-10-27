# MolChat Agent

**El agente de [MolDesign](https://github.com/srcacahuate619/moldesign-app):
un asistente de laboratorio auditable que coordina flujos de química
computacional desde texto o voz.**

MolChat es el agente que vive dentro de la plataforma MolDesign: conversa con
el investigador, propone planes verificables, pide aprobación humana donde
toca y sigue los trabajos científicos hasta su resultado con evidencia. Este
repositorio es su fuente única (GPL-3.0-or-later); MolDesign lo incluye como
programa independiente (sidecar) y conserva los motores, la identidad y las
autorizaciones. La ciencia nunca se duplica aquí: se consume por API HTTP
versionada (`docs/CONTRATO_MOLDESIGN.md`).

> Estado: **fases 0–5 cerradas y verificadas contra una MolDesign real**
> (contrato 27/27, ejecución completa sin terminal, voz de extremo a
> extremo, ciclo de hipótesis de dos rondas con aprobación humana y vídeo
> científico de Molcy del mejor resultado, con su acta de procedencia).
> Revisa los límites científicos y de seguridad antes de fiarte de
> cualquier número.

## Qué existe en esta versión

- Núcleo independiente de Python 3.11+, GPL-3.0-or-later, sin motores científicos
  duplicados.
- Catálogo estricto de herramientas respaldadas por endpoints actuales de
  MolDesign. No permite ejecutar shell, código Python, URLs arbitrarias ni
  operaciones fuera de la lista.
- Planificación mediante proveedores intercambiables (Muse Spark 1.3 Standard
  por defecto, OpenAI-compatibles, llama-server/Ollama locales, o `fake`
  determinista sin claves), con JSON estructurado validado localmente y contra
  el conjunto exacto de herramientas enviado. El planificador sólo ve
  herramientas de lectura y preflight: nunca aprueba ni inicia docking por
  sí solo.
- Planes en dos esquemas: secuenciales (`/1`) y con referencias tipadas entre
  pasos (`/2`, `{"$from": "s1.task_id"}`), validadas antes de ejecutar.
- Revisión de planes antes de su ejecución, con huella SHA-256; la copia que
  se ejecuta es inmutable tras la aprobación.
- Propuestas de docking de extremo a extremo: el agente las **crea** (cuando
  la plataforma expone CR-07), el humano aprueba ligado al hash del plan, la
  plataforma revalida identidad y `proposal_hash`, y el agente sigue el
  trabajo hasta su estado terminal (con cancelación y presupuestos).
- Ciclo de hipótesis acotado con expediente: cribado por preflight, ranking
  determinista, una propuesta por ronda y aprobación humana en cada una.
- Registro de resultados, fallos y hashes de salida; parada ante error y
  estado persistente que se reanuda sin re-ejecutar nada.
- Entrada por audio WAV mediante el Whisper local de MolDesign (con sesión),
  o push-to-talk en la UI con confirmación antes de entrar como turno.
- Sidecar local (`molchat-agent serve`, extra `server`): API en loopback con
  sesiones acuñadas y UI propia servida en el mismo origen. Ver
  [`docs/SIDECAR.md`](docs/SIDECAR.md).

## Instalar en entorno de desarrollo

```bash
python -m venv .venv
python -m pip install -e '.[dev]'
python -m pytest -q
cd ui && npm install && npm test && npm run build && cd ..
```

El backend de MolDesign debe estar iniciado para ejecutar herramientas reales.
No necesitas clonar ni instalar todo su árbol científico dentro de este repo.

## Sidecar (sin terminal, con UI)

```bash
python -m pip install -e '.[server]'        # Starlette + uvicorn del sidecar
MOLCHAT_PROVIDER=fake molchat-agent serve   # demo sin claves
```

Abre `http://127.0.0.1:8771`, pega la sesión impresa una sola vez y úsalo.
Detalles, modos y API en [`docs/SIDECAR.md`](docs/SIDECAR.md).

## Configuración

| Variable | Uso |
|---|---|
| `MOLDESIGN_BASE_URL` | `http://127.0.0.1:8000` por defecto |
| `MOLDESIGN_TOKEN` | Token de sesión de tu propia cuenta MolDesign |
| `MOLDESIGN_ALLOW_REMOTE` | `1` sólo si autorizas un backend remoto HTTPS |
| `MODEL_API_KEY` | Clave de Meta Model API para planificar con Muse Spark |
| `MOLCHAT_PROFILE` | `hackathon` (Meta + locales) o `default` (todo, con consentimiento) |
| `MOLCHAT_PROVIDER` | Proveedor activo (`meta` por defecto; `fake` para demo sin claves) |

Los tokens se leen en el proceso. No se incluyen en el plan, los resultados
ni los archivos del repositorio. No publiques `.env`.

## Primer flujo con dos etapas

1. Diagnosticar y pedir un plan (se envía **el texto del objetivo** al
   proveedor; no incluyas datos privados sin autorización para compartirlos):

   ```bash
   molchat-agent doctor
   molchat-agent plan --provider fake "Lista los receptores"  # sin claves
   molchat-agent plan "Lista los receptores" --out plan.json  # proveedor activo
   ```

   Un destino remoto exige consentimiento previo
   (`molchat-agent doctor --grant-consent proveedor@host`).

2. Revisarlo y ejecutarlo contra MolDesign:

   ```bash
   molchat-agent inspect plan.json
   molchat-agent execute plan.json --out report.json
   ```

### Aprobación de una propuesta

El agente puede crear la propuesta (`create_docking_proposal`, con clave de
idempotencia) o trabajar con una existente. El paso de aprobación
(`approve_docking_proposal`, con `proposal_id` y `proposal_hash`) nunca lo
emite el modelo por sí solo: va en un plan revisado y aprobado por un humano.
Después de revisarlo:

```bash
molchat-agent inspect plan.json
molchat-agent execute plan.json --approve-digest 'sha256:HUELLA_DEL_PLAN' \
  --approve-step s1 --out report.json
```

La aplicación original vuelve a comprobar la identidad del usuario, el estado
de la propuesta y su hash antes de lanzar una evaluación.

### Transcripción local

```bash
molchat-agent transcribe-local comando.wav --lang es
```

Esta operación produce texto; **no lo ejecuta automáticamente**. Debe revisarse
antes de convertirse en un plan de laboratorio.

## Límites científicos y de seguridad

- Un score de docking no prueba unión, eficacia ni seguridad clínica.
- El planificador no calcula propiedades; éstas proceden exclusivamente de los
  motores y controles de MolDesign.
- Un preflight devuelve advertencias, bloqueantes y condiciones no evaluadas:
  el ejecutor se detiene ante bloqueantes técnicos, sin convertir las señales
  no evaluadas automáticamente en aprobaciones científicas.
- El backend local se restringe a loopback; para un servidor remoto se exige
  HTTPS y configuración explícita. No se siguen redirecciones HTTP.
- Las propiedades por conversación usan un dataset demo local de 8 moléculas
  (valores RDKit grabados); la cobertura completa espera la API de plataforma
  (CR-01) y lo desconocido se abstiene en vez de inventar.
- El vídeo científico lo renderiza Molcy en la plataforma, nunca el agente;
  el agente pide el trabajo, lo sigue y enlaza su acta de procedencia
  (`molcy.procedencia/1`). Solo puede ser fuente de vídeo una corrida que el
  investigador haya guardado en Moldex: es la regla de la plataforma y el
  agente la respeta pidiendo ese guardado dentro del plan aprobado.

Consulta [`docs/CONTRATO_MOLDESIGN.md`](docs/CONTRATO_MOLDESIGN.md) para el
contrato vigente con la plataforma y el registro de corridas en vivo;
[`docs/AUDITORIA.md`](docs/AUDITORIA.md) para el mapa de dependencias y
licencias; [`docs/PARIDAD.md`](docs/PARIDAD.md) para qué hace ya este agente
frente al MolChat que vivía dentro de MolDesign; y
[`docs/SEGURIDAD.md`](docs/SEGURIDAD.md) para el modelo de amenazas.

**Licencia:** GNU GPL-3.0-or-later. Consulte `LICENSE` y `NOTICE.md`.

