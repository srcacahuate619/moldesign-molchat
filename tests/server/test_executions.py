"""Plans and background executions over the sidecar API."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from molchat_agent.config import MolChatConfig
from molchat_agent.conversation.memory import MemoryStore
from molchat_agent.conversation.tools import QualityBackend
from molchat_agent.orchestration.jobs import JobTracker
from molchat_agent.orchestration.store import ExecutionStore
from molchat_agent.providers import build_registry
from molchat_agent.server.app import create_app
from molchat_agent.server.auth import mint, standalone_secret
from molchat_agent.server.executions import ExecutionManager
from molchat_agent.server.state import ServerState

FIXTURES = Path(__file__).parent.parent / "quality" / "fixtures" / "properties.json"
SECRET = standalone_secret()
NOW = 1_800_000_000
ALL = {"read", "chat", "plan", "approve", "cancel", "transcribe"}


class StubBridge:
    def __init__(self):
        self.calls = []

    async def call(self, name, args, **kwargs):
        self.calls.append((name, dict(args)))
        if name == "approve_docking_proposal":
            return {"task_id": "task-9"}
        if name == "evaluation_status":
            return {"status": "SUCCESS", "progress": 100}
        return {"ok": True}


class GateBridge(StubBridge):
    """Blocks the first status poll until the test releases it."""

    def __init__(self):
        super().__init__()
        self.release = asyncio.Event()
        self.status_calls = 0

    async def call(self, name, args, **kwargs):
        if name == "evaluation_status":
            self.status_calls += 1
            if self.status_calls == 1:
                await asyncio.wait_for(self.release.wait(), timeout=10)
            return {"status": "FAILURE", "error": "cancelled remotely"}
        if name == "cancel_evaluation":
            self.calls.append((name, dict(args)))
            return {"cancelled": True}
        return await super().call(name, args, **kwargs)


def _read_plan():
    return {"goal": "Listar", "planner": "test", "steps": [
        {"id": "s1", "capability": "list_targets", "arguments": {},
         "rationale": ""}]}


def _approve_plan():
    return {"goal": "Aprobar", "planner": "test", "steps": [
        {"id": "s1", "capability": "approve_docking_proposal",
         "arguments": {"proposal_id": "p1",
                       "proposal_hash": "sha256:" + "c" * 64},
         "rationale": ""}]}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr("molchat_agent.server.auth.time.time", lambda: NOW)
    bridge = StubBridge()
    store = ExecutionStore(tmp_path / "exec.db")

    async def no_sleep(_delay):
        pass

    manager = ExecutionManager(
        bridge, store,
        tracker_factory=lambda: JobTracker(bridge, store=store, sleep=no_sleep,
                                           jitter=0))
    registry = build_registry(MolChatConfig(profile="hackathon"))
    state = ServerState(
        secret=SECRET, registry=registry,
        memory=MemoryStore(tmp_path / "mem.db"),
        backend=QualityBackend(FIXTURES), provider_id="fake",
        executions=manager)
    app = create_app(state, allowed_hosts=("testserver",))
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    return client, bridge, manager


def _auth(sub="cuenta-1", scopes=None):
    token = mint(SECRET, sub, scopes or ALL, 3600, now=NOW)
    return {"Authorization": f"Bearer {token}"}


def _events(body: bytes):
    return [json.loads(line[5:].strip()) for line in body.decode().splitlines()
            if line.startswith("data:")]


async def _wait_terminal(client, headers, exec_id, tries=100):
    for _ in range(tries):
        view = (await client.get(f"/v1/executions/{exec_id}",
                                 headers=headers)).json()
        if view["state"] not in ("queued", "running", "cancelling"):
            return view
        await asyncio.sleep(0.05)
    raise AssertionError(f"execution {exec_id} never settled: {view['state']}")


@pytest.mark.asyncio
async def test_propose_plan_returns_digest(world):
    client, _, _ = world
    response = await client.post("/v1/plans", headers=_auth(),
                                 json={"goal": "listar receptores"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["digest"].startswith("sha256:")
    assert payload["plan"]["steps"][0]["capability"] in (
        "list_targets", "list_evaluations")
    assert (await client.post("/v1/plans", headers=_auth(),
                              json={"goal": "  "})).status_code == 400
    assert (await client.post("/v1/plans", headers=_auth(scopes={"read"}),
                              json={"goal": "x"})).status_code == 403


@pytest.mark.asyncio
async def test_read_only_execution_completes(world):
    client, bridge, _ = world
    submitted = await client.post("/v1/executions", headers=_auth(),
                                  json={"plan": _read_plan()})
    assert submitted.status_code == 202
    exec_id = submitted.json()["id"]
    view = await _wait_terminal(client, _auth(), exec_id)
    assert view["state"] == "completed"
    assert view["report"]["plan_digest"] == view["digest"]
    assert bridge.calls == [("list_targets", {})]


@pytest.mark.asyncio
async def test_sensitive_plan_needs_approve_scope(world):
    client, _, _ = world
    denied = await client.post(
        "/v1/executions", headers=_auth(scopes={"read", "plan"}),
        json={"plan": _approve_plan()})
    assert denied.status_code == 403
    assert "approve" in denied.json()["error"]


@pytest.mark.asyncio
async def test_sensitive_plan_without_approval_waits(world):
    client, bridge, _ = world
    submitted = await client.post("/v1/executions", headers=_auth(),
                                  json={"plan": _approve_plan()})
    view = await _wait_terminal(client, _auth(), submitted.json()["id"])
    assert view["state"] == "awaiting_approval"
    assert bridge.calls == []  # nothing sent without the human decision


@pytest.mark.asyncio
async def test_approved_write_job_followed_to_terminal(world):
    from molchat_agent.plan import Plan

    client, bridge, _ = world
    plan = Plan.from_dict(_approve_plan())
    submitted = await client.post(
        "/v1/executions", headers=_auth(),
        json={"plan": plan.as_dict(), "approval_digest": plan.digest,
              "approved_steps": ["s1"]})
    view = await _wait_terminal(client, _auth(), submitted.json()["id"])
    assert view["state"] == "completed"
    assert view["report"]["outcomes"][0]["result"]["final"]["status"] == "SUCCESS"
    assert ("approve_docking_proposal", {"proposal_id": "p1",
                                         "proposal_hash": "sha256:" + "c" * 64}) \
        in bridge.calls


@pytest.mark.asyncio
async def test_invalid_plans_rejected(world):
    client, _, _ = world
    assert (await client.post("/v1/executions", headers=_auth(),
                              json={"plan": {"goal": "x"}})).status_code == 400
    assert (await client.post("/v1/executions", headers=_auth(),
                              json={"plan": "nope"})).status_code == 400
    assert (await client.get("/v1/executions/nope",
                             headers=_auth())).status_code == 404


@pytest.mark.asyncio
async def test_execution_events_end_on_terminal(world):
    client, _, _ = world
    submitted = await client.post("/v1/executions", headers=_auth(),
                                  json={"plan": _read_plan()})
    response = await client.get(f"/v1/executions/{submitted.json()['id']}/events",
                                headers=_auth())
    assert response.status_code == 200
    snapshots = _events(response.content)
    assert snapshots[0]["type"] == "snapshot"
    assert snapshots[-1]["state"] == "completed"
    assert snapshots[-1]["report"]["plan_digest"] == snapshots[-1]["digest"]
    assert (await client.get("/v1/executions/nope/events",
                             headers=_auth())).status_code == 404


@pytest.mark.asyncio
async def test_cancel_marks_and_cancels_remote_job(tmp_path, monkeypatch):
    monkeypatch.setattr("molchat_agent.server.auth.time.time", lambda: NOW)
    bridge = GateBridge()
    store = ExecutionStore(tmp_path / "exec.db")

    async def no_sleep(_delay):
        pass

    manager = ExecutionManager(
        bridge, store,
        tracker_factory=lambda: JobTracker(bridge, store=store, sleep=no_sleep,
                                           jitter=0))
    registry = build_registry(MolChatConfig(profile="hackathon"))
    state = ServerState(
        secret=SECRET, registry=registry,
        memory=MemoryStore(tmp_path / "mem.db"),
        backend=QualityBackend(FIXTURES), provider_id="fake",
        executions=manager)
    app = create_app(state, allowed_hosts=("testserver",))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport,
                                 base_url="http://testserver") as client:
        from molchat_agent.plan import Plan

        plan = Plan.from_dict(_approve_plan())
        submitted = await client.post(
            "/v1/executions", headers=_auth(),
            json={"plan": plan.as_dict(), "approval_digest": plan.digest,
                  "approved_steps": ["s1"]})
        exec_id = submitted.json()["id"]
        for _ in range(100):
            if bridge.status_calls >= 1:
                break
            await asyncio.sleep(0.05)
        assert bridge.status_calls >= 1  # runner is inside the follow loop
        cancelled = await client.post(f"/v1/executions/{exec_id}/cancel",
                                      headers=_auth())
        assert cancelled.json()["cancelled"] is True
        assert ("cancel_evaluation", {"task_id": "task-9"}) in bridge.calls
        bridge.release.set()
        view = await _wait_terminal(client, _auth(), exec_id)
        assert view["state"] == "cancelled"
        assert view["report"] is not None  # final evidence attached
        again = await client.post(f"/v1/executions/{exec_id}/cancel",
                                  headers=_auth())
        assert again.json() == {"cancelled": False,
                                "detail": "already terminal: cancelled"}


@pytest.mark.asyncio
async def test_cancel_needs_scope_and_existing_id(world):
    client, _, _ = world
    submitted = await client.post("/v1/executions", headers=_auth(),
                                  json={"plan": _read_plan()})
    exec_id = submitted.json()["id"]
    denied = await client.post(f"/v1/executions/{exec_id}/cancel",
                               headers=_auth(scopes={"read"}))
    assert denied.status_code == 403
    assert (await client.post("/v1/executions/nope/cancel",
                              headers=_auth())).status_code == 404
