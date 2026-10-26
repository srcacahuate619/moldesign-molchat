# Auditoría de extracción — MolChat Agent, 26-10-2026

## Decisión y estado

- **Destino propuesto:** `srcacahuate619/moldesign-molchat`, repositorio nuevo.
  Al comenzar esta fase no existía remotamente. Este árbol es una entrega local,
  no una publicación en GitHub.
- **Licencia elegida por el propietario:** GPL-3.0-or-later (decisión
  2026-10-26, aplicada en la Fase 0: `LICENSE` íntegro desde Molcy,
  `pyproject.toml` con `license = "GPL-3.0-or-later"`).
- **Modo:** núcleo independiente, conectado por HTTP al backend FastAPI ya
  existente en MolDesign. No hay fork ni traslado del runtime científico.
- **Fuente auditada:** `srcacahuate619/moldesign-app`, rama pública `main`,
  código consultado el 2026-10-26. Commit de referencia fijado en la Fase 0:
  `66ff524334267c56558b7a3cce94cb919edbad2e` (rama `codex/release-hygiene`,
  verificado el 2026-10-26; asunto: `FEP-06-HUM: contacto para inscribirse y
  entregar`). La matriz formal de compatibilidad usará este commit.
- **Estado de validación:** revisión estática de endpoints, contratos y
  documentos. Las pruebas automatizadas de este repo usan dobles HTTP, no
  son una validación científica de Vina ni una integración con MolDesign real.

## Decisión de producto y patrón Molcy (Fase 0, 2026-10-26)

Un solo MolChat con fuente única en este repositorio público. MolDesign lo
vendoriza fijado por manifiesto y lo ejecuta como programa independiente
(sidecar) por HTTP, igual que hace con Molcy (ADR 92/95 de MolDesign): incluido
por defecto, opcional en runtime y reemplazable por una versión externa
compatible. El MolChat interno de MolDesign se congela, alcanza paridad con el
nuevo y se borra; no se mantienen dos MolChats. Planificación vigente en
`PLAN.md` (documento interno); `docs/HOJA_DE_RUTA.md` queda supersedida.

## Contratos de integración identificados

| Nuevo capability | MolDesign FastAPI | Riesgo | Observaciones |
|---|---|---|---|
| `list_targets` | `GET /targets/` | Lectura | Filtra targets inaccesibles al usuario |
| `check_preflight` | `POST /evaluation/preflight` | Lectura lógica | No lanza docking; acepta SMILES y PDB |
| `list_evaluations` | `GET /history/evaluations` | Lectura privada | Exige sesión; historial del propietario |
| `evaluation_status` | `GET /evaluation/status/{task_id}` | Lectura | El servidor verifica acceso al trabajo |
| `get_docking_proposal` | `GET /ai/proposals/{proposal_id}` | Lectura privada | Exige sesión |
| `approve_docking_proposal` | `POST /ai/proposals/{proposal_id}/approve` | Ejecución | Identidad y `proposal_hash` revalidados por servidor |
| `transcribe-local` | `POST /ai/speech-to-text?lang=es` | Entrada de audio | Endpoint local de Whisper, requiere sesión |

**No exponemos** `/evaluation/submit` como herramienta del modelo. Ese endpoint
permite introducir una evaluación directamente y omitir la revisión humana del
flujo MolChat. Se conserva el patrón que ya existe en MolDesign: propuesta,
revisión de una huella concreta y aprobación posterior por servidor.

### Componentes existentes revisados

| Ruta de MolDesign | Decisión |
|---|---|
| `backend/services/ai/chat_service.py` | Conservar en MolDesign; no extraer ni duplicar |
| `backend/services/ai/tool_registry.py` | Inspiración de contrato; nuevo allowlist HTTP independiente |
| `backend/services/ai/propuestas_de_docking.py` | Servidor sigue siendo dueño de la propuesta |
| `backend/services/ai/providers/registry.py` | Configuración de proveedores actual sigue en la app |
| `backend/services/ai/tools/*.py` | No copiar: dependencia del runtime, DB e identidad |
| `backend/api/routers/ai.py` | Superficie HTTP de voz, chat y aprobación existente |
| `backend/api/routers/evaluation.py` | Preflight, estado y tareas |
| `frontend/components/ai/ChatPanel.tsx` | Reutilización visual futura mediante integración, no copiado ahora |
| `frontend/hooks/useSpeechRecognition.ts` | UI de voz existente; primer bridge usa endpoint local |

Referencias de la auditoría: [MolChat v3](https://github.com/srcacahuate619/moldesign-app/blob/main/docs/34_MOLCHAT_V3.md),
[gate de seguridad de MolChat](https://github.com/srcacahuate619/moldesign-app/blob/main/docs/67_GATE_MOLCHAT.md),
[propuestas de docking](https://github.com/srcacahuate619/moldesign-app/blob/main/backend/services/ai/propuestas_de_docking.py),
[router AI](https://github.com/srcacahuate619/moldesign-app/blob/main/backend/api/routers/ai.py),
[router de evaluación](https://github.com/srcacahuate619/moldesign-app/blob/main/backend/api/routers/evaluation.py).

## Dictamen de licencias

| Fuente | Licencia declarada | Uso por MolChat Agent | Dictamen inicial |
|---|---|---|---|
| `moldesign-app` | PolyForm Noncommercial 1.0.0 | API HTTP | No se copia código ni se relicencia contenido |
| `moldesign-molcy` | GPL-3.0-or-later | Texto estándar de LICENSE | No se incorpora código funcional |
| Código nuevo de `moldesign-molchat` | GPL-3.0-or-later | Núcleo del agente | Debe conservar avisos en todos los archivos redistribuidos |
| `httpx` 0.28.1 | BSD-3-Clause (metadatos instalados) | Dependencia de cliente HTTP | Compatibilidad preliminar; revisar avisos transitivos al distribuir |
| Meta Model API | Términos del servicio/modelo | Servicio externo opcional | No redistribuir pesos ni confundir sus términos con GPL |

**Advertencia legal técnica:** GPL y PolyForm Noncommercial no son licencias
equivalentes; no se puede afirmar que basta con cambiar el encabezado de los
archivos existentes. Si el propietario posee todos los derechos patrimoniales
de una parte, podrá decidir sobre su reutilización, pero contribuciones y
dependencias necesitan comprobación. La mera conexión por API no equivale a
copiar o enlazar automáticamente código de otro proyecto; se debe evaluar la
distribución final si se empaqueta una versión combinada.

## Fronteras de seguridad de la fase 1

1. Lista cerrada de endpoints y tipos de parámetros. Sin acceso a sistema
   de archivos, shell, URLs arbitrarias, herramientas no registradas.
2. Backend local restringido a loopback. Backend remoto sólo con HTTPS y
   opción `MOLDESIGN_ALLOW_REMOTE=1`.
3. Token MolDesign tomado de entorno. La identidad no puede ser elegida por
   el modelo; el servidor conserva su control.
4. Meta recibe únicamente el objetivo explícito del usuario y la lista de
   capacidades. Los resultados y el historial no se envían a Meta en fase 1.
5. Planificación y ejecución separadas. Las operaciones riesgosas no aparecen
   en el catálogo que se ofrece al modelo; un plan manual requiere huella y
   aprobación de cada paso sensible.
6. Informe con huella del plan, estado de cada paso y SHA-256 del JSON de su
   resultado. Esto prueba integridad local del registro, no calidad científica.
7. Ante un error, se detiene el flujo; no hay reintento automático de
   operaciones que pudieran duplicar un cálculo.

## Riesgos y trabajos abiertos

- **Integración sin comprobar:** falta ejecutar la suite contra una instalación
  real, con sesión y PDB/SMILES públicos, antes de hablar de compatibilidad
  verificada.
- **No hay bindings entre pasos:** el siguiente paso todavía no puede referirse
  automáticamente al `task_id` del anterior. En fase 1 el plan es secuencial y
  de parámetros literales; es una limitación declarada.
- **Preflight no es autorización:** el ejecutor detiene el flujo si
  `technical_blockers` está poblado o no tiene el formato esperado; sin embargo,
  falta una política por protocolo para las advertencias y las condiciones
  `not_evaluated`. Sólo una validación científica real puede fijarla.
- **No ejecuta Molcy ni cubre toda MolDesign:** esos conectores requieren
  diseñar interfaces versionadas sin duplicar los motores.
- **Privacidad del modelo remoto:** no enviar estructuras privadas o
  resultados del usuario a Meta por defecto. La expansión cloud debe tener
  consentimiento por destino y visibilidad de payload.
- **Faltan pruebas end-to-end y rendimiento:** los mocks no prueban GPU,
  runtime de Windows, Vina, ni transcripción en hardware real.
- **Licencias derivadas y marca:** revisar cualquier código transferido y
  metadatos de distribución antes de publicar un binario.

