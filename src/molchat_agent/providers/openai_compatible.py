"""Generic OpenAI-compatible planner (remote or loopback-local).

Design reimplemented from MolDesign's ``openai_provider.py`` without copying
it. Differences are deliberate and safer: no third-party defaults (no
surprise calls to Groq/OpenAI), remote requires HTTPS, and locality is
computed from the URL host — a loopback ``base_url`` is local even though
the provider id is cloud-shaped.
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator
from urllib.parse import urlsplit

import httpx

from ..config import load_config
from ..plan import Plan
from .base import (
    CatalogEntry,
    ChatEvent,
    HealthCheckResult,
    HealthStatus,
    ProviderConfig,
    ProviderInfo,
    TurnContext,
    plan_from_content,
    read_only_catalog,
    readonly_plan_schema,
)

LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def is_loopback_url(url: str) -> bool:
    try:
        return (urlsplit(url).hostname or "").lower() in LOOPBACK_HOSTS
    except ValueError:
        return False


class OpenAICompatibleProvider:
    """Chat-completions planner against any OpenAI-compatible endpoint."""

    id = "openai-compatible"

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None, temperature: float = 0.1,
                 client: httpx.AsyncClient | None = None) -> None:
        config = load_config()
        resolved_base = (base_url if base_url is not None
                         else config.openai_compat_base_url).strip().rstrip("/")
        if resolved_base:
            scheme = (urlsplit(resolved_base).scheme or "").lower()
            if is_loopback_url(resolved_base):
                self.locality: str = "local"
            else:
                if scheme != "https":
                    raise ValueError(
                        "Un endpoint remoto exige HTTPS; loopback para local.")
                self.locality = "remote"
        else:
            # Unknown destination: fail closed until configured.
            self.locality = "remote"
        self.config = ProviderConfig(
            api_key=api_key if api_key is not None else (config.openai_compat_api_key or ""),
            base_url=resolved_base,
            model=model if model is not None else config.openai_compat_model,
            temperature=temperature,
        )
        self._client = client
        self._owns_client = client is None

    @property
    def _http(self) -> httpx.AsyncClient:
        """Transport, created on first use (fast builds, no leaks)."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0, trust_env=False)
        return self._client

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            name="OpenAI-compatible",
            description="Cualquier endpoint estilo OpenAI (nube o loopback local).",
            requires_api_key=self.locality == "remote",
            requires_base_url=True,
        )

    async def __aenter__(self) -> "OpenAICompatibleProvider":
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    async def health(self) -> HealthCheckResult:
        if not self.config.base_url:
            return HealthCheckResult(
                status=HealthStatus.NOT_CONFIGURED,
                message="Falta OPENAI_COMPAT_BASE_URL.")
        if self.locality == "remote" and not self.config.api_key:
            return HealthCheckResult(
                status=HealthStatus.NO_API_KEY,
                message="Falta OPENAI_COMPAT_API_KEY para el endpoint remoto.")
        start = time.monotonic()
        try:
            response = await self._http.get(
                f"{self.config.base_url}/models", headers=self._headers(),
                timeout=httpx.Timeout(5.0, connect=1.0))
        except (httpx.RequestError, ValueError) as exc:
            return HealthCheckResult(
                status=HealthStatus.CONNECTION_ERROR,
                message=f"No responde en {self.config.base_url}: {exc}",
                latency_ms=(time.monotonic() - start) * 1000)
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        if response.status_code == 200:
            return HealthCheckResult(
                status=HealthStatus.OK,
                message=f"Responde en {self.config.base_url}.", latency_ms=elapsed_ms)
        if response.status_code in (401, 403):
            return HealthCheckResult(
                status=HealthStatus.NO_API_KEY,
                message=f"El endpoint rechazó la clave (HTTP {response.status_code}).",
                latency_ms=elapsed_ms)
        return HealthCheckResult(
            status=HealthStatus.CONNECTION_ERROR,
            message=f"El endpoint devolvió HTTP {response.status_code}.",
            latency_ms=elapsed_ms)

    def _payload(self, goal: str, catalog: list[CatalogEntry] | None) -> dict[str, Any]:
        safe_tools = read_only_catalog(catalog)
        return {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "messages": [
                {"role": "system", "content": (
                    "Eres un planificador de química computacional. Propón SOLO una secuencia "
                    "de herramientas enumeradas en el catálogo. Nunca inventes IDs, SMILES, "
                    "datos de receptores ni resultados. Devuelve el plan como JSON con la "
                    "estructura indicada."
                )},
                {"role": "user", "content": json.dumps(
                    {"goal": goal, "capabilities": safe_tools}, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "molchat_readonly_plan", "strict": False,
                "schema": readonly_plan_schema(safe_tools),
            }},
        }

    async def plan(self, goal: str, catalog: list[CatalogEntry] | None = None) -> Plan:
        if not self.config.base_url:
            raise ValueError("Falta OPENAI_COMPAT_BASE_URL; nada que contactar.")
        if self.locality == "remote" and not self.config.api_key:
            raise ValueError("Falta OPENAI_COMPAT_API_KEY para el endpoint remoto.")
        if not self.config.model:
            raise ValueError("Falta OPENAI_COMPAT_MODEL; el endpoint no sabe qué servir.")
        try:
            response = await self._http.post(
                f"{self.config.base_url}/chat/completions",
                json=self._payload(goal, catalog), headers=self._headers())
            if response.status_code >= 400 or response.is_redirect:
                raise ProviderError(
                    f"El endpoint devolvió HTTP {response.status_code}.")
            content = response.json()["choices"][0]["message"]["content"]
            allowed = [t["name"] for t in read_only_catalog(catalog)]
            return plan_from_content(content, goal, f"openai-compatible:{self.config.model}",
                                     allowed)
        except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("El proveedor no entregó un plan válido.") from exc

    async def chat(self, turn: TurnContext) -> AsyncIterator[ChatEvent]:
        if not self.config.base_url:
            raise ValueError("Falta OPENAI_COMPAT_BASE_URL; nada que contactar.")
        if self.locality == "remote" and not self.config.api_key:
            raise ValueError("Falta OPENAI_COMPAT_API_KEY para el endpoint remoto.")
        if not self.config.model:
            raise ValueError("Falta OPENAI_COMPAT_MODEL; el endpoint no sabe qué servir.")
        messages = turn.messages or [{"role": "user", "content": turn.text}]
        try:
            response = await self._http.post(
                f"{self.config.base_url}/chat/completions",
                json={"model": self.config.model, "messages": messages,
                      "temperature": self.config.temperature,
                      "max_tokens": self.config.max_tokens},
                headers=self._headers())
            if response.status_code >= 400 or response.is_redirect:
                raise ProviderError(
                    f"El endpoint devolvió HTTP {response.status_code}.")
            content = response.json()["choices"][0]["message"]["content"]
        except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("El proveedor no entregó respuesta de chat.") from exc
        yield ChatEvent(type="token", text=content)
        yield ChatEvent(type="done", done=True)
