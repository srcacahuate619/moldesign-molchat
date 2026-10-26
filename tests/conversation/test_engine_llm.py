"""Engine LLM path: verified conceptual answers, consent, deferrals."""

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


@pytest.mark.asyncio
async def test_persist_failure_is_declared_not_fatal(fake_engine, monkeypatch):
    engine, conv_id = fake_engine

    def _explode(*args, **kwargs):
        raise PersistenciaFallida("disco lleno")

    monkeypatch.setattr(engine._memory, "add_message", _explode)
    result = await engine.turn(conv_id, "propiedades del etanol")
    assert "Propiedades de etanol:" in result.text
    assert "no se pudo guardar el turno" in result.text
