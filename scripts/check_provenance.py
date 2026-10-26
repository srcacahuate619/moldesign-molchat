"""Fail if PROVENANCE.md is missing, incomplete, or incoherent.

Ledger gate (PLAN §21, Fase 0 puerta de salida): every ``src``/``tests``/
``scripts`` Python file must be covered by a provenance entry, every entry
must carry the six mandatory fields, the resulting license must be
``GPL-3.0-or-later``, and any cited MolDesign commit must be well-formed and
match the reference commit fixed in Fase 0.

Usage: ``python scripts/check_provenance.py`` from the repo root.
Exit 0 = coherent, 1 = problems (listed, never hidden).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "PROVENANCE.md"
EXPECTED_LICENSE = "GPL-3.0-or-later"
REQUIRED_FIELDS = (
    "Origen",
    "Commit de MolDesign",
    "Autoría",
    "Transformación",
    "Licencia resultante",
    "Tests",
)
COVERAGE_GLOBS = ("src/**/*.py", "tests/**/*.py", "scripts/*.py")
SHA = re.compile(r"\b[0-9a-f]{40}\b")


def _safe_stdout() -> None:
    """Never crash while reporting: Windows consoles are not UTF-8."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, OSError, ValueError):
        pass


def main() -> int:
    _safe_stdout()
    problems: list[str] = []
    if not LEDGER.exists():
        print("check_provenance: PROVENANCE.md missing")
        return 1
    text = LEDGER.read_text(encoding="utf-8")

    ref_match = re.search(r"Commit de referencia.*?([0-9a-f]{40})", text, re.S)
    if not ref_match:
        problems.append("no fixed 40-hex MolDesign reference commit declared")
        reference = None
    else:
        reference = ref_match.group(1)

    # Split ledger into entries headed by "### <path[, path...]>".
    entries: dict[str, dict[str, str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("### "):
            current = line[4:].strip()
            entries[current] = {}
        elif current is not None and line.strip().startswith("- "):
            field, _, value = line.strip()[2:].partition(":")
            entries[current][field.strip()] = value.strip()
    if not entries:
        problems.append("no entries found (expected '### path' sections)")

    covered: set[str] = set()
    for header, fields in entries.items():
        for path in [p.strip() for p in header.split(",")]:
            covered.add(path.replace("\\", "/"))
        for required in REQUIRED_FIELDS:
            if required not in fields or not fields[required]:
                problems.append(f"[{header}] missing field: {required}")
        lic = fields.get("Licencia resultante", "")
        if lic and lic != EXPECTED_LICENSE:
            problems.append(f"[{header}] unexpected license: {lic!r}")
        commit = fields.get("Commit de MolDesign", "")
        if commit and not commit.startswith("N/A"):
            sha = SHA.search(commit)
            if not sha:
                problems.append(f"[{header}] malformed commit (want 40-hex or N/A)")
            elif reference and sha.group(0) != reference:
                problems.append(
                    f"[{header}] commit {sha.group(0)} != reference {reference}")

    for glob in COVERAGE_GLOBS:
        for path in sorted(ROOT.glob(glob)):
            rel = path.relative_to(ROOT).as_posix()
            if rel not in covered:
                problems.append(f"uncovered file: {rel}")

    if problems:
        print(f"check_provenance: {len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"check_provenance: coherent "
          f"({len(entries)} entries, ref {reference})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
