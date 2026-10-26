"""Small-model planning measurement, F2-C5 baseline.

Runs fixed planning goals against a local OpenAI-compatible server and
scores each goal: formally valid AND no invented identifiers AND no extra
steps. This is the baseline that justifies the deterministic layer: small
models plan fluently and wrongly at the same time.

Usage: python scripts/measure_small_models.py --model <name>
       [--base-url http://127.0.0.1:8400/v1] [--out reports/small_models.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from molchat_agent.capabilities import CAPABILITIES  # noqa: E402
from molchat_agent.providers.local_http import LlamaServerProvider  # noqa: E402

GOALS = json.loads((ROOT / "tests" / "quality" / "small_model_goals.json").read_text())["goals"]


def _leaves(arguments: Any) -> list[Any]:
    if isinstance(arguments, dict):
        found = []
        for value in arguments.values():
            found.extend(_leaves(value))
        return found
    if isinstance(arguments, list):
        found = []
        for value in arguments:
            found.extend(_leaves(value))
        return found
    return [arguments]


def invented_values(plan_dict: dict, goal: str) -> list[str]:
    """Argument string values (len>=2) that never appear in the goal text."""
    lowered = goal.lower()
    invented = []
    for step in plan_dict.get("steps", []):
        for value in _leaves(step.get("arguments", {})):
            if isinstance(value, str) and len(value) >= 2 and value.lower() not in lowered:
                invented.append(f"{step.get('capability')}.{value}")
    return invented


async def _measure(provider: LlamaServerProvider, goal: dict) -> dict:
    started = time.monotonic()
    row: dict[str, Any] = {"id": goal["id"], "goal": goal["goal"]}
    try:
        plan = await provider.plan(goal["goal"])
        plan_dict = plan.as_dict()
    except Exception as exc:  # noqa: BLE001 - rejected plans are data
        row.update(valid=False, invented=["<rejected>"],
                   steps=0, clean=False,
                   latency_ms=int((time.monotonic() - started) * 1000),
                   error=f"{type(exc).__name__}: {exc}"[:160])
        return row
    read_only = all(CAPABILITIES[s.capability].risk == "read" for s in plan.steps)
    invented = invented_values(plan_dict, goal["goal"])
    within_steps = len(plan.steps) <= goal["max_steps"]
    row.update(valid=read_only, invented=invented, steps=len(plan.steps),
               clean=bool(read_only and not invented and within_steps),
               latency_ms=int((time.monotonic() - started) * 1000), error="")
    return row


async def main_async(args: argparse.Namespace) -> dict:
    provider = LlamaServerProvider(base_url=args.base_url, model=args.model)
    health = await provider.health()
    if health.status.value != "ok":
        raise SystemExit(f"servidor no listo: {health.message}")
    rows = []
    for goal in GOALS:
        print(f"--- {goal['id']}: {goal['goal'][:50]} ---", flush=True)
        row = await _measure(provider, goal)
        rows.append(row)
        print(f"  valido={row['valid']} inventados={row['invented']} "
              f"pasos={row['steps']} limpio={row['clean']}")
    return {"model": args.model, "base_url": args.base_url,
            "score": sum(1 for r in rows if r["clean"]), "of": len(rows),
            "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Medición de modelos pequeños (F2-C5)")
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8400/v1")
    parser.add_argument("--out", default="reports/small_models.json")
    args = parser.parse_args()
    report = asyncio.run(main_async(args))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{report['model']}: {report['score']}/{report['of']} limpios -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
