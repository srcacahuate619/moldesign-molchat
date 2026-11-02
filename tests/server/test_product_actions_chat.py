"""Saving in Moldex and asking Molcy for a video through the hosted chat: the model proposes, the person confirms."""
import json
from pathlib import Path

import httpx
import pytest

from molchat_agent.bridge import MolDesignBridge
from molchat_agent.config import MolChatConfig
from molchat_agent.conversation.memory import MemoryStore
from molchat_agent.conversation.tools import QualityBackend
from molchat_agent.providers import build_registry
from molchat_agent.server.app import create_app
from molchat_agent.server.auth import mint, standalone_secret
from molchat_agent.server.state import ServerState

from tests.conversation.fake_moldesign import MOLECULE, TASK, VIDEO_JOB, FakeMolDesign

VIDEO = {"task_id": TASK, "scene": "resultado", "format": "horizontal"}


def events(response):
    return [json.loads(line[5:].strip()) for line in response.text.splitlines() if line.startswith("data:")]


def call(name, args, call_id="c1"):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class Chat:
    """A hosted sidecar over a fake MolDesign, with a model that makes the tool calls a test scripts."""

    def __init__(self, tmp_path, monkeypatch, fake):
        registry = build_registry(MolChatConfig())
        registry.set_active("fake")
        secret = standalone_secret()
        self.state = ServerState(secret=secret, registry=registry, memory=MemoryStore(tmp_path / "memory.db"),
                                 backend=QualityBackend(Path(__file__).parent.parent / "quality/fixtures/properties.json"),
                                 hosted=True)
        self.fake, self.secret = fake, secret
        self.headers = {"Authorization": f"Bearer {mint(secret, 'owner', {'chat'}, 3600)}"}
        self.script, self.final, self.seen_tools, self.seen_system, self.tool_results = [], "Hecho.", [], [], []

        async def model(messages, tools):
            if messages[-1]["role"] == "user":
                self.seen_tools = {item["function"]["name"] for item in tools}
                self.seen_system = messages[0]["content"]
                calls = list(self.script)
                if calls:
                    return {"role": "assistant", "content": None, "tool_calls": calls}
            elif messages[-1]["role"] == "tool":
                tail = []
                for message in reversed(messages):
                    if message["role"] != "tool":
                        break
                    tail.append(json.loads(message["content"]))
                self.tool_results = list(reversed(tail))
            return {"role": "assistant", "content": self.final}

        monkeypatch.setattr(registry.get("fake"), "chat_with_tools", model, raising=False)

        async def registry_for_turn(_token):
            return registry
        monkeypatch.setattr(self.state, "registro_de_turno", registry_for_turn)

    async def __aenter__(self):
        self.host = httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(self.fake.handler))
        self.state.bridge = MolDesignBridge(client=self.host)
        app = create_app(self.state, allowed_hosts=("testserver",))
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        return self

    async def __aexit__(self, *_):
        await self.client.aclose()
        await self.host.aclose()

    async def say(self, text, script=(), final="Hecho."):
        self.script, self.final, self.tool_results = list(script), final, []
        response = await self.client.post("/v1/chat", headers=self.headers, json={"text": text, **(
            {"conversation_id": self.conv} if getattr(self, "conv", None) else {})})
        evs = events(response)
        self.conv = next(e["id"] for e in evs if e["type"] == "conversation")
        return next(e["result"] for e in evs if e["type"] == "result")

    async def messages(self):
        return (await self.client.get(f"/v1/conversations/{self.conv}", headers=self.headers)).json()["messages"]


@pytest.mark.asyncio
async def test_asking_for_a_video_leaves_a_card_and_writes_nothing(tmp_path, monkeypatch):
    fake = FakeMolDesign(saved=False)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        result = await chat.say("hazme un vídeo horizontal del resultado de la tarea t-8t69, con el título «Mi vídeo»",
                                [call("request_molcy_video", {**VIDEO, "title": "Mi vídeo"})], final="Listo, generé el vídeo y ya está guardado.")
        assert {"save_to_moldex", "request_molcy_video", "get_molcy_video_status"} <= chat.seen_tools
        assert "Nunca digas que se guardó" in chat.seen_system
    assert fake.writes() == []
    (card,) = result["action_proposals"]
    assert card["kind"] == "molcy_video" and card["title"] == "Generar vídeo con Molcy" and card["saves_first"] is True
    assert any("Título: Mi vídeo" in line for line in card["lines"])
    assert result["text"].startswith("Dejé preparado «Generar vídeo con Molcy». Todavía no se hizo nada")
    assert "generé" not in result["text"] and "ya está guardado" not in result["text"]
    assert set(card) == {"id", "kind", "title", "lines", "saves_first"} and MOLECULE not in json.dumps(card)


@pytest.mark.asyncio
async def test_the_click_saves_then_queues_the_video_with_the_accounts_session(tmp_path, monkeypatch):
    fake = FakeMolDesign(saved=False)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        card = (await chat.say("vídeo del resultado", [call("request_molcy_video", {**VIDEO, "title": "Mi vídeo"})]))["action_proposals"][0]
        assert fake.writes() == []
        confirmed = await chat.client.post(f"/v1/actions/{card['id']}/confirm", headers=chat.headers)
        assert confirmed.status_code == 200 and confirmed.json()["state"] == "done"
        outcome = confirmed.json()["outcome"]
        assert outcome["status"] == "started" and outcome["job_id"] == VIDEO_JOB and outcome["saved_first"] is True
        assert [(c.method, c.path) for c in fake.writes()] == [("POST", f"/history/save/{MOLECULE}"), ("POST", "/molcy/trabajos")]
        assert fake.writes()[1].body["presentacion"] == {"titulo": "Mi vídeo"} and fake.writes()[1].body["dispositivo"] == "gpu"
        assert {c.auth for c in fake.calls} == {chat.headers["Authorization"]}
        # a second click reports what happened; it does not queue a second video
        again = await chat.client.post(f"/v1/actions/{card['id']}/confirm", headers=chat.headers)
        assert again.json()["outcome"] == outcome and len(fake.writes()) == 2
        last = (await chat.messages())[-1]
        assert last["role"] == "assistant" and VIDEO_JOB in last["content"] and "vídeo en cola en Molcy" in last["content"]


@pytest.mark.asyncio
async def test_a_refusal_from_molcy_ends_the_card_with_the_reason_and_the_conversation_says_so(tmp_path, monkeypatch):
    fake = FakeMolDesign(saved=True, video_status=409, video_reply={"detail": "No hay una GPU compatible."})
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        card = (await chat.say("vídeo", [call("request_molcy_video", VIDEO)]))["action_proposals"][0]
        outcome = (await chat.client.post(f"/v1/actions/{card['id']}/confirm", headers=chat.headers)).json()["outcome"]
        assert outcome["status"] == "rejected" and "No hay una GPU compatible." in outcome["message"]
        last = (await chat.messages())[-1]["content"]
        assert "no se completó" in last and "No hay una GPU compatible." in last and "en cola" not in last


@pytest.mark.asyncio
async def test_saving_in_moldex_is_its_own_card_and_its_own_click(tmp_path, monkeypatch):
    fake = FakeMolDesign(saved=False)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        result = await chat.say("guarda esa corrida en Moldex como «Mi corrida»", [call("save_to_moldex", {"task_id": TASK, "name": "Mi corrida"})])
        card, = result["action_proposals"]
        assert card["kind"] == "save_moldex" and fake.writes() == []
        outcome = (await chat.client.post(f"/v1/actions/{card['id']}/confirm", headers=chat.headers)).json()["outcome"]
        assert outcome["status"] == "saved" and outcome["name"] == "Mi corrida"
        assert [(c.path, c.params) for c in fake.writes()] == [(f"/history/save/{MOLECULE}", {"task_id": TASK, "name": "Mi corrida"})]
        assert "quedó guardada en Moldex" in (await chat.messages())[-1]["content"]


@pytest.mark.asyncio
async def test_cancelling_does_nothing_and_a_later_click_cannot_revive_it(tmp_path, monkeypatch):
    fake = FakeMolDesign(saved=False)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        card = (await chat.say("vídeo", [call("request_molcy_video", VIDEO)]))["action_proposals"][0]
        cancelled = await chat.client.post(f"/v1/actions/{card['id']}/cancel", headers=chat.headers)
        assert cancelled.json()["state"] == "cancelled"
        late = await chat.client.post(f"/v1/actions/{card['id']}/confirm", headers=chat.headers)
        assert late.status_code == 200 and late.json()["state"] == "cancelled" and late.json()["outcome"]["status"] == "cancelled"
        assert fake.writes() == []
        assert "cancelado; no se hizo nada" in (await chat.messages())[-1]["content"]


@pytest.mark.asyncio
async def test_only_the_owner_with_the_chat_scope_can_confirm_and_only_while_it_lasts(tmp_path, monkeypatch):
    fake = FakeMolDesign(saved=True)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        card = (await chat.say("vídeo", [call("request_molcy_video", VIDEO)]))["action_proposals"][0]
        url = f"/v1/actions/{card['id']}/confirm"
        read_only = {"Authorization": f"Bearer {mint(chat.secret, 'owner', {'read'}, 3600)}"}
        other = {"Authorization": f"Bearer {mint(chat.secret, 'intruder', {'chat'}, 3600)}"}
        assert (await chat.client.post(url, headers=read_only)).status_code == 403
        assert (await chat.client.post(url, headers=other)).status_code == 403
        assert (await chat.client.post(url)).status_code == 401
        assert (await chat.client.post("/v1/actions/no-existe/confirm", headers=chat.headers)).status_code == 404
        chat.state.proposals[card["id"]].expires = 0
        assert (await chat.client.post(url, headers=chat.headers)).status_code == 404
        assert fake.writes() == []


@pytest.mark.asyncio
async def test_a_proposal_cannot_be_confirmed_outside_the_hosted_mode(tmp_path, monkeypatch):
    fake = FakeMolDesign(saved=True)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        card = (await chat.say("vídeo", [call("request_molcy_video", VIDEO)]))["action_proposals"][0]
        chat.state.hosted = False
        assert (await chat.client.post(f"/v1/actions/{card['id']}/confirm", headers=chat.headers)).status_code == 409
        assert fake.writes() == []


@pytest.mark.asyncio
async def test_a_claim_of_a_done_deed_without_any_tool_is_corrected_and_nothing_is_written(tmp_path, monkeypatch):
    fake = FakeMolDesign()
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        result = await chat.say("guarda la corrida", final="Guardé la corrida en Moldex y generé el vídeo.")
    assert result["action_proposals"] == [] and fake.writes() == []
    assert "Guardé" not in result["text"] and "generé" not in result["text"]
    assert result["text"].count("No se confirmó") == 2


@pytest.mark.asyncio
async def test_a_negative_control_ordinary_answers_pass_untouched(tmp_path, monkeypatch):
    async with Chat(tmp_path, monkeypatch, FakeMolDesign()) as chat:
        result = await chat.say("¿puedo hacer un vídeo?", final="Sí: para generar el vídeo necesitas una GPU y guardar antes la corrida.")
    assert result["text"] == "Sí: para generar el vídeo necesitas una GPU y guardar antes la corrida." and result["action_proposals"] == []


@pytest.mark.asyncio
async def test_invalid_arguments_never_become_a_proposal(tmp_path, monkeypatch):
    fake = FakeMolDesign(saved=True)
    bad = [{**VIDEO, "scene": "pelicula"}, {**VIDEO, "format": "cuadrado"}, {"task_id": TASK}, {**VIDEO, "cierre": "no"},
           {**VIDEO, "show_previous": True}, {**VIDEO, "color_polar": "verde"}]
    for arguments in bad:
        async with Chat(tmp_path, monkeypatch, fake) as chat:
            result = await chat.say("vídeo", [call("request_molcy_video", arguments)], final="No pude prepararlo.")
        assert result["action_proposals"] == [], arguments
        assert fake.writes() == [], arguments


@pytest.mark.asyncio
async def test_asking_twice_in_a_turn_is_still_one_card(tmp_path, monkeypatch):
    fake = FakeMolDesign(saved=True)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        result = await chat.say("vídeo", [call("request_molcy_video", VIDEO, "a"), call("request_molcy_video", VIDEO, "b")])
        assert [r["status"] for r in chat.tool_results] == ["awaiting_confirmation", "busy"]
    assert len(result["action_proposals"]) == 1


@pytest.mark.asyncio
async def test_an_unfinished_run_gets_no_card(tmp_path, monkeypatch):
    fake = FakeMolDesign(job_status="STARTED")
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        result = await chat.say("guárdala", [call("save_to_moldex", {"task_id": TASK})], final="Todavía no terminó.")
        assert chat.tool_results[0]["status"] == "not_ready"
    assert result["action_proposals"] == [] and result["text"] == "Todavía no terminó." and fake.writes() == []


@pytest.mark.asyncio
async def test_following_a_video_reads_molcy_and_writes_nothing(tmp_path, monkeypatch):
    reply = {"id": VIDEO_JOB, "estado": "renderizando", "fase": "Renderizando", "progreso": {"fotogramas": 120, "total": 480}}
    fake = FakeMolDesign(state_reply=reply)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        result = await chat.say("¿cómo va el vídeo?", [call("get_molcy_video_status", {"job_id": VIDEO_JOB})],
                                final="Está renderizando: 120 de 480 fotogramas.")
        assert chat.tool_results[0]["job_state"] == "renderizando"
    assert fake.writes() == [] and result["action_proposals"] == []
    assert [c.path for c in fake.calls] == [f"/molcy/trabajos/{VIDEO_JOB}"]
