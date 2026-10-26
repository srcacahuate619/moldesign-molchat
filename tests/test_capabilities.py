import pytest

from molchat_agent.capabilities import CAPABILITIES, PlanValidationError, capability
from molchat_agent.plan import Plan


def make_plan(tool="list_targets", arguments=None):
    return Plan.from_dict({
        "goal": "Probar las capacidades del laboratorio", "planner": "test",
        "steps": [{"id": "s1", "capability": tool,
                   "arguments": {} if arguments is None else arguments, "rationale": "Prueba"}],
    })


def test_catalog_only_declares_known_routes():
    assert CAPABILITIES["check_preflight"].path == "/evaluation/preflight"
    assert CAPABILITIES["approve_docking_proposal"].risk == "approval_required"
    assert all(c.path.startswith("/") for c in CAPABILITIES.values())


def test_plan_digest_changes_when_parameters_change():
    first = make_plan("list_evaluations", {"page": 1})
    second = make_plan("list_evaluations", {"page": 2})
    assert first.digest.startswith("sha256:")
    assert first.digest != second.digest


@pytest.mark.parametrize("tool,args", [
    ("execute_shell", {}),
    ("list_targets", {"url": "http://evil.example"}),
    ("check_preflight", {"target_pdb_id": "1HSG"}),
    ("check_preflight", {"target_pdb_id": "1HSG", "smiles": ""}),
    ("evaluation_status", {"task_id": "../../etc/passwd"}),
    ("list_evaluations", {"page": True}),
    ("approve_docking_proposal", {"proposal_id": "safe", "proposal_hash": "123"}),
])
def test_reject_untrusted_or_invalid_actions(tool, args):
    with pytest.raises(PlanValidationError):
        make_plan(tool, args)


def test_route_is_fixed_and_parameters_encoded():
    tool = capability("evaluation_status")
    method, path, params = tool.request({"task_id": "case_123-4"})
    assert (method, path, params) == ("GET", "/evaluation/status/case_123-4", {})


def test_missing_fields_and_too_many_steps_rejected():
    with pytest.raises(PlanValidationError):
        Plan.from_dict({"goal": "x", "steps": [], "planner": "manual"})
    with pytest.raises(PlanValidationError):
        Plan.from_dict({"goal": "x", "steps": [
            {"id": f"s{i+1}", "capability": "list_targets", "arguments": {}, "rationale": ""}
            for i in range(9)], "planner": "manual"})

