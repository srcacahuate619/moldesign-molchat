"""llama-server provider: loopback-only OpenAI-compatible planning."""

import json

import httpx
import pytest

from molchat_agent.providers.base import HealthStatus, ProviderError
from molchat_agent.providers.local_http import LlamaServerProvider


def _plan_body(capability="list_targets"):
    return {"steps": [{"capability": capability, "arguments": {},
                        "rationale": "demo"}]}


def test_non_loopback_base_is_rejected_at_construction():
    with pytest.raises(ValueError, match="loopback"):
        LlamaServerProvider(base_url="https://cloud.example/v1", model="m")
    assert LlamaServerProvider(
        base_url="http://127.0.0.1:8400/v1", model="m").locality == "local"


@pytest.mark.asyncio
async def test_llama_server_passes_tools_and_returns_structured_call():
    def handler(request):
        data = json.loads(request.content)
        assert data["tools"][0]["function"]["name"] == "demo"
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": None,
            "tool_calls": [{"id": "call-1", "type": "function", "function": {"name": "demo", "arguments": "{}"}}]}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = LlamaServerProvider(model="m", client=client)
        result = await provider.chat_with_tools([{"role": "user", "content": "hola"}],
                                                [{"type": "function", "function": {"name": "demo"}}])
    assert result["tool_calls"][0]["function"]["name"] == "demo"


@pytest.mark.asyncio
async def test_health_reports_models_or_connection_error():
    def healthy(request):
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "qwen-test"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(healthy)) as client:
        result = await LlamaServerProvider(model="qwen-test", client=client).health()
    assert result.status == HealthStatus.OK
    assert "qwen-test" in result.message

    def down(_):
        raise httpx.ConnectError("refused")

    async with httpx.AsyncClient(transport=httpx.MockTransport(down)) as client:
        result = await LlamaServerProvider(model="m", client=client).health()
    assert result.status == HealthStatus.CONNECTION_ERROR


@pytest.mark.asyncio
async def test_plan_needs_a_model_before_network():
    def handle(_):
        raise AssertionError("must not emit")  # pragma: no cover

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="LLAMA_SERVER_MODEL"):
            await LlamaServerProvider(model="", client=client).plan("hola")


@pytest.mark.asyncio
async def test_plan_parses_chat_completions_json():
    seen: dict = {}

    def handle(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [
            {"message": {"content": json.dumps(_plan_body())}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider = LlamaServerProvider(model="qwen-test", client=client)
        plan = await provider.plan("¿Qué receptores tengo?")
    assert plan.planner == "llama-server:qwen-test"
    assert plan.steps[0].capability == "list_targets"
    assert seen["response_format"]["type"] == "json_schema"
    # Generation is bounded: a plan is short JSON, and an unbounded thinking
    # model would spend the whole client timeout reasoning (Fase 1 live run).
    assert seen["max_tokens"] == provider.config.max_tokens


@pytest.mark.asyncio
async def test_server_error_becomes_provider_error():
    def handle(_):
        return httpx.Response(500, json={"error": "boom"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderError):
            await LlamaServerProvider(model="m", client=client).plan("hola")


@pytest.mark.asyncio
async def test_fabricated_approval_step_is_rejected_locally():
    """MP-02 on the raw-ProviderError path (no RuntimeError wrap here)."""
    fabricated = {"steps": [{
        "capability": "approve_docking_proposal",
        "arguments": {"proposal_id": "p1", "proposal_hash": "sha256:" + "a" * 64},
        "rationale": "fabricado"}]}

    def handle(_):
        return httpx.Response(200, json={"choices": [
            {"message": {"content": json.dumps(fabricated)}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderError, match="fuera del catálogo enviado"):
            await LlamaServerProvider(model="m", client=client).plan("aprueba algo")
