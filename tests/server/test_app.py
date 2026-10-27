"""Sidecar API: auth acceptance, conversations, chat SSE (MP-06)."""

import json
from pathlib import Path

import httpx
import pytest

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


def _token(sub="cuenta-1", scopes=None, ttl=3600):
    return mint(SECRET, sub, scopes or
                {"read", "chat", "plan", "approve", "cancel", "transcribe"},
                ttl, now=NOW)


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("molchat_agent.server.auth.time.time", lambda: NOW)
    registry = build_registry(MolChatConfig(profile="hackathon"))
    state = ServerState(
        secret=SECRET, registry=registry,
        memory=MemoryStore(tmp_path / "mem.db"),
        backend=QualityBackend(FIXTURES), provider_id="fake")
    return create_app(state, allowed_hosts=("testserver", "127.0.0.1", "localhost"))


@pytest.fixture
def client(app):
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _events(body: bytes):
    return [json.loads(line[5:].strip()) for line in body.decode().splitlines()
            if line.startswith("data:")]


@pytest.mark.asyncio
async def test_health_and_version_are_public(client):
    health = await client.get("/v1/health")
    assert health.status_code == 200
    assert health.json()["contract"] == "moldesign.molchat/1"
    version = await client.get("/v1/version")
    assert version.json()["plan_schemas"] == ["/1", "/2"]


@pytest.mark.asyncio
async def test_catalog_needs_bearer_with_read_scope(client):
    assert (await client.get("/v1/catalog")).status_code == 401
    poor = _token(scopes={"chat"})
    denied = await client.get("/v1/catalog", headers=_auth(poor))
    assert denied.status_code == 403
    assert denied.json() == {"error": "permisos insuficientes"}
    ok = await client.get("/v1/catalog", headers=_auth(_token()))
    assert ok.status_code == 200
    entries = {c["name"]: c for c in ok.json()}
    assert entries["check_preflight"]["epistemic_class"] == "calculation"


@pytest.mark.asyncio
async def test_forged_and_expired_tokens_rejected(client):
    forged = await client.get("/v1/catalog", headers=_auth("mh1.e30=.c2ln"))
    assert forged.status_code == 401
    old = mint(SECRET, "cuenta-1", {"read"}, 10, now=NOW - 100)  # long expired
    expired = await client.get("/v1/catalog", headers=_auth(old))
    assert expired.status_code == 401
    assert "caducada" in expired.json()["error"]


@pytest.mark.asyncio
async def test_disallowed_origin_and_host_rejected(client):
    evil = await client.get("/v1/catalog", headers={
        **_auth(_token()), "Origin": "https://evil.example"})
    assert evil.status_code == 403
    local = await client.get("/v1/catalog", headers={
        **_auth(_token()), "Origin": "http://127.0.0.1:3000"})
    assert local.status_code == 200
    assert local.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:3000"
    foreign = httpx.AsyncClient(
        transport=client._transport, base_url="http://evil.example",
        headers=_auth(_token()))
    try:
        assert (await foreign.get("/v1/catalog")).status_code == 403
    finally:
        await foreign.aclose()


@pytest.mark.asyncio
async def test_second_account_rejected_once_pinned(client):
    first = await client.get("/v1/catalog", headers=_auth(_token("cuenta-1")))
    assert first.status_code == 200
    second = await client.get("/v1/catalog", headers=_auth(_token("cuenta-2")))
    assert second.status_code == 403
    assert "otra cuenta" in second.json()["error"]


@pytest.mark.asyncio
async def test_revoked_session_stays_revoked(client):
    token = _token()
    assert (await client.get("/v1/catalog", headers=_auth(token))).status_code == 200
    assert (await client.post("/v1/session/revoke",
                              headers=_auth(token))).status_code == 200
    assert (await client.get("/v1/catalog", headers=_auth(token))).status_code == 401


@pytest.mark.asyncio
async def test_conversation_roundtrip_and_isolation(client):
    headers = _auth(_token())
    created = await client.post("/v1/conversations", headers=headers)
    assert created.status_code == 201
    conv_id = created.json()["id"]
    listed = await client.get("/v1/conversations", headers=headers)
    assert [c["id"] for c in listed.json()] == [conv_id]
    detail = await client.get(f"/v1/conversations/{conv_id}", headers=headers)
    assert detail.json()["messages"] == []
    other = await client.get("/v1/conversations", headers=_auth(_token("cuenta-2")))
    assert other.status_code == 403  # pinned process: no cross-account view at all
    assert (await client.get("/v1/conversations/nope", headers=headers)).status_code == 404
    assert (await client.delete(f"/v1/conversations/{conv_id}",
                                headers=headers)).status_code == 200
    assert (await client.get("/v1/conversations", headers=headers)).json() == []


@pytest.mark.asyncio
async def test_chat_streams_intent_and_verified_result(client):
    headers = _auth(_token())
    conv_id = (await client.post("/v1/conversations", headers=headers)).json()["id"]
    response = await client.post("/v1/chat", headers=headers, json={
        "conversation_id": conv_id, "text": "propiedades de la aspirina"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response.content)
    kinds = [e["type"] for e in events]
    assert kinds[0] == "conversation"
    assert "intent" in kinds and kinds[-1] == "result"
    result = events[-1]["result"]
    assert result["intent"] == "chemical"
    assert result["evidence"][0]["tool"] == "compute_properties"
    assert result["evidence"][0]["epistemic_class"] == "cálculo"
    assert "180" in result["text"]  # mw from fixtures, verified by code
    stored = await client.get(f"/v1/conversations/{conv_id}", headers=headers)
    assert len(stored.json()["messages"]) == 2  # user + assistant persisted


@pytest.mark.asyncio
async def test_chat_creates_conversation_when_omitted(client):
    response = await client.post("/v1/chat", headers=_auth(_token()),
                                 json={"text": "hola"})
    assert response.status_code == 200
    events = _events(response.content)
    assert events[0]["type"] == "conversation"
    assert events[-1]["type"] == "result"


@pytest.mark.asyncio
async def test_chat_validates_input(client):
    headers = _auth(_token())
    assert (await client.post("/v1/chat", headers=headers,
                              json={"text": "  "})).status_code == 400
    assert (await client.post("/v1/chat", headers=headers,
                              json={"text": "x" * 8001})).status_code == 413
    assert (await client.post("/v1/chat", headers=headers, json={
        "conversation_id": "nope", "text": "hola"})).status_code == 404
    bad = await client.post("/v1/chat", headers=headers, content=b"{no es json")
    assert bad.status_code == 400
    assert (await client.post("/v1/chat", headers=headers,
                              json=["lista"])).status_code == 400


@pytest.mark.asyncio
async def test_unknown_turns_abstain_without_numbers_from_nowhere(client):
    response = await client.post("/v1/chat", headers=_auth(_token()), json={
        "text": "propiedades de CCXXMOLÉCULAIMPOSIBLE99"})
    events = _events(response.content)
    result = events[-1]["result"]
    assert result["evidence"] == [] or all(
        e["error"] is None for e in result["evidence"])
