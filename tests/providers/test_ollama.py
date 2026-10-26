"""Ollama provider: native API, model must be installed."""

import json

import httpx
import pytest

from molchat_agent.providers.base import HealthStatus, ProviderError
from molchat_agent.providers.local_http import OllamaProvider

TAGS = {"models": [{"name": "gemma3:1b"}, {"name": "qwen-test:latest"}]}
PLAN = {"steps": [{"capability": "list_targets", "arguments": {},
                    "rationale": "demo"}]}


def _transport():
    def handle(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json=TAGS)
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["stream"] is False
        return httpx.Response(200, json={"message": {"content": json.dumps(PLAN)}})

    return httpx.MockTransport(handle)


def test_non_loopback_base_is_rejected_at_construction():
    with pytest.raises(ValueError, match="loopback"):
        OllamaProvider(base_url="http://192.168.1.10:11434", model="m")


@pytest.mark.asyncio
async def test_health_validates_model_is_installed():
    async with httpx.AsyncClient(transport=_transport()) as client:
        ok = await OllamaProvider(model="gemma3:1b", client=client).health()
        assert ok.status == HealthStatus.OK
        bare = await OllamaProvider(model="qwen-test", client=client).health()
        assert bare.status == HealthStatus.OK  # resolves to :latest
        missing = await OllamaProvider(model="nope:99", client=client).health()
        assert missing.status == HealthStatus.NOT_AVAILABLE
        assert "ollama pull" in missing.message


@pytest.mark.asyncio
async def test_plan_refuses_uninstalled_model_before_chatting():
    calls = []

    def handle(request):
        calls.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json=TAGS)
        raise AssertionError("must not chat")  # pragma: no cover

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderError, match="ollama pull"):
            await OllamaProvider(model="nope:99", client=client).plan("hola")
    assert calls == ["/api/tags"]


@pytest.mark.asyncio
async def test_plan_returns_valid_tagged_plan():
    async with httpx.AsyncClient(transport=_transport()) as client:
        plan = await OllamaProvider(model="gemma3:1b", client=client).plan(
            "¿Qué receptores tengo?")
    assert plan.planner == "ollama:gemma3:1b"
    assert plan.steps[0].capability == "list_targets"
