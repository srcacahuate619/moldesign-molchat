"""Fase 3 exit-gate demo, operator-driven (needs a real MolDesign + token).

Phases (run separately; each prints its report path, state, and digest):
  A  /2 plan, 3 read steps with bindings (no approval needed)
  B  preflight block on an unknown target (expects blocked, no silent pass)
  C  approve an existing proposal -> follow the job to a terminal state
  D  cancel a running task by id

C needs --proposal-id (from MolDesign) and, after human review,
--approve-digest/--approve-step. D needs --cancel-task. Missing
prerequisites SKIP with a printed reason (exit 3); real failures exit 1.

Usage:
  MOLDESIGN_BASE_URL=... MOLDESIGN_TOKEN=... PYTHONPATH=src \
    python scripts/demo_fase3.py --phase all --store reports/demo_fase3.db
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from molchat_agent.bridge import MolDesignBridge  # noqa: E402
from molchat_agent.executor import AgentExecutor, save_report  # noqa: E402
from molchat_agent.orchestration.budget import Budget  # noqa: E402
from molchat_agent.orchestration.jobs import JobTracker  # noqa: E402
from molchat_agent.orchestration.store import ExecutionStore  # noqa: E402
from molchat_agent.plan import Plan  # noqa: E402

SKIP = 3


def _phase_a_plan() -> Plan:
    return Plan.from_dict({
        "goal": "Detalle y SAR de la primera evaluación del historial",
        "planner": "demo-fase3", "schema": "/2",
        "steps": [
            {"id": "s1", "capability": "list_evaluations", "arguments": {},
             "rationale": "historial propio"},
            {"id": "s2", "capability": "get_evaluation_result",
             "arguments": {"molecule_id": {"$from": "s1.items.0.molecule_id"}},
             "rationale": "resultado del primero"},
            {"id": "s3", "capability": "get_sar",
             "arguments": {"molecule_id": {"$from": "s1.items.0.molecule_id"}},
             "rationale": "SAR del mismo"},
        ],
    })


def _phase_b_plan() -> Plan:
    return Plan.from_dict({
        "goal": "Preflight contra un receptor inexistente (debe bloquear)",
        "planner": "demo-fase3",
        "steps": [{"id": "s1", "capability": "check_preflight",
                   "arguments": {"smiles": "CCO", "target_pdb_id": "ZZZZ"},
                   "rationale": "blanco inválido"}],
    })


def _phase_c_plan(proposal_id: str, proposal_hash: str) -> Plan:
    return Plan.from_dict({
        "goal": "Aprobar propuesta y seguir la evaluación", "planner": "demo-fase3",
        "steps": [{"id": "s1", "capability": "approve_docking_proposal",
                   "arguments": {"proposal_id": proposal_id,
                                 "proposal_hash": proposal_hash},
                   "rationale": "revisada por el operador"}],
    })


def _phase_d_plan(task_id: str) -> Plan:
    return Plan.from_dict({
        "goal": "Cancelar tarea en curso", "planner": "demo-fase3",
        "steps": [{"id": "s1", "capability": "cancel_evaluation",
                   "arguments": {"task_id": task_id}, "rationale": "petición expresa"}],
    })


async def _run(executor: AgentExecutor, plan: Plan, out: Path, **approvals) -> str:
    report = await executor.execute(plan, **approvals)
    save_report(report, out)
    print(f"  estado={report.state} huella={report.plan_digest} informe={out}")
    for outcome in report.outcomes:
        print(f"    {outcome.id} {outcome.capability}: {outcome.state}"
              + (f" ({outcome.error})" if outcome.error else ""))
    return report.state


async def main_async(args: argparse.Namespace) -> int:
    store = ExecutionStore(args.store)
    async with MolDesignBridge.from_env() as bridge:
        jobs = JobTracker(bridge, store=store)
        executor = AgentExecutor(bridge, store=store, jobs=jobs,
                                 budget=Budget(max_time_s=args.timeout))
        phases = ["A", "B", "C", "D"] if args.phase == "all" else [args.phase]
        failed, skipped = [], []
        for phase in phases:
            print(f"== Fase {phase} ==")
            if phase == "A":
                state = await _run(executor, _phase_a_plan(),
                                   Path(args.reports) / "demo_fase3_A.json")
                if state == "blocked":
                    print("  SKIP: la cuenta no tiene evaluaciones con molecule_id.")
                    skipped.append(phase)
                elif state != "completed":
                    failed.append(phase)
            elif phase == "B":
                state = await _run(executor, _phase_b_plan(),
                                   Path(args.reports) / "demo_fase3_B.json")
                if state != "blocked":
                    print(f"  FAIL: se esperaba blocked, hubo {state}.")
                    failed.append(phase)
            elif phase == "C":
                if not args.proposal_id:
                    print("  SKIP: falta --proposal-id (ver propuesta en MolDesign).")
                    skipped.append(phase)
                    continue
                try:
                    proposal = await bridge.call(
                        "get_docking_proposal", {"proposal_id": args.proposal_id})
                except Exception as exc:
                    print(f"  FAIL: no se pudo leer la propuesta: {exc}")
                    failed.append(phase)
                    continue
                print(f"  propuesta: estado={proposal.get('estado')} "
                      f"hash={str(proposal.get('hash'))[:19]}…")
                plan = _phase_c_plan(args.proposal_id, proposal["hash"])
                print(f"  plan s1 approve; huella={plan.digest}")
                if not args.approve_digest:
                    print("  Revisa y re-ejecuta con --approve-digest/--approve-step.")
                    skipped.append(phase)
                    continue
                state = await _run(
                    executor, plan, Path(args.reports) / "demo_fase3_C.json",
                    approval_digest=args.approve_digest,
                    approved_steps=set(args.approve_step or []))
                if state == "awaiting_approval":
                    print("  SKIP: digest/pasos no aprobados; revisa y reintenta.")
                    skipped.append(phase)
                elif state not in ("completed", "failed"):
                    print(f"  FAIL: trabajo sin estado terminal ({state}).")
                    failed.append(phase)
            elif phase == "D":
                if not args.cancel_task:
                    print("  SKIP: falta --cancel-task (tarea en curso).")
                    skipped.append(phase)
                    continue
                state = await _run(executor, _phase_d_plan(args.cancel_task),
                                   Path(args.reports) / "demo_fase3_D.json")
                if state != "completed":
                    failed.append(phase)
    print(f"Puerta Fase 3: fallos={failed or 'ninguno'} pendientes={skipped or 'ninguno'}.")
    if failed:
        return 1
    if skipped:
        return SKIP
    print("Demo completa.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Demo puerta de salida Fase 3")
    parser.add_argument("--phase", default="all", choices=["all", "A", "B", "C", "D"])
    parser.add_argument("--store", default="reports/demo_fase3.db")
    parser.add_argument("--reports", default="reports")
    parser.add_argument("--timeout", type=float, default=1200.0)
    parser.add_argument("--proposal-id", default="")
    parser.add_argument("--approve-digest", default="")
    parser.add_argument("--approve-step", action="append", default=[])
    parser.add_argument("--cancel-task", default="")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
