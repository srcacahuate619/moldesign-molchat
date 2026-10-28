"""F2-C1 regression: every failure path returns text, never a tuple.

Four `_abstain` call sites used to double-wrap the 3-tuple, so
``TurnResult.text`` could be a tuple. Fake never hits these paths; a real
provider does. Each test forces one path and asserts ``isinstance(str)``.
"""

import pytest

from molchat_agent.config import load_config
from molchat_agent.conversation.engine import ConversationEngine
from molchat_agent.conversation.memory import MemoryStore
from molchat_agent.conversation.tools import MoleculeRecord, ToolError
from molchat_agent.providers import build_registry
from molchat_agent.providers.base import ProviderError


class _EmptyPropsBackend:
    """Backend that answers with records lacking every descriptor."""

    def __init__(self):
        self.calls = []

    async def properties(self, smiles: str) -> MoleculeRecord:
        self.calls.append(("properties", smiles))
        return MoleculeRecord(name="x", smiles=smiles, props={})

    def name_for(self, smiles: str):
        return None


class _FailingChatProvider:
    id = "failing"
    locality = "local"

    def __init__(self):
        from molchat_agent.providers.base import ProviderConfig
        self.config = ProviderConfig()

    async def health(self):
        from molchat_agent.providers.base import HealthCheckResult, HealthStatus
        return HealthCheckResult(status=HealthStatus.OK)

    async def plan(self, goal, catalog=None):
        raise ProviderError("boom")

    async def chat(self, turn):
        raise ProviderError("boom")
        yield


@pytest.fixture
def world(tmp_path):
    memory = MemoryStore(tmp_path / "memory.db")
    return memory


def _engine(memory, backend, user_id="f2c1-test", provider_id="fake"):
    registry = build_registry(load_config({"MOLCHAT_PROVIDER": provider_id}))
    return ConversationEngine(registry=registry, backend=backend,
                              memory=memory, user_id=user_id)


@pytest.mark.asyncio
async def test_conceptual_provider_failure_returns_text(world):
    engine = _engine(world, _EmptyPropsBackend())
    engine._registry.register(_FailingChatProvider())
    engine._provider_id = "failing"
    conv_id = world.create_conversation("f2c1-test")
    result = await engine.turn(conv_id, "qué es un fármaco?")
    assert isinstance(result.text, str)
    assert "No puedo responder eso de forma verificada" in result.text


@pytest.mark.asyncio
async def test_properties_without_descriptors_returns_text(world):
    engine = _engine(world, _EmptyPropsBackend())
    conv_id = world.create_conversation("f2c1-test")
    result = await engine.turn(conv_id, "calcula propiedades de la aspirina")
    assert isinstance(result.text, str)
    assert "No puedo responder eso de forma verificada" in result.text


@pytest.mark.asyncio
async def test_incomplete_multicompare_returns_text(world):
    engine = _engine(world, _EmptyPropsBackend())
    conv_id = world.create_conversation("f2c1-test")
    result = await engine.turn(
        conv_id, "compará la aspirina, el ibuprofeno y el paracetamol")
    assert isinstance(result.text, str)
    assert "No puedo responder eso de forma verificada" in result.text


@pytest.mark.asyncio
async def test_druglikeness_without_descriptors_returns_text(world):
    engine = _engine(world, _EmptyPropsBackend())
    conv_id = world.create_conversation("f2c1-test")
    result = await engine.turn(conv_id, "la aspirina cumple la regla de Lipinski?")
    assert isinstance(result.text, str)
    assert "No puedo responder eso de forma verificada" in result.text


@pytest.mark.asyncio
async def test_tool_error_path_returns_text(world):
    from molchat_agent.conversation.tools import QualityBackend
    from pathlib import Path
    fixtures = Path(__file__).parent.parent / "quality" / "fixtures" / "properties.json"
    engine = _engine(world, QualityBackend(fixtures))
    conv_id = world.create_conversation("f2c1-test")
    result = await engine.turn(conv_id, "CCCCCCCCCCCCCCCCCCCCCCCCCCCC")
    assert isinstance(result.text, str)


@pytest.mark.asyncio
async def test_conceptual_needs_a_configured_provider(world):
    """Unconfigured remote provider: denial path also returns text."""
    # OpenAI es el proveedor genérico del catálogo; sin clave ni autorización, la
    # respuesta es el rechazo en texto, no una excepción.
    registry = build_registry(load_config({"MOLCHAT_PROVIDER": "openai",
                                           "MOLCHAT_PROFILE": "default"}))
    engine = ConversationEngine(registry=registry, backend=_EmptyPropsBackend(),
                                memory=world, user_id="f2c1-test")
    conv_id = world.create_conversation("f2c1-test")
    result = await engine.turn(conv_id, "qué es un fármaco?")
    assert isinstance(result.text, str)
