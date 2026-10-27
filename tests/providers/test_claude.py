"""Claude provider: Messages API shape, read-only plans, health mapping."""

import json

import httpx
import pytest

from molchat_agent.providers.base import HealthStatus, TurnContext
from molchat_agent.providers.claude import ClaudeProvider


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_plan_posts_messages_api_and_parses_text_block():
    observed = {}

    def handle(request):
        assert request.url.host == "api.anthropic.com"
        assert request.url.path == "/v1/messages"
        assert request.headers["x-api-key"] == "test-key"
        assert request.headers["anthropic-version"] == "2023-06-01"
        observed.update(json.loads(request.content))
        plan = {"steps": [{"capability": "list_targets", "arguments": {},
                            "rationale": "consultar"}]}
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": json.dumps(plan)}],
            "stop_reason": "end_turn"})

    async with _client(handle) as client:
        async with ClaudeProvider(api_key="test-key", client=client) as provider:
            plan = await provider.plan("¿Qué receptores tengo?")
    assert plan.steps[0].capability == "list_targets"
    assert "approve_docking_proposal" not in json.dumps(observed)
    assert observed["system"].startswith("Eres un planificador")
    assert observed["messages"][0]["role"] == "user"


@pytest.mark.asyncio
async def test_plan_rejects_tools_outside_sent_catalog():
    def handle(_request):
        result = {"steps": [{"capability": "approve_docking_proposal",
                              "arguments": {"proposal_id": "p",
                                            "proposal_hash": "sha256:" + "a" * 64},
                              "rationale": ""}]}
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": json.dumps(result)}]})

    async with _client(handle) as client:
        async with ClaudeProvider(api_key="test", client=client) as provider:
            from molchat_agent.providers.base import ProviderError

            with pytest.raises(ProviderError):
                await provider.plan("aprueba todo")


@pytest.mark.asyncio
async def test_chat_extracts_system_and_streams_events():
    observed = {}

    def handle(request):
        observed.update(json.loads(request.content))
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "La aspirina inhibe COX."}]})

    turn = TurnContext(text="x", messages=[
        {"role": "system", "content": "Eres químico."},
        {"role": "user", "content": "¿Qué hace la aspirina?"}])
    async with _client(handle) as client:
        async with ClaudeProvider(api_key="test", client=client) as provider:
            events = [e async for e in provider.chat(turn)]
    assert observed["system"] == "Eres químico."
    assert observed["messages"] == [
        {"role": "user", "content": "¿Qué hace la aspirina?"}]
    assert [e.type for e in events] == ["token", "done"]
    assert "COX" in events[0].text


@pytest.mark.asyncio
async def test_health_maps_key_auth_and_quota():
    async with _client(lambda r: httpx.Response(200, json={})) as client:
        provider = ClaudeProvider(client=client)
        assert (await provider.health()).status == HealthStatus.NO_API_KEY
    for status, expected in ((200, HealthStatus.OK), (401, HealthStatus.NO_API_KEY),
                             (429, HealthStatus.NO_TOKENS), (500, HealthStatus.CONNECTION_ERROR)):
        async with _client(lambda r, s=status: httpx.Response(s, json={})) as client:
            async with ClaudeProvider(api_key="test", client=client) as provider:
                assert (await provider.health()).status == expected
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        async with ClaudeProvider(api_key="") as provider:
            await provider.plan("x")
