import json

import pytest

from molchat_agent.executor import AgentExecutor, save_report
from molchat_agent.plan import Plan


class FakeBridge:
    def __init__(self, fail=False, preflight_blockers=None):
        self.calls = []
        self.fail = fail
        self.preflight_blockers = preflight_blockers

    async def call(self, capability, args, **kwargs):
        self.calls.append((capability, args.copy()))
        if self.fail:
            raise RuntimeError("Error de laboratorio")
        if capability == "check_preflight":
            return {"technical_blockers": self.preflight_blockers or [], "warnings": []}
        return {"ok": True, "tool": capability}


def make_approval_plan():
    return Plan.from_dict({
        "goal": "Ejecutar una propuesta aprobada", "planner": "manual",
        "steps": [{"id": "s1", "capability": "approve_docking_proposal",
                   "arguments": {"proposal_id": "approved123",
                                 "proposal_hash": "sha256:" + "b" * 64},
                   "rationale": "El investigador revisó la propuesta"}],
    })


@pytest.mark.asyncio
async def test_sensitive_action_is_blocked_without_exact_approval():
    bridge = FakeBridge()
    plan = make_approval_plan()
    report = await AgentExecutor(bridge).execute(plan)
    assert report.state == "awaiting_approval"
    assert bridge.calls == []
    wrong = await AgentExecutor(bridge).execute(
        plan, approval_digest="sha256:" + "0" * 64, approved_steps={"s1"}
    )
    assert wrong.state == "awaiting_approval"
    assert bridge.calls == []


@pytest.mark.asyncio
async def test_sensitive_action_requires_both_digest_and_step():
    bridge = FakeBridge()
    plan = make_approval_plan()
    report = await AgentExecutor(bridge).execute(
        plan, approval_digest=plan.digest, approved_steps={"s1"}
    )
    assert report.state == "completed"
    assert bridge.calls[0][0] == "approve_docking_proposal"
    assert report.outcomes[0].result_sha256.startswith("sha256:")


@pytest.mark.asyncio
async def test_mutation_after_approval_invalidates_digest():
    plan = make_approval_plan()
    digest = plan.digest
    plan.steps[0].arguments["proposal_id"] = "changed"
    bridge = FakeBridge()
    report = await AgentExecutor(bridge).execute(
        plan, approval_digest=digest, approved_steps={"s1"}
    )
    assert report.state == "awaiting_approval"
    assert bridge.calls == []


@pytest.mark.asyncio
async def test_no_silent_retry_and_report(tmp_path):
    plan = Plan.from_dict({"goal": "Consultar el catálogo", "planner": "manual", "steps": [
        {"id": "s1", "capability": "list_targets", "arguments": {}, "rationale": ""},
        {"id": "s2", "capability": "list_targets", "arguments": {}, "rationale": ""},
    ]})
    bridge = FakeBridge(fail=True)
    report = await AgentExecutor(bridge).execute(plan)
    assert report.state == "failed"
    assert len(bridge.calls) == 1
    target = tmp_path / "report.json"
    save_report(report, target)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["schema"] == "moldesign.molchat.execution/1"
    assert data["outcomes"][0]["state"] == "failed"


@pytest.mark.asyncio
async def test_preflight_blockers_stop_the_workflow_before_approval():
    plan = Plan.from_dict({"goal": "Preparar antes de aprobar", "planner": "manual", "steps": [
        {"id": "s1", "capability": "check_preflight",
         "arguments": {"smiles": "CCO", "target_pdb_id": "1HSG"}, "rationale": ""},
        {"id": "s2", "capability": "approve_docking_proposal",
         "arguments": {"proposal_id": "demo", "proposal_hash": "sha256:" + "a" * 64},
         "rationale": ""},
    ]})
    bridge = FakeBridge(preflight_blockers=[{"code": "INVALID_TARGET"}])
    report = await AgentExecutor(bridge).execute(
        plan, approval_digest=plan.digest, approved_steps={"s2"}
    )
    assert report.state == "blocked"
    assert [call[0] for call in bridge.calls] == ["check_preflight"]


def test_plan_construction_and_export_copy_arguments():
    raw = {"goal": "Consultar", "planner": "manual", "steps": [
        {"id": "s1", "capability": "list_evaluations",
         "arguments": {"page": 2}, "rationale": ""},
    ]}
    plan = Plan.from_dict(raw)
    raw["steps"][0]["arguments"]["page"] = 999
    assert plan.steps[0].arguments == {"page": 2}
    exported = plan.as_dict()
    exported["steps"][0]["arguments"]["page"] = 999
    assert plan.steps[0].arguments == {"page": 2}
    assert plan.as_dict()["steps"][0]["arguments"] == {"page": 2}


@pytest.mark.asyncio
async def test_mutation_during_await_cannot_alter_executed_request():
    """MP-01: mutating the original plan mid-flight changes nothing executed."""
    plan = Plan.from_dict({"goal": "Consultar dos veces", "planner": "manual", "steps": [
        {"id": "s1", "capability": "list_targets", "arguments": {}, "rationale": ""},
        {"id": "s2", "capability": "list_evaluations",
         "arguments": {"page": 2}, "rationale": ""},
    ]})
    digest_before = plan.digest

    class MutatingBridge(FakeBridge):
        async def call(self, capability, args, **kwargs):
            result = await super().call(capability, args, **kwargs)
            plan.steps[1].arguments["page"] = 999  # attacker mid-flight
            return result

    bridge = MutatingBridge()
    report = await AgentExecutor(bridge).execute(plan)
    assert report.state == "completed"
    assert report.plan_digest == digest_before
    s2_calls = [args for name, args in bridge.calls if name == "list_evaluations"]
    assert s2_calls == [{"page": 2}]


class ScriptedBridge:
    """Bridge stub with scripted responses and recorded calls."""

    def __init__(self, responses):
        self.responses = dict(responses)
        self.calls = []

    async def call(self, capability, args, **kwargs):
        self.calls.append((capability, dict(args)))
        response = self.responses[capability]
        if isinstance(response, list):
            if len(response) > 1:
                return response.pop(0)
            return response[0]
        return response


def _two_step_binding_plan():
    return Plan.from_dict({
        "goal": "Detalle del primero", "planner": "manual", "schema": "/2",
        "steps": [
            {"id": "s1", "capability": "list_evaluations", "arguments": {},
             "rationale": "listar"},
            {"id": "s2", "capability": "get_evaluation_result",
             "arguments": {"molecule_id": {"$from": "s1.items.0.molecule_id"}},
             "rationale": "detalle"},
        ],
    })


@pytest.mark.asyncio
async def test_bindings_resolve_against_prior_results():
    bridge = ScriptedBridge({
        "list_evaluations": {"items": [{"molecule_id": "12345678-1234-1234-1234-123456789012"}]},
        "get_evaluation_result": {"id": "r1"},
    })
    report = await AgentExecutor(bridge).execute(_two_step_binding_plan())
    assert report.state == "completed"
    assert bridge.calls[1] == ("get_evaluation_result", {
        "molecule_id": "12345678-1234-1234-1234-123456789012"})


@pytest.mark.asyncio
async def test_unresolvable_binding_blocks_without_inventing():
    bridge = ScriptedBridge({"list_evaluations": {"items": []}})
    report = await AgentExecutor(bridge).execute(_two_step_binding_plan())
    assert report.state == "blocked"
    assert report.outcomes[-1].state == "blocked"
    assert [name for name, _ in bridge.calls] == ["list_evaluations"]


@pytest.mark.asyncio
async def test_binding_type_mismatch_blocks():
    bridge = ScriptedBridge({
        "list_evaluations": {"items": [{"molecule_id": "no-es-uuid"}]},
        "get_evaluation_result": {"id": "r1"},
    })
    report = await AgentExecutor(bridge).execute(_two_step_binding_plan())
    assert report.state == "blocked"
    assert [name for name, _ in bridge.calls] == ["list_evaluations"]


@pytest.mark.asyncio
async def test_bytes_results_are_wrapped_and_hashed_raw():
    from hashlib import sha256

    bridge = ScriptedBridge({"export_batch": b"a,b\n1,2\n"})
    plan = Plan.from_dict({"goal": "Exportar", "planner": "manual", "steps": [
        {"id": "s1", "capability": "export_batch",
         "arguments": {"batch_id": "b1", "format": "csv"}, "rationale": ""}]})
    report = await AgentExecutor(bridge).execute(plan)
    assert report.state == "completed"
    outcome = report.outcomes[0]
    assert outcome.result["encoding"] == "base64"
    assert outcome.result_sha256 == "sha256:" + sha256(b"a,b\n1,2\n").hexdigest()


@pytest.mark.asyncio
async def test_write_job_is_followed_to_terminal(tmp_path):
    from molchat_agent.orchestration.jobs import JobTracker
    from molchat_agent.orchestration.store import ExecutionStore

    async def no_sleep(_delay):
        pass

    bridge = ScriptedBridge({
        "approve_docking_proposal": {"task_id": "task-7"},
        "evaluation_status": [{"status": "STARTED"}, {"status": "SUCCESS"}],
    })
    store = ExecutionStore(tmp_path / "exec.db")
    jobs = JobTracker(bridge, store=store, sleep=no_sleep, jitter=0)
    plan = Plan.from_dict({"goal": "Aprobar y seguir", "planner": "manual", "steps": [
        {"id": "s1", "capability": "approve_docking_proposal",
         "arguments": {"proposal_id": "p1", "proposal_hash": "sha256:" + "c" * 64},
         "rationale": ""}]})
    report = await AgentExecutor(bridge, store=store, jobs=jobs).execute(
        plan, approval_digest=plan.digest, approved_steps={"s1"})
    assert report.state == "completed"
    assert report.outcomes[0].result["final"]["status"] == "SUCCESS"
    transitions = store.transitions(plan.digest)
    assert [(t["from"], t["to"]) for t in transitions] == [
        ("approved", "running"), ("running", "waiting_job"),
        ("waiting_job", "running"), ("running", "done")]
    assert store.pending_jobs(plan.digest) == []


@pytest.mark.asyncio
async def test_failed_job_fails_report(tmp_path):
    from molchat_agent.orchestration.jobs import JobTracker
    from molchat_agent.orchestration.store import ExecutionStore

    async def no_sleep(_delay):
        pass

    bridge = ScriptedBridge({
        "approve_docking_proposal": {"task_id": "task-8"},
        "evaluation_status": [{"status": "FAILURE", "error": "vina murió"}],
    })
    store = ExecutionStore(tmp_path / "exec.db")
    jobs = JobTracker(bridge, store=store, sleep=no_sleep, jitter=0)
    plan = Plan.from_dict({"goal": "Aprobar", "planner": "manual", "steps": [
        {"id": "s1", "capability": "approve_docking_proposal",
         "arguments": {"proposal_id": "p1", "proposal_hash": "sha256:" + "c" * 64},
         "rationale": ""}]})
    report = await AgentExecutor(bridge, store=store, jobs=jobs).execute(
        plan, approval_digest=plan.digest, approved_steps={"s1"})
    assert report.state == "failed"
    assert "FAILURE" in (report.outcomes[0].error or "")


@pytest.mark.asyncio
async def test_read_steps_never_trigger_follow():
    bridge = ScriptedBridge({"evaluation_status": {"status": "STARTED", "task_id": "t"}})
    from molchat_agent.orchestration.jobs import JobTracker

    async def no_sleep(_delay):
        pass

    jobs = JobTracker(bridge, sleep=no_sleep, jitter=0)
    plan = Plan.from_dict({"goal": "Consultar", "planner": "manual", "steps": [
        {"id": "s1", "capability": "evaluation_status",
         "arguments": {"task_id": "task-1"}, "rationale": ""}]})
    report = await AgentExecutor(bridge, jobs=jobs).execute(plan)
    assert report.state == "completed"
    assert bridge.calls == [("evaluation_status", {"task_id": "task-1"})]


@pytest.mark.asyncio
async def test_budget_exceeded_blocks(tmp_path):
    from molchat_agent.orchestration.budget import Budget
    from molchat_agent.orchestration.store import ExecutionStore

    plan = Plan.from_dict({"goal": "Consultar", "planner": "manual", "steps": [
        {"id": "s1", "capability": "list_targets", "arguments": {}, "rationale": ""}]})
    report = await AgentExecutor(
        ScriptedBridge({"list_targets": []}),
        store=ExecutionStore(tmp_path / "exec.db"),
        budget=Budget(max_time_s=0.0)).execute(plan)
    assert report.state == "blocked"
    assert "Presupuesto" in (report.outcomes[0].error or "")


@pytest.mark.asyncio
async def test_resume_completes_without_reexecuting(tmp_path):
    from molchat_agent.orchestration.jobs import JobTracker
    from molchat_agent.orchestration.store import ExecutionStore

    async def no_sleep(_delay):
        pass

    bridge = ScriptedBridge({
        "list_evaluations": {"items": [{"molecule_id": "12345678-1234-1234-1234-123456789012"}]},
        "get_evaluation_result": {"id": "r1"},
    })
    store = ExecutionStore(tmp_path / "exec.db")
    jobs = JobTracker(bridge, store=store, sleep=no_sleep, jitter=0)
    plan = _two_step_binding_plan()
    first = await AgentExecutor(bridge, store=store, jobs=jobs).execute(plan)
    assert first.state == "completed"
    calls_after_first = len(bridge.calls)
    # Terminal plans resume as a no-op rebuild from the store.
    second = await AgentExecutor(bridge, store=store, jobs=jobs).resume(plan.digest)
    assert second.state == "completed"
    assert len(second.outcomes) == 2
    assert len(bridge.calls) == calls_after_first


@pytest.mark.asyncio
async def test_resume_continues_waiting_job_without_relaunch(tmp_path):
    from molchat_agent.orchestration.jobs import JobTracker
    from molchat_agent.orchestration.store import ExecutionStore

    async def no_sleep(_delay):
        pass

    bridge = ScriptedBridge({
        "approve_docking_proposal": {"task_id": "task-9"},
        "evaluation_status": [{"status": "STARTED"}, {"status": "SUCCESS"}],
    })
    store = ExecutionStore(tmp_path / "exec.db")
    jobs = JobTracker(bridge, store=store, sleep=no_sleep, jitter=0)
    plan = Plan.from_dict({"goal": "Aprobar", "planner": "manual", "steps": [
        {"id": "s1", "capability": "approve_docking_proposal",
         "arguments": {"proposal_id": "p1", "proposal_hash": "sha256:" + "c" * 64},
         "rationale": ""}]})
    # Simulate a crash after launch: plan running, one pending job row.
    store.save_plan(plan.digest, plan.as_dict(), "waiting_job")
    store.save_job(plan.digest, "s1", "evaluation", "task-9")
    report = await AgentExecutor(bridge, store=store, jobs=jobs).resume(
        plan.digest, approval_digest=plan.digest, approved_steps={"s1"})
    assert report.state == "completed"
    launches = [c for c in bridge.calls if c[0] == "approve_docking_proposal"]
    assert launches == []  # the launch was NOT repeated
    assert report.outcomes[0].result["final"]["status"] == "SUCCESS"


def _approve_plan():
    return Plan.from_dict({"goal": "Aprobar", "planner": "manual", "steps": [
        {"id": "s1", "capability": "approve_docking_proposal",
         "arguments": {"proposal_id": "p1", "proposal_hash": "sha256:" + "c" * 64},
         "rationale": ""}]})


@pytest.mark.asyncio
async def test_lost_response_on_write_is_ambiguous_without_resend(tmp_path):
    """MP-04: lost response after create -> ambiguous, single send."""
    from molchat_agent.bridge import BridgeTransportError
    from molchat_agent.orchestration.jobs import JobTracker
    from molchat_agent.orchestration.store import ExecutionStore

    async def no_sleep(_delay):
        pass

    class LossyBridge(ScriptedBridge):
        async def call(self, capability, args, **kwargs):
            if capability == "approve_docking_proposal":
                self.calls.append((capability, dict(args)))
                raise BridgeTransportError("conexión cortada")
            return await super().call(capability, args, **kwargs)

    bridge = LossyBridge({})
    store = ExecutionStore(tmp_path / "exec.db")
    jobs = JobTracker(bridge, store=store, sleep=no_sleep, jitter=0)
    plan = _approve_plan()
    report = await AgentExecutor(bridge, store=store, jobs=jobs).execute(
        plan, approval_digest=plan.digest, approved_steps={"s1"})
    assert report.state == "ambiguous"
    assert "Sin reenvío" in report.outcomes[0].error
    sends = [c for c in bridge.calls if c[0] == "approve_docking_proposal"]
    assert len(sends) == 1
    # Retrying the same plan refuses without a second send.
    again = await AgentExecutor(bridge, store=store, jobs=jobs).execute(
        plan, approval_digest=plan.digest, approved_steps={"s1"})
    assert again.state == "ambiguous"
    assert len([c for c in bridge.calls if c[0] == "approve_docking_proposal"]) == 1


@pytest.mark.asyncio
async def test_lost_response_on_read_is_plain_failure():
    from molchat_agent.bridge import BridgeTransportError

    class LossyBridge(ScriptedBridge):
        async def call(self, capability, args, **kwargs):
            raise BridgeTransportError("corte")

    plan = Plan.from_dict({"goal": "g", "planner": "m", "steps": [
        {"id": "s1", "capability": "list_targets", "arguments": {}, "rationale": ""}]})
    report = await AgentExecutor(LossyBridge({})).execute(plan)
    assert report.state == "failed"


@pytest.mark.asyncio
async def test_concurrent_same_plan_sends_once(tmp_path):
    import asyncio

    from molchat_agent.orchestration.store import ExecutionStore

    bridge = ScriptedBridge({"approve_docking_proposal": {"task_id": "t"}})
    store = ExecutionStore(tmp_path / "exec.db")
    plan = _approve_plan()
    first, second = await asyncio.gather(
        AgentExecutor(bridge, store=store).execute(
            plan, approval_digest=plan.digest, approved_steps={"s1"}),
        AgentExecutor(bridge, store=store).execute(
            plan, approval_digest=plan.digest, approved_steps={"s1"}))
    sends = [c for c in bridge.calls if c[0] == "approve_docking_proposal"]
    assert len(sends) == 1
    states = sorted([first.state, second.state])
    assert set(states) <= {"completed", "ambiguous"}
    assert "completed" in states  # exactly one run did the work


@pytest.mark.asyncio
async def test_same_key_different_body_is_refused(tmp_path):
    from molchat_agent.orchestration.store import ExecutionStore

    store = ExecutionStore(tmp_path / "exec.db")
    plan = _approve_plan()
    key = f"{plan.digest}:s1"
    assert store.claim_key(key, plan.digest, "s1", "hash-original") == "claimed"
    assert store.claim_key(key, plan.digest, "s1", "hash-original") == "duplicate"
    assert store.claim_key(key, plan.digest, "s1", "hash-distinto") == "conflict"
    # Executor-level: pre-claimed key with other params -> blocked, zero sends.
    store2 = ExecutionStore(tmp_path / "exec2.db")
    store2.save_plan(plan.digest, plan.as_dict())
    store2.claim_key(key, plan.digest, "s1", "hash-distinto")
    bridge = ScriptedBridge({"approve_docking_proposal": {"task_id": "t"}})
    report = await AgentExecutor(bridge, store=store2).execute(
        plan, approval_digest=plan.digest, approved_steps={"s1"})
    assert report.state == "blocked"
    assert bridge.calls == []


@pytest.mark.asyncio
async def test_reconnect_with_fresh_objects_resumes_without_relaunch(tmp_path):
    """MP-04: new process, same DB file -> resume, never relaunch."""
    from molchat_agent.orchestration.jobs import JobTracker
    from molchat_agent.orchestration.store import ExecutionStore

    async def no_sleep(_delay):
        pass

    db = tmp_path / "exec.db"
    plan = _two_step_binding_plan()
    bridge = ScriptedBridge({
        "list_evaluations": {"items": [{"molecule_id": "12345678-1234-1234-1234-123456789012"}]},
        "get_evaluation_result": {"id": "r1"},
    })
    first = await AgentExecutor(bridge, store=ExecutionStore(db)).execute(plan)
    assert first.state == "completed"
    # "Restart": brand-new objects over the same file.
    bridge2 = ScriptedBridge({
        "list_evaluations": {"items": [{"molecule_id": "12345678-1234-1234-1234-123456789012"}]},
        "get_evaluation_result": {"id": "r1"},
    })
    store2 = ExecutionStore(db)
    jobs2 = JobTracker(bridge2, store=store2, sleep=no_sleep, jitter=0)
    second = await AgentExecutor(bridge2, store=store2, jobs=jobs2).resume(plan.digest)
    assert second.state == "completed"
    assert bridge2.calls == []


@pytest.mark.asyncio
async def test_explicit_cancel_step_completes_once():
    bridge = ScriptedBridge({"cancel_evaluation": {"cancelled": True}})
    plan = Plan.from_dict({"goal": "Cancelar", "planner": "manual", "steps": [
        {"id": "s1", "capability": "cancel_evaluation",
         "arguments": {"task_id": "task-1"}, "rationale": ""}]})
    report = await AgentExecutor(bridge).execute(
        plan, approval_digest=plan.digest, approved_steps={"s1"})
    assert report.state == "completed"
    assert bridge.calls == [("cancel_evaluation", {"task_id": "task-1"})]


@pytest.mark.asyncio
async def test_follow_poll_failure_maps_to_failed_not_crash():
    bridge = ScriptedBridge({"approve_docking_proposal": {"task_id": "t"}})
    from molchat_agent.orchestration.jobs import JobTracker

    async def no_sleep(_delay):
        pass

    async def boom(*args, **kwargs):
        raise RuntimeError("sondeo roto")

    jobs = JobTracker(bridge, sleep=no_sleep, jitter=0)
    jobs.follow_evaluation = boom  # type: ignore[method-assign]
    plan = _approve_plan()
    report = await AgentExecutor(bridge, jobs=jobs).execute(
        plan, approval_digest=plan.digest, approved_steps={"s1"})
    assert report.state == "failed"
    assert "seguimiento" in (report.outcomes[0].error or "")


@pytest.mark.asyncio
async def test_report_echoes_approvals_presented():
    plan = make_approval_plan()
    report = await AgentExecutor(FakeBridge()).execute(
        plan, approval_digest=plan.digest, approved_steps={"s1"})
    assert report.as_dict()["approvals"] == {"digest": plan.digest, "steps": ["s1"]}


@pytest.mark.asyncio
async def test_reevaluate_does_not_alter_prior_evidence(tmp_path):
    """MP-05: each run's evidence is immutable under its own digest."""
    from molchat_agent.orchestration.store import ExecutionStore

    db = tmp_path / "exec.db"
    first_id = "12345678-1234-1234-1234-123456789012"
    plan_a = Plan.from_dict({"goal": "A", "planner": "m", "steps": [
        {"id": "s1", "capability": "get_evaluation_result",
         "arguments": {"molecule_id": first_id}, "rationale": ""}]})
    bridge_a = ScriptedBridge({"get_evaluation_result": {"affinity_kcal": -8.1}})
    report_a = await AgentExecutor(bridge_a, store=ExecutionStore(db)).execute(plan_a)
    path_a = tmp_path / "a.json"
    save_report(report_a, path_a)
    bytes_before = path_a.read_bytes()
    plan_b = Plan.from_dict({"goal": "B", "planner": "m", "steps": [
        {"id": "s1", "capability": "get_evaluation_result",
         "arguments": {"molecule_id": first_id}, "rationale": ""}]})
    bridge_b = ScriptedBridge({"get_evaluation_result": {"affinity_kcal": -7.0}})
    await AgentExecutor(bridge_b, store=ExecutionStore(db)).execute(plan_b)
    assert path_a.read_bytes() == bytes_before
    stored = ExecutionStore(db).outcomes(plan_a.digest)
    assert stored[0]["result"] == {"affinity_kcal": -8.1}

