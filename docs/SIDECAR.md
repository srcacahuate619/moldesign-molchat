# Sidecar MolChat: API local + UI propia (Fase 4)

El sidecar es el MolChat utilizable sin terminal: un proceso Python en
loopback que sirve la API (`/v1/*`) y la UI construida (`ui/dist`), contra
un MolDesign local sin tocar su frontend (modo standalone, el modo demo
del hackathon) o acuñado por el host (modo integrado, Fase 6).

## Arranque en un comando (demo, sin claves)

```bash
python -m pip install -e '.[server]'
cd ui && npm install && npm run build && cd ..
MOLCHAT_PROVIDER=fake molchat-agent serve
```

Salida (la sesión se imprime **una sola vez**):

```text
MolChat sidecar en http://127.0.0.1:8771 (con UI)
Sesión standalone (se muestra una sola vez; no la registres):
  mh1.…
```

Abre la URL, pega la sesión en la pantalla de desbloqueo y úsalo: conversar,
proponer planes, aprobar por hash, seguir trabajos, dictar con push-to-talk.
Sin `MOLDESIGN_TOKEN` ni backend, la conversación determinista y los planes
funcionan; las ejecuciones contra la plataforma fallan en alto con su causa
(verificado 2026-10-27: `EXEC-FINAL: failed` con MolDesign apagado, sin
números inventados).

Con un MolDesign local y token, todo el circuito es real:

```bash
MOLDESIGN_BASE_URL=http://127.0.0.1:8000 MOLDESIGN_TOKEN=… molchat-agent serve
```

## Modos

| Modo | Secreto | Sesiones | UI |
|---|---|---|---|
| Standalone (demo) | aleatorio por arranque, nunca persistido | el sidecar acuña una (scopes completos, caducidad `MOLCHAT_SESSION_TTL_S`) | servida en `/` mismo origen |
| Host (integrado) | `MOLCHAT_HOST_SECRET` compartido | las acuña MolDesign (`sub`, scopes, `exp` corta, audiencia `molchat`) | embebida por el host; deep links §11.3 |

## API (`/v1/*`)

Salud y versión son públicas; todo lo demás exige `Authorization: Bearer`
con el permiso indicado. Errores: JSON `{"error": …}`; los 500 nunca fugan
detalles.

| Método | Ruta | Permiso | Efecto |
|---|---|---|---|
| `GET` | `/v1/health`, `/v1/version` | — | estado, versión, contrato `moldesign.molchat/1` |
| `GET` | `/v1/catalog` | `read` | capacidades con riesgo y clase epistémica |
| `GET/POST` | `/v1/conversations` | `chat` | listar / crear conversación propia |
| `GET/DELETE` | `/v1/conversations/{id}` | `chat` | leer (≤200 mensajes) / borrar |
| `POST` | `/v1/chat` | `chat` | turno por SSE (`conversation`, `intent`, `response`, `result`) |
| `POST` | `/v1/plans` | `plan` | objetivo → plan de solo lectura + huella |
| `POST` | `/v1/executions` | `plan` (+`approve` si hay pasos sensibles) | ejecuta en segundo plano (202) |
| `GET` | `/v1/executions/{id}`, `…/events` | `read` | estado/reporte, snapshots SSE |
| `POST` | `/v1/executions/{id}/cancel` | `cancel` | cancela trabajos remotos, marca `cancelling` |
| `POST` | `/v1/transcribe?lang=` | `transcribe` | audio → texto (para confirmar; nunca ejecuta) |
| `POST` | `/v1/session/revoke` | sesión válida | revoca la sesión propia |

## Seguridad (MP-06, implementado y probado)

- Bind solo loopback (`--host` no loopback se rehúsa); `Host` admitido
  verificado contra rebindings; `Origin` no loopback y no listado → 403.
- Firma HMAC, audiencia, caducidad y permisos verificados **por llamada**;
  401 sin credenciales o revocada, 403 con permisos insuficientes.
- Proceso monousuario ligado a la primera cuenta (`sub`): otra cuenta
  recibe 403 explícito (reiniciar para cambiar de identidad, PD-04).
- Topes: JSON 1 MB, texto 8000 caracteres, audio 15 MB, estáticos 20 MB.
- Desconectar al observador (cerrar SSE/pestaña) **no cancela** el cálculo;
  cancelar es la acción explícita, que cancela los trabajos remotos y deja
  el reporte final como evidencia.
- La UI no recibe el token de plataforma ni llama a MolDesign: todo pasa
  por el sidecar. Los mensajes al host son 5 acciones cerradas
  (`ui/src/lib/deeplinks.ts`); en standalone no hay host y se declara.

## Puerta de salida de la fase (verificado)

- Investigador usa la UI para pedir, revisar y aprobar un plan real sin
  terminal: conversación SSE con evidencia, planes con huella y aprobación
  por pasos, trabajos con progreso y cancelación, ajustes con idioma y
  revocación (24 tests UI en verde, `npm test` en `ui/`).
- Voz local produce un turno confirmado: push-to-talk → WAV 16 kHz mono →
  Whisper local → texto editable → turno normal (el endpoint exige sesión
  MolDesign; sin STT responde 503 honesto).
- Ningún secreto en logs ni reportes: `check_secrets.py` en verde; el token
  standalone se imprime una vez a consola del operador y vive en
  `sessionStorage`; `config.redacted()` nunca muestra valores.
- `python scripts/check_ui_build.py` en verde: el `dist` servido está al día.
