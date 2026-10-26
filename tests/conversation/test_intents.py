"""Intent classifier spec: quality queries + internal regression cases."""

import pytest

from molchat_agent.conversation.intents import classify, smiles_plausible


@pytest.mark.parametrize("query, expected", [
    # B: properties of a known molecule
    ("calcula propiedades de la aspirina", "chemical"),
    ("propiedades del ibuprofeno", "chemical"),
    ("dame las propiedades fisicoquimicas del paracetamol", "chemical"),
    ("que propiedades tiene la cafeina?", "chemical"),
    ("MW y LogP de la morfina", "chemical"),
    ("CC(=O)Oc1ccccc1C(=O)O", "chemical"),
    ("cual es el peso molecular del etanol?", "chemical"),
    ("propiedades de la dopamina", "chemical"),
    ("que propiedades tiene la glucosa?", "chemical"),
    # C: pairwise comparison
    ("compará la aspirina con el ibuprofeno", "compare"),
    ("compara paracetamol vs ibuprofeno", "compare"),
    ("cual es la diferencia entre aspirina y paracetamol?", "compare"),
    ("comparar la cafeina con la morfina", "compare"),
    ("que molecula tiene mayor peso molecular, ibuprofeno o paracetamol?", "compare"),
    # K: conceptual, no tools
    ("qué es un fármaco?", "conceptual"),
    ("explica que es el docking molecular", "conceptual"),
    ("que son los SMILES?", "conceptual"),
    ("para qué sirve un modelo de scoring?", "conceptual"),
    ("que es la afinidad de union?", "conceptual"),
    # I: invalid / edges
    ("calcula propiedades de KILLMEnow", "invalid_smiles"),
    ("zzzzzzzz", "unknown"),  # lowercase: not even SMILES-shaped
    ("", "unknown"),
    ("CCCCCCCCCCCCCCCCCCCCCCCCCCCC", "chemical"),  # plausible alkane
    ("hola", "unknown"),
    ("que es 12345?", "conceptual"),
    # A: anaphora
    ("y del paracetamol?", "recall_anaphoric"),
    ("y la cafeina?", "recall_anaphoric"),
    ("esa primera molécula, qué es?", "recall_anaphoric"),
    # D: drug-likeness routes deterministically (ours, not via tool-loop)
    ("la aspirina cumple la regla de Lipinski?", "druglikeness"),
    ("verifica drug-likeness del paracetamol", "druglikeness"),
    ("chequea PAINS de la cafeina", "druglikeness"),
    # M: molgraph (honest deferral in Fase 2)
    ("que moleculas hay contra 5-HT1A?", "molgraph"),
    ("top 5 moleculas por score", "molgraph"),
    # R/L/V: session ranking (superlative, no names)
    ("cual tiene menor peso molecular?", "rank_session"),
    ("cual es la mas lipofilica?", "rank_session"),
    ("cual tiene mayor peso molecular?", "rank_session"),
    # H: history
    ("que evalué contra 7E2Y?", "query_history"),
    ("cuales son mis mejores evaluaciones?", "query_history"),
    ("que moleculas tengo en mi historial?", "query_history"),
    # Internal regression: preparation check (comprobacion_previa)
    ("¿por qué está bloqueado el receptor 8HFI?", "preparation"),
    ("¿está listo 7E2Y para acoplar?", "preparation"),
    ("advertencias de la preparación de 6LU7", "preparation"),
    ("is 7E2Y ready for docking?", "preparation"),
    ("¿qué advertencias tiene el dossier?", "unknown"),
    ("¿qué se preparó en 2024?", "unknown"),
    # Internal regression: docking classifier
    ("calcula la afinidad de la aspirina contra 7E2Y", "docking"),
    ("acopla CC(=O)Oc1ccccc1C(=O)O contra 1AJ6", "docking"),
    # Suggest / source / design / recall
    ("dame una variante de la aspirina", "suggest"),
    ("dame un smiles interesante", "suggest"),
    ("cita la fuente de los valores ADME", "source"),
    ("Dame el SMILES de un análogo con un anillo fusionado", "design"),
    ("recordas la primera molecula?", "recall_molecular"),
])
def test_classify_routes(query, expected):
    assert classify(query).name == expected


def test_compare_resolves_both_sides_in_order():
    intent = classify("compará la aspirina con el ibuprofeno")
    assert intent.tool == "compare_properties" or intent.tool == "compare_molecules"
    assert intent.smiles == "CC(=O)Oc1ccccc1C(=O)O"
    assert intent.smiles_b == "CC(C)Cc1ccc(C(C)C(=O)O)cc1"
    assert intent.smiles_source == "name"


def test_three_way_compare_fills_smiles_list():
    intent = classify("compará la aspirina, el ibuprofeno y el paracetamol")
    assert intent.name == "compare"
    assert intent.smiles_list is not None and len(intent.smiles_list) == 3


def test_docking_extracts_target():
    intent = classify("calcula la afinidad de la aspirina contra 7E2Y")
    assert intent.target == "7E2Y"
    assert intent.smiles_source == "name"


def test_explicit_smiles_beats_name():
    intent = classify("propiedades de CCO")
    assert intent.smiles == "CCO"
    assert intent.smiles_source == "explicit"


@pytest.mark.parametrize("token, expected", [
    ("CCO", True),
    ("CC(=O)Oc1ccccc1C(=O)O", True),
    ("CCCCCCCCCCCCCCCCCCCCCCCCCCCC", True),
    ("Cn1c(=O)c2c(ncn2C)n(C)c1=O", True),
    ("KILLMEnow", False),  # L starts no element
    ("zzzzzzzz", False),  # z is not aromatic
    ("EstoNoEsUnSmiles!!", False),  # ! outside the alphabet
    ("C1CC", False),  # unpaired ring digit
    ("CC(", False),  # unbalanced
    ("AB", False),  # too short
])
def test_smiles_plausibility(token, expected):
    assert smiles_plausible(token) is expected
