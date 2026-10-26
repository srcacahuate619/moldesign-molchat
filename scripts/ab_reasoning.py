"""A/B of Meta reasoning_effort over quality-suite planning goals (task 2.9).

Feeds tool-facing quality queries as planning goals to Muse Spark 1.3
Standard at medium/high/xhigh and measures valid plans, latency, and token
usage per level. The Fase 1 default (medium) only changes with this data.

Needs MODEL_API_KEY and a granted meta@api.meta.ai destination
(`molchat-agent doctor --grant-consent meta@api.meta.ai`); planning goes
through the registry gate, never around it.

Usage: PYTHONPATH=src python scripts/ab_reasoning.py [--levels medium,high,xhigh]
       [--cases B01,B02] [--out reports/ab_reasoning.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from molchat_agent.capabilities import CAPABILITIES  # noqa: E402
from molchat_agent.config import load_config  # noqa: E402
from molchat_agent.providers import build_registry  # noqa: E402

CASES = json.loads((ROOT / "tests" / "quality" / "cases.json").read_text())["cases"]

# Tool-facing cases double as planning goals (factual turns need tools).
TOOL_FACING_PREFIXES = ("B", "C", "A", "D", "R", "H", "L", "V")


def _goals(wanted: set[str] | None) -> list[tuple[str, str]]:
    goals = []
    for case in CASES:
        if not case["id"].startswith(TOOL_FACING_PREFIXES):
            continue
        if wanted and case["id"] not in wanted:
            continue
        goals.append((case["id"], case["seq"][case["check"]]))
    return goals


async def _run_level(registry, goals, level: str) -> dict:
    from molchat_agent.plan import Plan  # noqa: E402
    from molchat_agent.providers.meta import MetaProvider  # noqa: E402

    rows = []
    for case_id, goal in goals:
        provider = registry.get("meta")
        assert isinstance(provider, MetaProvider)
        provider.reasoning_effort = level
        started = time.monotonic()
        try:
            plan = await registry.plan(goal, provider_id="meta")
            assert isinstance(plan, Plan)
            read_only = all(CAPABILITIES[s.capability].risk == "read"
                            for s in plan.steps)
            rows.append({"case": case_id, "valid": read_only,
                         "steps": len(plan.steps),
                         "latency_ms": int((time.monotonic() - started) * 1000),
                         "error": "" if read_only else "non-read step"})
        except Exception as exc:  # noqa: BLE001 - failed goals are data
            rows.append({"case": case_id, "valid": False, "steps": 0,
                         "latency_ms": int((time.monotonic() - started) * 1000),
                         "error": f"{type(exc).__name__}: {exc}"[:160]})
    valid = [r for r in rows if r["valid"]]
    latencies = sorted(r["latency_ms"] for r in rows)
    return {"level": level, "cases": len(rows), "valid": len(valid),
            "latency_ms": {"p50": latencies[len(latencies) // 2] if latencies else 0,
                           "max": max(latencies) if latencies else 0},
            "rows": rows}


async def main_async(args: argparse.Namespace) -> dict:
    config = load_config()
    if not config.model_api_key:
        raise SystemExit("Falta MODEL_API_KEY; el A/B necesita la API real de Meta.")
    registry = build_registry(config)
    reason = registry.block_reason("meta")
    if reason:
        raise SystemExit(f"Destino no autorizado: {reason}")
    levels = [level.strip() for level in args.levels.split(",")]
    goals = _goals(set(args.cases.split(",")) if args.cases else None)
    print(f"metas: {len(goals)}; niveles: {levels}")
    report = {"goals": [g[0] for g in goals], "levels": {}}
    for level in levels:
        print(f"--- nivel {level} ---")
        report["levels"][level] = await _run_level(registry, goals, level)
        summary = report["levels"][level]
        print(f"{level}: {summary['valid']}/{summary['cases']} válidos, "
              f"p50 {summary['latency_ms']['p50']} ms")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="A/B de reasoning_effort (2.9)")
    parser.add_argument("--levels", default="medium,high,xhigh")
    parser.add_argument("--cases", default="")
    parser.add_argument("--out", default="reports/ab_reasoning.json")
    args = parser.parse_args()
    report = asyncio.run(main_async(args))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"informe: {out}")
    print("\n| Nivel | Válidos | p50 ms |")
    print("|---|---|---|")
    for level, summary in report["levels"].items():
        print(f"| {level} | {summary['valid']}/{summary['cases']} "
              f"| {summary['latency_ms']['p50']} |")
    print("\nCoste: tokens no expuestos por esta corrida; la comparativa usa "
          "validez y latencia. Traducir a coste cuando el pricing aplique.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
