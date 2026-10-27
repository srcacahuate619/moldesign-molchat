"""Job tracker: backoff polling, cancel, SSE fallback, resume."""

import pytest

from molchat_agent.orchestration.budget import Budget, BudgetExceeded, BudgetTracker
from molchat_agent.orchestration.jobs import JobTracker
from molchat_agent.orchestration.store import ExecutionStore


class ScriptedBridge:
    """Bridge stub with scripted status sequences per remote id."""

    def __init__(self, scripts):
        self.scripts = {k: list(v) for k, v in scripts.items()}
        self.calls = []
        self.stream_calls = 0

    async def call(self, name, args):
        self.calls.append((name, dict(args)))
        if name == "stream_evaluation":
            self.stream_calls += 1
            return {"events": [{"type": "start"}]}
        if name in ("cancel_evaluation", "cancel_batch", "cancel_molcy_job"):
            return {"cancelled": True}
        remote = args.get("task_id") or args.get("batch_id") or args.get("job_id")
        script = self.scripts.get(remote, [{"status": "SUCCESS"}])
        if len(script) > 1:
            return script.pop(0)
        return script[0]


@pytest.fixture
def sleep_recorder():
    delays = []

    async def sleep(delay):
        delays.append(delay)

    sleep.delays = delays
    return sleep


def _tracker(bridge, sleep_recorder, tmp_path=None, **kwargs):
    store = ExecutionStore(tmp_path / "exec.db") if tmp_path else None
    kwargs.setdefault("jitter", 0)
    return JobTracker(bridge, store=store, sleep=sleep_recorder, **kwargs)


@pytest.mark.asyncio
async def test_follow_reaches_success_with_backoff(sleep_recorder, tmp_path):
    bridge = ScriptedBridge({"t1": [{"status": "PENDING"}, {"status": "STARTED"},
                                    {"status": "SUCCESS", "progress": 100}]})
    tracker = _tracker(bridge, sleep_recorder, tmp_path)
    result = await tracker.follow_evaluation("t1", digest="d", step_id="s1")
    assert result.outcome == "done"
    assert result.polls == 3
    assert sleep_recorder.delays == [2.0, 4.0]
    assert bridge.stream_calls == 1  # one SSE wait before polling
    store = ExecutionStore(tmp_path / "exec.db")
    assert store.pending_jobs("d") == []  # terminal row updated


@pytest.mark.asyncio
async def test_failure_and_unknown_states(sleep_recorder):
    bridge = ScriptedBridge({"t9": [{"status": "FAILURE", "error": "boom"}]})
    tracker = _tracker(bridge, sleep_recorder)
    result = await tracker.follow_evaluation("t9")
    assert result.outcome == "failed"
    assert result.polls == 1  # terminal on first poll: no sleeps
    assert sleep_recorder.delays == []


@pytest.mark.asyncio
async def test_unknown_state_polls_until_budget(sleep_recorder):
    bridge = ScriptedBridge({"t2": [{"status": "WEIRD"}]})
    tracker = _tracker(bridge, sleep_recorder,
                        budget=BudgetTracker(Budget(max_polls_per_job=3)))
    with pytest.raises(BudgetExceeded, match="sondeos"):
        await tracker.follow_evaluation("t2")


@pytest.mark.asyncio
async def test_batch_outcomes_and_cancel(sleep_recorder):
    bridge = ScriptedBridge({"b1": [{"status": "running"}, {"status": "completed"}],
                             "b2": [{"status": "cancelled"}]})
    tracker = _tracker(bridge, sleep_recorder)
    assert (await tracker.follow_batch("b1")).outcome == "done"
    assert (await tracker.follow_batch("b2")).outcome == "cancelled"
    assert await tracker.cancel("batch", "b1") == {"cancelled": True}
    assert await tracker.cancel("evaluation", "t1") == {"cancelled": True}
    with pytest.raises(ValueError, match="desconocido"):
        await tracker.cancel("nope", "x")


@pytest.mark.asyncio
async def test_stream_failure_falls_back_to_polling(sleep_recorder):
    class FlakyStream(ScriptedBridge):
        async def call(self, name, args):
            if name == "stream_evaluation":
                raise RuntimeError("SSE caído")
            return await super().call(name, args)

    bridge = FlakyStream({"t3": [{"status": "STARTED"}, {"status": "SUCCESS"}]})
    tracker = _tracker(bridge, sleep_recorder)
    result = await tracker.follow_evaluation("t3")
    assert result.outcome == "done"
    assert result.polls == 2


@pytest.mark.asyncio
async def test_resume_reuses_job_row(sleep_recorder, tmp_path):
    bridge = ScriptedBridge({"t4": [{"status": "SUCCESS"}]})
    store = ExecutionStore(tmp_path / "exec.db")
    store.save_plan("d", {"goal": "g"}, "waiting_job")
    job_id = store.save_job("d", "s1", "evaluation", "t4")
    tracker = JobTracker(bridge, store=store, sleep=sleep_recorder, jitter=0)
    result = await tracker.follow_evaluation("t4", digest="d", step_id="s1", job_id=job_id)
    assert result.outcome == "done"
    assert store.pending_jobs("d") == []


@pytest.mark.asyncio
async def test_backoff_caps_at_max_delay(sleep_recorder):
    bridge = ScriptedBridge({"t5": [{"status": "STARTED"}]})
    tracker = _tracker(bridge, sleep_recorder, base_delay=10.0, max_delay=12.0,
                        budget=BudgetTracker(Budget(max_polls_per_job=4)))
    with pytest.raises(BudgetExceeded):
        await tracker.follow_evaluation("t5")
    assert sleep_recorder.delays == [10.0, 12.0, 12.0]


@pytest.mark.asyncio
async def test_job_start_budget_enforced():
    tracker = JobTracker(ScriptedBridge({}), budget=BudgetTracker(Budget(max_jobs=0)))
    with pytest.raises(BudgetExceeded, match="concurrentes"):
        await tracker.follow_evaluation("t1")


@pytest.mark.asyncio
async def test_molcy_render_followed_to_terminal(sleep_recorder):
    bridge = ScriptedBridge({
        "j-1": [{"estado": "en_cola"}, {"estado": "renderizando"},
                {"estado": "completo", "video_sha256": "abc"}],
        "j-2": [{"estado": "fallido", "motivo": "sin GPU"}],
        "j-3": [{"estado": "cancelado"}],
    })
    tracker = _tracker(bridge, sleep_recorder)
    done = await tracker.follow_molcy("j-1")
    assert done.outcome == "done"
    assert done.status["video_sha256"] == "abc"
    assert (await tracker.follow_molcy("j-2")).outcome == "failed"
    assert (await tracker.follow_molcy("j-3")).outcome == "cancelled"
    assert await tracker.cancel("molcy", "j-1") == {"cancelled": True}
    assert ("cancel_molcy_job", {"job_id": "j-1"}) in bridge.calls
