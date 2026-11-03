"""The iteration loop: deterministic, tolerant of failures, and honest about what it did not do."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from molchat_agent.workflows.iteration import (
    Molecule, IterationRunner, IterationSpec, SpecError, VideoRequest, judge)


def spec_dict(**over: Any) -> dict[str, Any]:
    base = {"case_name": "hipotesis-8T69", "pdb_id": "8t69",
            "molecules": [{"name": "A", "smiles": "CCO"}, {"name": "B", "smiles": "CCN"},
                          {"name": "C", "smiles": "CCC"}, {"name": "D", "smiles": "CCCl"}],
            "threshold_kcal": -9.5}
    base.update(over)
    return base


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeHost:
    """Statuses by SMILES; anything not listed is applied and started."""

    def __init__(self, *, load: dict[str, Any] | None = None, evaluate: dict[str, Any] | None = None,
                 case: str = "created", receptor: str = "applied") -> None:
        self.load_by, self.evaluate_by = load or {}, evaluate or {}
        self.case, self.receptor = case, receptor
        self.current = ""
        self.calls: list[tuple[str, str]] = []
        self.evaluations = 0

    async def create_case(self, name: str) -> dict[str, Any]:
        self.calls.append(("create_case", name))
        return {"status": self.case}

    async def assign_receptor(self, case_name: str, pdb_id: str) -> dict[str, Any]:
        self.calls.append(("assign_receptor", pdb_id))
        return {"status": self.receptor}

    async def load_smiles(self, case_name: str, smiles: str) -> dict[str, Any]:
        self.calls.append(("load_smiles", smiles))
        self.current = smiles
        outcome = self.load_by.get(smiles, {"status": "applied"})
        if isinstance(outcome, list):  # a sequence of answers: busy, busy, applied
            outcome = outcome.pop(0) if len(outcome) > 1 else outcome[0]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def case_status(self, case_name: str) -> dict[str, Any]:
        self.calls.append(("case_status", case_name))
        return {"status": "idle"}

    async def evaluate(self, case_name: str) -> dict[str, Any]:
        self.evaluations += 1
        self.calls.append(("evaluate", self.current))
        outcome = self.evaluate_by.get(self.current, {"status": "started", "task_id": f"t-{self.current}"})
        if isinstance(outcome, list):  # a sequence of answers: busy, busy, started
            value = outcome.pop(0) if len(outcome) > 1 else outcome[0]
            return value
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakePlatform:
    def __init__(self, scores: dict[str, tuple[float | None, str | None]], *, never: set[str] | None = None,
                 failing: set[str] | None = None, clock: Clock | None = None) -> None:
        self.scores, self.never, self.failing = scores, never or set(), failing or set()
        self.saved: list[tuple[str, str]] = []
        self.videos: list[tuple[str, str]] = []
        self.video_polls = 0

    async def job(self, task_id: str) -> dict[str, Any]:
        smiles = task_id[2:]
        if smiles in self.never:
            return {"status": "STARTED"}
        if smiles in self.failing:
            return {"status": "FAILURE", "error": "RDKit no pudo embeber la molécula"}
        affinity, _ = self.scores[smiles]
        return {"status": "SUCCESS", "result": {"molecule_id": f"m-{smiles}", "affinity_kcal": affinity}}

    async def top_pose(self, task_id: str) -> dict[str, Any]:
        return {"physical_status": self.scores[task_id[2:]][1]}

    async def save(self, task_id: str, molecule_id: str, name: str | None) -> dict[str, Any]:
        self.saved.append((task_id, molecule_id))
        return {"status": "saved", "task_id": task_id}

    async def request_video(self, task_id: str, molecule_id: str, video: VideoRequest) -> dict[str, Any]:
        self.videos.append((task_id, video.scene))
        return {"status": "started", "job_id": "a" * 8 + "-" * 4 + "b" * 24}

    async def video_status(self, job_id: str) -> dict[str, Any]:
        self.video_polls += 1
        return {"status": "ok", "job_state": "completo" if self.video_polls >= 2 else "en_curso"}


def runner(spec: IterationSpec, host: FakeHost, platform: FakePlatform, clock: Clock | None = None,
           events: list[dict[str, Any]] | None = None) -> IterationRunner:
    clock = clock or Clock()
    return IterationRunner(spec, host, platform, (events.append if events is not None else None),  # type: ignore[arg-type]
                           clock=clock, sleep=clock.sleep, poll_s=1.0, busy_wait_s=1.0)


SCORES = {"CCO": (-7.1, "passed"), "CCN": (-9.8, "passed"), "CCC": (-10.4, "passed"), "CCCl": (-8.0, "passed")}


async def test_stops_at_the_first_molecule_that_meets_the_rule() -> None:
    spec = IterationSpec.from_dict(spec_dict(video={"scene": "busqueda", "format": "previsualizacion"}))
    host, platform = FakeHost(), FakePlatform(SCORES)
    out = await runner(spec, host, platform).run()
    assert out.state == "completed" and out.selected == 2
    assert [r.status for r in out.records] == ["evaluated", "evaluated", "skipped", "skipped"]
    assert out.records[0].outcome == "below_threshold" and out.records[1].outcome == "qualifies"
    assert host.evaluations == 2  # C and D were never evaluated
    assert platform.saved == [("t-CCN", "m-CCN")] and platform.videos == [("t-CCN", "busqueda")]
    assert out.saved["status"] == "saved" and out.video["status"] == "started"


async def test_a_failing_molecule_is_recorded_and_the_loop_goes_on() -> None:
    spec = IterationSpec.from_dict(spec_dict())
    host = FakeHost(load={"CCO": {"status": "failed"}}, evaluate={"CCN": {"status": "blocked", "reason": "preflight"}})
    out = await runner(spec, host, FakePlatform(SCORES)).run()
    assert [r.status for r in out.records[:3]] == ["failed", "failed", "evaluated"]
    assert "preflight" in out.records[1].reason
    assert out.selected == 3 and out.state == "completed"


async def test_an_unexpected_exception_in_one_molecule_does_not_stop_the_others() -> None:
    spec = IterationSpec.from_dict(spec_dict())
    host = FakeHost(load={"CCO": RuntimeError("boom")})
    out = await runner(spec, host, FakePlatform(SCORES)).run()
    assert out.records[0].status == "failed" and "RuntimeError" in out.records[0].reason
    assert out.selected == 2


async def test_a_failed_job_and_a_timeout_are_each_recorded_without_stopping() -> None:
    spec = IterationSpec.from_dict(spec_dict(per_molecule_timeout_s=30))
    platform = FakePlatform(SCORES, never={"CCO"}, failing={"CCN"})
    out = await runner(spec, FakeHost(), platform).run()
    assert out.records[0].status == "timeout" and out.records[1].status == "failed"
    assert "RDKit" in out.records[1].reason
    assert out.selected == 3


async def test_energy_alone_does_not_qualify_a_pose_the_physical_controls_reject() -> None:
    scores = {**SCORES, "CCN": (-11.0, "failed")}
    spec = IterationSpec.from_dict(spec_dict())
    out = await runner(spec, FakeHost(), FakePlatform(scores)).run()
    assert out.records[1].outcome == "near" and "físicos" in out.records[1].reason
    assert out.selected == 3  # the loop went on to the next molecule


async def test_physical_check_not_evaluated_is_not_a_pass() -> None:
    scores = {**SCORES, "CCN": (-11.0, None)}
    out = await runner(IterationSpec.from_dict(spec_dict()), FakeHost(), FakePlatform(scores)).run()
    assert out.records[1].outcome == "near" and "no evaluados" in out.records[1].reason


async def test_without_the_physical_requirement_energy_is_enough() -> None:
    scores = {**SCORES, "CCN": (-11.0, "failed")}
    out = await runner(IterationSpec.from_dict(spec_dict(require_physical=False)), FakeHost(), FakePlatform(scores)).run()
    assert out.selected == 2


async def test_nobody_qualifies_means_nothing_is_saved_and_no_video() -> None:
    scores = {k: (-6.0, "passed") for k in SCORES}
    spec = IterationSpec.from_dict(spec_dict(video={"scene": "busqueda", "format": "previsualizacion"}))
    platform = FakePlatform(scores)
    out = await runner(spec, FakeHost(), platform).run()
    assert out.state == "none_qualified" and out.selected is None
    assert platform.saved == [] and platform.videos == []
    assert out.saved is None and out.video is None
    assert any("Ninguna molécula cumplió" in note for note in out.notes)


async def test_stop_all_evaluates_the_whole_list_and_keeps_the_lowest_energy() -> None:
    spec = IterationSpec.from_dict(spec_dict(stop="all"))
    host, platform = FakeHost(), FakePlatform(SCORES)
    out = await runner(spec, host, platform).run()
    assert host.evaluations == 4 and out.selected == 3  # CCC, -10.4, beats CCN, -9.8
    assert platform.saved == [("t-CCC", "m-CCC")]


async def test_busy_is_retried_and_unknown_is_never_repeated() -> None:
    spec = IterationSpec.from_dict(spec_dict())
    host = FakeHost(evaluate={"CCO": [{"status": "busy"}, {"status": "busy"}, {"status": "started", "task_id": "t-CCO"}],
                              "CCN": {"status": "unknown"}})
    out = await runner(spec, host, FakePlatform(SCORES)).run()
    assert out.records[0].status == "evaluated"
    assert out.records[1].status == "unknown" and "no se repitió" in out.records[1].reason
    assert [c for c in host.calls if c == ("evaluate", "CCN")] == [("evaluate", "CCN")]


class LockedAfterRun(FakeHost):
    """What the real window does: after a run finishes it keeps the case locked while it closes the run (~45 s)."""

    def __init__(self, clock: Clock, lock_s: float, *, knows_case_status: bool = True) -> None:
        super().__init__()
        self.clock, self.lock_s, self.free_at = clock, lock_s, 0.0
        self.knows_case_status = knows_case_status

    def locked(self) -> bool:
        return self.clock.now < self.free_at

    async def case_status(self, case_name: str) -> dict[str, Any]:
        self.calls.append(("case_status", case_name))
        if not self.knows_case_status:
            return {"status": "unknown"}
        return {"status": "busy", "run_state": "running"} if self.locked() else {"status": "idle"}

    async def load_smiles(self, case_name: str, smiles: str) -> dict[str, Any]:
        if self.locked():
            self.calls.append(("load_smiles_busy", smiles))
            return {"status": "busy"}
        return await super().load_smiles(case_name, smiles)


class LockingPlatform(FakePlatform):
    def __init__(self, scores: dict[str, tuple[float | None, str | None]], host: LockedAfterRun) -> None:
        super().__init__(scores)
        self.host = host

    async def job(self, task_id: str) -> dict[str, Any]:
        self.host.free_at = self.host.clock.now + self.host.lock_s  # Vina is done; the window is still closing the run
        return await super().job(task_id)


async def test_the_loop_asks_the_window_and_waits_for_each_run_to_close_before_loading_the_next() -> None:
    """The failure seen in the app: molecule 1 was evaluated, the window was still closing its run, the load of
    molecule 2 answered «busy» and was never retried, so 2, 3 and 4 were all reported as failed. Now the loop asks
    the window (``case_status``) and loads only when the case is free, so no load is ever refused."""
    clock = Clock()
    host = LockedAfterRun(clock, lock_s=45.0)
    events: list[dict[str, Any]] = []
    out = await runner(IterationSpec.from_dict(spec_dict(stop="all")), host, LockingPlatform(SCORES, host), clock, events).run()
    assert [r.status for r in out.records] == ["evaluated"] * 4
    assert out.selected == 3 and out.state == "completed"  # CCC, -10.4
    assert not any(c[0] == "load_smiles_busy" for c in host.calls)  # it waited instead of being refused
    assert out.records[0].seconds_waiting_case == 0 and out.records[0].case_state_before == "idle"
    assert out.records[1].case_state_before == "idle" and 44 <= out.records[1].seconds_waiting_case <= 46
    phases = [e["message"] for e in events if e["event"] == "phase"]
    assert any("sigue cerrando la corrida anterior" in (m or "") for m in phases) and phases[-1] is None


async def test_an_older_window_without_case_status_still_works_by_retrying_busy_loads() -> None:
    clock = Clock()
    host = LockedAfterRun(clock, lock_s=45.0, knows_case_status=False)
    out = await runner(IterationSpec.from_dict(spec_dict(stop="all")), host, LockingPlatform(SCORES, host), clock).run()
    assert [r.status for r in out.records] == ["evaluated"] * 4
    assert ("load_smiles_busy", "CCN") in host.calls and out.records[1].case_state_before == "unknown"


async def test_the_decision_is_made_on_vinas_number_and_a_qualifying_molecule_never_waits_for_the_window() -> None:
    clock = Clock()
    host = LockedAfterRun(clock, lock_s=45.0)
    out = await runner(IterationSpec.from_dict(spec_dict()), host, LockingPlatform(SCORES, host), clock).run()
    assert out.selected == 2 and [r.status for r in out.records] == ["evaluated", "evaluated", "skipped", "skipped"]
    # two questions: before A (free) and before B (waited for A's run to close); none after B qualified
    assert len([c for c in host.calls if c[0] == "case_status"]) > 2
    assert host.locked()  # B's run was still closing when the loop moved on to save it


async def test_a_window_that_never_frees_is_reported_as_busy_not_as_a_bad_molecule_and_the_loop_goes_on() -> None:
    clock = Clock()
    host = FakeHost(load={"CCN": {"status": "busy"}})
    spec = IterationSpec.from_dict(spec_dict(stop="all"))
    out = await runner(spec, host, FakePlatform(SCORES), clock).run()
    second = out.records[1]
    assert second.status == "failed" and "siguió ocupado 240 s" in second.reason
    assert "cargó la molécula" in second.reason
    assert [r.status for r in out.records] == ["evaluated", "failed", "evaluated", "evaluated"]
    assert clock.now >= 240  # it waited the whole budget before giving up


async def test_the_wait_never_outlasts_the_plans_own_time() -> None:
    clock = Clock()
    host = FakeHost(load={"CCN": {"status": "busy"}})
    spec = IterationSpec.from_dict(spec_dict(budget_s=60, stop="all"))
    out = await runner(spec, host, FakePlatform(SCORES), clock).run()
    assert out.records[1].status == "failed" and clock.now < 120  # gave up with the plan's time, not after 240 s


async def test_unknown_on_load_is_not_repeated() -> None:
    host = FakeHost(load={"CCN": {"status": "unknown"}})
    out = await runner(IterationSpec.from_dict(spec_dict()), host, FakePlatform(SCORES)).run()
    assert [c for c in host.calls if c == ("load_smiles", "CCN")] == [("load_smiles", "CCN")]
    assert out.records[1].status == "failed"


async def test_a_busy_receptor_assignment_is_retried_before_the_plan_gives_up() -> None:
    class Host(FakeHost):
        answers = [{"status": "busy"}, {"status": "busy"}, {"status": "applied"}]

        async def assign_receptor(self, case_name: str, pdb_id: str) -> dict[str, Any]:
            self.calls.append(("assign_receptor", pdb_id))
            return self.answers.pop(0)

    host = Host()
    out = await runner(IterationSpec.from_dict(spec_dict()), host, FakePlatform(SCORES)).run()
    assert out.state == "completed" and [c for c in host.calls if c[0] == "assign_receptor"] == [("assign_receptor", "8T69")] * 3


async def test_a_case_that_cannot_be_prepared_blocks_before_any_evaluation() -> None:
    host = FakeHost(receptor="receptor_not_found")
    out = await runner(IterationSpec.from_dict(spec_dict()), host, FakePlatform(SCORES)).run()
    assert out.state == "blocked" and host.evaluations == 0
    assert all(r.status == "skipped" for r in out.records)
    assert any("asignar el receptor" in n for n in out.notes)


async def test_an_existing_case_is_reused_and_said() -> None:
    out = await runner(IterationSpec.from_dict(spec_dict()), FakeHost(case="exists"), FakePlatform(SCORES)).run()
    assert any("ya existía" in n for n in out.notes) and out.state == "completed"


async def test_the_time_budget_skips_what_is_left_and_still_keeps_what_it_found() -> None:
    clock = Clock()
    spec = IterationSpec.from_dict(spec_dict(budget_s=60, stop="all"))

    class Slow(FakePlatform):
        async def job(self, task_id: str) -> dict[str, Any]:
            clock.now += 50
            return await super().job(task_id)

    out = await runner(spec, FakeHost(), Slow(SCORES, clock=clock), clock).run()
    assert out.state == "budget_exhausted"
    assert out.records[0].status == "evaluated" and out.records[1].status == "evaluated"
    assert out.records[2].status == "skipped" and "tiempo" in out.records[2].reason
    assert out.selected == 2  # what was found before the budget ran out is kept


async def test_cancellation_is_not_swallowed() -> None:
    host = FakeHost(load={"CCO": asyncio.CancelledError()})
    with pytest.raises(asyncio.CancelledError):
        await runner(IterationSpec.from_dict(spec_dict()), host, FakePlatform(SCORES)).run()


async def test_a_video_is_not_requested_when_the_run_was_not_saved() -> None:
    class NoSave(FakePlatform):
        async def save(self, task_id: str, molecule_id: str, name: str | None) -> dict[str, Any]:
            return {"status": "rejected"}

    spec = IterationSpec.from_dict(spec_dict(video={"scene": "busqueda", "format": "previsualizacion"}))
    platform = NoSave(SCORES)
    out = await runner(spec, FakeHost(), platform).run()
    assert out.video["status"] == "not_requested" and platform.videos == []


async def test_follow_video_waits_for_the_render_to_finish() -> None:
    spec = IterationSpec.from_dict(spec_dict(video={"scene": "busqueda", "format": "previsualizacion"}))
    platform = FakePlatform(SCORES)
    run = runner(spec, FakeHost(), platform)
    await run.run()
    final = await run.follow_video(timeout_s=600)
    assert final["final"] == "completo" and platform.video_polls == 2


async def test_events_carry_each_molecule_for_the_live_table() -> None:
    events: list[dict[str, Any]] = []
    await runner(IterationSpec.from_dict(spec_dict()), FakeHost(), FakePlatform(SCORES), events=events).run()
    kinds = [e["event"] for e in events]
    assert kinds[0] == "started" and kinds[-1] == "finished" and kinds.count("molecule") == 2
    assert all(e["type"] == "workflow" for e in events)


# ── The spec: what a card can show and a hash can bind ──────────────────────────────────────────────


def test_the_digest_binds_every_parameter() -> None:
    base = IterationSpec.from_dict(spec_dict())
    assert base.digest == IterationSpec.from_dict(spec_dict()).digest
    for change in ({"threshold_kcal": -9.0}, {"stop": "all"}, {"pdb_id": "7E2Y"}, {"require_physical": False},
                   {"molecules": [{"smiles": "CCO"}]}, {"package": True}):
        assert IterationSpec.from_dict(spec_dict(**change)).digest != base.digest, change


@pytest.mark.parametrize("change,fragment", [
    ({"threshold_kcal": 2.0}, "negativo"), ({"threshold_kcal": 0}, "negativo"), ({"threshold_kcal": -50}, "negativo"),
    ({"threshold_kcal": True}, "número"), ({"threshold_kcal": float("nan")}, "número"),
    ({"molecules": []}, "entre 1 y"), ({"molecules": [{"smiles": "CCO"}] * 2}, "repite"),
    ({"molecules": [{"smiles": "C C"}]}, "espacios"), ({"molecules": [{"name": "x"}]}, "smiles"),
    ({"molecules": [{"smiles": "C"}] * 0 + [{"smiles": f"C{i}"} for i in range(13)]}, "entre 1 y"),
    ({"stop": "forever"}, "stop"), ({"pdb_id": "8T69; drop"}, "pdb_id"), ({"case_name": "  "}, "case_name"),
    ({"case_name": "a\x00b"}, "control"), ({"video": {"scene": "x", "format": "horizontal"}}, "video"),
    ({"budget_s": 5}, "budget_s"), ({"unknown": 1}, "desconocidos"), ({"package": "yes"}, "package")])
def test_invalid_specs_say_which_field_failed(change: dict[str, Any], fragment: str) -> None:
    with pytest.raises(SpecError) as caught:
        IterationSpec.from_dict(spec_dict(**change))
    assert fragment in str(caught.value)


def test_a_video_turns_saving_on_and_the_card_says_everything_the_run_will_do() -> None:
    spec = IterationSpec.from_dict(spec_dict(save=False, video={"scene": "busqueda", "format": "previsualizacion"},
                                             preparation=True, package=True))
    assert spec.save is True
    text = "\n".join(spec.card_lines())
    for expected in ("hipotesis-8T69", "8T69", "-9.5", "controles físicos", "Moldex", "Molcy", "Preparación", "único ZIP", "se sigue"):
        assert expected in text


def test_judge_reads_numbers_but_never_invents_a_pass() -> None:
    spec = IterationSpec.from_dict(spec_dict())
    assert judge(spec, -9.5, "passed")[0] == "qualifies"
    assert judge(spec, -9.4, "passed")[0] == "below_threshold"
    assert judge(spec, None, "passed")[0] == "below_threshold"
    assert judge(spec, -12.0, "failed")[0] == "near"
    assert Molecule("a", "C").smiles == "C"


class MolcyTabHost(FakeHost):
    def __init__(self, answer: dict[str, Any]) -> None:
        super().__init__()
        self.answer, self.renders = answer, []

    async def render_video(self, task_id: str, scene: str, format: str, video: Any = None) -> dict[str, Any]:
        self.renders.append((task_id, scene, format))
        return self.answer


async def test_the_video_is_launched_by_the_molcy_tab_in_view_not_behind_the_window() -> None:
    spec = IterationSpec.from_dict(spec_dict(video={"scene": "busqueda", "format": "horizontal"}))
    host, platform = MolcyTabHost({"status": "started", "job_id": "job-from-tab"}), FakePlatform(SCORES)
    out = await runner(spec, host, platform).run()
    assert host.renders == [("t-CCN", "busqueda", "horizontal")]
    assert platform.videos == []  # MolChat did not ask the backend by itself
    assert out.video["status"] == "started" and out.video["job_id"] == "job-from-tab"


async def test_a_tab_that_cannot_render_is_declared_with_its_reason_and_never_retried_behind_its_back() -> None:
    spec = IterationSpec.from_dict(spec_dict(video={"scene": "busqueda", "format": "horizontal"}))
    host = MolcyTabHost({"status": "unavailable", "reason": "Esta máquina no tiene una GPU compatible"})
    platform = FakePlatform(SCORES)
    out = await runner(spec, host, platform).run()
    assert out.video["status"] == "unavailable" and "GPU compatible" in out.video["message"]
    assert platform.videos == [] and len(host.renders) == 1
    unknown = MolcyTabHost({"status": "unknown"})
    out = await runner(spec, unknown, platform).run()
    assert out.video["status"] == "unknown" and "no se repitió" in out.video["message"] and len(unknown.renders) == 1

