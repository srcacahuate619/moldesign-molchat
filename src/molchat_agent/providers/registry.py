"""Provider registry: profiles, active provider, and plan routing.

Reimplemented from the design of MolDesign's ``providers/registry.py``
without its per-user persistence: this sidecar is single-user and reads
configuration from :mod:`molchat_agent.config`. Per-destination consent
enforcement (tarea 1.4) extends :meth:`ProviderRegistry.plan`.
"""

from __future__ import annotations

import httpx

from ..config import HACKATHON_PROFILE, MolChatConfig, load_config
from ..plan import Plan
from .base import (
    CatalogEntry,
    HealthCheckResult,
    HealthStatus,
    LLMProvider,
    ProviderConfig,
    ProviderDisabled,
    ProviderError,
)
from .fake import FakeProvider
from .local_http import LlamaServerProvider, OllamaProvider
from .meta import MetaProvider
from .openai_compatible import OpenAICompatibleProvider

# In the hackathon profile, Meta is the only remote destination allowed.
# Local providers are always allowed; unknown means remote (fail closed).
HACKATHON_REMOTE_ALLOWLIST = frozenset({"meta"})
PROFILE_DEFAULT_PROVIDER = "meta"


class UnknownProviderError(KeyError):
    """No provider is registered under that id."""


class BrokenProvider:
    """Placeholder when a provider cannot even be constructed from config.

    Keeps ``doctor`` and ``status`` reporting instead of crashing: the
    configuration error is the report.
    """

    locality = "remote"

    def __init__(self, provider_id: str, error: str) -> None:
        self.id = provider_id
        self.config = ProviderConfig()
        self._error = error

    async def health(self) -> HealthCheckResult:
        return HealthCheckResult(
            status=HealthStatus.NOT_AVAILABLE, message=self._error)

    async def plan(self, goal: str, catalog: list[CatalogEntry] | None = None) -> Plan:
        raise ProviderError(self._error)

    async def chat(self, turn):  # pragma: no cover - never reached usefully
        raise NotImplementedError("chat en streaming llega en la Fase 2")
        yield


class ProviderRegistry:
    def __init__(self, *, profile: str = HACKATHON_PROFILE) -> None:
        self._profile = profile
        self._providers: dict[str, LLMProvider] = {}
        self._active_id: str | None = None

    @property
    def profile(self) -> str:
        return self._profile

    def register(self, provider: LLMProvider) -> None:
        self._providers[provider.id] = provider

    def ids(self) -> list[str]:
        return sorted(self._providers)

    def is_enabled(self, provider_id: str) -> bool:
        provider = self._providers[provider_id]
        if provider.locality == "local":
            return True
        if self._profile != HACKATHON_PROFILE:
            return True
        return provider_id in HACKATHON_REMOTE_ALLOWLIST

    def get(self, provider_id: str) -> LLMProvider:
        try:
            provider = self._providers[provider_id]
        except KeyError as exc:
            raise UnknownProviderError(f"Proveedor desconocido: {provider_id}") from exc
        if not self.is_enabled(provider_id):
            raise ProviderDisabled(
                f"El perfil {self._profile!r} no permite el proveedor remoto "
                f"{provider_id!r}. Usa 'meta' o un proveedor local.")
        return provider

    def set_active(self, provider_id: str) -> None:
        self.get(provider_id)  # validates known + enabled
        self._active_id = provider_id

    @property
    def active_id(self) -> str:
        if self._active_id is not None:
            return self._active_id
        if PROFILE_DEFAULT_PROVIDER in self._providers:
            return PROFILE_DEFAULT_PROVIDER
        return "fake"

    async def plan(self, goal: str, catalog: list[CatalogEntry] | None = None,
                   provider_id: str | None = None) -> Plan:
        return await self.get(provider_id or self.active_id).plan(goal, catalog)


def build_registry(config: MolChatConfig | None = None,
                   clients: dict[str, httpx.AsyncClient] | None = None) -> ProviderRegistry:
    """Default registry from environment config: fake, Meta,
    OpenAI-compatible, llama-server and Ollama. ``clients`` injects
    transports (tests). A provider that rejects its own configuration is
    registered broken instead of crashing the factory.
    """
    config = config or load_config()
    transports = clients or {}
    registry = ProviderRegistry(profile=config.profile)
    registry.register(FakeProvider())
    try:
        registry.register(MetaProvider(
            api_key=config.model_api_key,
            model=config.meta_model,
            reasoning_effort=config.meta_reasoning_effort,
            client=transports.get("meta")))
    except ValueError as exc:
        registry.register(BrokenProvider("meta", str(exc)))
    try:
        registry.register(OpenAICompatibleProvider(
            api_key=config.openai_compat_api_key,
            base_url=config.openai_compat_base_url,
            model=config.openai_compat_model,
            client=transports.get("openai-compatible")))
    except ValueError as exc:
        registry.register(BrokenProvider("openai-compatible", str(exc)))
    try:
        registry.register(LlamaServerProvider(
            base_url=config.llama_server_url,
            model=config.llama_server_model,
            client=transports.get("llama-server")))
    except ValueError as exc:
        registry.register(BrokenProvider("llama-server", str(exc)))
    try:
        registry.register(OllamaProvider(
            base_url=config.ollama_url,
            model=config.ollama_model,
            client=transports.get("ollama")))
    except ValueError as exc:
        registry.register(BrokenProvider("ollama", str(exc)))
    if config.provider is not None:
        registry.set_active(config.provider)
    return registry
