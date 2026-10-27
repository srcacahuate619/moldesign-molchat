"""Hypothesis cycle: screen, approve-by-digest, run, compare, expediente."""

import pytest

from molchat_agent.orchestration.budget import BudgetExceeded
from molchat_agent.orchestration.hypothesis import (
    HypothesisBudget,
    HypothesisRunner,
    compare_result,
    rank_key,
)
from molchat_agent.orchestration.jobs import JobTracker
from molchat_agent.orchestration.store import ExecutionStore


class CycleBridge:
    """Scripted platform: preflights, proposals, jobs, history."""

    def __init__(self):
        self.calls = []
        self.statuses = [{"status": "SUCCESS"}]

    async def call(self, name, args, **kwargs):
        self.calls.append((name, dict(args)))
        if name == "check_preflight":
            if args["smiles"] == "MALO":
                return {"technical_blockers": ["SMILES inválido"],
                        "warnings": [], "not_evaluated": []}
            return {"technical_blockers": [],
                    "warnings": ["pose justa"] if args["smiles"] == "CCO" else [],
                    "not_evaluated": []}
        if name == "create_docking_proposal":
            return {"proposal_id": "p-1", "proposal_hash": "sha256:" + "a" * 64,
                    "estado": "pendiente"}
        if name == "approve_docking_proposal":
            return {"task_id": "task-1"}
        if name == "evaluation_status":
            return dict(self.statuses[0])
        if name == "list_evaluations":
            return {"items": [{"affinity_kcal": -5.0}, {"affinity_kcal": -7.0}]}
        raise AssertionError(f"llamada inesperada: {name}")


async def _props(smiles):
    if smiles == "CCO":
        return {"mw": 46.07, "druglikeness": {"lipinski": True}}
    return {"mw": 100.0, "druglikeness": {"lipinski": False}}


async def _narrator(prompt):
    assert "COMPARACIÓN" in prompt
    return "La corrida mejora el histórico en 1.5 kcal/mol."


@pytest.fixture
def runner(tmp_path):
    async def no_sleep(_delay):
        pass

    bridge = CycleBridge()
    store = ExecutionStore(tmp_path / "exec.db")
    jobs = JobTracker(bridge, store=store, sleep=no_sleep, jitter=0)
    return HypothesisRunner(bridge=bridge, store=store, jobs=jobs,
                            properties=_props, narrator=_narrator)


def test_rank_key_orders_eligibility_warnings_lipinski():
    from molchat_agent.orchestration.hypothesis import Candidate

    blocked = Candidate("MALO", 0, preflight={"warnings": []}, eligible=False)
    warned = Candidate("CCO", 1, preflight={"warnings": ["w"]},
                       properties={"druglikeness": {"lipinski": True}},
                       eligible=True)
    clean = Candidate("CCC", 2, preflight={"warnings": []},
                      properties={"druglikeness": {"lipinski": True}},
                      eligible=True)
    assert [c.smiles for c in sorted([blocked, warned, clean], key=rank_key)] == [
        "CCC", "CCO", "MALO"]


def test_compare_result_is_deterministic():
    better = compare_result({"affinity_kcal": -8.5},
                            [{"affinity_kcal": -5.0}, {"affinity_kcal": -7.0}])
    assert better["history_best_kcal"] == -7.0
    assert better["delta_vs_best"] == -1.5
    assert better["verdict"] == "mejora el mejor histórico"
    assert compare_result({}, [])["verdict"] == "sin referencia previa"
    assert compare_result({}, [{"affinity_kcal": -5.0}])["verdict"] == \
        "sin afinidad medida"


@pytest.mark.asyncio
async def test_full_iteration_with_approval(runner):
    screening = await runner.screen("inhibir X", "7E2Y", ["CCO", "MALO", "CCC"])
    assert [c.smiles for c in screening.ranked()] == ["CCC", "CCO", "MALO"]
    assert screening.ranked()[-1].eligible is False
    record = runner.propose_run(screening)
    assert record.decision == "pending"
    assert record.pending.candidate.smiles == "CCC"
    assert record.pending.plan["schema"] == "/2"
    with pytest.raises(ValueError, match="huella"):
        await runner.execute_run(record, approval_digest="sha256:otra",
                                 approved_steps={"s1", "s2"})
    sends = [c for c in runner._bridge.calls
             if c[0] in ("create_docking_proposal", "approve_docking_proposal")]
    assert sends == []  # wrong digest: nothing sent
    report = await runner.execute_run(
        record, approval_digest=record.pending.digest,
        approved_steps={"s1", "s2"})
    assert report.state == "completed"
    comparison = await runner.compare_and_report(record)
    assert comparison["history_best_kcal"] == -7.0
    assert record.synthesis is not None
    assert runner.iterations[0].decision == "approved"


@pytest.mark.asyncio
async def test_second_iteration_proposes_next_candidate(runner):
    # Regression (Fase 5 live): re-proposing the best candidate yields the
    # identical plan digest, the executor returns the stored report, and
    # the "second run" launches nothing (same task_id, history unchanged).
    screening = await runner.screen("inhibir X", "7E2Y", ["CCC", "CCO"])
    first = runner.propose_run(screening)
    assert first.pending.candidate.smiles == "CCC"
    await runner.execute_run(first, approval_digest=first.pending.digest,
                             approved_steps={"s1", "s2"})
    second = runner.propose_run(screening)
    assert second.pending is not None
    assert second.pending.candidate.smiles == "CCO"
    assert second.pending.digest != first.pending.digest


@pytest.mark.asyncio
async def test_compare_unwraps_followed_job_result(runner):
    # Real shape: outcome.result.final = {task_id, status, result: {...}}.
    # Without unwrapping, affinity_kcal read as null live (Fase 5).
    runner._bridge.statuses = [{"status": "SUCCESS", "result": {
        "affinity_kcal": -6.25, "molecule_id": "m-9"}}]
    screening = await runner.screen("inhibir X", "7E2Y", ["CCC"])
    record = runner.propose_run(screening)
    await runner.execute_run(record, approval_digest=record.pending.digest,
                             approved_steps={"s1", "s2"})
    comparison = await runner.compare_and_report(record)
    assert comparison["affinity_kcal"] == -6.25
    assert comparison["delta_vs_best"] == 0.75  # vs history best -7.0
    assert comparison["verdict"] == "no mejora el mejor histórico"


@pytest.mark.asyncio
async def test_no_eligible_candidate_is_honest(runner):
    screening = await runner.screen("inhibir X", "7E2Y", ["MALO"])
    record = runner.propose_run(screening)
    assert record.decision == "no_candidate"
    assert record.pending is None
    with pytest.raises(ValueError, match="sin plan pendiente"):
        await runner.execute_run(record, approval_digest="x", approved_steps=set())


@pytest.mark.asyncio
async def test_decline_and_budgets(tmp_path):
    async def no_sleep(_delay):
        pass

    bridge = CycleBridge()
    store = ExecutionStore(tmp_path / "exec.db")
    jobs = JobTracker(bridge, store=store, sleep=no_sleep, jitter=0)
    runner = HypothesisRunner(bridge=bridge, store=store, jobs=jobs,
                              budget=HypothesisBudget(max_iterations=1, max_runs=1),
                              properties=_props)
    screening = await runner.screen("inhibir X", "7E2Y", ["CCO"])
    record = runner.propose_run(screening)
    runner.decline_run(record, "quiero revisar el preflight")
    assert record.decision == "declined"
    assert record.report["declined_reason"].startswith("quiero")
    assert [c for c in bridge.calls if c[0] == "create_docking_proposal"] == []
    allowed, reason = runner.can_continue()
    assert allowed is False and "iteraciones" in reason
    with pytest.raises(BudgetExceeded):
        await runner.screen("otra", "7E2Y", ["CCO"])


@pytest.mark.asyncio
async def test_expediente_is_saved_and_declared(tmp_path, runner):
    screening = await runner.screen("inhibir X", "7E2Y", ["CCO"])
    record = runner.propose_run(screening)
    await runner.execute_run(record, approval_digest=record.pending.digest,
                             approved_steps={"s1", "s2"})
    await runner.compare_and_report(record)
    path = runner.save_expediente(tmp_path / "expediente.json")
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == "moldesign.molchat.expediente/1"
    assert "no es un caso de MolDesign" in payload["note"]
    assert payload["budget"]["runs_used"] == 1
    assert payload["iterations"][0]["plan_digest"] == record.pending.digest
