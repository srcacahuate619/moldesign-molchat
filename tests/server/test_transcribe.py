"""Transcribe endpoint: scoped, capped, returns text for confirmation."""

from pathlib import Path

import httpx
import pytest

from molchat_agent.bridge import BridgeError
from molchat_agent.config import MolChatConfig
from molchat_agent.conversation.memory import MemoryStore
from molchat_agent.conversation.tools import QualityBackend
from molchat_agent.providers import build_registry
from molchat_agent.server.app import create_app
from molchat_agent.server.auth import mint, standalone_secret
from molchat_agent.server.state import ServerState

FIXTURES = Path(__file__).parent.parent / "quality" / "fixtures" / "properties.json"
SECRET = standalone_secret()
NOW = 1_800_000_000


class StubSTT:
    def __init__(self, text="propiedades de la aspirina"):
        self.text = text
        self.calls = []

    async def transcribe(self, audio, *, lang="es"):
        self.calls.append((bytes(audio), lang))
        if isinstance(self.text, Exception):
            raise self.text
        return self.text


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr("molchat_agent.server.auth.time.time", lambda: NOW)
    stt = StubSTT()
    registry = build_registry(MolChatConfig(profile="hackathon"))
    state = ServerState(
        secret=SECRET, registry=registry,
        memory=MemoryStore(tmp_path / "mem.db"),
        backend=QualityBackend(FIXTURES), provider_id="fake", stt=stt)
    app = create_app(state, allowed_hosts=("testserver",))
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    return client, stt, state


def _auth(scopes):
    return {"Authorization": f"Bearer {mint(SECRET, 'cuenta-1', scopes, 3600, now=NOW)}"}


@pytest.mark.asyncio
async def test_transcribe_roundtrip_returns_text_only(world):
    client, stt, state = world
    headers = {**_auth({"transcribe"}), "Content-Type": "audio/wav"}
    response = await client.post("/v1/transcribe?lang=es", headers=headers,
                                 content=b"RIFF-test-audio")
    assert response.status_code == 200
    assert response.json() == {"text": "propiedades de la aspirina", "lang": "es"}
    assert stt.calls == [(b"RIFF-test-audio", "es")]
    # Nothing was executed: no conversations, no turns.
    assert state.memory.list_conversations("cuenta-1") == []


@pytest.mark.asyncio
async def test_transcribe_requires_audio_scope_and_type(world):
    client, stt, state = world
    no_scope = await client.post(
        "/v1/transcribe", headers={**_auth({"read"}), "Content-Type": "audio/wav"},
        content=b"RIFF-x")
    assert no_scope.status_code == 403
    no_audio = await client.post(
        "/v1/transcribe", headers={**_auth({"transcribe"}),
                                   "Content-Type": "application/json"},
        content=b"{}")
    assert no_audio.status_code == 415


@pytest.mark.asyncio
async def test_transcribe_caps_and_failures(world):
    client, stt, state = world
    headers = {**_auth({"transcribe"}), "Content-Type": "audio/wav"}
    ok = await client.post("/v1/transcribe?lang=en", headers=headers,
                           content=b"RIFF-test-audio")
    assert ok.status_code == 200
    assert ok.json() == {"text": "propiedades de la aspirina", "lang": "en"}
    assert stt.calls == [(b"RIFF-test-audio", "en")]
    # Nothing was executed: no conversations, no turns.
    assert state.memory.list_conversations("cuenta-1") == []
    assert (await client.post("/v1/transcribe?lang=fr", headers=headers,
                              content=b"RIFF-x")).status_code == 400
    assert (await client.post("/v1/transcribe", headers=headers,
                              content=b"")).status_code == 400
    stt.text = BridgeError("Whisper caído")
    failed = await client.post("/v1/transcribe", headers=headers, content=b"RIFF-x")
    assert failed.status_code == 502


@pytest.mark.asyncio
async def test_transcribe_unavailable_without_backend(tmp_path, monkeypatch):
    monkeypatch.setattr("molchat_agent.server.auth.time.time", lambda: NOW)
    registry = build_registry(MolChatConfig(profile="hackathon"))
    state = ServerState(
        secret=SECRET, registry=registry,
        memory=MemoryStore(tmp_path / "mem.db"),
        backend=QualityBackend(FIXTURES), provider_id="fake", stt=None)
    app = create_app(state, allowed_hosts=("testserver",))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport,
                                 base_url="http://testserver") as client:
        headers = {**_auth({"transcribe"}), "Content-Type": "audio/wav"}
        response = await client.post("/v1/transcribe", headers=headers,
                                     content=b"RIFF-x")
        assert response.status_code == 503
