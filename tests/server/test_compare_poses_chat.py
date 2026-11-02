"""Comparing two poses through the hosted chat: the evidence is MolDesign's, and the answer carries its verdict."""
import pytest

from tests.conversation.fake_moldesign import TASK, FakeMolDesign
from tests.server.test_product_actions_chat import Chat, call

CONTACTS = {1: [("hbond", "ASP34A", 2.91), ("hydrophobic", "LEU12A", 3.8)],
            2: [("hbond", "ASP34A", 3.05), ("hbond", "SER90A", 2.8)]}
ASK = "compara la pose 1 y la pose 2 de la tarea t-8t69"


@pytest.mark.asyncio
async def test_the_tool_and_its_instructions_reach_the_model_and_the_answer_cites_the_lock(tmp_path, monkeypatch):
    fake = FakeMolDesign(contacts=CONTACTS)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        result = await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2})],
                                final="La pose 1 tiene la energía de Vina más baja, por 0,4 kcal/mol; ambas contactan Asp34A.")
        assert "compare_poses" in chat.seen_tools and "No declares ganadora" in chat.seen_system
        (shown,) = chat.tool_results
    assert shown["status"] == "ok" and shown["difference"]["right_minus_left_vina_kcal_mol"] == 0.4
    assert "0,4" in result["text"] and "[dato no verificado]" not in result["text"]
    assert "Controles físicos según MolDesign — pose 1: superó los controles físicos; pose 2: superó los controles físicos" in result["text"]
    assert fake.writes() == [] and not result.get("action_proposals")


@pytest.mark.asyncio
async def test_a_number_the_tool_did_not_return_is_not_kept(tmp_path, monkeypatch):
    async with Chat(tmp_path, monkeypatch, FakeMolDesign(contacts=CONTACTS)) as chat:
        result = await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2})],
                                final="La pose 2 es 3,7 kcal/mol peor que la 1.")
    assert "3,7" not in result["text"]


@pytest.mark.asyncio
async def test_the_answer_ends_with_what_the_lock_says_even_if_the_model_calls_a_failed_pose_valid(tmp_path, monkeypatch):
    fake = FakeMolDesign(comparison_case="sugerida_falla", contacts=CONTACTS)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        result = await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2})],
                                final="Las dos poses son válidas y la 2 es la mejor.")
    assert result["text"].rstrip().endswith("no se declara ganadora.")
    assert "pose 1: superó los controles físicos; pose 2: no superó los controles físicos" in result["text"]


@pytest.mark.asyncio
async def test_zero_contacts_are_never_left_as_proof_of_no_interaction(tmp_path, monkeypatch):
    """The real 8T69 run gave zero contacts for two poses that touch the pocket; the model said they do not interact."""
    fake = FakeMolDesign(contacts={1: [], 2: []})
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        result = await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2})],
                                final="Ninguna de las dos poses interactúa con el receptor.")
        (shown,) = chat.tool_results
    assert shown["contacts"]["conclusive"] is False
    assert "Cero contactos tipificados en la pose 1, la pose 2" in result["text"]
    assert "no prueba que no haya interacción" in result["text"]
    assert result["text"].rstrip().endswith("no se declara ganadora.")


@pytest.mark.asyncio
async def test_vinas_rmsd_bounds_are_worded_by_the_host_not_left_to_the_model(tmp_path, monkeypatch):
    """The model called Vina's bounds a confidence interval; the host's sentence says what they are."""
    fake = FakeMolDesign(comparison_case="rmsd_de_la_mejor_pose", contacts=CONTACTS)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        result = await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2})],
                                final="El RMSD de Vina entre ambas es un intervalo de confianza de 2,251 a 4,259 Å.")
    assert "Vina da las cotas de la pose 2 contra su mejor pose, la 1" in result["text"]
    assert "Son cotas, no un intervalo de confianza" in result["text"]


@pytest.mark.asyncio
async def test_a_failed_comparison_adds_no_verdict_it_does_not_have(tmp_path, monkeypatch):
    async with Chat(tmp_path, monkeypatch, FakeMolDesign(comparison_status=409)) as chat:
        result = await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2})],
                                final="Todavía no hay resultado que comparar.")
    assert "Controles físicos según MolDesign" not in result["text"]


@pytest.mark.asyncio
async def test_arguments_outside_the_closed_schema_never_reach_moldesign(tmp_path, monkeypatch):
    fake = FakeMolDesign(contacts=CONTACTS)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 0, "right": 2})])
        await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 21})])
        await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2, "save": "si"})])
    assert not [c for c in fake.calls if "pose-comparison" in c.path or "interactions" in c.path]
