"""Engine deterministic paths: tools feed code-built answers, no LLM."""

from pathlib import Path

import pytest

from molchat_agent.conversation.engine import ConversationEngine
from molchat_agent.conversation.evidence import EVIDENCE_END
from molchat_agent.conversation.memory import ConversationNotFound, MemoryStore
from molchat_agent.conversation.tools import QualityBackend
from molchat_agent.config import load_config
from molchat_agent.providers import build_registry

FIXTURES = Path(__file__).parent.parent / "quality" / "fixtures" / "properties.json"


@pytest.fixture
def engine(tmp_path):
    registry = build_registry(load_config({"MOLCHAT_PROVIDER": "fake"}))
    backend = QualityBackend(FIXTURES)
    memory = MemoryStore(tmp_path / "memory.db")
    eng = ConversationEngine(registry=registry, backend=backend, memory=memory,
                             user_id="engine-test")
    conv_id = memory.create_conversation("engine-test")
    return eng, backend, memory, conv_id


@pytest.mark.asyncio
async def test_chemical_turn_reports_tool_values(engine):
    eng, backend, memory, conv_id = engine
    result = await eng.turn(conv_id, "calcula propiedades de la aspirina")
    assert result.intent_name == "chemical"
    assert result.used_llm is False
    assert "Propiedades de aspirina:" in result.text
    assert "180.2" in result.text and "1.31" in result.text
    assert EVIDENCE_END in result.text
    assert "[cálculo ·" in result.text
    assert memory.session_molecules(conv_id, "engine-test")[0]["name"] == "aspirina"
    assert backend.calls == [("properties", "CC(=O)Oc1ccccc1C(=O)O")]


@pytest.mark.asyncio
async def test_compare_records_both_and_names_winner(engine):
    eng, backend, memory, conv_id = engine
    result = await eng.turn(conv_id, "compará la aspirina con el ibuprofeno")
    assert result.intent_name == "compare"
    assert "mayor en ibuprofeno (206.3 vs 180.2)" in result.text
    assert [m["name"] for m in memory.session_molecules(conv_id, "engine-test")] == [
        "aspirina", "ibuprofeno"]
    assert len(backend.calls) == 2


@pytest.mark.asyncio
async def test_rank_uses_session_without_new_tool_calls(engine):
    eng, backend, memory, conv_id = engine
    await eng.turn(conv_id, "calcula propiedades de la aspirina")
    await eng.turn(conv_id, "propiedades del ibuprofeno")
    calls_before = len(backend.calls)
    result = await eng.turn(conv_id, "cual tiene menor peso molecular?")
    assert result.intent_name == "rank_session"
    assert "**aspirina**" in result.text
    assert len(backend.calls) == calls_before  # ranking reuses session data


@pytest.mark.asyncio
async def test_rank_without_molecules_is_honest(engine):
    eng, *_ , conv_id = engine
    result = await eng.turn(conv_id, "cual tiene menor peso molecular?")
    assert "No hay moléculas registradas" in result.text


@pytest.mark.asyncio
async def test_history_lists_session_and_declares_gap(engine):
    eng, _, _, conv_id = engine
    await eng.turn(conv_id, "propiedades del etanol")
    result = await eng.turn(conv_id, "que moleculas tengo en mi historial?")
    assert result.intent_name == "query_history"
    assert "1. etanol (MW 46.1 Da)" in result.text
    assert "persistido" in result.text


@pytest.mark.asyncio
async def test_druglikeness_reports_rules(engine):
    eng, _, _, conv_id = engine
    result = await eng.turn(conv_id, "la aspirina cumple la regla de Lipinski?")
    assert result.intent_name == "druglikeness"
    assert "Lipinski: CUMPLE" in result.text
    assert "PAINS (dato registrado): sin alertas." in result.text


@pytest.mark.asyncio
async def test_recall_with_name_reruns_properties(engine):
    eng, backend, _, conv_id = engine
    await eng.turn(conv_id, "calcula propiedades de la aspirina")
    result = await eng.turn(conv_id, "y del paracetamol?")
    assert result.intent_name == "recall_anaphoric"
    assert "Propiedades de paracetamol:" in result.text
    assert backend.calls[-1][1] == "CC(=O)Nc1ccc(O)cc1"


@pytest.mark.asyncio
async def test_recall_without_context_asks(engine):
    eng, _, _, conv_id = engine
    result = await eng.turn(conv_id, "y del paracetamol?")
    # Named anaphora resolves even without prior context.
    assert "Propiedades de paracetamol:" in result.text


@pytest.mark.asyncio
async def test_pure_anaphora_without_context_asks(engine):
    eng, backend, _, conv_id = engine
    result = await eng.turn(conv_id, "esa primera molécula, qué es?")
    assert "¿De qué molécula hablas?" in result.text
    assert backend.calls == []


@pytest.mark.asyncio
async def test_unknown_tool_data_abstains_without_numbers(engine):
    eng, backend, _, conv_id = engine
    result = await eng.turn(conv_id, "CCCCCCCCCCCCCCCCCCCCCCCCCCCC")
    assert "No puedo responder eso de forma verificada" in result.text
    assert "180.2" not in result.text
    assert backend.calls  # it tried, then abstained


@pytest.mark.asyncio
async def test_foreign_conversation_is_rejected(engine):
    eng, _, memory, _ = engine
    other = memory.create_conversation("other-test")
    with pytest.raises(ConversationNotFound):
        await eng.turn(other, "hola")


@pytest.mark.asyncio
async def test_turn_stream_yields_intent_response_result(engine):
    eng, _, _, conv_id = engine
    events = [e async for e in eng.turn_stream(conv_id, "hola")]
    assert [e["type"] for e in events] == ["intent", "response", "result"]
    assert events[2]["result"].latency_ms >= 0
