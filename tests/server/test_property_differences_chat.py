"""A figure that differs from PubChem is explained by a method only when MolDesign's own variant reproduces it."""
import json

import httpx
import pytest

from molchat_agent.conversation.tools import MoleculeRecord
from molchat_agent.server.app import create_app

from tests.server.test_harness_chat import events, state_for

CLOPIDOGREL = "COC(=O)[C@H](c1ccccc1Cl)N1CCc2sccc2C1"
METHODS = {"tpsa": "RDKit rdMolDescriptors.CalcTPSA (Ertl 2000) con includeSandP=False: suma sólo N y O; el azufre y el fósforo no cuentan",
           "hba": "RDKit Lipinski.NOCount (número de átomos de N y O)"}
TPSA_VARIANT = {"name": "tpsa_incl_s_p", "applies_to": "tpsa", "unit": "Å²", "value": 57.78,
                "method": "RDKit rdMolDescriptors.CalcTPSA(mol, includeSandP=True): suma también las contribuciones del azufre y el fósforo (Ertl 2000)"}
HBA_VARIANT = {"name": "hba_rdkit_num_h_acceptors", "applies_to": "hba", "unit": None, "value": 4,
               "method": "RDKit rdMolDescriptors.CalcNumHBA: aceptores de enlace de hidrógeno según los patrones SMARTS de RDKit (no es el recuento de todos los N y O)"}
PUBCHEM = {"CID": 60606, "SMILES": CLOPIDOGREL, "TPSA": 57.8, "HBondAcceptorCount": 4, "MolecularWeight": "321.8"}


async def ask(tmp_path, monkeypatch, *, props, variants, pubchem=PUBCHEM, final="Calculé las propiedades de clopidogrel."):
    pytest.importorskip("rdkit")
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")

    class Backend:
        async def properties(self, smiles):
            assert smiles == CLOPIDOGREL
            return MoleculeRecord(name=smiles, smiles=smiles, props=props, source="MolDesign / RDKit", methods=METHODS, variants=variants)
    state.backend = Backend()

    async def model(messages, _tools):
        if messages[-1]["role"] == "user":
            name, args = "pubchem_lookup", {"name": "clopidogrel"}
        elif "matches" in json.loads(messages[-1]["content"]):
            name, args = "compute_properties", {"name": CLOPIDOGREL}
        else:
            return {"role": "assistant", "content": final}
        return {"role": "assistant", "content": None, "tool_calls": [{"id": name, "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)}}]}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)

    class Bridge:
        def with_token(self, token): return self
        async def authorize_pubchem(self): pass
    state.bridge = Bridge()

    async def registry_for_turn(_token): return registry
    monkeypatch.setattr(state, "registro_de_turno", registry_for_turn)

    async def public(request):
        if "/name/" in request.url.path: return httpx.Response(200, json={"IdentifierList": {"CID": [60606]}})
        if "/property/" in request.url.path: return httpx.Response(200, json={"PropertyTable": {"Properties": [pubchem]}})
        return httpx.Response(200, json={"InformationList": {"Information": [{"CID": 60606, "Title": "Clopidogrel"}]}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(public)) as external:
        state.pubchem_client = external
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))),
                                     base_url="http://testserver") as client:
            response = await client.post("/v1/chat", headers=headers, json={"text": "compara las propiedades de clopidogrel con PubChem"})
    return next(e["result"] for e in events(response) if e["type"] == "result")


PROPS = {"mw": 321.82, "logp": 3.76, "tpsa": 29.54, "hbd": 0, "hba": 3, "rot_bonds": 4, "heavy_atoms": 21, "rings": 3}


@pytest.mark.asyncio
async def test_a_tpsa_and_an_hba_that_differ_are_explained_with_the_calculation_that_reproduces_them(tmp_path, monkeypatch):
    result = await ask(tmp_path, monkeypatch, props=PROPS, variants=[TPSA_VARIANT, HBA_VARIANT])
    text = result["text"]
    assert ("TPSA: PubChem da 57.8 Å² y MolDesign 29.54 Å². No son cifras contradictorias: MolDesign usa RDKit rdMolDescriptors."
            "CalcTPSA (Ertl 2000) con includeSandP=False") in text
    assert "el mismo RDKit da 57.78 Å², que coincide con PubChem" in text
    assert "Aceptores de enlace de hidrógeno: PubChem da 4 y MolDesign 3." in text
    assert "el mismo RDKit da 4, que coincide con PubChem" in text and "no es un error de cálculo" in text.replace("no un error", "no es un error")
    # The variants are calculations, shown beside the product's own figures, never in their place.
    values = result["evidence"][0]["values"]
    assert values["tpsa"] == "29.54" and values["variante: tpsa_incl_s_p"] == "57.78" and values["hba"] == "3"


@pytest.mark.asyncio
async def test_when_no_variant_reproduces_pubchem_the_difference_is_not_explained(tmp_path, monkeypatch):
    far = {**TPSA_VARIANT, "value": 40.0}
    result = await ask(tmp_path, monkeypatch, props=PROPS, variants=[far])
    text = result["text"]
    assert "tampoco coincide con PubChem" in text and "la diferencia no queda explicada" in text
    assert "No son cifras contradictorias" not in text and "coincide con PubChem." not in text.replace("tampoco coincide con PubChem", "")


@pytest.mark.asyncio
async def test_an_older_host_without_variants_adds_no_explanation(tmp_path, monkeypatch):
    result = await ask(tmp_path, monkeypatch, props=PROPS, variants=[])
    assert "No son cifras contradictorias" not in result["text"] and "no queda explicada" not in result["text"]


@pytest.mark.asyncio
async def test_figures_that_agree_get_no_note(tmp_path, monkeypatch):
    agree = {**PROPS, "tpsa": 57.8, "hba": 4}
    result = await ask(tmp_path, monkeypatch, props=agree, variants=[TPSA_VARIANT, HBA_VARIANT])
    assert "No son cifras contradictorias" not in result["text"] and "no queda explicada" not in result["text"]


@pytest.mark.asyncio
async def test_a_different_pubchem_structure_is_not_explained_as_a_method(tmp_path, monkeypatch):
    """The note needs the exact SMILES link; a reference for another structure never gets a method explanation."""
    other = {**PUBCHEM, "SMILES": "CCO"}
    result = await ask(tmp_path, monkeypatch, props=PROPS, variants=[TPSA_VARIANT, HBA_VARIANT], pubchem=other)
    assert "No son cifras contradictorias" not in result["text"]
