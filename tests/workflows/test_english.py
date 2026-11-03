"""A plan proposed in English is carried out, written down and delivered in English.

MolChat only spoke Spanish: the plan card, the iteration's events and the whole notebook were written in Spanish
whatever language MolDesign showed. The language is now the turn's, and a plan keeps the one it was proposed in.
"""
from __future__ import annotations

import io
import re
import zipfile

from molchat_agent.lang import current, tr, using, valid
from molchat_agent.workflows.deliverable import build_deliverable, verify_deliverable
from molchat_agent.workflows.notebook import build_notebook, pdf_available, render_markdown, render_pdf
from molchat_agent.workflows.service import WorkflowProposal, new_workflow, workflow_answer

from test_notebook_and_deliverable import outcome

SPANISH = re.compile(r"[áéíóúñ¿¡«»]|\b(el|la|los|las|del|que|para|con|por|sin|una|cada|corrida|molécula)\b", re.I)


def test_the_language_is_spanish_unless_a_turn_says_english() -> None:
    assert current() == "es" and tr("hola", "hello") == "hola"
    with using("en"):
        assert tr("hola", "hello") == "hello"
    assert current() == "es"
    assert valid("en") == "en" and valid("fr") == "es" and valid(None) == "es"


def test_an_english_notebook_has_no_spanish_of_its_own() -> None:
    out = outcome()
    out.notes = []  # notes and reasons are recorded during the run, in the run's language: none here
    for record in out.records:
        record.reason = None
    with using("en"):
        nb = build_notebook(out, approved_at="2026-11-03T10:00:00+00:00", finished_at="2026-11-03T10:09:00+00:00")
    md = render_markdown(nb)  # rendered outside the turn: the notebook keeps its own language
    assert nb["lang"] == "en"
    for heading in ("# Agent notebook — hipotesis-8T69", "## What was asked", "## What was approved",
                    "## Run conditions", "## Record per molecule", "## Limits and provenance"):
        assert heading in md
    assert "Stops at the first one that meets it: Vina ≤ -9.5 kcal/mol" in md
    # the request is the person's own words (Spanish here) and stays literal; everything else is English
    own = md.replace(nb["request"], "")
    assert SPANISH.findall(own) == []


def test_an_english_pdf_is_written_too() -> None:
    if not pdf_available():
        return
    with using("en"):
        nb = build_notebook(outcome(), approved_at="a", finished_at="b")
    assert render_pdf(nb)[:4] == b"%PDF"


def test_an_english_delivery_names_its_folders_in_english() -> None:
    with using("en"):
        blob, manifest = build_deliverable("c", "sha256:x", notebook_pdf=None, notebook_md=b"# n", notebook_json=b"{}",
                                           preparation=None, video=None)
    names = set(zipfile.ZipFile(io.BytesIO(blob)).namelist())
    assert {"README.txt", "notebook/notebook.md", "notebook/notebook.json"} <= names
    assert {item["item"] for item in manifest["missing"]} == {"notebook/notebook.pdf", "preparation/", "video/"}
    assert verify_deliverable(blob) == []


def test_a_plan_keeps_the_language_it_was_proposed_in() -> None:
    from molchat_agent.workflows.iteration import IterationSpec
    spec = IterationSpec.from_dict({"case_name": "c", "pdb_id": "8T69", "threshold_kcal": -9,
                                    "molecules": [{"name": "a", "smiles": "CCO"}]})
    workflows: dict[str, WorkflowProposal] = {}
    with using("en"):
        proposal = new_workflow(workflows, "owner", None, spec)
        assert proposal is not None and proposal.lang == "en"
        assert workflow_answer(proposal).startswith("I prepared an iteration over 1 molecule with")
        assert proposal.view()["title"] == "Molecule iteration"
    assert new_workflow(workflows, "owner", None, spec).lang == "es"


def test_moldesign_is_asked_in_the_chats_language() -> None:
    """MolDesign translates its own messages (the run warnings among them) when asked: an English plan asks in English,
    so its notebook no longer copies Spanish warnings (seen in the hackathon take, 2026-11-03)."""
    import asyncio

    import httpx

    from molchat_agent.bridge import MolDesignBridge, _ask_in_chat_language

    bridge = MolDesignBridge(require_contract=False)
    assert _ask_in_chat_language in bridge.client.event_hooks["request"]

    async def asked(lang: str) -> str:
        request = httpx.Request("GET", "http://127.0.0.1:8000/evaluation/status/x")
        with using(lang):
            await _ask_in_chat_language(request)
        return request.headers["Accept-Language"]

    assert asyncio.run(asked("en")) == "en" and asyncio.run(asked("es")) == "es"
    asyncio.run(bridge.client.aclose())


def test_run_warnings_carry_an_english_severity_in_an_english_notebook() -> None:
    from molchat_agent.workflows.notebook import run_lines

    run = {"warnings": [{"code": "ESPECIE_ACOPLADA_DISTINTA", "severity": "precaucion",
                         "message": "The docked species differs from the input."},
                        {"code": "ESTEREOQUIMICA_NO_DECLARADA", "severity": "critica", "message": "2 unassigned centres."}]}
    with using("en"):
        lines = "\n".join(run_lines(run))
    assert "[caution] The docked species differs from the input. (ESPECIE_ACOPLADA_DISTINTA)" in lines
    assert "[critical] 2 unassigned centres." in lines
    with using("es"):
        assert "[precaución]" in "\n".join(run_lines(run))


def test_saving_to_moldex_is_reported_in_english() -> None:
    import asyncio

    import httpx

    from molchat_agent.bridge import MolDesignBridge
    from molchat_agent.conversation.product_actions import run_save

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "saved", "name": "ketanserin"})

    async def save() -> dict:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(handle)) as client:
            bridge = MolDesignBridge(require_contract=False, token="t", client=client)
            with using("en"):
                return await run_save(bridge, {"task_id": "t-1", "molecule_id": "m-1"})

    assert asyncio.run(save())["message"] == "Run saved to Moldex."


def test_preparation_state_is_named_as_moldesign_names_it_in_english() -> None:
    from molchat_agent.workflows.service import readiness_label

    with using("en"):
        assert [readiness_label(c) for c in ("REVISION", "BLOQUEADO", "TRANSFERIBLE")] == ["REVIEW", "BLOCKED", "TRANSFERABLE"]
    assert readiness_label("REVISION") == "REVISION" and readiness_label(None) is None


def test_the_plan_card_names_molcy_scene_as_the_molcy_tab_does() -> None:
    from molchat_agent.workflows.iteration import IterationSpec

    spec = IterationSpec.from_dict({"case_name": "c", "pdb_id": "8T69", "molecules": [{"name": "a", "smiles": "CCO"}],
                                    "threshold_kcal": -9.5, "video": {"scene": "resultado", "format": "previsualizacion"}})
    with using("en"):
        assert any("scene Result, format test (short preview)" in line for line in spec.card_lines())
    assert any("escena resultado" in line for line in spec.card_lines())
