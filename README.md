# MolChat Agent

**Agente independiente y auditable para coordinar flujos de química computacional
en MolDesign desde texto o voz.**

> Estado: **MVP técnico de integración (fase 1)**. El planificador de Meta y el
> puente HTTP están implementados, pero aún requieren pruebas de integración
> contra un MolDesign instalado y credenciales reales. No es un laboratorio
> autónomo de producción ni hace afirmaciones clínicas.

## Qué existe en esta versión

- Núcleo independiente de Python 3.11+, GPL-3.0-or-later, sin motores científicos
  duplicados.
- Catálogo estricto de herramientas respaldadas por endpoints actuales de
  MolDesign. No permite ejecutar shell, código Python, URLs arbitrarias ni
  operaciones fuera de la lista.
- Planificación opcional mediante **Muse Spark 1.3** en Meta Model API, con JSON
  estructurado validado localmente. El planificador sólo ve herramientas de
  lectura y preflight, nunca inicia docking.
- Revisión de planes antes de su ejecución, con huella SHA-256.
- Aprobación de propuestas de docking mediante el **mismo endpoint existente**
  de MolDesign, bajo una segunda autorización humana ligada al hash del plan y
  con el `proposal_hash` verificado por el servidor.
- Registro de resultados, fallos y hashes de salida; parada ante error.
- Entrada por audio WAV mediante el Whisper local de MolDesign (con sesión).

## Instalar en entorno de desarrollo

```bash
python -m venv .venv
python -m pip install -e '.[dev]'
python -m pytest -q
```

El backend de MolDesign debe estar iniciado para ejecutar herramientas reales.
No necesitas clonar ni instalar todo su árbol científico dentro de este repo.

## Configuración

| Variable | Uso |
|---|---|
| `MOLDESIGN_BASE_URL` | `http://127.0.0.1:8000` por defecto |
| `MOLDESIGN_TOKEN` | Token de sesión de tu propia cuenta MolDesign |
| `MOLDESIGN_ALLOW_REMOTE` | `1` sólo si autorizas un backend remoto HTTPS |
| `MODEL_API_KEY` | Clave de Meta Model API para planificar con Muse Spark |

Los tokens se leen en el proceso. No se incluyen en el plan, los resultados
ni los archivos del repositorio. No publiques `.env`.

## Primer flujo con dos etapas

1. Pedir un plan (se envía **el texto del objetivo** a Meta; no incluyas datos
   privados si no tienes autorización para compartirlos):

   ```bash
   molchat-agent plan "Lista los receptores disponibles" --out plan.json
   ```

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
- Falta validar el puente con un runtime MolDesign instalado, realizar las
  pruebas de voz extremo a extremo y desarrollar una interfaz visual propia.

Consulta [`docs/AUDITORIA.md`](docs/AUDITORIA.md) para el mapa de dependencias,
contratos y licencias; [`docs/HOJA_DE_RUTA.md`](docs/HOJA_DE_RUTA.md) para los pasos
pendientes.

**Licencia:** GNU GPL-3.0-or-later. Consulte `LICENSE` y `NOTICE.md`.

