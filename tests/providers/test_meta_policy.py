"""Meta policy: Standard only, contributor never, reasoning configured."""

import json

import httpx
import pytest

from molchat_agent.providers import build_registry
from molchat_agent.providers.base import HealthStatus
from molchat_agent.providers.meta import (
    DEFAULT_REASONING_EFFORT,
    MetaProvider,
)


def _ok_transport(seen=None):
    def handle(request):
        if seen is not None:
            seen.update(json.loads(request.content))
        plan = {"steps": [{"capability": "list_targets", "arguments": {},
                            "rationale": "demo"}]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(plan)}}]})
    return httpx.MockTransport(handle)


def test_default_model_is_standard_and_reasoning_is_medium():
    provider = MetaProvider(api_key="test")
    assert provider.config.model == "muse-spark-1.3"
    assert provider.reasoning_effort == DEFAULT_REASONING_EFFORT == "medium"


@pytest.mark.parametrize("model", [
    "muse-spark-1.3-contributor",
    "MUSE-SPARK-1.3-CONTRIBUTOR",
    "other-contributor-tier",
])
def test_contributor_variants_are_always_rejected(model):
    with pytest.raises(ValueError, match="prohibido"):
        MetaProvider(api_key="test", model=model)


def test_unknown_reasoning_level_is_rejected():
    with pytest.raises(ValueError, match="reasoning_effort"):
        MetaProvider(api_key="test", reasoning_effort="ultra")


@pytest.mark.asyncio
async def test_payload_carries_model_and_reasoning_effort():
    seen: dict = {}
    transport = _ok_transport(seen)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = MetaProvider(api_key="test", reasoning_effort="high", client=client)
        plan = await provider.plan("¿Qué receptores tengo?")
    assert seen["model"] == "muse-spark-1.3"
    assert seen["reasoning_effort"] == "high"
    assert plan.planner == "meta:muse-spark-1.3"


@pytest.mark.asyncio
async def test_plan_without_key_fails_before_network():
    def handle(_):
        raise AssertionError("must not emit without a key")  # pragma: no cover

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="MODEL_API_KEY"):
            await MetaProvider(client=client).plan("hola")


@pytest.mark.asyncio
async def test_health_reports_key_and_auth_states():
    assert (await MetaProvider().health()).status == HealthStatus.NO_API_KEY

    def unauthorized(_):
        return httpx.Response(401, json={"error": "bad key"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(unauthorized)) as client:
        result = await MetaProvider(api_key="test", client=client).health()
    assert result.status == HealthStatus.NO_API_KEY
    assert "test" not in result.message

    async with httpx.AsyncClient(transport=_ok_transport()) as client:
        result = await MetaProvider(api_key="test", client=client).health()
    assert result.status == HealthStatus.OK


def test_factory_registers_meta_and_survives_bad_config():
    from molchat_agent.config import load_config

    registry = build_registry(load_config({}))
    assert registry.ids() == ["anthropic", "baseten-hackathon", "deepseek", "fake", "gemini", "llama-server",
                              "meta", "nvidia", "ollama", "openai"]
    assert registry.active_id is None  # sin proveedor por defecto

    broken = build_registry(load_config({"META_MODEL": "muse-spark-1.3-contributor"}))
    provider = broken.get("meta")
    assert type(provider).__name__ == "BrokenProvider"


@pytest.mark.asyncio
async def test_fabricated_approval_step_is_rejected_locally():
    """MP-02: approve exists in the catalog but was never offered to the model."""
    fabricated = {"steps": [{
        "capability": "approve_docking_proposal",
        "arguments": {"proposal_id": "p1", "proposal_hash": "sha256:" + "a" * 64},
        "rationale": "fabricado"}]}

    def handle(_):
        return httpx.Response(200, json={"choices": [
            {"message": {"content": json.dumps(fabricated)}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(RuntimeError, match="no entregó un plan válido"):
            await MetaProvider(api_key="test", client=client).plan("aprueba algo")
