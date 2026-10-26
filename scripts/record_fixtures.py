"""Record RDKit property fixtures for the quality suite.

Runs MolDesign's own ``rdkit_tools`` (by path given on the command line, so
this repo never hardcodes a machine path) over the 8 quality-suite molecules
and writes typed JSON fixtures. Values are computed facts, not copies.

Usage: ``python scripts/record_fixtures.py <moldesign-backend-dir> <out-json>``
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import re
import sys
from pathlib import Path

# Verified against known_molecules.KNOWN_SMILES at the reference commit.
MOLECULES = {
    "aspirina": "CC(=O)Oc1ccccc1C(=O)O",
    "ibuprofeno": "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
    "paracetamol": "CC(=O)Nc1ccc(O)cc1",
    "cafeina": "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
    "morfina": "Oc1ccc2C[C@H]3N(C)CC[C@@]45[C@@H](Oc1c24)[C@H](O)C=C[C@H]35",
    "etanol": "CCO",
    "dopamina": "C1=CC(=C(C=C1CCN)O)O",
    "glucosa": "OC[C@H]1O[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O",
}

_PROPS_RE = {
    "mw": re.compile(r"MW:\s*(-?\d+\.?\d*)\s*Da"),
    "logp": re.compile(r"LogP:\s*(-?\d+\.?\d*)"),
    "tpsa": re.compile(r"TPSA:\s*(-?\d+\.?\d*)"),
    "hbd": re.compile(r"H-Bond Donors:\s*(\d+)"),
    "hba": re.compile(r"H-Bond Acceptors:\s*(\d+)"),
    "rot_bonds": re.compile(r"Rotatable Bonds:\s*(\d+)"),
    "heavy_atoms": re.compile(r"Heavy Atoms:\s*(\d+)"),
    "rings": re.compile(r"Rings:\s*(\d+)"),
}


def _parse_props(text: str) -> dict[str, float | int]:
    values: dict[str, float | int] = {}
    for key, pattern in _PROPS_RE.items():
        match = pattern.search(text)
        if not match:
            raise ValueError(f"missing {key} in tool output: {text[:80]!r}")
        raw = match.group(1)
        values[key] = int(raw) if key in ("hbd", "hba", "rot_bonds", "heavy_atoms", "rings") else float(raw)
    return values


def _parse_druglikeness(text: str) -> dict:
    lipinski = re.search(r"Lipinski:\s*(APROBADO|FALLIDO)", text)
    veber = re.search(r"Veber:\s*(APROBADO|FALLIDO)", text)
    if not lipinski or not veber:
        raise ValueError(f"unparseable druglikeness output: {text[:120]!r}")
    pains_alerts: list[str] = []
    evaluated = "no se pudo evaluar" not in text
    alerts = re.search(r"PAINS ALERTS:\s*(.+?)\.", text)
    if alerts:
        pains_alerts = [a.strip() for a in alerts.group(1).split(",")]
    return {"lipinski": lipinski.group(1) == "APROBADO",
            "veber": veber.group(1) == "APROBADO",
            "pains_evaluated": evaluated, "pains_alerts": pains_alerts}


async def _record(compute_properties, check_druglikeness, validate_smiles) -> list[dict]:
    records = []
    for name, smiles in MOLECULES.items():
        props_text = await compute_properties(smiles)
        if props_text.startswith("Error"):
            raise ValueError(f"{name}: {props_text}")
        dl_text = await check_druglikeness(smiles)
        canon_match = re.search(r"canónico:\s*(\S+)", await validate_smiles(smiles))
        records.append({
            "name": name,
            "smiles": smiles,
            "canonical": canon_match.group(1) if canon_match else smiles,
            "properties": _parse_props(props_text),
            "druglikeness": _parse_druglikeness(dl_text) if not dl_text.startswith("Error") else None,
        })
    return records


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: record_fixtures.py <moldesign-backend-dir> <out-json>")
        return 2
    backend = Path(sys.argv[1])
    if not (backend / "services" / "ai" / "tools" / "rdkit_tools.py").exists():
        print(f"not a MolDesign backend dir: {backend}")
        return 2
    sys.path.insert(0, str(backend))
    from services.ai.tools.rdkit_tools import (  # noqa: E402
        check_druglikeness, compute_properties, validate_smiles)

    records = asyncio.run(_record(compute_properties, check_druglikeness, validate_smiles))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "scripts/record_fixtures.py (MolDesign rdkit_tools output, parsed)",
        "molecules": records,
    }
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"recorded {len(records)} molecules -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
