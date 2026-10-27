"""Gemini provider: generateContent shape, role merge, health mapping."""

import json

import httpx
import pytest

from molchat_agent.providers.base import HealthStatus, TurnContext
from molchat_agent.providers.gemini import GeminiProvider, _to_contents


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _candidate(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


@pytest.mark.asyncio
async def test_plan_posts_json_mime_and_system_instruction():
    observed = {}

    def handle(request):
        assert request.url.host == "generativelanguage.googleapis.com"
        assert request.url.path.endswith(":generateContent")
        assert request.headers["x-goog-api-key"] == "test-key"
        observed.update(json.loads(request.content))
        plan = {"steps": [{"capability": "list_targets", "arguments": {},
                            "rationale": "consultar"}]}
        return httpx.Response(200, json=_candidate(json.dumps(plan)))

    async with _client(handle) as client:
        async with GeminiProvider(api_key="test-key", client=client) as provider:
            plan = await provider.plan("¿Qué receptores tengo?")
    assert plan.steps[0].capability == "list_targets"
    assert observed["generationConfig"]["responseMimeType"] == "application/json"
    assert "planificador" in observed["system_instruction"]["parts"][0]["text"]
    assert "approve_docking_proposal" not in json.dumps(observed)


def test_role_mapping_merges_consecutive_turns():
    system, contents = _to_contents([
        {"role": "system", "content": "Eres químico."},
        {"role": "user", "content": "hola"},
        {"role": "user", "content": "¿aspirina?"},
        {"role": "assistant", "content": "claro"},
    ])
    assert system == "Eres químico."
    assert contents == [
        {"role": "user", "parts": [{"text": "hola\n¿aspirina?"}]},
        {"role": "model", "parts": [{"text": "claro"}]},
    ]


@pytest.mark.asyncio
async def test_chat_sends_contents_and_yields_text():
    def handle(_request):
        return httpx.Response(200, json=_candidate("Son 180.2 Da."))

    turn = TurnContext(text="peso de aspirina")
    async with _client(handle) as client:
        async with GeminiProvider(api_key="test", client=client) as provider:
            events = [e async for e in provider.chat(turn)]
    assert [e.type for e in events] == ["token", "done"]
    assert "180.2" in events[0].text


@pytest.mark.asyncio
async def test_health_maps_key_forbidden_and_quota():
    async with _client(lambda r: httpx.Response(200, json={})) as client:
        provider = GeminiProvider(client=client)
        assert (await provider.health()).status == HealthStatus.NO_API_KEY
    for status, expected in ((200, HealthStatus.OK), (403, HealthStatus.NO_TOKENS),
                             (429, HealthStatus.NO_TOKENS), (500, HealthStatus.CONNECTION_ERROR)):
        async with _client(lambda r, s=status: httpx.Response(s, json={})) as client:
            async with GeminiProvider(api_key="test", client=client) as provider:
                assert (await provider.health()).status == expected
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        async with GeminiProvider(api_key="") as provider:
            await provider.plan("x")
