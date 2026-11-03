"""Preparación inside the plan: the window builds the projection, MolDesign audits it and builds its own package."""
import asyncio
import io
import json
import zipfile

import pytest

from molchat_agent.workflows.service import PreparationHttp
from tests.conversation.fake_moldesign import MOLECULE, PACKAGE_BYTES
from tests.server.test_product_actions_chat import Chat
from tests.server.test_workflow_chat import PROJECTION, Window, approve, fake, propose


def audited(estado="REVISION", molecule=MOLECULE):
    return {"status": "audited", "molecule_id": molecule, "estado": estado, "projection": PROJECTION}


@pytest.mark.asyncio
async def test_preparation_is_audited_by_moldesign_and_its_package_goes_into_the_zip_untouched(tmp_path, monkeypatch):
    md = fake()
    async with Chat(tmp_path, monkeypatch, md) as chat:
        chat.state.preparation = PreparationHttp
        card = (await propose(chat))["workflow_proposals"][0]
        window = Window(chat)
        await approve(chat, card, window)
        workflow = chat.state.workflows[card["id"]]

        assert window.seen.count("preparation-requests") == 1
        # MolDesign did the audit and built the package, from the projection the window built, with the account's session
        posts = {c.path: c for c in md.calls if "/evaluation/dossier/" in c.path}
        assert set(posts) == {f"/evaluation/dossier/{MOLECULE}/preparacion", f"/evaluation/dossier/{MOLECULE}/package"}
        assert all(c.body == PROJECTION and c.auth == chat.headers["Authorization"] for c in posts.values())

        prep = workflow.outcome.preparation
        assert prep["status"] == "exported" and prep["readiness"] == "REVISION" and "package" not in prep
        assert prep["in_review"] == ["Aguas del sitio", "Estado de protonación"] and "no los decidió" in prep["message"]
        with zipfile.ZipFile(io.BytesIO(workflow.files["entrega.zip"])) as archive:
            manifest = json.loads(archive.read("MANIFEST.json"))
            assert archive.read("preparacion/dossier_t-8t69.zip") == PACKAGE_BYTES
        assert manifest["missing"] == []
        assert workflow.summary["preparation"] == "REVISION"
        notebook = workflow.files["cuaderno.md"].decode()
        assert "Preparación: exported · Preparación: REVISION" in notebook or "REVISION" in notebook


@pytest.mark.asyncio
async def test_a_blocked_audit_still_ships_and_says_it_is_blocked(tmp_path, monkeypatch):
    md = fake()
    md.preparation_state = "BLOQUEADO"
    async with Chat(tmp_path, monkeypatch, md) as chat:
        chat.state.preparation = PreparationHttp
        card = (await propose(chat))["workflow_proposals"][0]
        await approve(chat, card, Window(chat, preparation=audited("BLOQUEADO")))
        workflow = chat.state.workflows[card["id"]]
    assert workflow.outcome.preparation["readiness"] == "BLOQUEADO" and workflow.summary["preparation"] == "BLOQUEADO"


@pytest.mark.asyncio
async def test_when_the_window_cannot_audit_the_zip_declares_it_and_the_plan_still_ends(tmp_path, monkeypatch):
    async with Chat(tmp_path, monkeypatch, fake()) as chat:
        chat.state.preparation = PreparationHttp
        card = (await propose(chat))["workflow_proposals"][0]
        await approve(chat, card, Window(chat, preparation={"status": "case_not_found"}))
        workflow = chat.state.workflows[card["id"]]
        with zipfile.ZipFile(io.BytesIO(workflow.files["entrega.zip"])) as archive:
            manifest = json.loads(archive.read("MANIFEST.json"))
    assert workflow.state == "done" and workflow.outcome.preparation["status"] == "case_not_found"
    assert [m["item"] for m in manifest["missing"]] == ["preparacion/"] and "Ningún caso" in manifest["missing"][0]["reason"]
    assert any(p["kind"] == "video" for p in manifest["pieces"])


@pytest.mark.asyncio
async def test_an_audit_for_another_molecule_is_not_accepted(tmp_path, monkeypatch):
    md = fake()
    async with Chat(tmp_path, monkeypatch, md) as chat:
        chat.state.preparation = PreparationHttp
        card = (await propose(chat))["workflow_proposals"][0]
        await approve(chat, card, Window(chat, preparation=audited(molecule="otra-molecula")))
        workflow = chat.state.workflows[card["id"]]
    assert workflow.outcome.preparation["status"] == "case_mismatch"
    assert not [c for c in md.calls if "/evaluation/dossier/" in c.path]


@pytest.mark.asyncio
async def test_a_package_that_moldesign_cannot_build_keeps_the_audit_and_declares_the_rest(tmp_path, monkeypatch):
    md = fake()
    md.package_status = 409
    async with Chat(tmp_path, monkeypatch, md) as chat:
        chat.state.preparation = PreparationHttp
        card = (await propose(chat))["workflow_proposals"][0]
        await approve(chat, card, Window(chat))
        workflow = chat.state.workflows[card["id"]]
    prep = workflow.outcome.preparation
    assert prep["status"] == "export_failed" and prep["readiness"] == "REVISION"
    assert "no entregó el paquete" in prep["message"]


@pytest.mark.asyncio
async def test_the_result_endpoint_refuses_what_is_not_the_contract(tmp_path, monkeypatch):
    async with Chat(tmp_path, monkeypatch, fake()) as chat:
        loop = asyncio.get_running_loop()

        async def post(payload):
            future = loop.create_future()
            chat.state.preparation_requests["r1"] = ("owner", future)
            response = await chat.client.post("/v1/preparation-requests/r1/result", headers=chat.headers, json=payload)
            return response.status_code, future.done()

        good = audited()
        assert await post(good) == (200, True)
        for bad in ({**good, "estado": "TODO_BIEN"}, {**good, "extra": 1}, {**good, "projection": "x"},
                    {**good, "molecule_id": "../x"}, {"status": "audited"}, {"status": "ok"},
                    {"status": "failed", "projection": {}}, {"status": "failed", "reason": "a\u0000b"}):
            assert await post(bad) == (400, False), bad
        assert await post({"status": "case_not_found", "reason": "no está"}) == (200, True)
        missing = await chat.client.post("/v1/preparation-requests/nope/result", headers=chat.headers, json=good)
        assert missing.status_code == 404
