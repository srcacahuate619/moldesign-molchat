import copy
import json

import httpx
import pytest

from molchat_agent.bridge import MolDesignBridge
from molchat_agent.conversation.evidence import numeric_leaves, redact_unverified
from molchat_agent.conversation.explain_evaluation import (
    build_evaluation_facts,
    declared_limits,
    evidence_values,
    explain_evaluation_tool,
)

# Shapes follow backend/core/models.py::EvaluationResultRead and services/targets/calibracion.py.
# The values are synthetic, except that the verified receptor repeats the published CAL-D-01-R4-2 figures.
FORBIDDEN = {"receptor_path": "receptores/cuenta-privada/receptor.pdbqt", "poses_file_path": "poses/cuenta-privada/poses.sdf",
             "total_score": 61.2, "mmgbsa_score": -33.1, "docking_poses": [{"x": 1}], "smiles": "CCO",
             "gnn_attention_svg": "<svg/>"}

VERIFIED = {"task_id": "t-8t69", "status": "SUCCESS", "progress": 100, "result": {
    "molecule_id": "m-1", "affinity_kcal": -9.483, "vina_version": "1.2.7", "vina_random_seed": 42,
    "target_name": "VMAT2", "docking_protocol": {"engine": "vina", "exhaustiveness": 8, "num_poses": 9, "seed": 42},
    "target_calibracion": {
        "nivel": "calibrado", "resumen": "Calibrado para este receptor (Spearman ρ medido)", "advertencia": "", "motivo": "",
        "requiere_advertencia": False, "spearman_rho": 0.39,
        "respaldo": {"rho": 0.39, "ic95": [0.22, 0.54], "n": 89, "panel": "serie congenérica de la patente",
                     "endpoint": "Ki de [3H]DTBZ"}},
    "scientific_warnings": [{"codigo": "AGUAS_RETIRADAS", "severidad": "info", "mensaje": "Se retiraron todas las aguas del receptor."}],
    "protocolo": {"vigente": True, "diferencias": []}, **FORBIDDEN}}

NOT_CALIBRATED = {"task_id": "t-demo", "status": "SUCCESS", "progress": 100, "result": {
    "affinity_kcal": -7.2, "vina_version": "1.2.7", "vina_random_seed": 42, "target_name": "Demo",
    "docking_protocol": {"engine": "vina", "exhaustiveness": 8, "num_poses": 9},
    "target_calibracion": {
        "nivel": "curado_estructural", "resumen": "Curado estructuralmente; sin calibrar y sin pipeline de familia",
        "advertencia": "Este receptor no tiene Spearman ρ medido. Trata el resultado como una hipótesis a comprobar.",
        "motivo": "faltan Spearman ρ del receptor y stacking calibrado para su familia", "requiere_advertencia": True,
        "respaldo": None, "rho_registrada_sin_respaldo": 0.13},
    "scientific_warnings": [], "protocolo": {"vigente": False, "diferencias": ["receta_receptor"]}, **FORBIDDEN}}

LEGACY = {"task_id": "t-old", "status": "SUCCESS", "progress": 100, "result": {
    "affinity_kcal": -6.0, "scientific_warnings": ["aviso suelto de una corrida antigua"]}}


def facts_of(job):
    return build_evaluation_facts(job["task_id"], job)


def test_a_verified_receptor_is_explained_with_the_measure_that_backs_it():
    facts = facts_of(VERIFIED)
    assert facts["affinity"]["value"] == -9.483 and facts["affinity"]["unit"] == "kcal/mol"
    assert facts["affinity"]["condition"] == {"engine": "vina", "vina_version": "1.2.7", "exhaustiveness": 8,
                                              "num_poses": 9, "seed": 42, "receptor": "VMAT2"}
    assert "No es una energía libre, ni un Ki" in facts["affinity"]["limit"]
    backing = facts["calibration"]["backing"]
    assert backing["spearman_rho"] == 0.39 and backing["ci95"] == [0.22, 0.54] and backing["n"] == 89
    assert backing["ci_level_percent"] == 95 and backing["ci_excludes_zero"] is True
    assert "no predice el Ki de una molécula" in facts["calibration"]["reading"]
    assert facts["warnings"]["items"][0]["code"] == "AGUAS_RETIRADAS" and facts["protocol"]["comparable_with_today"] is True
    assert facts["absent"] == []


def test_a_receptor_without_backing_is_never_presented_as_calibrated():
    facts = facts_of(NOT_CALIBRATED)
    calibration = facts["calibration"]
    assert calibration["level"] == "curado_estructural" and calibration["backing"] is None
    assert "reading" not in calibration and "hipótesis a comprobar" in calibration["warning"]
    assert calibration["recorded_rho_without_backing"] == 0.13 and "No concede calibración" in calibration["recorded_rho_note"]
    assert facts["protocol"] == {"comparable_with_today": False, "differences": ["receta_receptor"]}


def test_an_interval_that_crosses_zero_is_flagged_by_the_code_not_by_the_model():
    job = copy.deepcopy(VERIFIED)
    job["result"]["target_calibracion"]["respaldo"].update({"rho": 0.13, "ic95": [-0.16, 0.41], "n": 57})
    backing = facts_of(job)["calibration"]["backing"]
    assert backing["ci_excludes_zero"] is False and backing["n"] == 57


def test_what_the_lock_did_not_declare_is_absent_never_good():
    facts = facts_of(LEGACY)
    assert facts["calibration"]["level"] is None and "ausente no significa calibrado" in facts["calibration"]["note"]
    assert facts["protocol"] is None and set(facts["absent"]) == {"target_calibracion", "protocolo"}
    assert facts["warnings"]["items"] == [{"code": None, "severity": "heredada", "message": "aviso suelto de una corrida antigua"}]
    assert "no la declara" in declared_limits(facts)


def test_only_allowed_fields_reach_the_model():
    # Control: the forbidden fields are in the input, so an empty result below means the allowlist works.
    assert all(key in VERIFIED["result"] for key in FORBIDDEN)
    dumped = json.dumps(facts_of(VERIFIED), ensure_ascii=False)
    for secret in ("cuenta-privada", "receptor.pdbqt", "poses.sdf", "61.2", "33.1", "<svg", "CCO", "docking_poses", "total_score", "mmgbsa"):
        assert secret not in dumped


@pytest.mark.parametrize("job, expected", [
    ({"task_id": "t-1", "status": "STARTED", "progress": 40, "result": None}, "STARTED"),
    ({"task_id": "t-1", "status": "FAILURE", "progress": 10, "error": "vina murió", "result": None}, "FAILURE"),
    ({"task_id": "t-1", "status": "SUCCESS", "result": None}, "SUCCESS"),
])
def test_a_run_without_result_has_nothing_to_explain(job, expected):
    facts = facts_of(job)
    assert facts["status"] == "not_ready" and facts["task_status"] == expected
    assert "affinity" not in facts and "calibration" not in facts


def test_declared_limits_carry_the_locks_own_warning_after_the_models_text():
    text = declared_limits(facts_of(NOT_CALIBRATED))
    assert text.startswith("Calibración declarada por MolDesign: Curado estructuralmente")
    assert "hipótesis a comprobar" in text
    assert declared_limits(facts_of(VERIFIED)) == "Calibración declarada por MolDesign: Calibrado para este receptor (Spearman ρ medido)."


def test_interface_rows_show_the_conditions_with_the_value():
    rows = evidence_values(facts_of(VERIFIED))
    assert rows["afinidad Vina (kcal/mol)"] == "-9.483" and rows["exhaustividad"] == "8" and rows["semilla"] == "42"
    assert rows["calibración"] == "calibrado" and rows["IC 95 %"] == "0.22 a 0.54" and rows["n"] == "89"
    assert rows["protocolo comparable con el vigente"] == "sí"


def test_a_spanish_explanation_survives_with_the_facts_and_a_made_up_number_does_not():
    facts = facts_of(VERIFIED)
    exact = numeric_leaves(facts)
    honest = ("Vina 1.2.7 dio −9,48 kcal/mol (exhaustividad 8, 9 poses, semilla 42). El receptor está calibrado: "
              "ρ = 0,39, IC 95 % 0,22–0,54, n = 89. Se retiraron todas las aguas.")
    assert redact_unverified(honest, set(), exact=exact)[1] == []
    made_up = honest + " La ρ sería 0,3 y el IC llegaría a 0,7."
    text, problems = redact_unverified(made_up, set(), exact=exact)
    assert len(problems) == 2 and text.count("[dato no verificado]") == 2


def tool_for(handler, token="test-account-token"):
    client = httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(handler))
    return explain_evaluation_tool(MolDesignBridge(client=client, token=token)), client


@pytest.mark.asyncio
async def test_the_tool_only_reads_with_the_accounts_session():
    seen = []
    async def host(request):
        seen.append(request)
        return httpx.Response(200, json=VERIFIED)
    tool, client = tool_for(host)
    async with client:
        facts = await tool.execute({"task_id": "t-8t69"})
    assert [(r.method, r.url.path) for r in seen] == [("GET", "/evaluation/status/t-8t69")]
    assert seen[0].headers["authorization"] == "Bearer test-account-token"
    assert facts["status"] == "ok" and facts["calibration"]["level"] == "calibrado"


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [403, 404])
async def test_a_foreign_or_unknown_run_is_not_found(code):
    async def host(_request):
        return httpx.Response(code)
    tool, client = tool_for(host)
    async with client:
        assert (await tool.execute({"task_id": "t-3"}))["status"] == "not_found"


@pytest.mark.asyncio
async def test_invalid_id_missing_session_and_mismatched_answer_abstain():
    calls = []
    async def host(request):
        calls.append(request)
        return httpx.Response(200, json={"task_id": "otra", "status": "SUCCESS"})
    tool, client = tool_for(host)
    async with client:
        assert (await tool.execute({"task_id": "../etc"}))["status"] == "invalid"
        assert not calls
        assert (await tool.execute({"task_id": "t-5"}))["status"] == "unavailable"
    tool, client = tool_for(host, token=None)
    async with client:
        assert (await tool.execute({"task_id": "t-6"}))["status"] == "unavailable"
