"""HTTP bridge to the *existing* MolDesign FastAPI contracts.

No filesystem, shell, or arbitrary HTTP endpoint is exposed as an agent tool.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

import httpx

from .tools import capability
from .config import load_config


class BridgeError(RuntimeError):
    """A MolDesign service call failed without exposing credentials."""


def validate_base_url(value: str, *, allow_remote: bool = False) -> str:
    url = urlsplit(value)
    local = url.hostname in ("127.0.0.1", "localhost", "::1")
    if (
        url.scheme not in ("http", "https") or not url.hostname or
        url.username or url.password or url.path not in ("", "/") or
        url.query or url.fragment
    ):
        raise ValueError("URL base MolDesign no válida")
    if not local and (not allow_remote or url.scheme != "https"):
        raise ValueError("Sólo loopback; un servidor remoto exige HTTPS y autorización expresa")
    return value.rstrip("/")


class MolDesignBridge:
    def __init__(
        self, base_url: str = "http://127.0.0.1:8000", *,
        token: str | None = None, allow_remote: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = validate_base_url(base_url, allow_remote=allow_remote)
        self._token = token
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url, timeout=30.0, follow_redirects=False,
            trust_env=False,
        )

    @classmethod
    def from_env(cls) -> "MolDesignBridge":
        config = load_config()
        return cls(
            base_url=config.moldesign_base_url,
            token=config.moldesign_token,
            allow_remote=config.moldesign_allow_remote,
        )

    async def __aenter__(self) -> "MolDesignBridge":
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def call(self, name: str, arguments: dict[str, Any]) -> Any:
        tool = capability(name)
        method, path, query, body, response_kind = tool.request(arguments)
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if tool.risk == "approval_required" and not self._token:
            raise BridgeError("Se requiere una sesión autenticada para aprobar")
        if response_kind == "sse":
            return await self._collect_sse(name, path, query, headers)
        try:
            if method == "GET":
                response = await self._client.get(path, params=query, headers=headers)
            else:
                kwargs: dict[str, Any] = {"params": query} if query else {}
                if body is not None:
                    kwargs["json"] = body
                response = await self._client.post(path, headers=headers, **kwargs)
            if response.status_code >= 400:
                raise BridgeError(f"MolDesign devolvió HTTP {response.status_code} en {name}")
            if response.is_redirect:
                raise BridgeError("MolDesign respondió con una redirección inesperada")
            if len(response.content) > 5_000_000:
                raise BridgeError("Respuesta superior al límite de 5 MB")
            if response_kind == "bytes":
                return response.content
            return response.json()
        except (httpx.RequestError, ValueError) as exc:
            raise BridgeError(f"No se pudo obtener una respuesta JSON de {name}") from exc

    async def _collect_sse(self, name: str, path: str, query: dict[str, Any],
                           headers: dict[str, str]) -> dict[str, Any]:
        """Collect SSE data events, bounded (500 events / 5 MB total)."""
        events: list[Any] = []
        total = 0
        try:
            async with self._client.stream(
                    "GET", path, params=query, headers=headers,
                    timeout=30.0) as response:
                if response.status_code >= 400:
                    raise BridgeError(f"MolDesign devolvió HTTP {response.status_code} en {name}")
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    total += len(payload)
                    if total > 5_000_000 or len(events) >= 500:
                        break
                    try:
                        events.append(json.loads(payload))
                    except ValueError:
                        events.append({"text": payload})
        except httpx.RequestError as exc:
            raise BridgeError(f"No se pudo leer el stream de {name}") from exc
        return {"events": events}

    async def transcribe_local(self, audio_bytes: bytes, *, lang: str = "es") -> str:
        """Use MolDesign's authenticated local Whisper endpoint."""
        if not self._token:
            raise BridgeError("La transcripción requiere una sesión MolDesign")
        if not audio_bytes or len(audio_bytes) > 15_000_000:
            raise ValueError("Audio vacío o superior al límite local de 15 MB")
        if lang not in ("es", "en"):
            raise ValueError("Esta primera integración admite es/en")
        try:
            response = await self._client.post(
                "/ai/speech-to-text", params={"lang": lang}, content=audio_bytes,
                headers={"Authorization": f"Bearer {self._token}",
                         "Content-Type": "audio/wav", "Accept": "application/json"},
                timeout=90.0,
            )
            if response.status_code >= 400 or response.is_redirect:
                raise BridgeError(f"Transcripción local falló (HTTP {response.status_code})")
            value = response.json().get("text", "")
            if not isinstance(value, str):
                raise BridgeError("Formato de transcripción inesperado")
            return value
        except (httpx.RequestError, ValueError) as exc:
            raise BridgeError("No se pudo transcribir el audio local") from exc

