"""Sidecar process state: single-user, pinned to the host identity (PD-04).

Scope (declared, MP-06): one process serves ONE account — the ``sub`` of the
first authenticated call pins the process. A different account gets 403 and
must restart the sidecar (or reconnect with its own process). Revoked
sessions stay revoked until restart. UI reconnects just work: auth is
stateless per request, nothing lives in the observer connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..conversation.engine import ConversationEngine
from ..conversation.memory import MemoryStore
from ..conversation.tools import ToolBackend
from ..providers.registry import ProviderRegistry
from ..voice.stt import SpeechToText
from .executions import ExecutionManager


class AccountMismatch(ValueError):
    """This sidecar process is already bound to another account."""


@dataclass
class ServerState:
    secret: bytes
    registry: ProviderRegistry
    memory: MemoryStore
    backend: ToolBackend
    allowed_origins: tuple[str, ...] = ()
    provider_id: str | None = None
    executions: ExecutionManager | None = None
    stt: SpeechToText | None = None
    user_id: str | None = None
    revoked: set[str] = field(default_factory=set)

    def pin_user(self, sub: str) -> None:
        """Bind the process to the first account; reject any other."""
        if self.user_id is None:
            self.user_id = sub
            return
        if self.user_id != sub:
            raise AccountMismatch(
                "este sidecar ya sirve a otra cuenta; "
                "reinícialo para cambiar de identidad")

    def engine_for(self, sub: str) -> ConversationEngine:
        return ConversationEngine(
            registry=self.registry, backend=self.backend, memory=self.memory,
            user_id=sub, provider_id=self.provider_id or self.registry.active_id)

    def revoke(self, jti: str) -> None:
        self.revoked.add(jti)

    def is_revoked(self, jti: str) -> bool:
        return jti in self.revoked

    def status(self) -> dict[str, Any]:
        return {"account_bound": self.user_id is not None,
                "revoked_sessions": len(self.revoked)}
