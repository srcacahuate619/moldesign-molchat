"""A method explanation needs a calculation that reproduces the other source; without one, it says so."""
import pytest

from molchat_agent.conversation.property_methods import property_difference_notes
from molchat_agent.conversation.tools import clean_variants

TPSA = {"name": "tpsa_incl_s_p", "applies_to": "tpsa", "value": 57.78, "method": "RDKit CalcTPSA(includeSandP=True)", "unit": "Å²"}
HBA = {"name": "hba_rdkit_num_h_acceptors", "applies_to": "hba", "value": 4, "method": "RDKit CalcNumHBA", "unit": None}
METHODS = {"tpsa": "RDKit CalcTPSA con includeSandP=False", "hba": "RDKit Lipinski.NOCount"}


def notes(reference, props, variants=(TPSA, HBA)):
    return property_difference_notes(reference, props, METHODS, list(variants))


def test_clopidogrel_tpsa_and_hba_are_explained_by_the_calculation_that_lands_on_pubchems_figure():
    found = {note["property"]: note for note in notes({"TPSA": 57.8, "HBondAcceptorCount": 4}, {"tpsa": 29.54, "hba": 3})}
    assert set(found) == {"tpsa", "hba"}
    assert found["tpsa"]["reproduces_pubchem"] is True and found["tpsa"]["variant_value"] == 57.78
    assert found["tpsa"]["text"].startswith("TPSA: PubChem da 57.8 Å² y MolDesign 29.54 Å².")
    assert "el mismo RDKit da 57.78 Å², que coincide con PubChem" in found["tpsa"]["text"]
    assert found["hba"]["text"].startswith("Aceptores de enlace de hidrógeno: PubChem da 4 y MolDesign 3.")
    assert "RDKit Lipinski.NOCount" in found["hba"]["text"] and "RDKit CalcNumHBA" in found["hba"]["text"]


def test_a_variant_that_does_not_land_on_pubchems_figure_is_reported_as_not_explaining_it():
    (note,) = notes({"TPSA": 57.8}, {"tpsa": 29.54}, [{**TPSA, "value": 40.0}])
    assert note["reproduces_pubchem"] is False
    assert "tampoco coincide con PubChem" in note["text"] and "no queda explicada" in note["text"]
    assert "No son cifras contradictorias" not in note["text"]


@pytest.mark.parametrize("variant_value,reproduces", [(57.75, True), (57.84, True), (57.85, False), (57.74, False)])
def test_a_variant_reproduces_pubchem_when_it_rounds_to_the_figure_pubchem_prints(variant_value, reproduces):
    (note,) = notes({"TPSA": 57.8}, {"tpsa": 29.54}, [{**TPSA, "value": variant_value}])
    assert note["reproduces_pubchem"] is reproduces


def test_counts_must_be_equal_to_reproduce():
    (note,) = notes({"HBondAcceptorCount": 5}, {"hba": 3}, [HBA])
    assert note["reproduces_pubchem"] is False


@pytest.mark.parametrize("reference,props,variants", [
    ({"TPSA": 57.8}, {"tpsa": 57.8}, [TPSA]),                       # they agree
    ({"TPSA": 57.8}, {"tpsa": 57.82}, [TPSA]),                      # within what PubChem prints
    ({"TPSA": 57.8}, {"tpsa": 29.54}, []),                          # no variant: nothing to prove it with
    ({"TPSA": 57.8}, {"tpsa": 29.54}, [{**TPSA, "applies_to": "logp"}]),  # a variant of another descriptor
    ({}, {"tpsa": 29.54}, [TPSA]),                                  # PubChem did not publish it
    (None, {"tpsa": 29.54}, [TPSA]),
    ({"TPSA": "n/a"}, {"tpsa": 29.54}, [TPSA]),
    ({"TPSA": True}, {"tpsa": 29.54}, [TPSA]),
    ({"TPSA": 57.8}, {"tpsa": None}, [TPSA]),
    ({"XLogP": 3.5}, {"logp": 3.76}, [TPSA]),                       # LogP/XLogP are not this module's business
])
def test_no_note_is_written_without_a_difference_and_a_variant_for_that_descriptor(reference, props, variants):
    assert notes(reference, props, variants) == []


def test_pubchem_values_arrive_as_text_or_numbers():
    (note,) = notes({"TPSA": "57.8"}, {"tpsa": 29.54}, [TPSA])
    assert note["pubchem"] == 57.8 and note["reproduces_pubchem"] is True


def test_a_missing_method_string_does_not_break_the_sentence():
    (note,) = property_difference_notes({"TPSA": 57.8}, {"tpsa": 29.54}, {}, [TPSA])
    assert "su definición del producto" in note["text"]


@pytest.mark.parametrize("raw,expected", [
    (None, []), ("x", []), ({}, []), ([None, 3, "x"], []),
    ([{"name": "a", "applies_to": "tpsa", "value": True, "method": "m"}], []),          # a boolean is not a number
    ([{"name": "a", "applies_to": "tpsa", "value": float("nan"), "method": "m"}], []),
    ([{"name": "a", "applies_to": "tpsa", "value": 1, "method": ""}], []),
    ([{"name": "a" * 61, "applies_to": "tpsa", "value": 1, "method": "m"}], []),
    ([{"name": "a", "applies_to": "tpsa", "value": 1, "method": "m", "unit": 3}], []),
    ([{"name": "a", "applies_to": "tpsa", "value": 1, "method": "m", "extra": "no"}],
     [{"name": "a", "applies_to": "tpsa", "value": 1, "method": "m", "unit": None}]),    # only the allowlist survives
])
def test_a_malformed_variant_is_dropped_never_repaired(raw, expected):
    assert clean_variants(raw) == expected


def test_a_good_variant_survives_next_to_a_bad_one():
    good = {"name": "a", "applies_to": "tpsa", "value": 1.5, "method": "m", "unit": "Å²"}
    assert clean_variants([{"name": "b", "value": 1}, good]) == [good]
