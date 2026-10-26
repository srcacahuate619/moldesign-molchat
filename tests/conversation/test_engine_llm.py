"""Engine LLM path: verified conceptual answers, consent, deferrals."""

import json
from pathlib import Path

import httpx
import pytest

from molchat_agent.conversation.engine import ConversationEngine
from molchat_agent.conversation.evidence import VERIFICATION_NOTE
from molchat_agent.conversation.memory import MemoryStore, PersistenciaFallida
from molchat_agent.conversation.tools import QualityBackend
from molchat_agent.config import load_config
from molchat_agent.providers import build_registry

FIXTURES = Path(__file__).parent.parent / "quality" / "fixtures" / "properties.json"


@pytest.fixture
def fake_engine(tmp_path):
    registry = build_registry(load_config({"MOLCHAT_PROVIDER": "fake"}))
    engine = ConversationEngine(
        registry=registry, backend=QualityBackend(FIXTURES),
        memory=MemoryStore(tmp_path / "memory.db"), user_id="llm-test")
    conv_id = engine._memory.create_conversation("llm-test")
    return engine, conv_id


def _meta_engine(tmp_path, chat_body, consents="c.json"):
    def handle(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": chat_body}}]})

    config = load_config({"MODEL_API_KEY": "test-key",
                          "MOLCHAT_CONSENTS_FILE": str(tmp_path / consents)})
    transport = httpx.MockTransport(handle)
    client = httpx.AsyncClient(transport=transport)
    registry = build_registry(config, clients={"meta": client})
    engine = ConversationEngine(
        registry=registry, backend=QualityBackend(FIXTURES),
        memory=MemoryStore(tmp_path / "memory.db"), user_id="llm-test")
    return engine, engine._memory.create_conversation("llm-test")


@pytest.mark.asyncio
async def test_conceptual_uses_canned_fake_without_tools(fake_engine):
    engine, conv_id = fake_engine
    result = await engine.turn(conv_id, "qué es un fármaco?")
    assert result.intent_name == "conceptual"
    assert result.used_llm is True
    assert "demostración" in result.text
    assert engine._backend.calls == []


@pytest.mark.asyncio
async def test_empty_greeting_and_invalid_are_safe(fake_engine):
    engine, conv_id = fake_engine
    assert "pregunta" in (await engine.turn(conv_id, "")).text
    assert "Hola" in (await engine.turn(conv_id, "hola")).text
    result = await engine.turn(conv_id, "calcula propiedades de KILLMEnow")
    assert result.intent_name == "invalid_smiles"
    assert "no es válido" in result.text


@pytest.mark.asyncio
async def test_unknown_routes_to_canned_conceptual(fake_engine):
    engine, conv_id = fake_engine
    result = await engine.turn(conv_id, "zzzzzzzz")
    assert result.intent_name == "unknown"
    assert "demostración" in result.text


@pytest.mark.asyncio
async def test_deferrals_name_their_phase(fake_engine):
    engine, conv_id = fake_engine
    assert "Fase 3" in (await engine.turn(conv_id, "calcula la afinidad de la aspirina contra 7E2Y")).text
    assert "Fase 5" in (await engine.turn(conv_id, "que moleculas hay contra 5-HT1A?")).text
    assert "no diseño moléculas" in (await engine.turn(
        conv_id, "Dame el SMILES de un análogo con un anillo fusionado")).text.lower()


@pytest.mark.asyncio
async def test_remote_conceptual_without_consent_emits_nothing(tmp_path):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    config = load_config({"MODEL_API_KEY": "test-key",
                          "MOLCHAT_CONSENTS_FILE": str(tmp_path / "c.json")})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    registry = build_registry(config, clients={"meta": client})
    engine = ConversationEngine(
        registry=registry, backend=QualityBackend(FIXTURES),
        memory=MemoryStore(tmp_path / "memory.db"), user_id="llm-test")
    conv_id = engine._memory.create_conversation("llm-test")
    result = await engine.turn(conv_id, "qué es un fármaco?")
    assert result.used_llm is False
    assert "meta@api.meta.ai" in result.text
    assert calls == []


@pytest.mark.asyncio
async def test_remote_conceptual_after_grant_uses_llm(tmp_path):
    engine, conv_id = _meta_engine(tmp_path, "Un fármaco es una sustancia con efecto.")
    engine._registry.grant("meta")
    result = await engine.turn(conv_id, "qué es un fármaco?")
    assert result.used_llm is True
    assert "sustancia" in result.text


@pytest.mark.asyncio
async def test_llm_numbers_without_tools_are_withheld(tmp_path):
    engine, conv_id = _meta_engine(tmp_path, "Un fármaco pesa MW 180.2 Da.")
    engine._registry.grant("meta")
    result = await engine.turn(conv_id, "qué es un fármaco?")
    assert VERIFICATION_NOTE in result.text
    assert "180.2" not in result.text
    assert "[dato no verificado]" in result.text


@pytest.mark.asyncio
async def test_query_quotation_and_ordinals_pass_verification(tmp_path):
    engine, conv_id = _meta_engine(tmp_path, "12345 es un número.\n1. Nota uno.")
    engine._registry.grant("meta")
    result = await engine.turn(conv_id, "que es 12345?")
    assert VERIFICATION_NOTE not in result.text
    assert "12345" in result.text


class _LocalSpy:
    """Local provider capturing the messages it receives."""

    id = "local-spy"
    locality = "local"

    def __init__(self):
        from molchat_agent.providers.base import ProviderConfig
        self.config = ProviderConfig()
        self.seen = []

    async def health(self):
        from molchat_agent.providers.base import HealthCheckResult, HealthStatus
        return HealthCheckResult(status=HealthStatus.OK)

    async def plan(self, goal, catalog=None):
        raise AssertionError("unreachable")

    async def chat(self, turn):
        from molchat_agent.providers.base import ChatEvent
        self.seen.append(turn.messages)
        yield ChatEvent(type="token", text="concepto local.")
        yield ChatEvent(type="done", done=True)


def _remote_spy_engine(tmp_path):
    """Meta mock capturing the remote payload after a scientific turn."""
    seen = {}

    def handle(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "concepto."}}]})

    config = load_config({"MODEL_API_KEY": "test-key",
                          "MOLCHAT_CONSENTS_FILE": str(tmp_path / "c.json")})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    registry = build_registry(config, clients={"meta": client})
    engine = ConversationEngine(
        registry=registry, backend=QualityBackend(FIXTURES),
        memory=MemoryStore(tmp_path / "memory.db"), user_id="llm-test")
    return engine, engine._memory.create_conversation("llm-test"), seen


@pytest.mark.asyncio
async def test_remote_chat_omits_scientific_history_without_content_grant(tmp_path):
    engine, conv_id, seen = _remote_spy_engine(tmp_path)
    engine._registry.grant("meta")
    await engine.turn(conv_id, "calcula propiedades de la aspirina")
    await engine.turn(conv_id, "qué es un fármaco?")
    roles = [m["role"] for m in seen["messages"]]
    assert roles == ["system", "user"]  # no history, no summary
    assert "180.2" not in json.dumps(seen)


@pytest.mark.asyncio
async def test_remote_chat_includes_history_with_content_grant(tmp_path):
    engine, conv_id, seen = _remote_spy_engine(tmp_path)
    engine._registry.grant("meta")
    engine._registry.grant_content("meta")
    await engine.turn(conv_id, "calcula propiedades de la aspirina")
    await engine.turn(conv_id, "qué es un fármaco?")
    assert len(seen["messages"]) > 2
    assert "180.2" in json.dumps(seen)


@pytest.mark.asyncio
async def test_local_chat_keeps_context_without_grants(tmp_path):
    registry = build_registry(load_config({}))
    spy = _LocalSpy()
    registry.register(spy)
    registry.set_active("local-spy")
    engine = ConversationEngine(
        registry=registry, backend=QualityBackend(FIXTURES),
        memory=MemoryStore(tmp_path / "memory.db"), user_id="llm-test")
    conv_id = engine._memory.create_conversation("llm-test")
    await engine.turn(conv_id, "calcula propiedades de la aspirina")
    await engine.turn(conv_id, "qué es un fármaco?")
    assert len(spy.seen[0]) > 2  # local: full context, nothing leaves


@pytest.mark.asyncio
async def test_persist_failure_is_declared_not_fatal(fake_engine, monkeypatch):
    engine, conv_id = fake_engine

    def _explode(*args, **kwargs):
        raise PersistenciaFallida("disco lleno")

    monkeypatch.setattr(engine._memory, "add_message", _explode)
    result = await engine.turn(conv_id, "propiedades del etanol")
    assert "Propiedades de etanol:" in result.text
    assert "no se pudo guardar el turno" in result.text
