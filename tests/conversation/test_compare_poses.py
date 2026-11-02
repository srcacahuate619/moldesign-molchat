"""Compare two poses of a finished run: MolDesign's evidence, the contacts diffed in code, and no winner."""
import copy
import json

import httpx
import pytest

from molchat_agent.bridge import MolDesignBridge
from molchat_agent.conversation import compare_poses as cp

from tests.conversation.fake_moldesign import MOLECULE, TASK, FakeMolDesign, comparison_fixture

TOKEN = "test-account-token"

LEFT = [("hbond", "ASP34A", 2.91), ("hydrophobic", "LEU12A", 3.8), ("hydrophobic", "PHE80A", 3.6), ("pi_stacking", "TYR41A", 4.4)]
RIGHT = [("hbond", "ASP34A", 3.05), ("hydrophobic", "LEU12A", 3.7), ("hbond", "SER90A", 2.8), ("hydrophobic", "VAL15A", 3.9)]


def bridge_for(fake=None, handler=None, token=TOKEN):
    fake = fake or FakeMolDesign()
    client = httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(handler or fake.handler))
    return MolDesignBridge(client=client, token=token), client, fake


async def compare(fake=None, handler=None, token=TOKEN, **args):
    bridge, client, fake = bridge_for(fake, handler, token)
    try:
        result = await cp.compare_poses_tool(bridge).execute({"task_id": TASK, "left": 1, "right": 2, **args})
    finally:
        await client.aclose()
    return result, fake


def reads(fake):
    return [(call.path, call.params) for call in fake.calls]


# ── The energy and the physical checks come from the lock, never from the model ────────────────────

@pytest.mark.asyncio
async def test_two_poses_that_pass_are_compared_with_their_energies_and_contacts():
    fake = FakeMolDesign(contacts={1: LEFT, 2: RIGHT})
    result, fake = await compare(fake)
    assert result["status"] == "ok" and result["source"] == "MolDesign GET /evaluation/pose-comparison"
    left, right = result["poses"]["left"], result["poses"]["right"]
    assert (left["rank"], left["vina_affinity_kcal_mol"], right["rank"], right["vina_affinity_kcal_mol"]) == (1, -8.3, 2, -7.9)
    difference = dict(result["difference"])
    rmsd = difference.pop("vina_rmsd_between_poses")
    assert difference == {"right_minus_left_vina_kcal_mol": 0.4, "lower_vina_energy": 1,
                          "physical_agreement": "both_passed", "within_near_tie": True,
                          "near_tie_threshold_kcal_mol": 1}
    assert rmsd["available"] is False and rmsd["reason_code"] == "ENGINE_NOT_DECLARED"
    assert right["selector_score"] == 0.52 and right["is_suggested"] is True and left["is_vina_top1"] is True
    assert result["selector"]["status"] == "selected" and result["next_step"] == "proceed_within_protocol"
    assert fake.writes() == []  # reading only
    assert (f"/evaluation/pose-comparison/{TASK}", {"left": "1", "right": "2"}) in reads(fake)


@pytest.mark.asyncio
async def test_no_winner_is_named_when_the_selector_suggests_a_pose_that_did_not_pass():
    result, _ = await compare(FakeMolDesign(comparison_case="sugerida_falla", contacts={1: LEFT, 2: RIGHT}))
    right = result["poses"]["right"]
    assert (right["physical_status"], right["physically_valid"], right["failing_checks"]) == ("failed", False, ["internal_energy"])
    assert result["difference"]["physical_agreement"] == "only_left_passed"
    assert result["next_step"] == "review" and result["alternatives"] == [1, 3]
    codes = {item["code"] for item in result["uncertainties"]}
    assert {"suggested_pose_not_passed", "selection_diverges"} <= codes
    assert all(item["meaning"] for item in result["uncertainties"])
    # The energy difference says which pose Vina scored lower; nothing says which pose is better.
    assert not {"winner", "best_pose", "preferred", "recommended_pose"} & (set(result) | set(result["difference"]))


@pytest.mark.asyncio
async def test_a_run_without_physical_checks_does_not_make_its_poses_valid():
    result, _ = await compare(FakeMolDesign(comparison_case="corrida_anterior", contacts={1: LEFT, 2: RIGHT}))
    assert result["legacy_run"] is True
    for side in ("left", "right"):
        assert result["poses"][side]["physical_status"] == "not_evaluated"
        assert result["poses"][side]["physically_valid"] is False
        assert result["poses"][side]["checks_passed"] is None
    assert result["difference"]["physical_agreement"] == "neither_passed"
    assert "no_physical_validation" in {item["code"] for item in result["uncertainties"]}
    assert "no tiene controles físicos evaluados" in cp.comparison_limits(result)


@pytest.mark.asyncio
async def test_a_pose_in_review_or_unevaluated_is_never_called_valid_even_if_the_flag_says_so():
    class Liar(FakeMolDesign):
        def handler(self, request):
            response = super().handler(request)
            if request.url.path.startswith("/evaluation/pose-comparison/"):
                data = response.json()
                data["right"].update(physical_status="review", physically_valid=True)
                return httpx.Response(200, json=data)
            return response

    result, _ = await compare(Liar(comparison_case="todas_pasan"), contacts="omitir")
    assert result["poses"]["right"]["physical_status"] == "review"
    assert result["poses"]["right"]["physically_valid"] is False
    assert "quedó en revisión (no cuenta como válida)" in cp.comparison_limits(result)


@pytest.mark.asyncio
async def test_a_partly_covered_run_keeps_the_pose_without_checks_unevaluated():
    result, _ = await compare(FakeMolDesign(comparison_case="cobertura_parcial", contacts={1: LEFT, 3: RIGHT}), right=3)
    assert result["poses"]["right"]["physical_status"] == "not_evaluated"
    assert result["poses"]["right"]["physically_valid"] is False
    assert "partial_coverage" in {item["code"] for item in result["uncertainties"]}


@pytest.mark.asyncio
async def test_a_pose_the_run_does_not_have_invents_neither_differences_nor_contacts():
    fake = FakeMolDesign(comparison_case="pose_inexistente", contacts={1: LEFT})
    result, fake = await compare(fake, right=7)
    assert result["poses"]["right"] == {"rank": 7, "found": False}
    assert result["difference"]["right_minus_left_vina_kcal_mol"] is None
    assert result["difference"]["physical_agreement"] == "unavailable"
    assert result["contacts"]["status"] == "unavailable"
    assert not [path for path, _ in reads(fake) if path.startswith("/evaluation/interactions/")]
    assert "la corrida no la tiene" in cp.comparison_limits(result)


# ── Vina's RMSD bounds are against ITS best pose: they describe a pair only when one of the two is that pose ──

@pytest.mark.asyncio
async def test_the_rmsd_bounds_describe_the_pair_when_one_pose_is_vinas_best():
    """The case of the real 8T69 run: pose 1 is the best (RMSD 0) and pose 2 carries 2.251 / 4.259 Å."""
    result, _ = await compare(FakeMolDesign(comparison_case="rmsd_de_la_mejor_pose", contacts={1: LEFT, 2: RIGHT}))
    rmsd = result["difference"]["vina_rmsd_between_poses"]
    assert (rmsd["available"], rmsd["reference_rank"], rmsd["other_rank"]) == (True, 1, 2)
    assert (rmsd["lower_bound_angstrom"], rmsd["upper_bound_angstrom"]) == (2.251, 4.259)
    # They are bounds, not a confidence interval, and they do not say which pose is the right one.
    assert "no un intervalo de confianza" in rmsd["meaning"] and "cuál de las dos poses es la correcta" in rmsd["meaning"]
    assert rmsd["meaning"] in result["reading_rules"]
    assert not any("no una distancia entre estas dos poses" in rule for rule in result["reading_rules"])


@pytest.mark.asyncio
async def test_two_poses_that_are_not_the_best_have_no_rmsd_between_them():
    result, _ = await compare(FakeMolDesign(comparison_case="rmsd_entre_dos_que_no_son_la_mejor", contacts={2: LEFT, 3: RIGHT}),
                              left=2, right=3)
    rmsd = result["difference"]["vina_rmsd_between_poses"]
    assert rmsd["available"] is False and rmsd["reason_code"] == "NEITHER_IS_VINA_BEST"
    assert "lower_bound_angstrom" not in rmsd and "upper_bound_angstrom" not in rmsd
    assert "ninguna de las dos es la mejor pose de Vina" in rmsd["meaning"] and rmsd["meaning"] in result["reading_rules"]
    # The per-pose bounds stay what they are: against Vina's best pose.
    assert result["poses"]["left"]["vina_rmsd_lb_vs_best"] == 2.251 and result["poses"]["right"]["vina_rmsd_lb_vs_best"] == 2.1


@pytest.mark.asyncio
@pytest.mark.parametrize("claim", [
    {"available": True, "reference_rank": 1, "other_rank": 2, "lower_bound_angstrom": "2.2", "upper_bound_angstrom": 4.2},
    {"available": True, "reference_rank": 1, "other_rank": 2, "lower_bound_angstrom": None, "upper_bound_angstrom": 4.2},
    {"available": True, "reference_rank": True, "other_rank": 2, "lower_bound_angstrom": 2.2, "upper_bound_angstrom": 4.2},
    {"available": "yes", "reference_rank": 1, "other_rank": 2, "lower_bound_angstrom": 2.2, "upper_bound_angstrom": 4.2},
    {"available": True, "reference_rank": 1, "other_rank": 2, "lower_bound_angstrom": float("inf"), "upper_bound_angstrom": 4.2},
    "available", None,
])
async def test_a_malformed_rmsd_claim_never_becomes_a_distance(claim):
    class Sloppy(FakeMolDesign):
        def handler(self, request):
            response = super().handler(request)
            if request.url.path.startswith("/evaluation/pose-comparison/"):
                data = response.json()
                data["difference"]["vina_rmsd_between_poses"] = claim
                return httpx.Response(200, content=json.dumps(data).encode(), headers={"content-type": "application/json"})
            return response

    result, _ = await compare(Sloppy(comparison_case="rmsd_de_la_mejor_pose", contacts={1: LEFT, 2: RIGHT}))
    rmsd = result["difference"]["vina_rmsd_between_poses"]
    assert rmsd["available"] is False and "lower_bound_angstrom" not in rmsd
    assert rmsd["meaning"].startswith("No hay un RMSD de Vina entre estas dos poses")


# ── The contacts are subtracted in code ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_the_contacts_two_poses_share_and_the_ones_only_one_has_are_computed_here():
    fake = FakeMolDesign(contacts={1: LEFT, 2: RIGHT})
    result, fake = await compare(fake)
    contacts = result["contacts"]
    assert contacts["status"] == "ok" and contacts["source"] == "MolDesign GET /evaluation/interactions"
    assert contacts["shared"] == [
        {"type": "hbond", "residue": "ASP34A", "left_distance_angstrom": 2.91, "right_distance_angstrom": 3.05},
        {"type": "hydrophobic", "residue": "LEU12A", "left_distance_angstrom": 3.8, "right_distance_angstrom": 3.7}]
    assert [(c["type"], c["residue"]) for c in contacts["only_left"]] == [("hydrophobic", "PHE80A"), ("pi_stacking", "TYR41A")]
    assert [(c["type"], c["residue"]) for c in contacts["only_right"]] == [("hbond", "SER90A"), ("hydrophobic", "VAL15A")]
    assert (contacts["shared_count"], contacts["only_left_count"], contacts["only_right_count"]) == (2, 2, 2)
    assert contacts["left"] == {"total": 4, "by_type": {"hbond": 1, "hydrophobic": 2, "pi_stacking": 1}}
    assert contacts["residues_in_both"] == ["ASP34A", "LEU12A"]
    assert contacts["residues_only_left"] == ["PHE80A", "TYR41A"] and contacts["residues_only_right"] == ["SER90A", "VAL15A"]
    assert contacts["conditions"] == {"engine": "prolif", "hydrogen_model": "rdkit_addhs",
                                      "contact_coverage": "first_match_per_type_and_residue",
                                      "receptor_chemistry": "standard_residue_templates",
                                      "pose_identity_verification": "stored_run_path_and_current_file_hash"}
    assert contacts["conclusive"] is True and contacts["caution"] is None and contacts["no_typed_contacts_in"] == []
    # One analysis per pose, asked for by the run's task and the rank, with the account's session.
    asked = [(params["pose_rank"], params["task_id"]) for path, params in reads(fake) if path == f"/evaluation/interactions/{MOLECULE}"]
    assert sorted(asked) == [("1", TASK), ("2", TASK)]
    assert {call.auth for call in fake.calls} == {f"Bearer {TOKEN}"}


def test_the_same_contact_listed_twice_keeps_the_closest_distance_and_counts_once():
    report = {"interactions": [{"type": "hydrophobic", "residue": "LEU12A", "distance": 4.2},
                               {"type": "hydrophobic", "residue": "LEU12A", "distance": 3.9},
                               {"type": "hydrophobic", "residue": "LEU12A", "distance": None}]}
    diff = cp.build_contact_diff(report, {"interactions": []})
    assert diff["left"]["total"] == 1 and diff["only_left"] == [{"type": "hydrophobic", "residue": "LEU12A", "distance_angstrom": 3.9}]


def test_a_long_list_is_cut_and_says_so():
    many = {"interactions": [{"type": "hydrophobic", "residue": f"ALA{n}A", "distance": 3.5} for n in range(40)]}
    diff = cp.build_contact_diff(many, {"interactions": []})
    assert diff["only_left_count"] == 40 and len(diff["only_left"]) == 20 and diff["truncated"] is True


@pytest.mark.parametrize("report", [None, {}, {"interactions": "x"}, {"interactions": None}])
def test_a_report_that_is_not_a_contact_list_is_not_read_as_no_contacts(report):
    assert cp.build_contact_diff(report, {"interactions": []})["status"] == "unavailable"
    assert cp.build_contact_diff({"interactions": []}, report)["status"] == "unavailable"


def test_a_contact_list_with_nothing_usable_is_an_empty_list_not_a_failure():
    junk = {"interactions": [None, 3, {"type": 1}, {"type": "hbond"}]}
    diff = cp.build_contact_diff(junk, junk)
    assert diff["status"] == "ok" and diff["left"]["total"] == 0 and diff["shared_count"] == 0


# ── A list with zero typed contacts is not a finding about the pose ───────────────────────────────

def _report(rank, contacts=(), engine="prolif:2.1.0", chemistry="standard_residue_templates"):
    return {"pose_rank": rank, "engine": engine, "receptor_chemistry": chemistry,
            "interactions": [{"type": kind, "residue": residue, "distance": distance} for kind, residue, distance in contacts]}


@pytest.mark.asyncio
async def test_zero_contacts_in_both_poses_is_declared_not_conclusive_and_the_host_says_so():
    result, _ = await compare(FakeMolDesign(contacts={1: [], 2: []}))
    contacts = result["contacts"]
    assert contacts["status"] == "ok" and contacts["conclusive"] is False
    assert contacts["no_typed_contacts_in"] == ["left", "right"] and contacts["shared_count"] == 0
    assert "Cero contactos tipificados en la pose 1, la pose 2" in contacts["caution"]
    assert "no prueba que no haya interacción" in contacts["caution"]
    limits = cp.comparison_limits(result)
    assert contacts["caution"] in limits and "comparación concluyente" in limits
    assert cp.evidence_values(result)["contactos tipificados"] == "0 en alguna pose: no concluyente"


def test_a_single_silent_pose_makes_the_comparison_not_conclusive_even_if_the_other_has_contacts():
    diff = cp.build_contact_diff(_report(1, [("hbond", "ASP34A", 2.9)]), _report(2))
    assert diff["conclusive"] is False and diff["no_typed_contacts_in"] == ["right"]
    assert "la pose 2" in diff["caution"] and "la pose 1" not in diff["caution"]
    assert diff["only_left_count"] == 1  # what was found is still reported; it is the silence that is not a finding


def test_two_poses_with_contacts_have_no_caution():
    diff = cp.build_contact_diff(_report(1, [("hbond", "ASP34A", 2.9)]), _report(2, [("hydrophobic", "LEU12A", 3.8)]))
    assert diff["conclusive"] is True and diff["caution"] is None and diff["no_typed_contacts_in"] == []


@pytest.mark.parametrize("engine,chemistry,expected", [
    ("prolif:2.1.0", "standard_residue_templates", "con la química estándar de los residuos del receptor"),
    ("prolif:2.1.0", "bonds_by_distance_only", "no percibió la aromaticidad ni las cargas del receptor"),
    ("prolif:2.1.0", "not_declared", "no percibió la aromaticidad ni las cargas del receptor"),
    ("prolif:2.1.0", None, "no percibió la aromaticidad ni las cargas del receptor"),
    ("distancias_sin_quimica", "not_declared", "respaldo por distancias"),
])
def test_the_caution_names_what_the_analysis_could_and_could_not_see(engine, chemistry, expected):
    diff = cp.build_contact_diff(_report(1, engine=engine, chemistry=chemistry), _report(2, engine=engine, chemistry=chemistry))
    assert expected in diff["caution"] and "no prueba que no haya interacción" in diff["caution"]


@pytest.mark.asyncio
async def test_if_one_pose_cannot_be_analysed_the_rest_of_the_comparison_still_stands():
    result, _ = await compare(FakeMolDesign(contacts={1: LEFT, 2: 422}))
    assert result["status"] == "ok" and result["difference"]["physical_agreement"] == "both_passed"
    assert result["contacts"]["status"] == "unavailable"
    assert "pose 2" in result["contacts"]["message"] and "sigue siendo válida" in result["contacts"]["message"]


@pytest.mark.asyncio
async def test_asking_only_for_energy_and_validity_does_not_run_the_contact_analysis():
    result, fake = await compare(FakeMolDesign(contacts={1: LEFT, 2: RIGHT}), contacts="omitir")
    assert result["contacts"]["status"] == "skipped"
    assert not [path for path, _ in reads(fake) if path.startswith("/evaluation/interactions/")]


# ── Refusals say what happened, and a foreign run is the same as an unknown one ────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("status,expected", [(409, "not_ready"), (404, "not_found"), (403, "not_found"),
                                             (422, "invalid"), (500, "unavailable")])
async def test_each_refusal_from_the_lock_becomes_an_honest_status(status, expected):
    result, _ = await compare(FakeMolDesign(comparison_status=status))
    assert result["status"] == expected and "poses" not in result


@pytest.mark.asyncio
async def test_an_unknown_task_is_not_found_and_leaks_nothing():
    result, fake = await compare(task_id="otra-tarea")
    assert result == {"status": "not_found", "task_id": "otra-tarea"}
    assert not [path for path, _ in reads(fake) if path.startswith("/evaluation/interactions/")]


@pytest.mark.asyncio
async def test_invalid_input_never_reaches_moldesign():
    for args in ({"task_id": "../etc"}, {"task_id": "a b"}, {"left": 2, "right": 2}):
        result, fake = await compare(**args)
        assert result["status"] == "invalid" and fake.calls == []
    result, fake = await compare(token=None)
    assert result["status"] == "unavailable" and fake.calls == []


@pytest.mark.asyncio
async def test_a_connection_error_is_unavailable_not_an_empty_comparison():
    def broken(_request):
        raise httpx.ConnectError("sin conexión")

    result, _ = await compare(handler=broken)
    assert result["status"] == "unavailable"


@pytest.mark.asyncio
async def test_a_comparison_for_another_task_is_not_trusted():
    class Swapped(FakeMolDesign):
        def handler(self, request):
            response = super().handler(request)
            if request.url.path.startswith("/evaluation/pose-comparison/"):
                return httpx.Response(200, json={**response.json(), "task_id": "otra"})
            return response

    result, _ = await compare(Swapped())
    assert result["status"] == "unavailable"


# ── Only what is on the allowlist reaches the model ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_field_moldesign_adds_later_does_not_reach_the_model():
    class Extra(FakeMolDesign):
        def handler(self, request):
            response = super().handler(request)
            if request.url.path.startswith("/evaluation/pose-comparison/"):
                data = copy.deepcopy(response.json())
                data["left"].update(source_file="run/poses.sdf", total_score=87.4)
                data.update(local_path="run/receptor.pdbqt", composite_score=91)
                return httpx.Response(200, json=data)
            return response

    result, _ = await compare(Extra(contacts={1: LEFT, 2: RIGHT}))
    flat = json.dumps(result)
    for leaked in ("run/poses.sdf", "run/receptor.pdbqt", "87.4", "composite_score", "total_score", MOLECULE):
        assert leaked not in flat


def test_the_fixtures_are_the_ones_moldesign_derives():
    # The fixture is generated by MolDesign's own derivation; if the shape changes there, this stops matching.
    for name in ("todas_pasan", "sugerida_falla", "cobertura_parcial", "corrida_anterior", "pose_inexistente"):
        data = comparison_fixture(name)
        assert {"left", "right", "difference", "selection", "decision", "stage", "legacy_run", "molecule_id"} <= set(data)
        facts = cp.build_comparison_facts(TASK, data)
        assert facts["status"] == "ok" and facts["reading_rules"]
