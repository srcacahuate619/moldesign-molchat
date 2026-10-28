"""Store and budget unit tests."""

import sqlite3

import pytest

from molchat_agent.orchestration.budget import (
    Budget,
    BudgetExceeded,
    BudgetTracker,
)
from molchat_agent.orchestration.store import ExecutionStore, StoreError


@pytest.fixture
def store(tmp_path):
    return ExecutionStore(tmp_path / "exec.db")


def test_state_machine_with_logged_transitions(store):
    digest = "sha256:" + "a" * 64
    store.save_plan(digest, {"goal": "g"}, "planned")
    assert store.get_state(digest) == "planned"
    store.set_state(digest, "approved", "humano")
    store.set_state(digest, "running")
    assert [t["to"] for t in store.transitions(digest)] == ["approved", "running"]
    assert store.transitions(digest)[0]["detail"] == "humano"
    with pytest.raises(ValueError, match="desconocido"):
        store.set_state(digest, "volando")
    store.set_state(digest, "done")
    with pytest.raises(ValueError, match="terminal"):
        store.set_state(digest, "running")
    with pytest.raises(KeyError):
        store.set_state("sha256:" + "z" * 64, "running")


def test_outcomes_roundtrip(store):
    digest = "sha256:" + "b" * 64
    store.save_plan(digest, {"goal": "g"})
    store.record_outcome(digest, {"id": "s1", "capability": "list_targets",
                                  "state": "completed", "result": {"a": 1},
                                  "result_sha256": "sha256:x", "error": None})
    (outcome,) = store.outcomes(digest)
    assert outcome["result"] == {"a": 1}
    assert outcome["result_sha256"] == "sha256:x"


def test_pending_jobs_and_resumable(store):
    digest = "sha256:" + "c" * 64
    store.save_plan(digest, {"goal": "g"}, "waiting_job")
    job = store.save_job(digest, "s2", "evaluation", "task-1")
    assert store.resumable() == [digest]
    assert store.pending_jobs(digest)[0]["remote_id"] == "task-1"
    store.update_job(job, "done", {"status": "SUCCESS"})
    assert store.pending_jobs(digest) == []
    store.set_state(digest, "done")
    assert store.resumable() == []


def test_store_failure_is_loud(tmp_path, monkeypatch):
    store = ExecutionStore(tmp_path / "exec.db")

    def _explode(*args, **kwargs):
        raise sqlite3.OperationalError("disco lleno")

    monkeypatch.setattr(sqlite3, "connect", _explode)
    with pytest.raises(StoreError):
        store.save_plan("sha256:" + "d" * 64, {})


def test_budget_trips():
    tracker = BudgetTracker(Budget(max_time_s=0.0, max_jobs=1))
    with pytest.raises(BudgetExceeded, match="tiempo"):
        tracker.check_time()
    tracker = BudgetTracker(Budget(max_jobs=1))
    tracker.check_time()
    tracker.check_job_start()
    with pytest.raises(BudgetExceeded, match="concurrentes"):
        tracker.check_job_start()


def test_presupuesto_cero_se_detiene_aunque_reloj_no_avance(monkeypatch):
    from molchat_agent.orchestration import budget
    monkeypatch.setattr(budget.time, 'monotonic', lambda: 100.0)
    tracker = BudgetTracker(Budget(max_time_s=0.0))
    with pytest.raises(BudgetExceeded, match='tiempo'):
        tracker.check_time()


def test_claim_key_states(store):
    assert store.claim_key("k", "d", "s1", "h1") == "claimed"
    assert store.claim_key("k", "d", "s1", "h1") == "duplicate"
    assert store.claim_key("k", "d", "s1", "h2") == "conflict"
    store.mark_key("k", "ambiguous")  # recorded, no error


def test_reopen_only_from_ambiguous(store):
    digest = "sha256:" + "e" * 64
    store.save_plan(digest, {"goal": "g"}, "ambiguous")
    store.reopen(digest, "recuperación")
    assert store.get_state(digest) == "running"
    assert store.transitions(digest)[-1]["detail"] == "recuperación"
    store.set_state(digest, "done")
    with pytest.raises(ValueError, match="solo ambiguous"):
        store.reopen(digest)
