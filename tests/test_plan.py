"""Plan schemas /1 (literals) and /2 (typed bindings)."""

import pytest

from molchat_agent.plan import (
    BindingError,
    Plan,
    is_binding,
    resolve_binding,
)
from molchat_agent.tools import PlanValidationError


def _plan_2():
    return Plan.from_dict({
        "goal": "Evaluar y seguir", "planner": "manual", "schema": "/2",
        "steps": [
            {"id": "s1", "capability": "list_evaluations", "arguments": {},
             "rationale": "ver qué hay"},
            {"id": "s2", "capability": "get_evaluation_result",
             "arguments": {"molecule_id": {"$from": "s1.items.0.molecule_id"}},
             "rationale": "detalle del primero"},
        ],
    })


def test_schema_1_without_schema_key_still_parses():
    plan = Plan.from_dict({"goal": "g", "planner": "manual", "steps": [
        {"id": "s1", "capability": "list_targets", "arguments": {}, "rationale": ""}]})
    assert plan.schema == "/1"
    assert plan.as_dict()["schema"] == "/1"


def test_bindings_require_schema_2():
    raw = {"goal": "g", "planner": "manual", "steps": [
        {"id": "s1", "capability": "list_evaluations", "arguments": {}, "rationale": ""},
        {"id": "s2", "capability": "get_evaluation_result",
         "arguments": {"molecule_id": {"$from": "s1.items.0.molecule_id"}},
         "rationale": ""}]}
    with pytest.raises(PlanValidationError, match="esquema /2"):
        Plan.from_dict(raw)
    raw["schema"] = "/2"
    assert Plan.from_dict(raw).schema == "/2"


def test_step_limits_per_schema():
    def steps(n):
        return [{"id": f"s{i+1}", "capability": "list_targets",
                 "arguments": {}, "rationale": ""} for i in range(n)]

    with pytest.raises(PlanValidationError, match="entre 1 y 8"):
        Plan.from_dict({"goal": "g", "planner": "m", "steps": steps(9)})
    assert len(Plan.from_dict(
        {"goal": "g", "planner": "m", "schema": "/2", "steps": steps(25)}).steps) == 25
    with pytest.raises(PlanValidationError, match="entre 1 y 25"):
        Plan.from_dict({"goal": "g", "planner": "m", "schema": "/2", "steps": steps(26)})


@pytest.mark.parametrize("ref", ["s2.task_id", "s0.x", "s9.nope", "task_id", "s1.",
                                 "s1.a b", "s1"])
def test_malformed_or_forward_references_rejected(ref):
    raw = {"goal": "g", "planner": "m", "schema": "/2", "steps": [
        {"id": "s1", "capability": "list_evaluations", "arguments": {}, "rationale": ""},
        {"id": "s2", "capability": "evaluation_status",
         "arguments": {"task_id": {"$from": ref}}, "rationale": ""}]}
    with pytest.raises(BindingError):
        Plan.from_dict(raw)


def test_undeclared_head_route_rejected():
    raw = {"goal": "g", "planner": "m", "schema": "/2", "steps": [
        {"id": "s1", "capability": "list_targets", "arguments": {}, "rationale": ""},
        {"id": "s2", "capability": "evaluation_status",
         "arguments": {"task_id": {"$from": "s1.targets.0.id"}}, "rationale": ""}]}
    with pytest.raises(BindingError, match="no declarada"):
        Plan.from_dict(raw)


def test_binding_with_extra_keys_is_not_a_binding():
    raw = {"goal": "g", "planner": "m", "schema": "/2", "steps": [
        {"id": "s1", "capability": "list_evaluations", "arguments": {}, "rationale": ""},
        {"id": "s2", "capability": "evaluation_status",
         "arguments": {"task_id": {"$from": "s1.items", "default": "x"}},
         "rationale": ""}]}
    with pytest.raises(PlanValidationError):
        Plan.from_dict(raw)
    assert is_binding({"$from": "s1.x"}) is True
    assert is_binding({"$from": "s1.x", "y": 1}) is False
    assert is_binding("s1.x") is False


def test_resolve_walks_dicts_and_lists():
    results = {"s1": {"items": [{"molecule_id": "m-1"}, {"molecule_id": "m-2"}]}}
    assert resolve_binding("s1.items.0.molecule_id", results) == "m-1"
    assert resolve_binding("s1.items.1.molecule_id", results) == "m-2"
    with pytest.raises(BindingError):
        resolve_binding("s1.items.5.molecule_id", results)
    with pytest.raises(BindingError):
        resolve_binding("s1.missing", results)
    with pytest.raises(BindingError):
        resolve_binding("s2.anything", results)
    with pytest.raises(BindingError):
        resolve_binding("nope", results)


def test_digest_covers_unresolved_bindings():
    first = _plan_2()
    second = _plan_2()
    assert first.digest == second.digest
    assert "$from" in first.as_dict()["steps"][1]["arguments"]["molecule_id"]
