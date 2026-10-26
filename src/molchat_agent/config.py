"""Centralized environment configuration.

This is the only module that reads ``os.environ`` (PLAN Fase 1, tarea 1.6).
Every other module receives explicit parameters or a :class:`MolChatConfig`.
Secrets live in memory only; they are never written to disk by this package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Mapping

HACKATHON_PROFILE = "hackathon"
DEFAULT_PROFILE = "default"
PROFILES = (HACKATHON_PROFILE, DEFAULT_PROFILE)


def _default_consents_file() -> Path:
    return Path.home() / ".molchat" / "consents.json"


@dataclass(frozen=True)
class MolChatConfig:
    """All settings, from environment with safe defaults."""

    moldesign_base_url: str = "http://127.0.0.1:8000"
    moldesign_token: str | None = None
    moldesign_allow_remote: bool = False
    profile: str = HACKATHON_PROFILE
    provider: str | None = None  # active provider override (else profile default)
    model_api_key: str | None = None  # Meta Model API
    meta_model: str = "muse-spark-1.3"
    meta_reasoning_effort: str = "medium"
    openai_compat_base_url: str = ""
    openai_compat_api_key: str | None = None
    openai_compat_model: str = ""
    llama_server_url: str = "http://127.0.0.1:8400/v1"
    llama_server_model: str = ""
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    consents_file: Path = field(default_factory=_default_consents_file)
    offline: bool = False

    def redacted(self) -> dict[str, str]:
        """Config summary safe to print: secrets become set/unset, never values."""
        def secret(value: str | None) -> str:
            return "set" if value else "unset"

        return {
            "moldesign_base_url": self.moldesign_base_url,
            "moldesign_token": secret(self.moldesign_token),
            "moldesign_allow_remote": str(self.moldesign_allow_remote),
            "profile": self.profile,
            "provider": self.provider or "(profile default)",
            "model_api_key": secret(self.model_api_key),
            "meta_model": self.meta_model,
            "meta_reasoning_effort": self.meta_reasoning_effort,
            "openai_compat_base_url": self.openai_compat_base_url or "(unset)",
            "openai_compat_api_key": secret(self.openai_compat_api_key),
            "openai_compat_model": self.openai_compat_model or "(unset)",
            "llama_server_url": self.llama_server_url,
            "llama_server_model": self.llama_server_model or "(unset)",
            "ollama_url": self.ollama_url,
            "ollama_model": self.ollama_model or "(unset)",
            "consents_file": str(self.consents_file),
            "offline": str(self.offline),
        }


def load_config(env: Mapping[str, str] | None = None) -> MolChatConfig:
    """Build config from ``env`` (defaults to ``os.environ``)."""
    source = env if env is not None else os.environ

    def text(name: str, default: str = "") -> str:
        return (source.get(name, default) or "").strip()

    def secret(name: str) -> str | None:
        return text(name) or None

    def flag(name: str) -> bool:
        return text(name) == "1"

    profile = text("MOLCHAT_PROFILE", HACKATHON_PROFILE)
    if profile not in PROFILES:
        raise ValueError(f"MOLCHAT_PROFILE debe ser uno de {list(PROFILES)}: {profile!r}")

    consents = text("MOLCHAT_CONSENTS_FILE")
    return MolChatConfig(
        moldesign_base_url=text("MOLDESIGN_BASE_URL", "http://127.0.0.1:8000"),
        moldesign_token=secret("MOLDESIGN_TOKEN"),
        moldesign_allow_remote=flag("MOLDESIGN_ALLOW_REMOTE"),
        profile=profile,
        provider=text("MOLCHAT_PROVIDER") or None,
        model_api_key=secret("MODEL_API_KEY"),
        meta_model=text("META_MODEL", "muse-spark-1.3"),
        meta_reasoning_effort=text("META_REASONING_EFFORT", "medium"),
        openai_compat_base_url=text("OPENAI_COMPAT_BASE_URL"),
        openai_compat_api_key=secret("OPENAI_COMPAT_API_KEY"),
        openai_compat_model=text("OPENAI_COMPAT_MODEL"),
        llama_server_url=text("LLAMA_SERVER_URL", "http://127.0.0.1:8400/v1"),
        llama_server_model=text("LLAMA_SERVER_MODEL"),
        ollama_url=text("OLLAMA_URL", "http://127.0.0.1:11434"),
        ollama_model=text("OLLAMA_MODEL"),
        consents_file=Path(consents) if consents else _default_consents_file(),
        offline=flag("MOLCHAT_OFFLINE"),
    )
