"""Fail if the built UI is missing or older than its sources.

Demo gate (PLAN Fase 4, tarea 4.5): the sidecar serves ``ui/dist`` when it
exists; serving a stale bundle while sources moved on is a silent lie this
gate refuses. Rebuild with ``npm run build`` inside ``ui/``.

Usage: ``python scripts/check_ui_build.py`` from the repo root.
Exit 0 = fresh, 1 = missing/stale (listed, never hidden).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "ui"
DIST = UI / "dist"
INDEX = DIST / "index.html"
SOURCES = ("src", "index.html", "package.json", "vite.config.ts", "tsconfig.json")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, OSError, ValueError):
        pass
    if not INDEX.is_file():
        print("check_ui_build: MISSING ui/dist (cd ui && npm install && npm run build)")
        return 1
    built_at = INDEX.stat().st_mtime
    stale: list[str] = []
    for name in SOURCES:
        target = UI / name
        if not target.exists():
            continue
        candidates = target.rglob("*") if target.is_dir() else (target,)
        for path in candidates:
            if path.is_file() and path.stat().st_mtime > built_at:
                stale.append(path.relative_to(ROOT).as_posix())
    if stale:
        print("check_ui_build: STALE ui/dist; rebuild (npm run build in ui/):")
        for entry in sorted(stale)[:20]:
            print(f"  - {entry}")
        if len(stale) > 20:
            print(f"  … and {len(stale) - 20} more")
        return 1
    assets = sorted(p.name for p in DIST.iterdir())
    print(f"check_ui_build: fresh (ui/dist: {', '.join(assets)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
