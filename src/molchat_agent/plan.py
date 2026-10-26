"""Immutable plans: their SHA-256 digest binds explicit human approvals.

Immutability is enforced by copying: ``from_dict`` deep-copies caller data
and ``as_dict`` deep-copies on export, so no reference the caller keeps can
mutate a plan (or be mutated through it) while a step is awaited (MP-01).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from .tools import capability, PlanValidationError

MAX_STEPS = 8


@dataclass(frozen=True)
class Step:
    id: str
    capability: str
    arguments: dict[str, Any]
    rationale: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "capability": self.capability,
                "arguments": copy.deepcopy(self.arguments),
                "rationale": self.rationale}


@dataclass(frozen=True)
class Plan:
    goal: str
    steps: tuple[Step, ...]
    planner: str = "manual"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Plan":
        if not isinstance(data, dict) or set(data) != {"goal", "steps", "planner"}:
            raise PlanValidationError("El plan debe contener goal, steps y planner")
        if not isinstance(data["goal"], str) or not 0 < len(data["goal"]) <= 4000:
            raise PlanValidationError("Objetivo vacío o demasiado largo")
        if not isinstance(data["planner"], str) or len(data["planner"]) > 100:
            raise PlanValidationError("Origen del plan no válido")
        raw_steps = data["steps"]
        if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= MAX_STEPS:
            raise PlanValidationError("Un plan requiere entre 1 y 8 pasos")
        steps: list[Step] = []
        for index, raw in enumerate(raw_steps):
            if not isinstance(raw, dict) or set(raw) != {"id", "capability", "arguments", "rationale"}:
                raise PlanValidationError(f"Paso {index}: campos inesperados")
            if not isinstance(raw["id"], str) or raw["id"] != f"s{index + 1}":
                raise PlanValidationError("Los pasos se identifican s1, s2, ...")
            if not isinstance(raw["capability"], str):
                raise PlanValidationError("Nombre de herramienta no válido")
            if not isinstance(raw["rationale"], str) or len(raw["rationale"]) > 600:
                raise PlanValidationError("Justificación demasiado larga")
            capability(raw["capability"]).validate(raw["arguments"])
            steps.append(Step(id=raw["id"], capability=raw["capability"],
                              arguments=copy.deepcopy(raw["arguments"]),
                              rationale=raw["rationale"]))
        return cls(goal=data["goal"], steps=tuple(steps), planner=data["planner"])

    def as_dict(self) -> dict[str, Any]:
        return {"goal": self.goal, "steps": [s.as_dict() for s in self.steps],
                "planner": self.planner}

    @property
    def digest(self) -> str:
        normalized = json.dumps(self.as_dict(), sort_keys=True, ensure_ascii=False,
                                separators=(",", ":"))
        return "sha256:" + sha256(normalized.encode("utf-8")).hexdigest()

