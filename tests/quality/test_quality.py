"""The 43 ported quality cases against the deterministic engine."""

import os

import pytest

from molchat_agent.config import load_config
from molchat_agent.conversation.engine import ConversationEngine
from molchat_agent.conversation.memory import MemoryStore
from molchat_agent.conversation.tools import QualityBackend
from molchat_agent.providers import build_registry

from .runner import FIXTURES_PATH, load_cases, load_fixtures, run_case

CASES = load_cases()
FIXTURES = load_fixtures()
assert len(CASES) == 43, f"la suite interna tiene 43 casos, hay {len(CASES)}"


def _engine(tmp_path, provider_id="fake"):
    registry = build_registry(load_config({"MOLCHAT_PROVIDER": provider_id}))
    memory = MemoryStore(tmp_path / "memory.db")
    engine = ConversationEngine(registry=registry,
                                backend=QualityBackend(FIXTURES_PATH),
                                memory=memory, user_id="quality-test")
    return engine, memory.create_conversation("quality-test")


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_quality_case(tmp_path, case):
    engine, conv_id = _engine(tmp_path)
    result = run_case(engine, conv_id, case, FIXTURES)
    assert result.ok, f"{result.id}: {result.problems} :: {result.query!r}"


def test_deterministic_turns_answer_within_300ms(tmp_path):
    engine, _ = _engine(tmp_path)
    # Warmup: cold SQLite/Defender first-touch is environmental noise, not turn cost.
    warmup_conv = engine._memory.create_conversation("quality-test")
    run_case(engine, warmup_conv, CASES[0], FIXTURES)
    slow = []
    for case in CASES:
        conv_id = engine._memory.create_conversation("quality-test")
        result = run_case(engine, conv_id, case, FIXTURES)
        assert result.ok, f"{result.id}: {result.problems}"
        for query, latency, used_llm in zip(case["seq"], result.latencies_ms,
                                            result.used_llm):
            if not used_llm and latency >= 300:
                slow.append((case["id"], query, latency))
    assert slow == [], f"turnos deterministas lentos: {slow}"


def test_local_provider_leg(tmp_path):
    """Same suite against a real local provider (manual, needs a server).

    Run with MOLCHAT_QUALITY_PROVIDER=llama-server (or ollama) plus the
    model env vars. Skips when nothing listens: environment, not verdict.
    """
    provider_id = os.environ.get("MOLCHAT_QUALITY_PROVIDER", "")
    if provider_id not in ("llama-server", "ollama"):
        pytest.skip("MOLCHAT_QUALITY_PROVIDER sin fijar (fake cubre la suite)")
    import asyncio

    engine, _ = _engine(tmp_path, provider_id)
    health = asyncio.run(engine._registry.get(provider_id).health())
    if health.status.value != "ok":
        pytest.skip(f"{provider_id} no responde: {health.message}")
    failures = []
    for case in CASES:
        conv_id = engine._memory.create_conversation("quality-test")
        result = run_case(engine, conv_id, case, FIXTURES)
        if not result.ok:
            failures.append((result.id, result.problems))
    assert failures == [], f"casos fallidos con {provider_id}: {failures}"
