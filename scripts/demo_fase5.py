"""Fase 5 exit demo, operator-driven (needs the CR worktree backend + token).

Two hypothesis rounds over researcher-provided candidates, then a Molcy
video of the best run with its acta linked:

  round: screen (preflights+rank) -> propose -> HUMAN approves digest+steps
         -> execute+follow -> compare vs history -> iteration synthesis
  video: request render of the best run -> follow -> read acta

Approvals are typed digests, never "sí": paste the shown digest back.
Missing prerequisites SKIP with a printed reason (exit 3); real failures
exit 1.

Usage:
  MOLDESIGN_BASE_URL=... MOLDESIGN_TOKEN=... PYTHONPATH=src \\
    python scripts/demo_fase5.py --objective "inhibir X" --target 7E2Y \\
      --candidates "CCO,CCC" --store reports/demo_fase5.db
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from molchat_agent.bridge import MolDesignBridge  # noqa: E402
from molchat_agent.conversation.tools import QualityBackend  # noqa: E402
from molchat_agent.executor import AgentExecutor, save_report  # noqa: E402
from molchat_agent.orchestration.budget import Budget  # noqa: E402
from molchat_agent.orchestration.hypothesis import (  # noqa: E402
    HypothesisBudget,
    HypothesisRunner,
)
from molchat_agent.orchestration.jobs import JobTracker  # noqa: E402
from molchat_agent.orchestration.store import ExecutionStore  # noqa: E402
from molchat_agent.plan import Plan  # noqa: E402
from molchat_agent.providers import build_registry  # noqa: E402
from molchat_agent.providers.base import TurnContext  # noqa: E402

SKIP = 3
DEMO_DATA = ROOT / "src" / "molchat_agent" / "conversation" / "data" / "demo_molecules.json"


async def _properties_fn(backend, smiles):
    try:
        record = await backend.properties(smiles)
    except Exception:
        return None
    return {"props": record.props, "druglikeness": record.druglikeness,
            "source": record.source}


def _narrator_fn(provider_id):
    async def narrate(prompt):
        registry = build_registry()
        provider = registry.get(provider_id or registry.active_id)
        reason = registry.block_reason(provider.id)
        if reason:
            return f"(sin síntesis LLM: {reason})"
        parts = []
        async for event in provider.chat(TurnContext(text=prompt)):
            if event.type == "token" and event.text:
                parts.append(event.text)
        return "".join(parts).strip() or "(sin síntesis: vacío)"
    return narrate


async def _run_video(bridge, store, jobs, molecule_id, task_id, reports):
    plan = Plan.from_dict({
        "goal": f"Vídeo del mejor resultado ({molecule_id[:8]})",
        "planner": "demo-fase5",
        "steps": [{"id": "s1", "capability": "request_case_video",
                   "arguments": {"origen": "moldex", "id": molecule_id,
                                 "escena": "resultado",
                                 "formato": "previsualizacion",
                                 "task_id": task_id},
                   "rationale": "render del mejor run"}],
    })
    print(f"  plan vídeo; huella={plan.digest}")
    answer = input("  Aprueba escribiendo la huella (o Enter para declinar): ").strip()
    if answer != plan.digest:
        print("  SKIP: vídeo no aprobado.")
        return None
    steps = input("  Pasos aprobados (ids, coma): ").strip()
    approved = {s.strip() for s in steps.split(",") if s.strip()}
    report = await AgentExecutor(bridge, store=store, jobs=jobs,
                                 budget=Budget()).execute(
        plan, approval_digest=plan.digest, approved_steps=approved)
    out = Path(reports) / "demo_fase5_video.json"
    save_report(report, out)
    print(f"  vídeo: estado={report.state} informe={out}")
    if report.state != "completed":
        return None
    job_id = report.outcomes[0].result.get("submitted", {}).get("id", "")
    acta_plan = Plan.from_dict({
        "goal": "Leer acta del vídeo", "planner": "demo-fase5",
        "steps": [{"id": "s1", "capability": "get_video_acta",
                   "arguments": {"job_id": job_id}, "rationale": "acta"}],
    })
    acta_report = await AgentExecutor(bridge, store=store, jobs=jobs).execute(acta_plan)
    outcome = acta_report.outcomes[0]
    print(f"  acta: estado={outcome.state} "
          f"schema={(outcome.result or {}).get('schema', '?')}")
    return {"job_id": job_id, "acta_state": outcome.state}


async def main_async(args: argparse.Namespace) -> int:
    candidates = [c.strip() for c in args.candidates.split(",") if c.strip()]
    if not candidates:
        print("SKIP: --candidates vacío.")
        return SKIP
    store = ExecutionStore(args.store)
    backend = QualityBackend(DEMO_DATA, source="demo dataset (CR-01 pendiente)")
    async with MolDesignBridge.from_env() as bridge:
        jobs = JobTracker(bridge, store=store)
        runner = HypothesisRunner(
            bridge=bridge, store=store, jobs=jobs,
            budget=HypothesisBudget(max_iterations=args.rounds, max_runs=args.rounds),
            properties=lambda smiles: _properties_fn(backend, smiles),
            narrator=_narrator_fn(args.narrator) if args.narrator else None)
        failed, skipped = [], []
        for round_no in range(1, args.rounds + 1):
            print(f"== Ronda {round_no} ==")
            allowed, reason = runner.can_continue()
            if not allowed:
                print(f"  SKIP: {reason}")
                skipped.append(f"ronda-{round_no}")
                continue
            screening = await runner.screen(args.objective, args.target, candidates)
            for candidate in screening.ranked():
                mark = "apta" if candidate.eligible else f"NO: {candidate.reason}"
                print(f"  #{candidate.rank} {candidate.smiles}: {mark}")
            record = runner.propose_run(screening)
            if record.decision == "no_candidate":
                print("  SKIP: ningún candidato apto.")
                skipped.append(f"ronda-{round_no}")
                continue
            assert record.pending is not None
            print(f"  plan s1=create s2=approve(bindings); "
                  f"huella={record.pending.digest}")
            answer = input("  Aprueba escribiendo la huella (o Enter para declinar): ").strip()
            if answer != record.pending.digest:
                runner.decline_run(record, "operador declinó en la demo")
                print("  SKIP: ronda declinada.")
                skipped.append(f"ronda-{round_no}")
                continue
            steps = input("  Pasos aprobados (ids, coma): ").strip()
            report = await runner.execute_run(
                record, approval_digest=record.pending.digest,
                approved_steps={s.strip() for s in steps.split(",") if s.strip()})
            print(f"  corrida: estado={report.state}")
            if report.state != "completed":
                failed.append(f"ronda-{round_no}")
                continue
            comparison = await runner.compare_and_report(record)
            print(f"  comparación: {json.dumps(comparison, ensure_ascii=False)}")
            if record.synthesis:
                print(f"  síntesis: {record.synthesis[:300]}")
        expediente_path = runner.save_expediente(Path(args.reports) / "expediente_fase5.json")
        print(f"Expediente: {expediente_path}")
        best_molecule = best_task = None
        best_affinity = None
        for record in runner.iterations:
            comparison = record.comparison or {}
            affinity = comparison.get("affinity_kcal")
            if isinstance(affinity, (int, float)) and (
                    best_affinity is None or affinity < best_affinity):
                best_affinity = affinity
                for outcome in (record.report or {}).get("outcomes", []):
                    final = (outcome.get("result") or {}).get("final", {})
                    result = final.get("result", final)
                    if isinstance(result, dict) and result.get("molecule_id"):
                        best_molecule = result["molecule_id"]
                        best_task = final.get("task_id")
        if best_molecule and best_task:
            print(f"== Vídeo del mejor ({best_affinity} kcal/mol) ==")
            video = await _run_video(bridge, store, jobs, best_molecule,
                                     best_task, args.reports)
            if video is None:
                skipped.append("video")
        elif not failed:
            print("SKIP: sin mejor corrida con molecule_id; vídeo omitido.")
            skipped.append("video")
    print(f"Puerta Fase 5: fallos={failed or 'ninguno'} pendientes={skipped or 'ninguno'}.")
    if failed:
        return 1
    if skipped:
        return SKIP
    print("Demo completa.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Demo puerta de salida Fase 5")
    parser.add_argument("--objective", required=True)
    parser.add_argument("--target", default="7E2Y")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--narrator", default="")
    parser.add_argument("--store", default="reports/demo_fase5.db")
    parser.add_argument("--reports", default="reports")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
