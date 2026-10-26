"""Provider registry: profiles, consent gate, and plan routing.

Reimplemented from the design of MolDesign's ``providers/registry.py`` and
``consent.py`` without their per-user persistence: this sidecar is
single-user and keeps consent in a local JSON file. The gate rules are the
same: the destination is computed (``provider@host``), never assumed;
unknown means remote; consent is never inherited; revoking is per provider;
offline mode overrides every grant.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

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


class ConsentDenied(PermissionError):
    """A remote destination was used without consent (or while offline)."""


# Providers whose destination does not depend on base_url.
FIXED_HOSTS = {"meta": "api.meta.ai"}

# Only these hosts are "this machine". A LAN IP is another computer.
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0"})


@dataclass(frozen=True)
class Destination:
    """Where a provider would send data, and whether that leaves the machine."""

    provider_id: str
    host: str
    url: str
    is_remote: bool

    @property
    def fingerprint(self) -> str:
        """Consent identity: changing base_url changes this, never inherits."""
        return f"{self.provider_id}@{self.host}"

    def as_dict(self) -> dict[str, Any]:
        return {"provider_id": self.provider_id, "host": self.host,
                "url": self.url, "is_remote": self.is_remote,
                "fingerprint": self.fingerprint}


def resolve_destination(provider: LLMProvider) -> Destination:
    """Compute the real destination of a provider. Unknown means remote."""
    pid = provider.id
    if pid == "fake" or provider.locality == "local" and not provider.config.base_url:
        return Destination(provider_id=pid, host="", url="en esta máquina",
                           is_remote=False)
    if pid in FIXED_HOSTS:
        host = FIXED_HOSTS[pid]
        return Destination(provider_id=pid, host=host, url=f"https://{host}",
                           is_remote=True)
    url = (provider.config.base_url or "").strip()
    if not url:
        return Destination(provider_id=pid, host="(sin declarar)", url="",
                           is_remote=True)
    host = (urlsplit(url).hostname or "(sin declarar)").lower()
    return Destination(provider_id=pid, host=host, url=url,
                       is_remote=host not in LOCAL_HOSTS)


class ConsentStore:
    """Granted destinations, persisted as local JSON (no secrets inside)."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or load_config().consents_file

    @property
    def path(self) -> Path:
        return self._path

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise ValueError(f"Fichero de consentimientos corrupto: {self._path}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"Fichero de consentimientos corrupto: {self._path}")
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass  # best effort on platforms without POSIX perms
        os.replace(tmp, self._path)

    def records(self) -> dict[str, Any]:
        return self._load()

    def granted(self, fingerprint: str) -> bool:
        return fingerprint in self._load()

    def grant(self, destination: Destination) -> dict[str, Any]:
        record = {
            "provider_id": destination.provider_id,
            "host": destination.host,
            "url": destination.url,
            "granted_at": datetime.now(timezone.utc).isoformat(),
        }
        data = self._load()
        data[destination.fingerprint] = record
        self._save(data)
        return record

    def revoke(self, provider_id: str) -> list[str]:
        """Withdraw every grant for a provider (by provider, not by host)."""
        data = self._load()
        removed = [f for f, r in data.items()
                   if r.get("provider_id") == provider_id]
        for fingerprint in removed:
            del data[fingerprint]
        if removed:
            self._save(data)
        return removed


@dataclass
class ProviderStatus:
    provider_id: str
    locality: str
    destination: Destination
    enabled: bool
    consented: bool
    health: HealthCheckResult | None  # None when disabled by profile


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
    def __init__(self, *, profile: str = HACKATHON_PROFILE,
                 consents: ConsentStore | None = None,
                 offline: bool = False) -> None:
        self._profile = profile
        self._providers: dict[str, LLMProvider] = {}
        self._active_id: str | None = None
        self._consents = consents or ConsentStore()
        self._offline = offline

    @property
    def profile(self) -> str:
        return self._profile

    @property
    def consents(self) -> ConsentStore:
        return self._consents

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
        provider = self.get(provider_id or self.active_id)
        reason = self.block_reason(provider.id)
        if reason:
            raise ConsentDenied(reason)
        return await provider.plan(goal, catalog)

    def destination(self, provider_id: str) -> Destination:
        return resolve_destination(self.get(provider_id))

    def block_reason(self, provider_id: str) -> str:
        """Why this provider must not emit now, or ``""`` when it may."""
        destination = self.destination(provider_id)
        if not destination.is_remote:
            return ""
        if self._offline:
            return (f"Modo offline: el objetivo saldría hacia {destination.host}. "
                    "No se envió aunque el destino esté autorizado.")
        if self._consents.granted(destination.fingerprint):
            return ""
        return (f"El objetivo saldría de esta máquina hacia {destination.host} "
                f"({destination.fingerprint}), y no lo envié: ese destino no está "
                "autorizado. Autorízalo con `molchat-agent doctor --grant-consent "
                f"{destination.fingerprint}`, o usa un proveedor local.")

    def grant(self, provider_id: str) -> dict[str, Any]:
        destination = self.destination(provider_id)
        if not destination.is_remote:
            raise ValueError(f"{provider_id} no sale de la máquina: nada que autorizar.")
        return self._consents.grant(destination)

    def revoke(self, provider_id: str) -> list[str]:
        self.get(provider_id)  # validates known (profile still gates use)
        return self._consents.revoke(provider_id)

    async def status(self) -> list[ProviderStatus]:
        """Every provider: destination, profile, consent, and health.

        Health of a non-consented remote destination is reported as
        ``no_consent`` WITHOUT probing it: a probe would send the very
        bytes consent exists to prevent. Live probes run concurrently.
        """
        async def probe(provider: LLMProvider) -> HealthCheckResult:
            try:
                return await provider.health()
            except Exception as exc:  # noqa: BLE001 - doctor must not crash
                return HealthCheckResult(
                    status=HealthStatus.NOT_AVAILABLE,
                    message=f"health falló: {exc}")

        rows: list[ProviderStatus] = []
        to_probe: list[LLMProvider] = []
        for provider_id in self.ids():
            provider = self._providers[provider_id]
            destination = resolve_destination(provider)
            enabled = self.is_enabled(provider_id)
            consented = ((not destination.is_remote)
                         or self._consents.granted(destination.fingerprint))
            if not enabled:
                rows.append(ProviderStatus(
                    provider_id=provider_id, locality=provider.locality,
                    destination=destination, enabled=False, consented=consented,
                    health=None))
            elif destination.is_remote and not consented:
                rows.append(ProviderStatus(
                    provider_id=provider_id, locality=provider.locality,
                    destination=destination, enabled=True, consented=False,
                    health=HealthCheckResult(
                        status=HealthStatus.NO_CONSENT,
                        message=f"Destino no autorizado ({destination.fingerprint}).")))
            else:
                to_probe.append(provider)
        probed = await asyncio.gather(*(probe(p) for p in to_probe))
        for provider, health in zip(to_probe, probed):
            destination = resolve_destination(provider)
            rows.append(ProviderStatus(
                provider_id=provider.id, locality=provider.locality,
                destination=destination, enabled=True, consented=True,
                health=health))
        rows.sort(key=lambda r: r.provider_id)
        return rows


def build_registry(config: MolChatConfig | None = None,
                   clients: dict[str, httpx.AsyncClient] | None = None) -> ProviderRegistry:
    """Default registry from environment config: fake, Meta,
    OpenAI-compatible, llama-server and Ollama. ``clients`` injects
    transports (tests). A provider that rejects its own configuration is
    registered broken instead of crashing the factory.
    """
    config = config or load_config()
    transports = clients or {}
    registry = ProviderRegistry(
        profile=config.profile,
        consents=ConsentStore(config.consents_file),
        offline=config.offline)
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
