"""An iteration through the hosted chat: the model proposes, one click approves, the plan runs by itself."""
import asyncio
import io
import json
import zipfile

import pytest

from tests.conversation.fake_moldesign import MOLECULE, TASK, VIDEO_BYTES, VIDEO_JOB, FakeMolDesign
from tests.server.test_product_actions_chat import Chat, call, events

REQUEST = ("molchat investiga esta lista de moléculas y si alguna pasa el umbral de -9.0 kcal/mol la guardas en moldex, "
           "generas un vídeo de búsqueda, le haces la auditoría en preparación y al final me preparas todo en un único archivo")
ITERATION = {"case_name": "hipotesis-8T69", "pdb_id": "8T69", "threshold_kcal": -9.0, "save": True,
             "molecules": [{"name": "Rota", "smiles": "C1CC"}, {"name": "Buena", "smiles": "CCN"}, {"name": "Nunca", "smiles": "CCO"}],
             "video": {"scene": "busqueda"}, "preparation": True, "package": True}
REGISTRIES = (("case_requests", "case-requests"), ("smiles_requests", "smiles-requests"),
              ("receptor_requests", "receptor-requests"), ("evaluation_requests", "evaluation-requests"),
              ("preparation_requests", "preparation-requests"), ("case_status_requests", "case-status-requests"),
              ("molcy_requests", "molcy-requests"))
PROJECTION = {"projection_version": 1, "case_id": "c-1", "name": "hipotesis-8T69"}


def fake() -> FakeMolDesign:
    return FakeMolDesign(saved=False, scenes=("resultado", "busqueda"), state_reply={"id": VIDEO_JOB, "estado": "completo"})


class Window:
    """The person's window: answers the host actions the plan asks for, like the interface does."""

    def __init__(self, chat, smiles=("applied",), preparation=None):
        self.chat, self.smiles, self.seen, self.stop = chat, list(smiles), [], asyncio.Event()
        self.answered: set[str] = set()
        self.preparation = preparation or {"status": "audited", "molecule_id": MOLECULE, "estado": "REVISION",
                                           "projection": PROJECTION}

    def answer(self, kind):
        if kind == "case-requests":
            return {"status": "created"}
        if kind == "receptor-requests":
            return {"status": "applied"}
        if kind == "preparation-requests":
            return self.preparation
        if kind == "case-status-requests":
            return {"status": "idle"}
        if kind == "molcy-requests":
            return {"status": "started", "job_id": VIDEO_JOB}
        if kind == "smiles-requests":
            return {"status": self.smiles.pop(0) if len(self.smiles) > 1 else self.smiles[0]}
        return {"status": "started", "task_id": TASK}

    async def run(self):
        while not self.stop.is_set():
            for attr, kind in REGISTRIES:
                for request_id in list(getattr(self.chat.state, attr)):
                    if request_id in self.answered:
                        continue
                    self.answered.add(request_id)
                    self.seen.append(kind)
                    await self.chat.client.post(f"/v1/{kind}/{request_id}/result", headers=self.chat.headers, json=self.answer(kind))
            await asyncio.sleep(0.005)


async def propose(chat, text=REQUEST, args=ITERATION):
    return await chat.say(text, [call("propose_iteration", args)], final="Listo, ya evalué todo y guardé el vídeo.")


async def approve(chat, card, window):
    task = asyncio.create_task(window.run())
    try:
        response = await chat.client.post(f"/v1/workflows/{card['id']}/run", headers=chat.headers, json={"digest": card["digest"]})
    finally:
        window.stop.set()
        await task
    return response


@pytest.mark.asyncio
async def test_asking_for_a_chain_leaves_one_card_and_runs_nothing(tmp_path, monkeypatch):
    md = fake()
    async with Chat(tmp_path, monkeypatch, md) as chat:
        result = await propose(chat)
        assert "propose_iteration" in chat.seen_tools and "Nunca digas que se evaluó" in chat.seen_system
        workflow = next(iter(chat.state.workflows.values()))
    (card,) = result["workflow_proposals"]
    assert card["kind"] == "iteration" and card["digest"] == workflow.spec.digest
    text = "\n".join(card["lines"])
    assert "Moldex" in text and "Molcy" in text and "Preparación" in text and "único ZIP" in text and "se sigue" in text
    assert result["text"].startswith("Dejé preparado una iteración de 3 moléculas con el umbral de -9 kcal/mol")
    assert "ya evalué" not in result["text"] and "[dato no verificado]" not in result["text"]
    assert md.writes() == [] and workflow.state == "pending"
    # the person's own words travel with the plan; the model cannot rewrite what was asked
    assert workflow.spec.original_request == REQUEST


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "Prepare a plan only and wait for approval. Case hipotesis-8T69, receptor 8T69.",
    "Prepara solo la tarjeta del plan y espera mi aprobación; caso hipotesis-8T69, receptor 8T69.",
])
@pytest.mark.parametrize("proposal_first", [False, True])
async def test_planning_turn_rejects_model_requested_host_writes_before_or_after_the_card(tmp_path, monkeypatch, text, proposal_first):
    md = fake()
    writes = [call("create_case", {"name": "hipotesis-8T69"}, "case"),
              call("load_case_smiles", {"case_name": "hipotesis-8T69", "smiles": "CCO"}, "smiles"),
              call("assign_case_receptor", {"case_name": "hipotesis-8T69", "pdb_id": "8T69"}, "receptor"),
              call("evaluate_case", {"case_name": "hipotesis-8T69"}, "evaluation")]
    plan = [call("propose_iteration", ITERATION, "plan")]
    async with Chat(tmp_path, monkeypatch, md) as chat:
        result = await asyncio.wait_for(chat.say(text, plan + writes if proposal_first else writes + plan), 5)
        assert len(result["workflow_proposals"]) == 1
        assert not {"create_case", "load_case_smiles", "assign_case_receptor", "evaluate_case"} & chat.seen_tools
        assert md.writes() == []
        assert all(not getattr(chat.state, attribute) for attribute, _ in REGISTRIES)
        assert all(workflow.state == "pending" for workflow in chat.state.workflows.values())


@pytest.mark.asyncio
async def test_a_proposed_workflow_blocks_subsequent_direct_writes_even_without_a_planning_keyword(tmp_path, monkeypatch):
    md = fake()
    script = [call("propose_iteration", ITERATION, "plan"),
              call("create_case", {"name": "hipotesis-8T69"}, "case"),
              call("load_case_smiles", {"case_name": "hipotesis-8T69", "smiles": "CCO"}, "smiles"),
              call("assign_case_receptor", {"case_name": "hipotesis-8T69", "pdb_id": "8T69"}, "receptor"),
              call("evaluate_case", {"case_name": "hipotesis-8T69"}, "evaluation")]
    async with Chat(tmp_path, monkeypatch, md) as chat:
        result = await asyncio.wait_for(chat.say("Investiga estos compuestos.", script), 5)
        assert "create_case" in chat.seen_tools  # available initially, but disabled once the card exists
        assert len(result["workflow_proposals"]) == 1 and md.writes() == []
        assert all(not getattr(chat.state, attribute) for attribute, _ in REGISTRIES)


@pytest.mark.asyncio
async def test_an_invalid_plan_is_refused_to_the_model_and_no_card_exists(tmp_path, monkeypatch):
    async with Chat(tmp_path, monkeypatch, fake()) as chat:
        result = await propose(chat, args={**ITERATION, "threshold_kcal": 0})
        (shown,) = chat.tool_results
        assert shown["status"] == "invalid" and "negativo" in shown["message"]
        assert not result.get("workflow_proposals") and chat.state.workflows == {}
        # outside the schema's own range the model never reaches the spec at all
        await propose(chat, args={**ITERATION, "threshold_kcal": 5})
        assert "error" in chat.tool_results[0] and chat.state.workflows == {}


@pytest.mark.asyncio
async def test_a_wrong_digest_does_not_run_and_the_click_runs_the_whole_plan_once(tmp_path, monkeypatch):
    md = fake()
    chat_dir = tmp_path / "salida"
    async with Chat(tmp_path, monkeypatch, md) as chat:
        chat.state.output_dir = chat_dir
        card = (await propose(chat))["workflow_proposals"][0]
        refused = await chat.client.post(f"/v1/workflows/{card['id']}/run", headers=chat.headers, json={"digest": "sha256:other"})
        assert refused.status_code == 409 and md.writes() == []

        window = Window(chat, smiles=("failed", "applied"))
        response = await approve(chat, card, window)
        assert response.status_code == 200
        stream = events(response)
        workflow = chat.state.workflows[card["id"]]

        assert workflow.state == "done" and workflow.outcome.state == "completed"
        # one molecule failed to load, the loop went on, the second qualified and the third was never evaluated
        statuses = [(r.name, r.status) for r in workflow.outcome.records]
        assert statuses == [("Rota", "failed"), ("Buena", "evaluated"), ("Nunca", "skipped")]
        assert window.seen.count("smiles-requests") == 2 and window.seen.count("evaluation-requests") == 1
        # the video is launched by the Molcy tab in view, not by MolChat behind the window
        assert [c.path for c in md.writes()] == [f"/history/save/{md.job()['result']['molecule_id']}"]
        assert window.seen.count("molcy-requests") == 1
        assert {c.auth for c in md.calls} == {chat.headers["Authorization"]}

        kinds = [e.get("event") for e in stream if e["type"] == "workflow"]
        assert kinds[0] == "approved" and kinds[-1] == "done" and "molecule" in kinds
        assert {e["type"] for e in stream} >= {"case_create", "case_smiles", "case_receptor", "case_evaluation", "workflow"}

        # the ZIP: the notebook and the video MolDesign rendered, with Preparación declared absent and why
        blob = workflow.files["entrega.zip"]
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            manifest = json.loads(archive.read("MANIFEST.json"))
            video = next(p["path"] for p in manifest["pieces"] if p["kind"] == "video")
            assert archive.read(video) == VIDEO_BYTES
        assert [m["item"] for m in manifest["missing"]] == ["preparacion/"]
        assert "no permite auditar" in manifest["missing"][0]["reason"]
        assert chat_dir.exists() and any(path.endswith("entrega.zip") for path in workflow.saved_paths.values())

        # the conversation keeps what really happened, with numbers the next turn may quote
        last = (await chat.messages())[-1]
        assert last["role"] == "assistant" and "Iteración «hipotesis-8T69» terminada: 1 de 3 moléculas evaluadas" in last["content"]

        # a second click reports the outcome, it does not run the plan again
        again = await chat.client.post(f"/v1/workflows/{card['id']}/run", headers=chat.headers, json={"digest": card["digest"]})
        assert again.json()["state"] == "done" and len(md.writes()) == 1  # only the Moldex save; the video went through the tab

        served = await chat.client.get(f"/v1/workflows/{card['id']}/files/entrega.zip", headers=chat.headers)
        assert served.status_code == 200 and served.content == blob
        assert (await chat.client.get(f"/v1/workflows/{card['id']}/files/../../secret", headers=chat.headers)).status_code == 404


@pytest.mark.asyncio
async def test_cancelling_before_the_click_leaves_nothing_to_run(tmp_path, monkeypatch):
    md = fake()
    async with Chat(tmp_path, monkeypatch, md) as chat:
        card = (await propose(chat))["workflow_proposals"][0]
        cancelled = await chat.client.post(f"/v1/workflows/{card['id']}/cancel", headers=chat.headers)
        assert cancelled.json()["state"] == "cancelled"
        late = await chat.client.post(f"/v1/workflows/{card['id']}/run", headers=chat.headers, json={"digest": card["digest"]})
        assert late.json()["state"] == "cancelled" and md.writes() == []


@pytest.mark.asyncio
async def test_another_account_cannot_run_or_read_the_plan(tmp_path, monkeypatch):
    from molchat_agent.server.auth import mint
    async with Chat(tmp_path, monkeypatch, fake()) as chat:
        card = (await propose(chat))["workflow_proposals"][0]
        stranger = {"Authorization": f"Bearer {mint(chat.secret, 'intruder', {'chat'}, 3600)}"}
        assert (await chat.client.get(f"/v1/workflows/{card['id']}", headers=stranger)).status_code in (403, 404)
        run = await chat.client.post(f"/v1/workflows/{card['id']}/run", headers=stranger, json={"digest": card["digest"]})
        assert run.status_code in (403, 404)
