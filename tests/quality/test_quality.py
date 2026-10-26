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
    env = dict(os.environ)
    env["MOLCHAT_PROVIDER"] = provider_id
    registry = build_registry(load_config(env))
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


def _slow_turns(engine, case):
    conv_id = engine._memory.create_conversation("quality-test")
    result = run_case(engine, conv_id, case, FIXTURES)
    assert result.ok, f"{result.id}: {result.problems}"
    return [(case["id"], query, latency)
            for query, latency, used_llm in zip(case["seq"], result.latencies_ms,
                                                result.used_llm)
            if not used_llm and latency >= 300]


def test_deterministic_turns_answer_within_300ms(tmp_path):
    """Every deterministic turn answers within 300 ms, with one retry.

    The retry is for transient machine load (a 787 ms spike was measured
    while llama-server mmap-loaded 1 GB next door); a consistently slow
    turn fails twice and fails the gate.
    """
    engine, _ = _engine(tmp_path)
    # Warmup: cold SQLite/Defender first-touch is environmental noise, not turn cost.
    warmup_conv = engine._memory.create_conversation("quality-test")
    run_case(engine, warmup_conv, CASES[0], FIXTURES)
    slow = [slow for case in CASES for slow in _slow_turns(engine, case)]
    if slow:
        retried = {case_id for case_id, _, _ in slow}
        slow = [s for case in CASES if case["id"] in retried
                for s in _slow_turns(engine, case)]
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
