# MolChat Agent

**Agente independiente y auditable para coordinar flujos de química computacional
en MolDesign desde texto o voz.**

> Estado: **sidecar utilizable (fase 4)**. Conversación con evidencia,
> planes con aprobación por hash, trabajos con cancelación y voz local con
> confirmación, servidos por `molchat-agent serve` con UI propia. Revisa los
> límites científicos y de seguridad antes de fiarte de cualquier número.

## Qué existe en esta versión

- Núcleo independiente de Python 3.11+, GPL-3.0-or-later, sin motores científicos
  duplicados.
- Catálogo estricto de herramientas respaldadas por endpoints actuales de
  MolDesign. No permite ejecutar shell, código Python, URLs arbitrarias ni
  operaciones fuera de la lista.
- Planificación mediante proveedores intercambiables (Muse Spark 1.3 Standard
  por defecto, OpenAI-compatibles, llama-server/Ollama locales, o `fake`
  determinista sin claves), con JSON estructurado validado localmente. El
  planificador sólo ve herramientas de lectura y preflight, nunca inicia docking.
- Revisión de planes antes de su ejecución, con huella SHA-256.
- Aprobación de propuestas de docking mediante el **mismo endpoint existente**
  de MolDesign, bajo una segunda autorización humana ligada al hash del plan y
  con el `proposal_hash` verificado por el servidor.
- Registro de resultados, fallos y hashes de salida; parada ante error.
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

La versión inicial sólo ofrece tareas secuenciales y pasos sin parámetros
dependientes de resultados anteriores. Este límite evita que el agente invente
identificadores científicos mientras añadimos un planificador verificable de
varias etapas.

### Aprobación de una propuesta existente

El plan de aprobación se redacta **manualmente** con `approve_docking_proposal`
e incluye un `proposal_id` y un `proposal_hash` obtenidos del flujo de MolDesign.
El modelo de Meta no puede emitir ese paso por sí solo. Después de revisarlo:

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

Consulta [`docs/AUDITORIA.md`](docs/AUDITORIA.md) para el mapa de dependencias,
contratos y licencias; [`docs/HOJA_DE_RUTA.md`](docs/HOJA_DE_RUTA.md) para los pasos
pendientes.

**Licencia:** GNU GPL-3.0-or-later. Consulte `LICENSE` y `NOTICE.md`.

