"""Standalone wiring: loopback-only bind, token modes, static UI."""

import httpx
import pytest

from molchat_agent.config import MolChatConfig
from molchat_agent.server.auth import verify
from molchat_agent.server.serve import (
    build_server,
    find_ui_dist,
    validate_bind_host,
)


def test_only_loopback_binds():
    for host in ("127.0.0.1", "localhost", "::1", "LOCALHOST"):
        assert validate_bind_host(host) == host
    for host in ("0.0.0.0", "192.168.1.10", "example.com", ""):
        with pytest.raises(ValueError, match="loopback"):
            validate_bind_host(host)


def test_standalone_build_mints_a_verifiable_token(tmp_path):
    served = build_server(MolChatConfig(
        memory_file=tmp_path / "mem.db", exec_store=tmp_path / "exec.db"))
    assert served.token is not None
    session = verify(served.secret, served.token)
    assert session.allows("read", "chat", "plan", "approve", "cancel", "transcribe")
    # STT: local faster-whisper fallback when importable (Fase 4 closure);
    # None only when neither the platform token nor the local model exists.
    from molchat_agent.voice.local_whisper import faster_whisper_available
    assert (served.state.stt is None) == (not faster_whisper_available())


def test_hosted_build_uses_shared_secret_and_no_token(tmp_path):
    served = build_server(MolChatConfig(
        host_secret="test-host-secret",
        memory_file=tmp_path / "mem.db", exec_store=tmp_path / "exec.db"))
    assert served.token is None
    assert served.secret == b"test-host-secret"


def test_find_ui_dist_prefers_explicit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no ./ui/dist here
    good = tmp_path / "dist"
    (good / "assets").mkdir(parents=True)
    (good / "index.html").write_text("<html></html>", encoding="utf-8")
    assert find_ui_dist(str(good)) == good
    assert find_ui_dist(str(tmp_path / "missing")) is None
    empty = tmp_path / "empty"
    empty.mkdir()
    assert find_ui_dist(str(empty)) is None
    assert find_ui_dist("") is None


@pytest.mark.asyncio
async def test_static_ui_served_and_traversal_blocked(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>UI</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    served = build_server(MolChatConfig(
        memory_file=tmp_path / "mem.db", exec_store=tmp_path / "exec.db",
        ui_dist=str(dist)))
    assert served.ui_dist == dist
    transport = httpx.ASGITransport(app=served.app)
    async with httpx.AsyncClient(transport=transport,
                                 base_url="http://127.0.0.1") as client:
        root = await client.get("/")
        assert root.status_code == 200
        assert "UI" in root.text
        assert root.headers["content-type"].startswith("text/html")
        js = await client.get("/assets/app.js")
        assert js.headers["content-type"].startswith("text/javascript")
        assert (await client.get("/no-existe")).status_code == 404
        assert (await client.get("/../mem.db")).status_code == 404
        # API routes still win over the catch-all.
        assert (await client.get("/v1/health")).status_code == 200


@pytest.mark.asyncio
async def test_api_only_without_built_ui(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no ./ui/dist fallback here
    served = build_server(MolChatConfig(
        memory_file=tmp_path / "mem.db", exec_store=tmp_path / "exec.db",
        ui_dist=str(tmp_path / "missing")))
    assert served.ui_dist is None
    transport = httpx.ASGITransport(app=served.app)
    async with httpx.AsyncClient(transport=transport,
                                 base_url="http://127.0.0.1") as client:
        root = await client.get("/")
        assert root.status_code == 200
        assert "health" in root.json()
