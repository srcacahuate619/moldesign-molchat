"""Non-streaming chat for the conceptual path (Fase 2)."""

import httpx
import pytest

from molchat_agent.providers.base import ProviderError, TurnContext
from molchat_agent.providers.local_http import LlamaServerProvider, OllamaProvider
from molchat_agent.providers.meta import MetaProvider
from molchat_agent.providers.openai_compatible import OpenAICompatibleProvider


def _completions_mock(content="Un fármaco es una sustancia con efecto terapéutico."):
    def handle(request):
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    return httpx.MockTransport(handle)


@pytest.mark.asyncio
async def test_chat_collects_token_then_done():
    async with httpx.AsyncClient(transport=_completions_mock()) as client:
        events = [e async for e in MetaProvider(api_key="test-key", client=client).chat(
            TurnContext(text="qué es un fármaco?"))]
    assert "".join(e.text for e in events if not e.done).startswith("Un fármaco")
    assert events[-1].done is True


@pytest.mark.asyncio
async def test_chat_sends_full_messages_when_given():
    seen = {}

    def handle(request):
        import json
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        [e async for e in MetaProvider(api_key="test-key", client=client).chat(
            TurnContext(text="q", messages=messages))]
    assert seen["messages"] == messages


@pytest.mark.asyncio
async def test_chat_errors_become_provider_error():
    def handle(_):
        return httpx.Response(500, json={"error": "boom"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderError):
            [e async for e in LlamaServerProvider(model="m", client=client).chat(
                TurnContext(text="hola"))]


@pytest.mark.asyncio
async def test_local_chats_extract_content():
    async with httpx.AsyncClient(transport=_completions_mock("r-llama")) as client:
        events = [e async for e in LlamaServerProvider(model="m", client=client).chat(
            TurnContext(text="hola"))]
    assert "".join(e.text for e in events if not e.done) == "r-llama"

    def ollama(request):
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json={"message": {"content": "r-ollama"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(ollama)) as client:
        events = [e async for e in OllamaProvider(model="m", client=client).chat(
            TurnContext(text="hola"))]
    assert "".join(e.text for e in events if not e.done) == "r-ollama"


@pytest.mark.asyncio
async def test_openai_chat_needs_config_first():
    with pytest.raises(ValueError, match="OPENAI_COMPAT_BASE_URL"):
        [e async for e in OpenAICompatibleProvider(base_url="").chat(
            TurnContext(text="hola"))]
