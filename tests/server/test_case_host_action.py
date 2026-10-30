import asyncio
import json
from pathlib import Path

import httpx
import pytest

from molchat_agent.config import MolChatConfig
from molchat_agent.conversation.case_selection import CreateCase
from molchat_agent.conversation.memory import MemoryStore
from molchat_agent.conversation.tools import QualityBackend
from molchat_agent.providers import build_registry
from molchat_agent.server.app import create_app
from molchat_agent.server.auth import mint, standalone_secret
from molchat_agent.server.state import ServerState


@pytest.mark.asyncio
@pytest.mark.parametrize("status, expected", [
    ("created", 'Se creó el caso "holamundo"'),
    ("exists", 'Ya existe un caso o carpeta con el nombre "holamundo"'),
    ("failed", "MolDesign no pudo crear el caso"),
    ("unknown", "No pude confirmar el resultado"),
])
async def test_case_turn_waits_for_host_and_persists_confirmed_result(tmp_path, monkeypatch, status, expected):
    async def select(_provider, _text):
        return CreateCase("holamundo")

    monkeypatch.setattr("molchat_agent.server.app.select_case", select)
    registry = build_registry(MolChatConfig())
    registry.set_active("fake")
    secret = standalone_secret()
    state = ServerState(secret=secret, registry=registry, memory=MemoryStore(tmp_path / "memory.db"),
                        backend=QualityBackend(Path(__file__).parent.parent / "quality/fixtures/properties.json"),
                        hosted=True)
    app = create_app(state, allowed_hosts=("testserver",))
    token = mint(secret, "owner", {"chat", "read"}, 3600)
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        turn = asyncio.create_task(client.post("/v1/chat", headers=headers,
                                               json={"text": 'crea un caso llamado "holamundo"'}))
        for _ in range(100):
            if state.case_requests:
                break
            await asyncio.sleep(0.01)
        assert len(state.case_requests) == 1
        request_id = next(iter(state.case_requests))
        assert not turn.done()
        other_token = mint(secret, "other", {"chat"}, 3600)
        other = await client.post(f"/v1/case-requests/{request_id}/result",
                                  headers={"Authorization": f"Bearer {other_token}"},
                                  json={"status": "created"})
        assert other.status_code == 403
        assert not turn.done()
        wrong = await client.post(f"/v1/case-requests/{request_id}/result", headers=headers,
                                  json={"status": "created", "other": "value"})
        assert wrong.status_code == 400
        ack = await client.post(f"/v1/case-requests/{request_id}/result", headers=headers,
                                json={"status": status})
        assert ack.status_code == 200
        response = await turn
        events = [json.loads(line[5:].strip()) for line in response.text.splitlines() if line.startswith("data:")]
        assert any(e.get("type") == "case_create" and e["name"] == "holamundo" for e in events)
        result = next(e["result"] for e in events if e.get("type") == "result")
        assert expected in result["text"]
        assert not state.case_requests
