"""OpenAI-compatible provider: locality from URL, safe defaults."""

import json

import httpx
import pytest

from molchat_agent.providers.base import HealthStatus, ProviderError
from molchat_agent.providers.openai_compatible import OpenAICompatibleProvider


def test_locality_is_computed_from_host_not_from_name():
    local = OpenAICompatibleProvider(base_url="http://127.0.0.1:8080/v1", model="m")
    assert local.locality == "local"
    remote = OpenAICompatibleProvider(base_url="https://cloud.example/v1",
                                       api_key="test-key", model="m")
    assert remote.locality == "remote"


def test_remote_over_plain_http_is_rejected():
    with pytest.raises(ValueError, match="HTTPS"):
        OpenAICompatibleProvider(base_url="http://cloud.example/v1", model="m")


def test_unconfigured_means_remote_fail_closed():
    provider = OpenAICompatibleProvider(base_url="", model="")
    assert provider.locality == "remote"  # unknown destination: not trusted


@pytest.mark.asyncio
async def test_health_reports_config_states_without_network():
    def handle(_):
        raise AssertionError("must not emit")  # pragma: no cover

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await OpenAICompatibleProvider(base_url="", client=client).health()
        assert result.status == HealthStatus.NOT_CONFIGURED
        result = await OpenAICompatibleProvider(
            base_url="https://cloud.example/v1", model="m", client=client).health()
        assert result.status == HealthStatus.NO_API_KEY


@pytest.mark.asyncio
async def test_plan_uses_json_schema_and_read_only_catalog():
    seen: dict = {}

    def handle(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": []})
        seen.update(json.loads(request.content))
        plan = {"steps": [{"capability": "list_targets", "arguments": {},
                            "rationale": "demo"}]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(plan)}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider = OpenAICompatibleProvider(
            base_url="http://127.0.0.1:8080/v1", model="demo", client=client)
        assert (await provider.health()).status == HealthStatus.OK
        plan = await provider.plan("¿Qué receptores tengo?")
    assert seen["response_format"]["type"] == "json_schema"
    assert "approve_docking_proposal" not in json.dumps(seen)
    assert plan.planner == "openai-compatible:demo"


@pytest.mark.asyncio
async def test_plan_requires_config_before_network():
    provider = OpenAICompatibleProvider(base_url="")
    with pytest.raises(ValueError, match="OPENAI_COMPAT_BASE_URL"):
        await provider.plan("hola")
    provider = OpenAICompatibleProvider(base_url="https://cloud.example/v1", model="m")
    with pytest.raises(ValueError, match="OPENAI_COMPAT_API_KEY"):
        await provider.plan("hola")


@pytest.mark.asyncio
async def test_bad_model_output_becomes_provider_error_not_a_plan():
    def handle(_):
        return httpx.Response(200, json={"choices": [{"message": {"content": "oops"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider = OpenAICompatibleProvider(
            base_url="http://127.0.0.1:8080/v1", model="m", client=client)
        with pytest.raises(ProviderError):
            await provider.plan("hola")
