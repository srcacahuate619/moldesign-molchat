"""What MolDesign says about each run, and where each SMILES came from, reaches the notebook instead of being dropped."""
from __future__ import annotations

from typing import Any

from molchat_agent.workflows.iteration import IterationRunner, IterationSpec
from molchat_agent.workflows.notebook import build_notebook, comparability, render_markdown, render_pdf
from molchat_agent.workflows.run_record import MAX_FIELD_CHARS, molecule_source, record_from_result

from test_iteration import SCORES, Clock, FakeHost, FakePlatform, spec_dict


def result(seed: int = 42, **over: Any) -> dict[str, Any]:
    base = {
        "molecule_id": "m-1", "affinity_kcal": -9.1, "vina_version": "1.2.7", "receptor_sha256": "8fc027ca",
        "scientific_warnings": [{"codigo": "HUECO_JUNTO_AL_SITIO", "severidad": "revisar", "mensaje": "Hay un hueco a 6 Å."},
                                "aviso antiguo sin código"],
        "docking_protocol": {"engine": "vina", "exhaustiveness": 8, "num_poses": 9, "seed": seed, "conformers_generated": 1,
                             "execution_provenance": {"box_center": [1.0, 2.0, 3.0], "box_size": [30.0, 30.0, 30.0]}},
        "ligand_state": {"smiles_entrada": "CCO",
                         "protonacion": {"aplicada": True, "ph": 7.4, "alternativas": 2},
                         "tautomeria": {"aplicada": False, "alternativas": 1},
                         "estereoquimica": {"centros_sin_asignar": 0, "dobles_sin_asignar": 0, "smiles_3d_efectivo": "CC[OH]",
                                            "perdida_en_la_especie_acoplada": {"centros": 1, "dobles": 0}}},
    }
    base.update(over)
    return base


def test_the_run_record_copies_protocol_warnings_and_docked_species() -> None:
    run = record_from_result(result())
    assert run is not None
    assert run["protocol"] == {"engine": "vina", "exhaustiveness": 8, "num_poses": 9, "seed": 42, "conformers": 1,
                               "requested": None, "box_center": [1.0, 2.0, 3.0], "box_size": [30.0, 30.0, 30.0]}
    assert run["warnings"] == [{"code": "HUECO_JUNTO_AL_SITIO", "severity": "revisar", "message": "Hay un hueco a 6 Å."},
                               {"code": None, "severity": "heredada", "message": "aviso antiguo sin código"}]
    assert run["species"]["input_smiles"] == "CCO" and run["species"]["docked_smiles_3d"] == "CC[OH]"
    assert run["species"]["stereo"]["lost_in_docked_species"] == {"centros": 1, "dobles": 0}


def test_what_the_run_did_not_persist_stays_unrecorded() -> None:
    run = record_from_result({"affinity_kcal": -7.0})
    assert run is not None
    assert run["protocol"] is None and run["warnings"] is None and run["species"] is None and run["vina_version"] is None
    assert record_from_result(None) is None


def test_a_huge_field_is_replaced_by_its_size_and_hash_not_cut() -> None:
    run = record_from_result(result(ligand_state={"smiles_entrada": "C" * (MAX_FIELD_CHARS + 10)}))
    assert run is not None
    assert "omitted" in run["raw"]["ligand_state"] and len(run["raw"]["ligand_state"]["sha256"]) == 64


LOOKUPS = [
    {"query": "etanol", "matches": [{"cid": 702, "name": "Ethanol", "source": "https://pubchem.ncbi.nlm.nih.gov/compound/702",
                                     "properties": {"SMILES": "CCO", "ConnectivitySMILES": "CCO"}}]},
    {"query": "tetrabenazina", "matches": [{"cid": 6018, "name": "Tetrabenazine", "source": "https://x/6018",
                                            "properties": {"SMILES": "C[C@H]1CN", "ConnectivitySMILES": "CC1CN"}}]},
]


def test_the_source_is_the_pubchem_lookup_whose_smiles_matches_literally() -> None:
    exact = molecule_source("CCO", LOOKUPS)
    assert exact is not None and exact["cid"] == 702 and exact["match"] == "exact" and exact["query"] == "etanol"
    flat = molecule_source("CC1CN", LOOKUPS)
    assert flat is not None and flat["cid"] == 6018 and flat["match"] == "connectivity_only"
    assert molecule_source("CCN", LOOKUPS) is None


def test_two_compounds_with_the_same_smiles_are_ambiguous() -> None:
    twice = LOOKUPS + [{"query": "alcohol", "matches": [{"cid": 9999, "name": "otro", "properties": {"SMILES": "CCO"}}]}]
    assert molecule_source("CCO", twice) == {"database": "PubChem", "match": "ambiguous", "cids": [702, 9999]}


async def test_the_loop_keeps_the_record_and_the_source_of_each_molecule() -> None:
    class RichPlatform(FakePlatform):
        async def job(self, task_id: str) -> dict[str, Any]:
            job = await super().job(task_id)
            job["result"] = {**result(), **job["result"]}
            return job

    spec = IterationSpec.from_dict(spec_dict(stop="all"))
    events: list[dict[str, Any]] = []
    clock = Clock()
    out = await IterationRunner(spec, FakeHost(), RichPlatform(SCORES), events.append, clock=clock, sleep=clock.sleep,
                                poll_s=1.0, busy_wait_s=1.0,
                                sources=[molecule_source(m.smiles, LOOKUPS) for m in spec.molecules]).run()
    first = out.records[0]
    assert first.source is not None and first.source["cid"] == 702
    assert out.records[1].source is None
    assert first.run is not None and first.run["warnings"][0]["code"] == "HUECO_JUNTO_AL_SITIO"
    shown = next(e["record"] for e in events if e.get("event") == "molecule")
    assert "raw" not in shown["run"] and "raw" in first.run  # the card gets the summary, the notebook the full copy


async def test_the_notebook_says_where_each_smiles_came_from_and_what_each_run_recorded() -> None:
    class RichPlatform(FakePlatform):
        async def job(self, task_id: str) -> dict[str, Any]:
            job = await super().job(task_id)
            seed = 7 if task_id.endswith("CCC") else 42
            job["result"] = {**result(seed=seed), **job["result"]}
            return job

    spec = IterationSpec.from_dict(spec_dict(stop="all"))
    clock = Clock()
    out = await IterationRunner(spec, FakeHost(), RichPlatform(SCORES), clock=clock, sleep=clock.sleep, poll_s=1.0, busy_wait_s=1.0,
                                sources=[molecule_source(m.smiles, LOOKUPS) for m in spec.molecules]).run()
    nb = build_notebook(out, approved_at="2026-11-03T10:00:00+00:00", finished_at="2026-11-03T10:30:00+00:00")
    assert nb["versions"] == {"vina": "1.2.7"}
    assert {"field": "semilla", "values": [42, 7]} in nb["comparability"]["different"]
    md = render_markdown(nb)
    assert "Procedencia: PubChem CID 702 («Ethanol», búsqueda «etanol»); el SMILES coincide con el de PubChem." in md
    assert "Procedencia: no registrada" in md
    assert "Avisos de la corrida (2):" in md and "[revisar] Hay un hueco a 6 Å. (HUECO_JUNTO_AL_SITIO)" in md
    assert "Distinto entre corridas: semilla (42 / 7)" in md
    assert "La especie acoplada perdió estereoquímica escrita: 1 centro y 0 dobles enlaces" in md
    assert render_pdf(nb) is None or render_pdf(nb)[:4] == b"%PDF"


def test_a_field_missing_in_one_run_is_not_counted_as_equal() -> None:
    a, b = record_from_result(result()), record_from_result({"affinity_kcal": -7.0, "vina_version": "1.2.7"})
    c = comparability([a, b])  # type: ignore[list-item]
    assert {"field": "versión de Vina", "value": "1.2.7"} in c["same"]
    assert "exhaustividad" in c["not_recorded"] and "receptor preparado" in c["not_recorded"]
