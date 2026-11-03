"""One evaluation on its own: the backend says when the result is ready and what it is; the window says when the
case can take another molecule. Each signal is asked to its owner and timed."""
from __future__ import annotations

from typing import Any

from molchat_agent.workflows.evaluation import EvaluationStep


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds


class Host:
    def __init__(self, *, load: Any = None, start: Any = None, states: list[str] | None = None) -> None:
        self.load, self.start = load or {"status": "applied"}, start or {"status": "started", "task_id": "t-1"}
        self.states = states or ["idle"]
        self.calls: list[str] = []

    async def load_smiles(self, case_name: str, smiles: str) -> dict[str, Any]:
        self.calls.append("load")
        return self.load.pop(0) if isinstance(self.load, list) else self.load

    async def evaluate(self, case_name: str) -> dict[str, Any]:
        self.calls.append("evaluate")
        return self.start

    async def case_status(self, case_name: str) -> dict[str, Any]:
        self.calls.append("case_status")
        return {"status": self.states.pop(0) if len(self.states) > 1 else self.states[0]}


class Backend:
    """The job is PENDING for ``pending_s`` seconds of the shared clock, then terminal."""

    def __init__(self, clock: Clock, *, pending_s: float = 30.0, final: dict[str, Any] | None = None,
                 physical: str | None = "passed") -> None:
        self.clock, self.pending_s, self.physical = clock, pending_s, physical
        self.final = final or {"status": "SUCCESS", "result": {"molecule_id": "m-1", "affinity_kcal": -9.483}}
        self.started_at: float | None = None
        self.polls = 0

    async def job(self, task_id: str) -> dict[str, Any]:
        self.polls += 1
        if self.started_at is None:
            self.started_at = self.clock.now
        return {"status": "PENDING"} if self.clock.now - self.started_at < self.pending_s else self.final

    async def top_pose(self, task_id: str) -> dict[str, Any]:
        return {"physical_status": self.physical}


def step(host: Host, backend: Backend, clock: Clock, messages: list[str | None] | None = None) -> EvaluationStep:
    return EvaluationStep(host, backend, clock=clock, sleep=clock.sleep, poll_s=2.0, busy_wait_s=5.0, busy_budget_s=240.0,
                          on_wait=(messages.append if messages is not None else None))


async def test_the_result_is_read_from_the_backend_when_the_job_is_terminal_and_the_time_is_measured() -> None:
    clock = Clock()
    backend = Backend(clock, pending_s=30.0)
    reading = await step(Host(), backend, clock).evaluate("caso", "CCO", timeout_s=420)
    assert reading.status == "evaluated" and reading.task_id == "t-1" and reading.molecule_id == "m-1"
    assert reading.vina_kcal == -9.483 and reading.physical_status == "passed"
    assert reading.seconds_to_result == 30.0 and backend.polls == 16  # every 2 s until 30 s


async def test_a_job_that_never_ends_is_a_timeout_with_its_task_and_a_failed_job_keeps_its_error() -> None:
    clock = Clock()
    reading = await step(Host(), Backend(clock, pending_s=10_000), clock).evaluate("caso", "CCO", timeout_s=60)
    assert reading.status == "timeout" and reading.task_id == "t-1" and reading.vina_kcal is None
    failed = Backend(clock, pending_s=0, final={"status": "FAILURE", "error": "RDKit no pudo embeber la molécula"})
    reading = await step(Host(), failed, clock).evaluate("caso", "CCO", timeout_s=60)
    assert reading.status == "failed" and "RDKit no pudo embeber" in reading.reason


async def test_a_missing_vina_number_is_not_invented() -> None:
    clock = Clock()
    backend = Backend(clock, pending_s=0, final={"status": "SUCCESS", "result": {"molecule_id": "m-1", "affinity_kcal": float("nan")}})
    reading = await step(Host(), backend, clock).evaluate("caso", "CCO", timeout_s=60)
    assert reading.status == "evaluated" and reading.vina_kcal is None


async def test_unknown_start_is_never_repeated_and_busy_load_is() -> None:
    clock = Clock()
    host = Host(start={"status": "unknown"})
    reading = await step(host, Backend(clock), clock).evaluate("caso", "CCO", timeout_s=60)
    assert reading.status == "unknown" and host.calls.count("evaluate") == 1
    host = Host(load=[{"status": "busy"}, {"status": "busy"}, {"status": "applied"}])
    reading = await step(host, Backend(clock, pending_s=0), clock).evaluate("caso", "CCO", timeout_s=60)
    assert reading.status == "evaluated" and host.calls.count("load") == 3


async def test_the_window_is_asked_until_the_case_is_free_and_says_so_while_waiting() -> None:
    clock = Clock()
    messages: list[str | None] = []
    host = Host(states=["busy"] * 9 + ["idle"])
    free = await step(host, Backend(clock), clock, messages).wait_until_free("caso")
    assert free.status == "idle" and free.seconds == 45.0 and free.asked == 10
    assert messages[0] and "cerrando la corrida anterior" in messages[0] and messages[-1] is None


async def test_a_window_that_never_frees_gives_up_within_its_budget_and_an_unknown_answer_returns_at_once() -> None:
    clock = Clock()
    free = await step(Host(states=["busy"]), Backend(clock), clock).wait_until_free("caso", budget_s=60)
    assert free.status == "busy" and free.seconds <= 60
    clock = Clock()
    free = await step(Host(states=["unknown"]), Backend(clock), clock).wait_until_free("caso")
    assert free.status == "unknown" and free.seconds == 0 and free.asked == 1
