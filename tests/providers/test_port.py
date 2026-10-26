"""Port-level guarantees shared by every provider."""

import pytest

from molchat_agent.capabilities import PlanValidationError
from molchat_agent.plan import Plan
from molchat_agent.providers.base import (
    HealthStatus,
    ProviderError,
    plan_from_content,
    read_only_catalog,
)
from molchat_agent.providers.fake import FakeProvider
from molchat_agent.providers import TurnContext


def test_read_only_catalog_excludes_anything_not_explicitly_read():
    entries = [
        {"name": "a", "risk": "read"},
        {"name": "b", "risk": "approval_required"},
        {"name": "c"},  # no risk declared: excluded, fail closed
    ]
    assert [e["name"] for e in read_only_catalog(entries)] == ["a"]


def test_default_catalog_never_offers_sensitive_tools():
    assert all(e["risk"] == "read" for e in read_only_catalog(None))
    assert "approve_docking_proposal" not in {e["name"] for e in read_only_catalog(None)}


def test_plan_from_content_assigns_ids_and_validates_contract():
    plan = plan_from_content(
        '{"steps": [{"capability": "list_targets", "arguments": {}, "rationale": ""}]}',
        "goal", "fake:deterministic")
    assert isinstance(plan, Plan)
    assert plan.steps[0].id == "s1"


def test_plan_from_content_rejects_unknown_tools_and_bad_json():
    with pytest.raises(ProviderError):
        plan_from_content("not json", "goal", "x")
    with pytest.raises(ProviderError):
        plan_from_content(
            '{"steps": [{"capability": "run_shell", "arguments": {}, "rationale": ""}]}',
            "goal", "x")


@pytest.mark.asyncio
async def test_fake_is_deterministic_and_read_only():
    provider = FakeProvider()
    first = await provider.plan("¿Qué receptores tengo?")
    second = await provider.plan("¿Qué receptores tengo?")
    assert first.digest == second.digest
    assert first.planner == "fake:deterministic"
    assert first.steps[0].capability == "list_targets"
    assert (await provider.health()).status == HealthStatus.OK


@pytest.mark.asyncio
async def test_fake_never_invents_identifiers():
    provider = FakeProvider()
    plan = await provider.plan("Dame el estado de la tarea XYZ")
    # No task id was given, so it lists instead of guessing one.
    assert plan.steps[0].capability == "list_evaluations"


@pytest.mark.asyncio
async def test_chat_is_an_explicit_fase_2_boundary():
    with pytest.raises(NotImplementedError):
        async for _ in FakeProvider().chat(TurnContext(text="hola")):
            pass


@pytest.mark.asyncio
async def test_fake_rejects_invalid_goals():
    with pytest.raises(PlanValidationError):
        await FakeProvider().plan("")
