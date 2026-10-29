"""Sidecar HTTP API: health, chat SSE, conversations, plans, executions.

Security posture (MP-06): loopback bind (enforced by ``serve``), Bearer
session per call, scopes per endpoint, Origin allowlist with CORS echo,
Host allowlist against DNS rebinding, JSON/audio payload caps. Only
``/v1/health`` and ``/v1/version`` answer without credentials. Errors are
JSON ``{"error": ...}``; unexpected failures never leak internals.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from .. import __version__
from ..bridge import BridgeError
from ..conversation.memory import Conversation, ConversationNotFound, PersistenciaFallida
from ..conversation.case_selection import select_case
from ..conversation.intents import classify
from ..plan import Plan
from ..providers.base import ProviderDisabled, ProviderError
from ..providers.registry import ConsentDenied
from ..tools import PlanValidationError, capability, catalog
from ..voice.stt import AUDIO_LIMIT, LANGS, STTError
from .auth import AuthError, Session, parse_bearer, verify
from .events import SSE_HEADERS, encode_event
from .executions import TERMINAL as EXEC_TERMINAL
from .state import AccountMismatch, ServerState

CONTRACT = "moldesign.molchat/1"

MAX_JSON_BODY = 1_000_000
MAX_CHAT_TEXT = 8000
MAX_MESSAGES_PER_CONVERSATION = 200
EXEC_SNAPSHOT_S = 0.5
EXEC_SNAPSHOT_LIMIT = 720  # 6 minutes of snapshots, then the stream closes
MAX_STATIC_FILE = 20_000_000

_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".map": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
    ".woff2": "font/woff2",
}

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def _origin_allowed(origin: str, allowed: tuple[str, ...]) -> bool:
    if origin in allowed:
        return True
    try:
        host = urlsplit(origin).hostname or ""
    except ValueError:
        return False
    return host.lower() in LOOPBACK_HOSTS


def create_app(state: ServerState, *, allowed_hosts: tuple[str, ...] | None = None,
               ui_dist: Path | None = None) -> Any:
    """Build the sidecar ASGI app (Starlette routes behind the host/origin guard)."""
    hosts = frozenset(allowed_hosts) if allowed_hosts is not None \
        else frozenset({"127.0.0.1", "localhost", "::1"})

    def require(*scopes: str):  # type: ignore[no-untyped-def]
        async def dependency(request: Request) -> Session:
            token = parse_bearer(request.headers.get("authorization"))
            if token is None:
                raise HTTPException(401, "falta la sesión del host")
            try:
                session = verify(state.secret, token)
            except AuthError as exc:
                raise HTTPException(401, str(exc)) from exc
            if state.is_revoked(session.jti):
                raise HTTPException(401, "sesión revocada")
            try:
                state.pin_user(session.sub)
            except AccountMismatch as exc:
                raise HTTPException(403, str(exc)) from exc
            if not session.allows(*scopes):
                raise HTTPException(403, "permisos insuficientes")
            return session

        return dependency

    need_read = require("read")
    need_chat = require("chat")
    need_plan = require("plan")
    need_cancel = require("cancel")
    need_transcribe = require("transcribe")

    def platform_token(request: Request) -> str | None:
        """The request's identity for platform calls, in hosted mode only.

        Standalone keeps its fixed configured token; hosted forwards the
        Bearer the host minted (the platform accepts it as identity).
        Called after the scope check, so the Bearer is already verified.
        """
        if not state.hosted:
            return None
        return parse_bearer(request.headers.get("authorization"))

    async def read_json(request: Request) -> Any:
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            raise HTTPException(400, "longitud no válida")
        if length > MAX_JSON_BODY:
            raise HTTPException(413, "cuerpo superior a 1 MB")
        try:
            body = await request.body()
        except Exception as exc:
            raise HTTPException(400, "no se pudo leer el cuerpo") from exc
        if len(body) > MAX_JSON_BODY:
            raise HTTPException(413, "cuerpo superior a 1 MB")
        if not body:
            return {}
        try:
            return json.loads(body)
        except ValueError as exc:
            raise HTTPException(400, "JSON no válido") from exc

    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "version": __version__, "contract": CONTRACT})

    async def version(_request: Request) -> JSONResponse:
        return JSONResponse({"molchat": __version__, "contract": CONTRACT,
                             "plan_schemas": ["/1", "/2"],
                             "stt": "platform" if state.hosted and state.bridge is not None else _stt_kind(state.stt)})

    async def get_catalog(request: Request) -> JSONResponse:
        await need_read(request)
        return JSONResponse([c.as_catalog_entry() for c in catalog().values()])

    def summarize(conv: Conversation) -> dict[str, Any]:
        return {"id": conv.id, "summary": conv.summary, "updated_at": conv.updated_at,
                "message_count": len(conv.messages)}

    async def create_conversation(request: Request) -> JSONResponse:
        session = await need_chat(request)
        conv_id = state.memory.create_conversation(session.sub)
        return JSONResponse({"id": conv_id}, status_code=201)

    async def list_conversations(request: Request) -> JSONResponse:
        session = await need_chat(request)
        return JSONResponse(
            [summarize(c) for c in state.memory.list_conversations(session.sub)])

    async def get_conversation(request: Request) -> JSONResponse:
        session = await need_chat(request)
        conv = state.memory.get_conversation(request.path_params["conv_id"], session.sub)
        if conv is None:
            return _error(404, "conversación no encontrada")
        messages = conv.messages[-MAX_MESSAGES_PER_CONVERSATION:]
        payload = summarize(conv)
        payload["messages"] = messages
        payload["truncated"] = len(conv.messages) > len(messages)
        return JSONResponse(payload)

    async def delete_conversation(request: Request) -> JSONResponse:
        session = await need_chat(request)
        deleted = state.memory.delete_conversation(
            request.path_params["conv_id"], session.sub)
        if not deleted:
            return _error(404, "conversación no encontrada")
        return JSONResponse({"deleted": True})

    async def chat(request: Request) -> StreamingResponse:
        session = await need_chat(request)
        payload = await read_json(request)
        if not isinstance(payload, dict):
            return _error(400, "el cuerpo debe ser un objeto")
        text = payload.get("text", "")
        if not isinstance(text, str) or not text.strip():
            return _error(400, "texto vacío")
        if len(text) > MAX_CHAT_TEXT:
            return _error(413, "texto superior a 8000 caracteres")
        conv_id = payload.get("conversation_id")
        if conv_id is not None and not isinstance(conv_id, str):
            return _error(400, "conversation_id no válido")
        registro = await state.registro_de_turno(platform_token(request))
        engine = state.engine_for(session.sub, platform_token(request), registro)
        if conv_id is None:
            conv_id = state.memory.create_conversation(session.sub)
        elif state.memory.get_conversation(conv_id, session.sub) is None:
            return _error(404, "conversación no encontrada")

        async def stream() -> AsyncIterator[bytes]:
            yield encode_event({"type": "conversation", "id": conv_id})
            try:
                if state.hosted and classify(text).name == "case_action":
                    started = time.monotonic()
                    yield encode_event({"type": "intent", "name": "case_action", "tool": "create_case"})
                    provider_id = registro.active_id
                    reason = registro.block_reason(provider_id) if provider_id else "No hay proveedor activo."
                    if reason:
                        answer = reason
                    else:
                        try:
                            selection = await select_case(registro.get(provider_id), text)
                        except (ProviderDisabled, ProviderError, ValueError, RuntimeError):
                            selection = None
                        if selection is None:
                            answer = ("No se creó ningún caso: el modelo no identificó una solicitud "
                                      "válida con un nombre explícito. Revisa el mensaje o el proveedor.")
                        else:
                            request_id = uuid.uuid4().hex
                            future = asyncio.get_running_loop().create_future()
                            state.case_requests[request_id] = (session.sub, future)
                            try:
                                yield encode_event({"type": "case_create", "request_id": request_id,
                                                    "name": selection.name})
                                try:
                                    outcome = await asyncio.wait_for(future, timeout=60)
                                except asyncio.TimeoutError:
                                    outcome = {"status": "unknown"}
                            finally:
                                state.case_requests.pop(request_id, None)
                            if outcome.get("status") == "created":
                                answer = f'Se creó el caso "{selection.name}" en MolDesign.'
                            elif outcome.get("status") == "exists":
                                answer = f'Ya existe un caso o carpeta con el nombre "{selection.name}". No se creó ni se modificó otro caso.'
                            elif outcome.get("status") == "failed":
                                answer = "MolDesign no pudo crear el caso. Revisa el estado de la aplicación."
                            else:
                                answer = "No pude confirmar el resultado. Revisa la lista de casos antes de reintentar."
                    try:
                        state.memory.add_message(conv_id, session.sub, "user", text)
                        state.memory.add_message(conv_id, session.sub, "assistant", answer)
                    except PersistenciaFallida:
                        answer += " No se pudo guardar el turno en el historial."
                    yield encode_event({"type": "result", "result": {
                        "text": answer, "intent": "case_action", "evidence": [],
                        "latency_ms": int((time.monotonic() - started) * 1000),
                        "used_llm": bool(provider_id and not reason),
                        "verified_values": [],
                    }})
                    return
                async for event in engine.turn_stream(conv_id, text):
                    yield encode_event(_public_event(event))
            except ConversationNotFound:
                yield encode_event({"type": "error",
                                    "error": "conversación no encontrada"})
            except Exception:  # noqa: BLE001 - stream must end cleanly, never leak
                yield encode_event({"type": "error", "error": "error interno del turno"})

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers=dict(SSE_HEADERS))

    async def case_result(request: Request) -> JSONResponse:
        session = await need_chat(request)
        pending = state.case_requests.get(request.path_params["request_id"])
        if pending is None or pending[0] != session.sub or pending[1].done():
            return _error(404, "solicitud no encontrada")
        payload = await read_json(request)
        if not isinstance(payload, dict) or set(payload) != {"status"} or payload["status"] not in ("created", "exists", "failed", "unknown"):
            return _error(400, "resultado no válido")
        pending[1].set_result({"status": payload["status"]})
        return JSONResponse({"accepted": True})

    async def revoke(request: Request) -> JSONResponse:
        token = parse_bearer(request.headers.get("authorization"))
        if token is None:
            raise HTTPException(401, "falta la sesión del host")
        try:
            session = verify(state.secret, token)
        except AuthError as exc:
            raise HTTPException(401, str(exc)) from exc
        state.revoke(session.jti)
        return JSONResponse({"revoked": True})

    async def propose_plan(request: Request) -> JSONResponse:
        await need_plan(request)
        payload = await read_json(request)
        if not isinstance(payload, dict):
            return _error(400, "el cuerpo debe ser un objeto")
        goal = payload.get("goal", "")
        if not isinstance(goal, str) or not goal.strip():
            return _error(400, "objetivo vacío")
        provider_id = payload.get("provider_id") or state.provider_id
        if provider_id is not None and not isinstance(provider_id, str):
            return _error(400, "provider_id no válido")
        try:
            registro = await state.registro_de_turno(platform_token(request))
            plan = await registro.plan(goal, provider_id=provider_id)
        except (ConsentDenied, ProviderDisabled) as exc:
            raise HTTPException(403, str(exc)) from exc
        except ProviderError as exc:
            raise HTTPException(502, f"el proveedor falló: {exc}") from exc
        return JSONResponse({"plan": plan.as_dict(), "digest": plan.digest})

    async def submit_execution(request: Request) -> JSONResponse:
        session = await need_plan(request)
        if state.executions is None:
            return _error(503, "ejecución no disponible en este sidecar")
        payload = await read_json(request)
        if not isinstance(payload, dict) or not isinstance(payload.get("plan"), dict):
            return _error(400, "se requiere un plan como objeto")
        try:
            plan = Plan.from_dict(payload["plan"])
        except PlanValidationError as exc:
            return _error(400, f"plan no válido: {exc}")
        if any(capability(s.capability).risk != "read" for s in plan.steps) \
                and not session.allows("approve"):
            raise HTTPException(403, "el plan tiene pasos sensibles: falta permiso approve")
        approved = payload.get("approved_steps", [])
        if not isinstance(approved, list) or not all(isinstance(s, str) for s in approved):
            return _error(400, "approved_steps debe ser una lista de ids")
        digest = payload.get("approval_digest")
        if digest is not None and not isinstance(digest, str):
            return _error(400, "approval_digest no válido")
        record = state.executions.submit(
            plan, approval_digest=digest, approved_steps=set(approved),
            platform_token=platform_token(request))
        return JSONResponse(state.executions.view(record), status_code=202)

    async def get_execution(request: Request) -> JSONResponse:
        await need_read(request)
        if state.executions is None:
            return _error(503, "ejecución no disponible en este sidecar")
        record = state.executions.get(request.path_params["exec_id"])
        if record is None:
            return _error(404, "ejecución no encontrada")
        return JSONResponse(state.executions.view(record))

    async def execution_events(request: Request) -> StreamingResponse:
        await need_read(request)
        if state.executions is None:
            return _error(503, "ejecución no disponible en este sidecar")  # type: ignore[return-value]
        record = state.executions.get(request.path_params["exec_id"])
        if record is None:
            return _error(404, "ejecución no encontrada")  # type: ignore[return-value]
        manager = state.executions

        async def stream() -> AsyncIterator[bytes]:
            for _ in range(EXEC_SNAPSHOT_LIMIT):
                current = manager.get(record.id)
                assert current is not None
                yield encode_event({"type": "snapshot", **manager.view(current)})
                if current.state in EXEC_TERMINAL:
                    return
                await asyncio.sleep(EXEC_SNAPSHOT_S)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers=dict(SSE_HEADERS))

    async def cancel_execution(request: Request) -> JSONResponse:
        await need_cancel(request)
        if state.executions is None:
            return _error(503, "ejecución no disponible en este sidecar")
        changed, detail = await state.executions.cancel(
            request.path_params["exec_id"],
            platform_token(request))
        if detail == "not-found":
            return _error(404, "ejecución no encontrada")
        return JSONResponse({"cancelled": changed, "detail": detail})

    async def transcribe(request: Request) -> JSONResponse:
        await need_transcribe(request)
        hosted_platform = state.hosted and state.bridge is not None
        if state.stt is None and not hosted_platform:
            return _error(503, "transcripción no disponible en este sidecar")
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("audio/"):
            return _error(415, "se requiere audio (audio/wav u otro audio/*)")
        lang = request.query_params.get("lang", "es")
        if lang not in LANGS:
            return _error(400, "esta primera integración admite es/en")
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return _error(400, "longitud no válida")
        if length > AUDIO_LIMIT:
            return _error(413, "audio superior a 15 MB")
        audio = await request.body()
        if not audio:
            return _error(400, "audio vacío")
        if len(audio) > AUDIO_LIMIT:
            return _error(413, "audio superior a 15 MB")
        if hosted_platform:
            # Platform STT first, with the request's identity; local chain
            # stays the fallback (same order as standalone, honest identity).
            assert state.bridge is not None
            try:
                text = await state.bridge.transcribe_local(
                    bytes(audio), lang=lang, token=platform_token(request))
            except ValueError as exc:
                return _error(400, str(exc))
            except BridgeError as exc:
                if state.stt is None:
                    raise HTTPException(502, f"la transcripción falló: {exc}") from exc
            else:
                return JSONResponse({"text": text, "lang": lang})
        try:
            assert state.stt is not None
            text = await state.stt.transcribe(bytes(audio), lang=lang)
        except ValueError as exc:
            return _error(400, str(exc))
        except (BridgeError, STTError) as exc:
            raise HTTPException(502, f"la transcripción falló: {exc}") from exc
        return JSONResponse({"text": text, "lang": lang})

    def static_file(name: str) -> Response:
        if ui_dist is None:
            return JSONResponse(
                {"message": "API del sidecar; construye ui/ (`npm run build`) "
                            "para servir la interfaz aquí.",
                 "health": "/v1/health"}, status_code=200)
        root = ui_dist.resolve()
        target = (root / name).resolve() if name else root / "index.html"
        if target != root and root not in target.parents:
            return _error(404, "no encontrado")  # type: ignore[return-value]
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file() or target.stat().st_size > MAX_STATIC_FILE:
            return _error(404, "no encontrado")  # type: ignore[return-value]
        media = _STATIC_TYPES.get(target.suffix.lower(), "application/octet-stream")
        return Response(target.read_bytes(), media_type=media,
                        headers={"Cache-Control": "no-store"})

    async def ui_root(_request: Request) -> Response:
        return static_file("")

    async def ui_asset(request: Request) -> Response:
        return static_file(request.path_params["path"])

    async def http_error(_request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, HTTPException)
        return _error(exc.status_code, str(exc.detail))

    async def unhandled(_request: Request, _exc: Exception) -> JSONResponse:
        return _error(500, "error interno")

    app = Starlette(
        routes=[
            Route("/v1/health", health, methods=["GET"]),
            Route("/v1/version", version, methods=["GET"]),
            Route("/v1/catalog", get_catalog, methods=["GET"]),
            Route("/v1/conversations", create_conversation, methods=["POST"]),
            Route("/v1/case-requests/{request_id}/result", case_result, methods=["POST"]),
            Route("/v1/conversations", list_conversations, methods=["GET"]),
            Route("/v1/conversations/{conv_id}", get_conversation, methods=["GET"]),
            Route("/v1/conversations/{conv_id}", delete_conversation, methods=["DELETE"]),
            Route("/v1/chat", chat, methods=["POST"]),
            Route("/v1/session/revoke", revoke, methods=["POST"]),
            Route("/v1/plans", propose_plan, methods=["POST"]),
            Route("/v1/executions", submit_execution, methods=["POST"]),
            Route("/v1/executions/{exec_id}", get_execution, methods=["GET"]),
            Route("/v1/executions/{exec_id}/events", execution_events, methods=["GET"]),
            Route("/v1/executions/{exec_id}/cancel", cancel_execution, methods=["POST"]),
            Route("/v1/transcribe", transcribe, methods=["POST"]),
            Route("/", ui_root, methods=["GET"]),
            Route("/{path:path}", ui_asset, methods=["GET"]),
        ],
        exception_handlers={HTTPException: http_error, Exception: unhandled},
    )
    return _Guard(app, state, hosts)


class _Guard:
    """Host/Origin enforcement + CORS echo, as pure ASGI (no version coupling)."""

    def __init__(self, app: Any, state: ServerState, hosts: frozenset[str]) -> None:
        self._app = app
        self._state = state
        self._hosts = hosts

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1")
                   for k, v in scope.get("headers", [])}
        host = _hostname(headers.get("host", ""))
        if host not in self._hosts:
            await _error(403, "host no permitido")(scope, receive, send)
            return
        origin = headers.get("origin")
        if origin is not None and not _origin_allowed(origin, self._state.allowed_origins):
            await _error(403, "origen no permitido")(scope, receive, send)
            return
        if scope.get("method") == "OPTIONS":
            response = JSONResponse({}, status_code=204)
            self._add_cors(response.headers, origin)
            await response(scope, receive, send)
            return
        await self._app(scope, receive, self._cors_sender(send, origin))

    def _cors_sender(self, send: Any, origin: str | None):  # type: ignore[no-untyped-def]
        async def sender(message: dict) -> None:
            if message["type"] == "http.response.start" and origin is not None \
                    and _origin_allowed(origin, self._state.allowed_origins):
                headers = dict(message.get("headers", []))
                headers[b"access-control-allow-origin"] = origin.encode("latin-1")
                headers[b"vary"] = b"Origin"
                headers[b"access-control-allow-headers"] = b"authorization, content-type"
                headers[b"access-control-allow-methods"] = b"GET, POST, DELETE, OPTIONS"
                message = {**message, "headers": list(headers.items())}
            await send(message)

        return sender

    def _add_cors(self, headers: Any, origin: str | None) -> None:
        if origin is not None and _origin_allowed(origin, self._state.allowed_origins):
            headers["Access-Control-Allow-Origin"] = origin
            headers["Vary"] = "Origin"
            headers["Access-Control-Allow-Headers"] = "authorization, content-type"
            headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"


def _hostname(value: str) -> str:
    try:
        return (urlsplit("//" + value).hostname or "").lower()
    except ValueError:
        return ""


def _stt_kind(stt: Any) -> str:
    """Declared transcription backend: local (default), cloud, or none."""
    if stt is None:
        return "none"
    from ..voice.cloud_stt import CloudSTT

    return "cloud" if isinstance(stt, CloudSTT) else "local"


def _public_event(event: dict[str, Any]) -> dict[str, Any]:
    """Serialize an engine event (Evidence/set are not JSON-native)."""
    if event.get("type") != "result":
        return event
    result = event["result"]
    return {"type": "result", "result": {
        "text": result.text,
        "intent": result.intent_name,
        "evidence": [{"tool": e.tool, "label": e.label,
                      "epistemic_class": e.epistemic_class.value,
                      "source": e.source, "values": e.values, "error": e.error}
                     for e in result.evidence],
        "latency_ms": result.latency_ms,
        "used_llm": result.used_llm,
        "verified_values": sorted(result.verified_values),
    }}
