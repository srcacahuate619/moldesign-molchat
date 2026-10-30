import pytest
from molchat_agent.conversation.structure_check import compare_editor_structure

Chem = pytest.importorskip("rdkit.Chem")

def molfile(smiles):
    return Chem.MolToMolBlock(Chem.MolFromSmiles(smiles))

def test_compares_structure_and_preserves_fragments_and_charges():
    assert compare_editor_structure("CCO", molfile("OCC"))["status"] == "match"
    assert compare_editor_structure("CCO.[Na+]", molfile("CCO"))["status"] == "different_structure"
    assert compare_editor_structure("CCO", molfile("CC[O-]"))["status"] == "different_structure"

def test_distinguishes_stereochemistry_and_unknown():
    assert compare_editor_structure("C[C@H](O)F", molfile("C[C@@H](O)F"))["status"] == "different_stereochemistry"
    assert compare_editor_structure("CC(O)F", molfile("CC(O)F"))["status"] == "match_stereo_unspecified"
    assert compare_editor_structure("CCO", "no es molfile")["status"] == "unverifiable"
