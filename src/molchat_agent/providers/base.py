"""The LLMProvider port: one interface for local and cloud planners.

Reimplemented from the design of MolDesign's ``providers/base.py``
(``AIProvider``, health states) without importing it and without its
per-user coupling. Every provider only ever sees read-only capabilities:
filtering happens here, not in each provider.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Literal, Protocol

from ..capabilities import CAPABILITIES, PlanValidationError
from ..plan import MAX_STEPS, Plan

CatalogEntry = dict[str, Any]


class HealthStatus(Enum):
    OK = "ok"
    NO_API_KEY = "no_api_key"
    NOT_CONFIGURED = "not_configured"
    CONNECTION_ERROR = "connection_error"
    NO_TOKENS = "no_tokens"
    NOT_AVAILABLE = "not_available"
    # Unknown by rule, not by failure: probing a non-consented remote
    # destination would send the very bytes consent exists to prevent.
    NO_CONSENT = "no_consent"


@dataclass
class HealthCheckResult:
    status: HealthStatus = HealthStatus.NOT_AVAILABLE
    message: str = ""
    latency_ms: float = 0.0


@dataclass
class ProviderConfig:
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.5
    max_tokens: int = 4096
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderInfo:
    id: str
    name: str
    description: str
    requires_api_key: bool
    requires_base_url: bool
    default_base_url: str = ""
    default_model: str = ""


@dataclass
class TurnContext:
    """Minimal turn for the Fase 2 streaming chat; kept forward-compatible."""

    text: str
    catalog: list[CatalogEntry] | None = None


@dataclass
class ChatEvent:
    type: str  # "token" | "warning" | "done"
    text: str = ""
    done: bool = False


class ProviderError(RuntimeError):
    """A provider failed without producing a usable plan."""


class ProviderDisabled(RuntimeError):
    """The active profile does not allow this provider."""


def read_only_catalog(catalog: list[CatalogEntry] | None) -> list[CatalogEntry]:
    """Catalog entries a planner may see: explicit ``read`` risk only.

    ``None`` means the full local catalog. Entries without an explicit
    ``"read"`` risk are excluded (fail closed).
    """
    entries = (catalog if catalog is not None
               else [c.as_catalog_entry() for c in CAPABILITIES.values()])
    return [e for e in entries if e.get("risk") == "read"]


def readonly_plan_schema(safe_tools: list[CatalogEntry]) -> dict[str, Any]:
    """JSON schema for planner output: steps only, tools from an enum."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["steps"],
        "properties": {
            "steps": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_STEPS,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["capability", "arguments", "rationale"],
                    "properties": {
                        "capability": {
                            "type": "string",
                            "enum": [t["name"] for t in safe_tools],
                        },
                        "arguments": {"type": "object"},
                        "rationale": {"type": "string"},
                    },
                },
            },
        },
    }


def plan_from_content(content: str, goal: str, planner: str) -> Plan:
    """Parse ``{"steps": [...]}`` model output into a validated plan.

    Step ids (s1, s2, …) are assigned locally and every step is validated
    against the capability contract; unknown tools or bad arguments raise
    instead of producing a plan.
    """
    try:
        decoded = json.loads(content)
        raw_steps = decoded["steps"]
        steps = [dict(id=f"s{n}", **item)
                 for n, item in enumerate(raw_steps, 1)]
        return Plan.from_dict({"goal": goal, "steps": steps, "planner": planner})
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ProviderError(f"El proveedor no entregó un plan válido: {exc}") from exc
    except PlanValidationError as exc:
        raise ProviderError(f"El proveedor propuso pasos fuera de contrato: {exc}") from exc


class LLMProvider(Protocol):
    id: str
    locality: Literal["local", "remote"]
    config: ProviderConfig

    async def health(self) -> HealthCheckResult: ...
    async def plan(self, goal: str, catalog: list[CatalogEntry] | None = None) -> Plan: ...
    async def chat(self, turn: TurnContext) -> AsyncIterator[ChatEvent]: ...
