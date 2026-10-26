import json

import pytest

from molchat_agent.executor import AgentExecutor, save_report
from molchat_agent.plan import Plan


class FakeBridge:
    def __init__(self, fail=False, preflight_blockers=None):
        self.calls = []
        self.fail = fail
        self.preflight_blockers = preflight_blockers

    async def call(self, capability, args):
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

