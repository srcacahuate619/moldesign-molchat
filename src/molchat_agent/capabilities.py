"""Allowlist of MolDesign HTTP capabilities (without copying scientific engines)."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import quote


class PlanValidationError(ValueError):
    """An action fails the scientific capability contract."""


@dataclass(frozen=True)
class FieldSpec:
    kind: type
    max_length: int | None = None
    minimum: int | None = None
    maximum: int | None = None
    pattern: str | None = None

    def validate(self, key: str, value: Any) -> None:
        if self.kind is int:
            if type(value) is not int:
                raise PlanValidationError(f"{key}: se necesita un entero")
            if self.minimum is not None and value < self.minimum:
                raise PlanValidationError(f"{key}: fuera de rango")
            if self.maximum is not None and value > self.maximum:
                raise PlanValidationError(f"{key}: fuera de rango")
        elif self.kind is str:
            if not isinstance(value, str) or not value.strip():
                raise PlanValidationError(f"{key}: se necesita texto no vacío")
            if self.max_length is not None and len(value) > self.max_length:
                raise PlanValidationError(f"{key}: demasiado largo")
            if self.pattern and not re.fullmatch(self.pattern, value):
                raise PlanValidationError(f"{key}: formato no válido")
        else:
            raise TypeError("Tipo de contrato no soportado")

    def json_schema(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": "integer" if self.kind is int else "string"}
        if self.max_length is not None:
            result["maxLength"] = self.max_length
        if self.minimum is not None:
            result["minimum"] = self.minimum
        if self.maximum is not None:
            result["maximum"] = self.maximum
        if self.pattern is not None:
            result["pattern"] = self.pattern
        return result


@dataclass(frozen=True)
class Capability:
    name: str
    description: str
    method: str
    path: str
    required: dict[str, FieldSpec]
    optional: dict[str, FieldSpec]
    risk: str = "read"
    path_fields: tuple[str, ...] = ()

    def validate(self, arguments: dict[str, Any]) -> None:
        if not isinstance(arguments, dict):
            raise PlanValidationError(f"{self.name}: argumentos no son objeto")
        fields = self.required | self.optional
        extra = set(arguments) - set(fields)
        missing = set(self.required) - set(arguments)
        if extra or missing:
            raise PlanValidationError(
                f"{self.name}: parámetros sobrantes {sorted(extra)} o faltantes {sorted(missing)}"
            )
        for key, value in arguments.items():
            fields[key].validate(key, value)

    def request(self, arguments: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
        self.validate(arguments)
        path = self.path
        for field in self.path_fields:
            path = path.replace("{" + field + "}", quote(str(arguments[field]), safe=""))
        parameters = {k: v for k, v in arguments.items() if k not in self.path_fields}
        return self.method, path, parameters

    def as_catalog_entry(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "risk": self.risk,
            "parameters": {
                "type": "object",
                "properties": {
                    key: spec.json_schema()
                    for key, spec in (self.required | self.optional).items()
                },
                "required": list(self.required),
                "additionalProperties": False,
            },
        }


_IDENTIFIER = FieldSpec(str, max_length=128, pattern=r"[a-zA-Z0-9_-]+")
_SMILES = FieldSpec(str, max_length=2000)
_TARGET = FieldSpec(str, max_length=10, pattern=r"[A-Za-z0-9_-]{4,10}")

CAPABILITIES: dict[str, Capability] = {
    "list_targets": Capability(
        "list_targets", "Listar receptores visibles para esta cuenta", "GET", "/targets/", {}, {}
    ),
    "check_preflight": Capability(
        "check_preflight", "Auditoría factual de receptor y ligando, sin docking",
        "POST", "/evaluation/preflight",
        {"smiles": _SMILES, "target_pdb_id": _TARGET},
        {"chain": FieldSpec(str, max_length=4), "docking_engine": FieldSpec(str, max_length=32)},
    ),
    "list_evaluations": Capability(
        "list_evaluations", "Consultar historial propio de evaluaciones",
        "GET", "/history/evaluations", {},
        {"page": FieldSpec(int, minimum=1, maximum=10000),
         "page_size": FieldSpec(int, minimum=1, maximum=100),
         "target_pdb_id": _TARGET},
    ),
    "evaluation_status": Capability(
        "evaluation_status", "Consultar estado de una evaluación existente",
        "GET", "/evaluation/status/{task_id}", {"task_id": _IDENTIFIER}, {},
        path_fields=("task_id",),
    ),
    "get_docking_proposal": Capability(
        "get_docking_proposal", "Leer propuesta de docking para su revisión",
        "GET", "/ai/proposals/{proposal_id}", {"proposal_id": _IDENTIFIER}, {},
        path_fields=("proposal_id",),
    ),
    "approve_docking_proposal": Capability(
        "approve_docking_proposal", "Aprobar propuesta preexistente; puede iniciar cálculo costoso",
        "POST", "/ai/proposals/{proposal_id}/approve",
        {"proposal_id": _IDENTIFIER,
         "proposal_hash": FieldSpec(str, max_length=71, pattern=r"sha256:[a-f0-9]{64}")},
        {}, risk="approval_required", path_fields=("proposal_id",),
    ),
}


def capability(name: str) -> Capability:
    try:
        return CAPABILITIES[name]
    except KeyError as exc:
        raise PlanValidationError(f"Herramienta no permitida: {name}") from exc

