"""Rank and compare responders: metric semantics and name/value binding."""

import json
from pathlib import Path

import pytest

from molchat_agent.conversation.deterministic import (
    MoleculeProps,
    build_compare_response,
    build_druglikeness_response,
    build_multi_compare_response,
    build_properties_response,
    build_rank_response,
    build_session_history_response,
    detect_direction,
    detect_metric,
)

FIXTURES = Path(__file__).parent.parent / "quality" / "fixtures" / "properties.json"


def _mol(name: str) -> MoleculeProps:
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    for entry in data["molecules"]:
        if entry["name"] == name:
            props = entry["properties"]
            return MoleculeProps(
                name=name, smiles=entry["smiles"],
                molecular_weight=props["mw"], log_p=props["logp"],
                tpsa=props["tpsa"], hbd=props["hbd"], hba=props["hba"],
                rotatable_bonds=props["rot_bonds"],
                heavy_atoms=props["heavy_atoms"], rings=props["rings"])
    raise AssertionError(f"sin fixture: {name}")


@pytest.mark.parametrize("query, metric", [
    ("cual tiene menor peso molecular?", "molecular_weight"),
    ("cual es la mas lipofilica?", "log_p"),
    ("mayor TPSA", "tpsa"),
    ("mejor afinidad", "affinity_kcal"),
    ("top score", "total_score"),
    ("quien tiene mas puentes?", None),
])
def test_detect_metric(query, metric):
    assert detect_metric(query) == metric


@pytest.mark.parametrize("query, metric, direction", [
    ("cual tiene menor peso molecular?", "molecular_weight", "min"),
    ("cual tiene mayor peso molecular?", "molecular_weight", "max"),
    ("la mas pesada", "molecular_weight", "max"),
    # "mas liviana" matches bare "mas" (max) AND "mas liviana" (min):
    # natural "asc" wins, which lists lightest-first for MW. Same as internal.
    ("la mas liviana", "molecular_weight", "asc"),
    ("cual es la mas lipofilica?", "log_p", "max"),
    ("la menos lipofilica", "log_p", "min"),
    ("mejor afinidad", "affinity_kcal", "min"),  # more negative wins
    ("peor afinidad", "affinity_kcal", "max"),
    ("cual tiene mayor o menor peso?", "molecular_weight", "asc"),  # natural
    ("mejor score", "total_score", "max"),
])
def test_detect_direction(query, metric, direction):
    assert detect_direction(query, metric) == direction


def test_rank_picks_lightest_with_real_values():
    molecules = [_mol("aspirina"), _mol("ibuprofeno"), _mol("paracetamol")]
    text = build_rank_response("cual tiene menor peso molecular?", molecules)
    assert "**paracetamol**" in text
    assert "151.2 Da" in text


def test_rank_winner_follows_values_not_names():
    """The historic inversion bug: names and values must never cross."""
    swapped = [MoleculeProps(name="paracetamol", molecular_weight=206.3),
               MoleculeProps(name="aspirina", molecular_weight=151.2)]
    text = build_rank_response("cual tiene menor peso molecular?", swapped)
    assert "**aspirina**" in text
    assert "paracetamol** con 151.2" not in text


def test_rank_reports_full_ordering():
    molecules = [_mol("aspirina"), _mol("ibuprofeno"), _mol("paracetamol")]
    text = build_rank_response("cual tiene mayor peso molecular?", molecules)
    assert text.index("ibuprofeno") < text.index("aspirina") < text.index("paracetamol")


def test_rank_without_data_is_none_not_a_guess():
    assert build_rank_response("cual es mejor?", []) is None
    assert build_rank_response("quien tiene mas puentes?",
                               [_mol("aspirina")]) is None
    molecules = [MoleculeProps(name="x"), MoleculeProps(name="y")]
    assert build_rank_response("cual tiene menor peso?", molecules) is None


def test_compare_names_winner_per_metric():
    text = build_compare_response("aspirina", _mol("aspirina"),
                                  "ibuprofeno", _mol("ibuprofeno"))
    assert "Comparación entre aspirina y ibuprofeno:" in text
    assert "mayor en ibuprofeno (206.3 vs 180.2)" in text  # MW
    assert "mayor en ibuprofeno (3.07 vs 1.31)" in text  # LogP


def test_multi_compare_builds_typed_table():
    text = build_multi_compare_response(
        [_mol("aspirina"), _mol("ibuprofeno"), _mol("paracetamol")])
    assert "Métrica | aspirina | ibuprofeno | paracetamol" in text
    assert "MW | 180.2 | 206.3 | 151.2" in text


def test_multi_compare_refuses_partial_tables():
    molecules = [_mol("aspirina"), MoleculeProps(name="fallida")]
    assert build_multi_compare_response(molecules) is None


def test_properties_response_lists_values_with_precision():
    text = build_properties_response("aspirina", _mol("aspirina"))
    assert text.startswith("Propiedades de aspirina:")
    assert "- MW: 180.2" in text
    assert "- LogP: 1.31" in text
    assert "- H-Bond Donors: 1" in text
    assert build_properties_response("x", MoleculeProps(name="x")) is None


def test_session_history_lists_computed_and_declares_persisted_gap():
    text = build_session_history_response([_mol("aspirina"), _mol("etanol")])
    assert "2 moléculas" in text
    assert "1. aspirina (MW 180.2 Da)" in text
    assert "persistido" in text and "aún no está conectado" in text
    empty = build_session_history_response([])
    assert "aún no calculaste" in empty


def test_druglikeness_reports_rules_and_recorded_pains():
    text = build_druglikeness_response("aspirina", _mol("aspirina"), [])
    assert "Lipinski: CUMPLE" in text
    assert "Veber: CUMPLE" in text
    assert "PAINS (dato registrado): sin alertas." in text
    alerts = build_druglikeness_response("dopamina", _mol("dopamina"),
                                         ["catechol_A(92)"])
    assert "alertas: catechol_A(92)" in alerts
    abstained = build_druglikeness_response("aspirina", _mol("aspirina"), None)
    assert "no afirmo que no haya alertas" in abstained
    assert build_druglikeness_response("x", MoleculeProps(name="x"), []) is None
