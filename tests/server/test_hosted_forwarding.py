"""Hosted identity forwarding: the sidecar re-sends the request's Bearer.

Standalone keeps its fixed configured token; hosted (MOLCHAT_HOST_SECRET)
forwards the Bearer the host minted, per request, to the platform. The
platform accepts it as identity (worktree `molchat_host/sesion.py`).
"""

from pathlib import Path

import httpx
import pytest

from molchat_agent.bridge import MolDesignBridge
from molchat_agent.config import MolChatConfig
from molchat_agent.conversation.memory import MemoryStore
from molchat_agent.conversation.tools import QualityBackend
from molchat_agent.orchestration.store import ExecutionStore
from molchat_agent.plan import Plan
from molchat_agent.providers import build_registry
from molchat_agent.server.app import create_app
from molchat_agent.server.auth import mint, standalone_secret
from molchat_agent.server.executions import ExecutionManager, ExecutionRecord
from molchat_agent.server.serve import build_server
from molchat_agent.server.state import ServerState

FIXTURES = Path(__file__).parent.parent / "quality" / "fixtures" / "properties.json"
SECRET = standalone_secret()
NOW = 1_800_000_000


class TokenBoundBridge:
    """Double recording with_token (plumbing proof without HTTP)."""

    def __init__(self):
        self.calls = []
        self.bound_tokens = []

    def with_token(self, token):
        self.bound_tokens.append(token)
        return self

    async def call(self, capability, args, **kwargs):
        self.calls.append((capability, dict(args)))
        return {"ok": True}


def _auth(scopes):
    return f"Bearer {mint(SECRET, 'cuenta-1', scopes, 3600, now=NOW)}"


def _plan():
    return Plan.from_dict({
        "goal": "Listar", "planner": "manual",
        "steps": [{"id": "s1", "capability": "list_targets", "arguments": {},
                   "rationale": "x"}],
    })


@pytest.fixture
def frozen_time(monkeypatch):
    monkeypatch.setattr("molchat_agent.server.auth.time.time", lambda: NOW)


@pytest.mark.asyncio
async def test_submit_and_cancel_bind_the_request_token(tmp_path):
    import asyncio as _aio

    bridge = TokenBoundBridge()
    manager = ExecutionManager(bridge, ExecutionStore(tmp_path / "exec.db"))
    record = manager.submit(_plan(), platform_token="bearer-1")
    for _ in range(100):
        if manager.get(record.id).state != "queued":
            break
        await _aio.sleep(0.01)
    assert bridge.bound_tokens == ["bearer-1"]
    manager._records["stuck"] = ExecutionRecord(
        id="stuck", digest="d" * 64, state="running")
    changed, _ = await manager.cancel("stuck", platform_token="bearer-2")
    assert changed is True
    assert bridge.bound_tokens == ["bearer-1", "bearer-2"]


@pytest.mark.asyncio
async def test_standalone_uses_the_fixed_bridge(tmp_path):
    import asyncio as _aio

    bridge = TokenBoundBridge()
    manager = ExecutionManager(bridge, ExecutionStore(tmp_path / "exec.db"))
    record = manager.submit(_plan())
    for _ in range(100):
        if bridge.calls:
            break
        await _aio.sleep(0.01)
    assert bridge.bound_tokens == []
    assert bridge.calls and bridge.calls[0][0] == "list_targets"
    assert manager.get(record.id).state == "completed"


@pytest.mark.asyncio
async def test_hosted_submit_sends_bearer_to_platform(tmp_path, frozen_time):
    seen = []

    def handle(request):
        seen.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"targets": []})

    transport = httpx.MockTransport(handle)
    platform = httpx.AsyncClient(base_url="http://127.0.0.1:18017",
                                 transport=transport)
    bridge = MolDesignBridge(require_contract=False, base_url="http://127.0.0.1:18017",
                             token="test-fixed", client=platform)
    state = ServerState(
        secret=SECRET, registry=build_registry(MolChatConfig(profile="hackathon")),
        memory=MemoryStore(tmp_path / "mem.db"), backend=QualityBackend(FIXTURES),
        provider_id="fake",
        executions=ExecutionManager(bridge, ExecutionStore(tmp_path / "exec.db")),
        hosted=True, bridge=bridge)
    app = create_app(state, allowed_hosts=("testserver",))
    token = _auth({"plan", "read"})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://testserver") as client:
        response = await client.post(
            "/v1/executions", headers={"Authorization": token},
            json={"plan": _plan().as_dict()})
        assert response.status_code == 202
        exec_id = response.json()["id"]
        import asyncio as _aio

        for _ in range(100):
            current = await client.get(
                f"/v1/executions/{exec_id}", headers={"Authorization": token})
            if current.json()["state"] == "completed":
                break
            await _aio.sleep(0.05)
        assert current.json()["state"] == "completed"
    assert seen == [token]  # the request's Bearer, not the fixed token


@pytest.mark.asyncio
async def test_standalone_submit_sends_fixed_token(tmp_path, frozen_time):
    seen = []

    def handle(request):
        seen.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"targets": []})

    platform = httpx.AsyncClient(base_url="http://127.0.0.1:8000",
                                 transport=httpx.MockTransport(handle))
    bridge = MolDesignBridge(require_contract=False, token="test-fixed", client=platform)
    state = ServerState(
        secret=SECRET, registry=build_registry(MolChatConfig(profile="hackathon")),
        memory=MemoryStore(tmp_path / "mem.db"), backend=QualityBackend(FIXTURES),
        provider_id="fake",
        executions=ExecutionManager(bridge, ExecutionStore(tmp_path / "exec.db")))
    app = create_app(state, allowed_hosts=("testserver",))
    token = _auth({"plan", "read"})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://testserver") as client:
        response = await client.post(
            "/v1/executions", headers={"Authorization": token},
            json={"plan": _plan().as_dict()})
        exec_id = response.json()["id"]
        import asyncio as _aio

        for _ in range(100):
            current = await client.get(
                f"/v1/executions/{exec_id}", headers={"Authorization": token})
            if current.json()["state"] == "completed":
                break
            await _aio.sleep(0.05)
    assert seen == ["Bearer test-fixed"]


class StubSTT:
    def __init__(self, text="texto local"):
        self.text = text
        self.calls = 0

    async def transcribe(self, audio, *, lang="es"):
        self.calls += 1
        return self.text


@pytest.mark.asyncio
async def test_hosted_transcribe_prefers_platform_then_local(tmp_path, frozen_time):
    seen = []
    mode = {"platform": "ok"}

    def handle(request):
        seen.append(request.headers.get("authorization"))
        if mode["platform"] == "ok":
            return httpx.Response(200, json={"text": "texto plataforma"})
        return httpx.Response(500, json={})

    platform = httpx.AsyncClient(base_url="http://127.0.0.1:18017",
                                 transport=httpx.MockTransport(handle))
    bridge = MolDesignBridge(require_contract=False, base_url="http://127.0.0.1:18017", client=platform)
    stt = StubSTT()
    state = ServerState(
        secret=SECRET, registry=build_registry(MolChatConfig(profile="hackathon")),
        memory=MemoryStore(tmp_path / "mem.db"), backend=QualityBackend(FIXTURES),
        provider_id="fake", stt=stt, hosted=True, bridge=bridge)
    app = create_app(state, allowed_hosts=("testserver",))
    token = _auth({"transcribe"})
    headers = {"Authorization": token, "Content-Type": "audio/wav"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://testserver") as client:
        first = await client.post("/v1/transcribe", headers=headers,
                                  content=b"RIFF-x")
        assert first.json() == {"text": "texto plataforma", "lang": "es"}
        assert stt.calls == 0  # platform answered; local untouched
        mode["platform"] = "down"
        second = await client.post("/v1/transcribe", headers=headers,
                                   content=b"RIFF-x")
        assert second.json() == {"text": "texto local", "lang": "es"}
        assert stt.calls == 1
    assert seen == [token, token]


def test_build_server_marks_hosted_mode(tmp_path):
    config = MolChatConfig(profile="hackathon", host_secret="test-host-secret",
                           memory_file=tmp_path / "mem.db",
                           exec_store=tmp_path / "exec.db",
                           consents_file=tmp_path / "c.json")
    served = build_server(config)
    assert served.state.hosted is True
    assert served.state.bridge is served.bridge
    assert served.token is None
    plain = build_server(MolChatConfig(profile="hackathon",
                                       memory_file=tmp_path / "m2.db",
                                       exec_store=tmp_path / "e2.db",
                                       consents_file=tmp_path / "c2.json"))
    assert plain.state.hosted is False
