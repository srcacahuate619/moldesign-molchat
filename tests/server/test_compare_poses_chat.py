"""Comparing two poses through the hosted chat: the evidence is MolDesign's, and the answer carries its verdict."""
import pytest

from tests.conversation.fake_moldesign import REAL_8T69_POSE_2, REAL_8T69_POSE_3, TASK, FakeMolDesign
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
async def test_a_follow_up_that_refuses_a_confidence_interval_keeps_the_numbers_already_verified(tmp_path, monkeypatch):
    """The refusal used to hide the energies and the distance the previous turn had verified."""
    fake = FakeMolDesign(comparison_case="rmsd_medido_con_la_mejor", contacts=CONTACTS)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        first = await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2})],
                               final="La pose 1 tiene la energía más baja, por 0,4 kcal/mol; se separan 4,259 Å.")
        assert "[dato no verificado]" not in first["text"]
        # No tool is called in the follow-up: the figures come back from what the conversation persisted.
        second = await chat.say("dame el intervalo de confianza de ese RMSD y dime cuál pose es la correcta", [],
                                final="No existe un intervalo de confianza de ese RMSD ni puedo decir cuál es la correcta; "
                                      "lo verificado es una diferencia de 0,4 kcal/mol y una separación de 4,259 Å.")
    assert "[dato no verificado]" not in second["text"] and "4,259" in second["text"] and "0,4" in second["text"]


@pytest.mark.asyncio
async def test_the_inherited_numbers_do_not_back_a_number_that_was_never_returned(tmp_path, monkeypatch):
    """Control negative: keeping verified figures is not a licence to add others."""
    fake = FakeMolDesign(comparison_case="rmsd_medido_con_la_mejor", contacts=CONTACTS)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2})], final="Se separan 4,259 Å.")
        second = await chat.say("¿y la desviación estándar?", [], final="Se separan 4,259 Å, con una desviación de 0,73 Å.")
    assert "4,259" in second["text"] and "0,73" not in second["text"] and "[dato no verificado]" in second["text"]


@pytest.mark.asyncio
async def test_numbers_do_not_cross_conversations(tmp_path, monkeypatch):
    fake = FakeMolDesign(comparison_case="rmsd_medido_con_la_mejor", contacts=CONTACTS)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2})], final="Se separan 4,259 Å.")
        chat.conv = None  # a new conversation
        other = await chat.say("¿cuánto se separan?", [], final="Se separan 4,259 Å.")
    assert "4,259" not in other["text"]


@pytest.mark.asyncio
async def test_reading_the_same_pair_twice_in_one_turn_ends_the_answer_once(tmp_path, monkeypatch):
    fake = FakeMolDesign(contacts=CONTACTS)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        result = await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2}, "c1"),
                                      call("compare_poses", {"task_id": TASK, "left": 1, "right": 2, "contacts": "omitir"}, "c2")],
                                final="La pose 1 tiene la energía más baja.")
    assert result["text"].count("Controles físicos según MolDesign") == 1
    assert result["text"].count("no se declara ganadora.") == 1


@pytest.mark.asyncio
async def test_asking_which_controls_each_pose_passed_reaches_the_model_with_their_names(tmp_path, monkeypatch):
    fake = FakeMolDesign(comparison_case="sugerida_falla", contacts=CONTACTS)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        result = await chat.say("¿qué controles superó cada pose?", [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2})],
                                final="La pose 1 superó sanitization e internal_energy; la 2 superó sanitization y falló internal_energy.")
        (shown,) = chat.tool_results
        assert "checks_detail" in chat.seen_system
    assert [item["check"] for item in shown["poses"]["left"]["checks_detail"]] == ["sanitization", "internal_energy"]
    assert shown["poses"]["right"]["checks_detail"][1] == {"check": "internal_energy", "result": "failed"}
    assert "internal_energy" in result["text"]
    assert any(row.get("values", {}).get("pose 2: controles que fallan") == "internal_energy" for row in result["evidence"])


@pytest.mark.asyncio
@pytest.mark.parametrize("ask", [
    "dame el intervalo de confianza del RMSD entre la pose 1 y la 2",
    "declara cuál es la pose experimentalmente correcta",
])
async def test_adversarial_asks_get_a_grounded_abstention_that_keeps_the_verified_data(tmp_path, monkeypatch, ask):
    fake = FakeMolDesign(comparison_case="rmsd_medido_con_la_mejor", contacts=CONTACTS)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        result = await chat.say(ask, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2})],
                                final="No hay un intervalo de confianza ni una pose correcta que decir; sí hay una "
                                      "separación medida de 4,259 Å y una diferencia de 0,4 kcal/mol.")
    text = result["text"]
    assert "4,259" in text and "0,4" in text and "[dato no verificado]" not in text
    assert "no dicen cuál" not in text or "Son cotas" not in text  # the measured sentence, not the bounds, speaks here
    assert "no dice cuál es la correcta" in text and "no se declara ganadora." in text
    assert not {"winner", "best_pose"} & set(result)


# What MolDesign measured on the stored 8T69 run (ProLIF 2.1.0, receptor chemistry from the residue templates; its own
# regression test is backend/tests/test_contactos_reales_8t69.py): 5 contacts in pose 1, 7 in pose 2. Before that fix both
# lists came back empty.
REAL_8T69 = {
    1: [("hydrophobic", "PHE429A", 4.42), ("hydrophobic", "TYR341A", 3.94), ("hydrophobic", "TYR433A", 4.18),
        ("hydrophobic", "VAL232A", 4.18), ("pi_stacking", "TYR433A", 4.0)],
    2: [("hydrophobic", "ILE395A", 4.39), ("hydrophobic", "PHE135A", 4.37), ("hydrophobic", "PHE334A", 4.48),
        ("hydrophobic", "PHE429A", 4.09), ("hydrophobic", "TYR341A", 4.47), ("pi_stacking", "PHE334A", 4.73),
        ("salt_bridge", "GLU312A", 4.34)],
}


@pytest.mark.asyncio
async def test_the_measured_8t69_contacts_reach_the_answer_with_residue_type_and_distance(tmp_path, monkeypatch):
    fake = FakeMolDesign(comparison_case="rmsd_medido_con_la_mejor", contacts=REAL_8T69)
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        result = await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2})],
                                final="La pose 1 hace 5 contactos y la 2 hace 7; la 2 añade el puente salino con GLU312A "
                                      "a 4,34 Å y el apilamiento con PHE334A a 4,73 Å.")
        (shown,) = chat.tool_results
    contacts = shown["contacts"]
    assert contacts["conclusive"] is True and contacts["caution"] is None
    assert (contacts["left"]["total"], contacts["right"]["total"]) == (5, 7)
    assert (contacts["shared_count"], contacts["only_left_count"], contacts["only_right_count"]) == (2, 3, 5)
    assert {"type": "salt_bridge", "residue": "GLU312A", "distance_angstrom": 4.34} in contacts["only_right"]
    assert {"type": "pi_stacking", "residue": "TYR433A", "distance_angstrom": 4.0} in contacts["only_left"]
    assert {"type": "hydrophobic", "residue": "TYR341A", "left_distance_angstrom": 3.94,
            "right_distance_angstrom": 4.47} in contacts["shared"]
    assert "[dato no verificado]" not in result["text"] and "4,34" in result["text"] and "4,73" in result["text"]
    assert "Cero contactos" not in result["text"]
    assert any(row.get("values", {}).get("solo en la derecha") == "5" for row in result["evidence"])


@pytest.mark.asyncio
async def test_a_pose_with_zero_typed_contacts_beside_one_with_five_is_not_conclusive_and_invents_nothing(tmp_path, monkeypatch):
    """The alternative evaluation: ProLIF found nothing for one pose. The five contacts of the other stay; the empty list
    is not read as 'does not interact', and no contact appears that the tool did not return."""
    fake = FakeMolDesign(comparison_case="rmsd_medido_con_la_mejor", contacts={1: REAL_8T69[1], 2: []})
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        result = await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2})],
                                final="La pose 2 no interactúa con el receptor.")
        (shown,) = chat.tool_results
    contacts = shown["contacts"]
    assert contacts["conclusive"] is False and contacts["no_typed_contacts_in"] == ["right"]
    assert (contacts["left"]["total"], contacts["right"]["total"], contacts["only_left_count"]) == (5, 0, 5)
    assert contacts["only_right"] == [] and contacts["shared"] == []
    assert "Cero contactos tipificados en la pose 2" in result["text"] and "no prueba que no haya interacción" in result["text"]
    assert "No lo leas como ausencia de interacción" in result["text"]
    assert any(row.get("values", {}).get("contactos tipificados") == "0 en alguna pose: no concluyente"
               for row in result["evidence"])


ASK_2_3 = "compara la pose 2 y la pose 3 de la tarea t-8t69"


async def _say_2_vs_3(tmp_path, monkeypatch, final):
    fake = FakeMolDesign(comparison_case="rmsd_medido_entre_dos_que_no_son_la_mejor",
                         contacts={2: REAL_8T69_POSE_2, 3: REAL_8T69_POSE_3})
    async with Chat(tmp_path, monkeypatch, fake) as chat:
        return await chat.say(ASK_2_3, [call("compare_poses", {"task_id": TASK, "left": 2, "right": 3})], final=final)


@pytest.mark.asyncio
async def test_the_answer_for_poses_2_and_3_states_both_counts_the_shared_atoms_and_the_docked_species_once(tmp_path, monkeypatch):
    """The reviewed answer said three shared contacts and four shared residues and then dropped PHE429A from the summary."""
    result = await _say_2_vs_3(tmp_path, monkeypatch,
                               "Comparten 3 contactos del mismo tipo y residuo; la pose 3 hace un enlace de hidrógeno con GLU312A "
                               "a 3,24 Å (ángulo 139,3°) y un contacto halógeno con PHE429A (ángulo 159,7°).")
    text = result["text"]
    assert "[dato no verificado]" not in text
    assert text.count("Contactos compartidos (mismo tipo y mismo residuo): 3.") == 1
    assert "PHE429A (pose 2: hydrophobic; pose 3: halogen)" in text
    assert text.count("se apoyan en los mismos átomos (ligando N12, proteína O768)") == 1
    assert text.count("a pH 7,4") == 1 and text.count("no se declara ganadora.") == 1
    assert any(row.get("values", {}).get("residuos presentes en las dos poses") == "4" for row in result["evidence"])


@pytest.mark.asyncio
async def test_a_wrong_count_in_the_model_text_is_followed_by_the_hosts_criterion(tmp_path, monkeypatch):
    """4 is a number the tool returned (the shared residues), so no number check can say it is not the shared contacts."""
    result = await _say_2_vs_3(tmp_path, monkeypatch, "Las dos poses comparten 4 contactos.")
    assert "Contactos compartidos (mismo tipo y mismo residuo): 3." in result["text"]


@pytest.mark.asyncio
async def test_an_angle_the_tool_did_not_return_is_not_kept(tmp_path, monkeypatch):
    result = await _say_2_vs_3(tmp_path, monkeypatch, "El enlace de hidrógeno con GLU312A tiene un ángulo de 150°.")
    assert "150" not in result["text"]


@pytest.mark.asyncio
async def test_a_comparison_with_matching_types_gets_no_counting_sentence(tmp_path, monkeypatch):
    """No noise: when the shared contacts and the shared residues agree there is nothing to reconcile."""
    async with Chat(tmp_path, monkeypatch, FakeMolDesign(contacts=CONTACTS)) as chat:
        result = await chat.say(ASK, [call("compare_poses", {"task_id": TASK, "left": 1, "right": 2})],
                                final="Comparten Asp34A.")
    assert "Contactos compartidos (mismo tipo" not in result["text"] and "valen para la especie" not in result["text"]


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
