"""Minimal tool backend for the deterministic turn.

Bridge scaffolding: the typed ``properties()`` call the engine needs now.
Evolves into ``tools/`` (tool-packs + catalog) in Fase 3. ``QualityBackend``
serves recorded RDKit fixtures so the quality suite runs offline and
deterministically; a ``PlatformBackend`` over HTTP replaces it later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class ToolError(RuntimeError):
    """A tool failed. The engine answers with abstention, never a number."""


@dataclass
class MoleculeRecord:
    name: str
    smiles: str
    props: dict[str, Any] = field(default_factory=dict)
    druglikeness: dict[str, Any] | None = None
    source: str = "fixtures RDKit grabados"
    verified_values: set[float] = field(default_factory=set)

    def __post_init__(self) -> None:
        for value in self.props.values():
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                self.verified_values.add(float(value))


class ToolBackend(Protocol):
    async def properties(self, smiles: str) -> MoleculeRecord: ...
    def name_for(self, smiles: str) -> str | None: ...


class QualityBackend:
    """Fixture-backed backend for tests and the quality suite."""

    def __init__(self, fixtures_path: str | Path) -> None:
        payload = json.loads(Path(fixtures_path).read_text(encoding="utf-8"))
        self._by_smiles: dict[str, dict] = {}
        self.calls: list[tuple[str, str]] = []
        for entry in payload["molecules"]:
            record = {"name": entry["name"], "smiles": entry["smiles"],
                      "props": entry["properties"],
                      "druglikeness": entry.get("druglikeness")}
            self._by_smiles[entry["smiles"]] = record
            if entry.get("canonical"):
                self._by_smiles.setdefault(entry["canonical"], record)

    async def properties(self, smiles: str) -> MoleculeRecord:
        self.calls.append(("properties", smiles))
        record = self._by_smiles.get((smiles or "").strip())
        if record is None:
            raise ToolError(f"sin datos registrados para {smiles!r}")
        return MoleculeRecord(name=record["name"], smiles=record["smiles"],
                              props=dict(record["props"]),
                              druglikeness=record["druglikeness"])

    def name_for(self, smiles: str) -> str | None:
        record = self._by_smiles.get((smiles or "").strip())
        return record["name"] if record else None
