"""Sequential audited execution, with explicit plan-bound human approval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .bridge import MolDesignBridge
from .tools import capability
from .plan import Plan


@dataclass
class StepOutcome:
    id: str
    capability: str
    state: str
    timestamp: str
    result: Any = None
    result_sha256: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ExecutionReport:
    plan: dict[str, Any]
    plan_digest: str
    outcomes: list[StepOutcome]
    state: str

    def as_dict(self) -> dict[str, Any]:
        return {"schema": "moldesign.molchat.execution/1", "plan": self.plan,
                "plan_digest": self.plan_digest, "state": self.state,
                "outcomes": [o.as_dict() for o in self.outcomes]}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentExecutor:
    def __init__(self, bridge: MolDesignBridge) -> None:
        self.bridge = bridge

    async def execute(
        self, plan: Plan, *, approval_digest: str | None = None,
        approved_steps: set[str] | None = None,
    ) -> ExecutionReport:
        # Freeze a validated snapshot before checking the signature, avoiding
        # any mutation of the original caller's nested dict while running.
        frozen = Plan.from_dict(plan.as_dict())
        digest = frozen.digest
        outcomes: list[StepOutcome] = []
        approved_steps = approved_steps or set()

        for step in frozen.steps:
            tool = capability(step.capability)
            if tool.risk != "read":
                if approval_digest != digest or step.id not in approved_steps:
                    outcomes.append(StepOutcome(
                        step.id, step.capability, "awaiting_approval", _now(),
                        error="Requiere aprobación humana ligada a la huella del plan",
                    ))
                    return ExecutionReport(frozen.as_dict(), digest, outcomes, "awaiting_approval")
            try:
                value = await self.bridge.call(step.capability, step.arguments)
            except Exception as exc:
                # Abort on errors. Never silently re-run write-capable tools.
                outcomes.append(StepOutcome(step.id, step.capability, "failed", _now(),
                                            error=f"{type(exc).__name__}: {exc}"))
                return ExecutionReport(frozen.as_dict(), digest, outcomes, "failed")
            raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
            # Scientific decision remains in MolDesign. Its actual preflight
            # contract exposes technical_blockers, warnings and not_evaluated;
            # we stop on blockers or an unexpected contract, never assume pass.
            if step.capability == "check_preflight":
                blockers = value.get("technical_blockers") if isinstance(value, dict) else None
                if not isinstance(blockers, list):
                    outcomes.append(StepOutcome(
                        step.id, step.capability, "failed", _now(), result=value,
                        result_sha256="sha256:" + sha256(raw).hexdigest(),
                        error="MolDesign no devolvió technical_blockers como lista",
                    ))
                    return ExecutionReport(frozen.as_dict(), digest, outcomes, "failed")
                if blockers:
                    outcomes.append(StepOutcome(
                        step.id, step.capability, "blocked", _now(), result=value,
                        result_sha256="sha256:" + sha256(raw).hexdigest(),
                        error="El preflight encontró bloqueantes técnicos; requiere intervención",
                    ))
                    return ExecutionReport(frozen.as_dict(), digest, outcomes, "blocked")
            outcomes.append(StepOutcome(
                step.id, step.capability, "completed", _now(), result=value,
                result_sha256="sha256:" + sha256(raw).hexdigest(),
            ))
        return ExecutionReport(frozen.as_dict(), digest, outcomes, "completed")


def save_report(report: ExecutionReport, path: str | Path) -> None:
    """Write the full evidence report locally; caller chooses the location."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # The CLI never writes logs to a cloud endpoint. Replace atomically.
    import os
    import tempfile
    name: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent,
                                         prefix=".molchat-", suffix=".tmp", delete=False) as out:
            name = out.name
            json.dump(report.as_dict(), out, ensure_ascii=False, indent=2)
            out.write("\n")
        os.replace(name, destination)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)

