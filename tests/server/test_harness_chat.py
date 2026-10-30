import asyncio
import json
from pathlib import Path

import httpx
import pytest

from molchat_agent.config import MolChatConfig
from molchat_agent.bridge import MolDesignBridge
from molchat_agent.conversation.memory import MemoryStore
from molchat_agent.conversation.tools import MoleculeRecord, QualityBackend
from molchat_agent.providers import build_registry
from molchat_agent.server.app import create_app
from molchat_agent.server.auth import mint, standalone_secret
from molchat_agent.server.state import ServerState


def events(response):
    return [json.loads(line[5:].strip()) for line in response.text.splitlines() if line.startswith("data:")]


def state_for(tmp_path):
    registry = build_registry(MolChatConfig())
    registry.set_active("fake")
    secret = standalone_secret()
    state = ServerState(secret=secret, registry=registry, memory=MemoryStore(tmp_path / "memory.db"),
                        backend=QualityBackend(Path(__file__).parent.parent / "quality/fixtures/properties.json"),
                        hosted=True)
    token = mint(secret, "owner", {"chat"}, 3600)
    return state, registry, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_chat_uses_direct_pubchem_and_resumes_selection(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    seen = []
    async def model(messages, tools):
        seen.append(list(messages))
        if len(seen) == 1:
            assert {t["function"]["name"] for t in tools} == {"pubchem_lookup", "create_case", "compute_properties", "load_case_smiles", "search_receptors", "pick_random_receptor", "assign_case_receptor", "verify_editor_structure", "show_property_comparison", "suggest_next_actions"}
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                    "function": {"name": "pubchem_lookup", "arguments": '{"name":"ibuprofeno"}'}}]}
        if len(seen) == 2:
            assert json.loads(messages[-1]["content"])["matches"][0]["cid"] == 3672
            return {"role": "assistant", "content": "Encontré una referencia en PubChem."}
        assert messages[1]["content"] == "Busca ibuprofeno en PubChem"
        assert "Selecciono la referencia PubChem 3672" in messages[-1]["content"]
        return {"role": "assistant", "content": "Referencia seleccionada; no dispongo del SMILES."}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    class Bridge:
        def with_token(self, token):
            return self
        async def authorize_pubchem(self):
            pass
    state.bridge = Bridge()
    async def registry_for_turn(_token):
        return registry
    monkeypatch.setattr(state, "registro_de_turno", registry_for_turn)
    async def public(request):
        if "/name/" in request.url.path:
            return httpx.Response(200, json={"IdentifierList": {"CID": [3672, 3673]}})
        if "/property/" in request.url.path:
            return httpx.Response(200, json={"PropertyTable": {"Properties": [
                {"CID": 3672, "MolecularFormula": "C13H18O2", "MolecularWeight": "206.28"},
                {"CID": 3673, "MolecularFormula": "C13H18O2"}]}})
        cid = int(request.url.path.split("/")[5])
        return httpx.Response(200, json={"InformationList": {"Information": [{"CID": cid, "Title": f"Ibuprofen {cid}"}]}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(public)) as external:
        state.pubchem_client = external
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))),
                                     base_url="http://testserver") as client:
            response = await client.post("/v1/chat", headers=headers, json={"text": "Busca ibuprofeno en PubChem"})
            entries = events(response)
            conv_id = next(e["id"] for e in entries if e["type"] == "conversation")
            assert next(e["result"] for e in entries if e["type"] == "result")["references"][0]["cid"] == 3672
            restored = await client.get(f"/v1/conversations/{conv_id}", headers=headers)
            assert len(restored.json()["pending_references"]) == 2
        # A fresh application state restores the selection from SQLite.
        restarted = ServerState(secret=state.secret, registry=registry, memory=MemoryStore(state.memory.path),
                                backend=state.backend, hosted=True, bridge=state.bridge, pubchem_client=external)
        monkeypatch.setattr(restarted, "registro_de_turno", registry_for_turn)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(restarted, allowed_hosts=("testserver",))),
                                     base_url="http://testserver") as client:
            selection = await client.post(f"/v1/conversations/{conv_id}/pubchem-selection", headers=headers, json={"cid": 3672})
            assert selection.status_code == 200 and "no dispongo" in selection.json()["text"]
            restored = (await client.get(f"/v1/conversations/{conv_id}", headers=headers)).json()
            assert any(message.get("content", "").startswith("Seleccionaste")
                       and len(message.get("references", [])) == 1
                       and message["references"][0]["cid"] == 3672 for message in restored["messages"])
            assert (await client.post(f"/v1/conversations/{conv_id}/pubchem-selection", headers=headers, json={"cid": 3672})).status_code == 404


@pytest.mark.asyncio
async def test_single_match_shows_properties_without_selection_and_preserves_formula(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    async def model(messages, tools):
        if messages[-1]["role"] == "user":
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                    "function": {"name": "pubchem_lookup", "arguments": '{"name":"ibuprofeno"}'}}]}
        result = json.loads(messages[-1]["content"])
        assert result["matches"][0]["properties"]["MolecularWeight"] == "206.28"
        assert result["matches"][0]["properties"]["SMILES"] == "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"
        return {"role": "assistant", "content": "Encontré 1 coincidencia: C13H18O2, peso 206.28."}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    class Bridge:
        def with_token(self, token):
            return self
        async def authorize_pubchem(self):
            pass
    state.bridge = Bridge()
    async def registry_for_turn(_token):
        return registry
    monkeypatch.setattr(state, "registro_de_turno", registry_for_turn)
    async def public(request):
        if "/name/" in request.url.path:
            return httpx.Response(200, json={"IdentifierList": {"CID": [3672]}})
        if "/property/" in request.url.path:
            return httpx.Response(200, json={"PropertyTable": {"Properties": [{"CID": 3672,
                "MolecularFormula": "C13H18O2", "MolecularWeight": "206.28", "SMILES": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"}]}})
        return httpx.Response(200, json={"InformationList": {"Information": [{"CID": 3672, "Title": "Ibuprofen"}]}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(public)) as external:
        state.pubchem_client = external
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))),
                                     base_url="http://testserver") as client:
            response = await client.post("/v1/chat", headers=headers, json={"text": "información sobre ibuprofeno"})
            entries = events(response)
            conv_id = next(e["id"] for e in entries if e["type"] == "conversation")
            result = next(e["result"] for e in entries if e["type"] == "result")
            assert result["references"][0]["properties"]["MolecularFormula"] == "C13H18O2"
            assert result["references"][0]["properties"]["SMILES"] == "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"
            assert "1 coincidencia" in result["text"] and "C13H18O2" in result["text"]
            assert "no verificado" not in result["text"]
            restored = (await client.get(f"/v1/conversations/{conv_id}", headers=headers)).json()
            assert restored["pending_references"] == []
            assert restored["messages"][-1]["references"][0]["properties"]["MolecularWeight"] == "206.28"
            selection = await client.post(f"/v1/conversations/{conv_id}/pubchem-selection", headers=headers, json={"cid": 3672})
            assert selection.status_code == 404


@pytest.mark.asyncio
async def test_calculated_values_are_cited_and_unverified_values_are_removed(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    async def model(messages, tools):
        if messages[-1]["role"] == "user":
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "calc", "type": "function",
                    "function": {"name": "compute_properties", "arguments": '{"name":"ibuprofeno"}'}}]}
        assert json.loads(messages[-1]["content"])["status"] == "ok"
        return {"role": "assistant", "content": "Su peso es 206.3; otro valor es 999.9."}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))),
                                 base_url="http://testserver") as client:
        response = await client.post("/v1/chat", headers=headers, json={"text": "propiedades del ibuprofeno"})
        result = next(e["result"] for e in events(response) if e["type"] == "result")
        assert result["evidence"] and "206.3" in result["text"]
        assert "999.9" not in result["text"] and "dato no verificado" in result["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("model_reply,expected,not_expected", [
    ("En este caso se ha creado una tabla de propiedades.", "tabla de propiedades", "No se confirmó"),
    ("Aquí tienes los datos. Se creó el caso ejemplo.", "Aquí tienes los datos.", "Se creó el caso"),
    ("No se creó un caso; faltan datos.", "No se creó un caso", "No se confirmó"),
    ("¿Quieres que cree un caso para esta molécula?", "que cree un caso", "No se confirmó"),
])
async def test_case_claim_guard_preserves_unrelated_response(tmp_path, monkeypatch, model_reply, expected, not_expected):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    async def model(_messages, _tools):
        return {"role": "assistant", "content": model_reply}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))),
                                 base_url="http://testserver") as client:
        response = await client.post("/v1/chat", headers=headers, json={"text": "Explícame las propiedades"})
        result = next(e["result"] for e in events(response) if e["type"] == "result")
        assert expected in result["text"]
        assert not_expected not in result["text"]
        assert not any(e["type"] == "case_create" for e in events(response))


@pytest.mark.asyncio
async def test_followup_keeps_conversation_context_for_tool_selection(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    async def model(messages, tools):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Encontré una referencia en PubChem."}
        assert messages[-1]["content"] == "ahora de PubChem"
        assert any(m.get("role") == "user" and "ibuprofeno" in m.get("content", "") for m in messages)
        return {"role": "assistant", "content": None, "tool_calls": [{"id": "search", "type": "function",
                "function": {"name": "pubchem_lookup", "arguments": '{"name":"ibuprofeno"}'}}]}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    class Bridge:
        def with_token(self, token):
            return self
        async def authorize_pubchem(self):
            pass
    state.bridge = Bridge()
    async def registry_for_turn(_token):
        return registry
    monkeypatch.setattr(state, "registro_de_turno", registry_for_turn)
    conv = state.memory.create_conversation("owner")
    state.memory.add_message(conv, "owner", "user", "Dame las propiedades del ibuprofeno")
    state.memory.add_message(conv, "owner", "assistant", "Aquí están las propiedades.")
    async def public(request):
        if "/name/" in request.url.path:
            return httpx.Response(200, json={"IdentifierList": {"CID": [3672]}})
        return httpx.Response(200, json={"InformationList": {"Information": [{"CID": 3672, "Title": "Ibuprofen"}]}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(public)) as external:
        state.pubchem_client = external
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))),
                                     base_url="http://testserver") as client:
            response = await client.post("/v1/chat", headers=headers, json={"text": "ahora de PubChem", "conversation_id": conv})
            result = next(e["result"] for e in events(response) if e["type"] == "result")
            assert result["references"][0]["cid"] == 3672


@pytest.mark.asyncio
async def test_followup_preserves_prior_structures_and_names_but_not_new_measurements(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    async def model(messages, _tools):
        assert any(smiles in message.get("content", "") for message in messages)
        return {"role": "assistant", "content": f'Caso "prueba 2", SMILES `{smiles}`. Peso 999.9.'}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    conv = state.memory.create_conversation("owner")
    state.memory.add_message(conv, "owner", "assistant", f'Caso "prueba 2"; PubChem: `{smiles}`.')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))),
                                 base_url="http://testserver") as client:
        response = await client.post("/v1/chat", headers=headers, json={"text": "¿puedes cargarlo?", "conversation_id": conv})
        answer = next(e["result"]["text"] for e in events(response) if e["type"] == "result")
        assert smiles in answer and 'prueba 2' in answer
        assert '999.9' not in answer and '[dato no verificado]' in answer


@pytest.mark.asyncio
async def test_model_can_retry_pubchem_with_english_name_after_not_found(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    calls = []
    async def model(messages, tools):
        assert "nombre en inglés" in messages[0]["content"]
        if messages[-1]["role"] == "user":
            name = "aspirina"
        elif json.loads(messages[-1]["content"])["status"] == "not_found":
            name = "aspirin"
        else:
            return {"role": "assistant", "content": "Encontré Aspirin en PubChem."}
        calls.append(name)
        return {"role": "assistant", "content": None, "tool_calls": [{"id": f"c{len(calls)}", "type": "function",
                "function": {"name": "pubchem_lookup", "arguments": json.dumps({"name": name})}}]}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    class Bridge:
        def with_token(self, token): return self
        async def authorize_pubchem(self): pass
    state.bridge = Bridge()
    async def registry_for_turn(_token): return registry
    monkeypatch.setattr(state, "registro_de_turno", registry_for_turn)
    async def public(request):
        if "/name/aspirina/" in request.url.path: return httpx.Response(404)
        if "/name/" in request.url.path: return httpx.Response(200, json={"IdentifierList": {"CID": [2244]}})
        if "/property/" in request.url.path: return httpx.Response(200, json={"PropertyTable": {"Properties": [{"CID": 2244, "MolecularFormula": "C9H8O4"}]}})
        return httpx.Response(200, json={"InformationList": {"Information": [{"CID": 2244, "Title": "Aspirin"}]}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(public)) as external:
        state.pubchem_client = external
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
            response = await client.post("/v1/chat", headers=headers, json={"text": "busca aspirina en PubChem"})
            result = next(e["result"] for e in events(response) if e["type"] == "result")
            assert calls == ["aspirina", "aspirin"] and result["references"][0]["cid"] == 2244


@pytest.mark.asyncio
async def test_comparison_links_only_exact_pubchem_smiles_and_survives_reload(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    class Backend:
        async def properties(self, smiles):
            assert smiles == "OCC"
            return MoleculeRecord(name="ethanol", smiles="CCO", props={"hba": 1}, source="RDKit",
                                  methods={"hba": "RDKit Lipinski.NOCount"})
    state.backend = Backend()
    async def model(messages, _tools):
        if messages[-1]["role"] == "user":
            name, args = "pubchem_lookup", {"name": "ethanol"}
        elif "matches" in json.loads(messages[-1]["content"]):
            name, args = "compute_properties", {"name": "OCC"}
        else:
            data = json.loads(messages[-1]["content"])
            assert data["structure"]["pubchem_cid"] == 702
            assert data["methods"]["hba"] == "RDKit Lipinski.NOCount"
            return {"role": "assistant", "content": "Datos disponibles para etanol."}
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
        if "/name/" in request.url.path: return httpx.Response(200, json={"IdentifierList": {"CID": [702]}})
        if "/property/" in request.url.path: return httpx.Response(200, json={"PropertyTable": {"Properties": [{"CID": 702, "SMILES": "OCC", "HBondAcceptorCount": 1}]}})
        return httpx.Response(200, json={"InformationList": {"Information": [{"CID": 702, "Title": "Ethanol"}]}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(public)) as external:
        state.pubchem_client = external
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
            response = await client.post("/v1/chat", headers=headers, json={"text": "compara etanol con PubChem"})
            entries = events(response)
            result = next(e["result"] for e in entries if e["type"] == "result")
            structure = result["evidence"][0]["structure"]
            assert structure["input_smiles"] == "OCC" and structure["pubchem_cid"] == 702
            assert structure["identity"] == "same"
            conv_id = next(e["id"] for e in entries if e["type"] == "conversation")
            restored = (await client.get(f"/v1/conversations/{conv_id}", headers=headers)).json()
            assert restored["messages"][-1]["evidence"][0]["structure"] == structure


@pytest.mark.asyncio
async def test_comparison_restores_verified_pubchem_reference_across_turns(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    reference = {"cid": 2244, "name": "Aspirin", "source": "https://pubchem.ncbi.nlm.nih.gov/compound/2244",
                 "properties": {"SMILES": "CCO", "MolecularWeight": "180.16", "XLogP": 1.2}, "properties_available": True}
    class Backend:
        async def properties(self, smiles):
            assert smiles == "CCO"
            return MoleculeRecord(name="test", smiles="CCO", props={"mw": 180.16, "logp": 1.31}, source="RDKit")
    state.backend = Backend()
    async def model(messages, _tools):
        if messages[-1]["role"] == "user":
            assert any('2244' in m.get('content', '') and 'CCO' in m.get('content', '') for m in messages)
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "calc", "type": "function",
                    "function": {"name": "compute_properties", "arguments": '{"name":"CCO"}'}}]}
        assert json.loads(messages[-1]["content"])["structure"]["pubchem_cid"] == 2244
        return {"role": "assistant", "content": "CID 2244, XLogP 1.2. PubChem refiere una clasificación de 1997. Valor inventado 999.9."}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    conv = state.memory.create_conversation("owner")
    state.memory.add_message(conv, "owner", "assistant", "Encontré aspirina.", references=[reference])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        response = await client.post("/v1/chat", headers=headers, json={"text": "calcula con MolDesign", "conversation_id": conv})
        result = next(e["result"] for e in events(response) if e["type"] == "result")
        assert result["evidence"][0]["structure"]["pubchem_cid"] == 2244
        assert result["references"] == [reference]
        assert "CID 2244" in result["text"] and "clasificación de 1997" in result["text"]
        assert "999.9" not in result["text"]
        restored = (await client.get(f"/v1/conversations/{conv}", headers=headers)).json()
        assert restored["messages"][-1]["references"] == [reference]


@pytest.mark.asyncio
async def test_explicit_comparison_marker_requires_linked_results_and_survives_reload(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    reference = {"cid": 702, "name": "Ethanol", "source": "https://pubchem.ncbi.nlm.nih.gov/compound/702",
                 "properties": {"SMILES": "CCO", "MolecularWeight": 46.07}, "properties_available": True}
    class Backend:
        async def properties(self, smiles):
            assert smiles == "CCO"
            return MoleculeRecord(name="ethanol", smiles="CCO", props={"mw": 46.07}, source="RDKit")
    state.backend = Backend()
    conv = state.memory.create_conversation("owner")
    state.memory.add_message(conv, "owner", "assistant", "Encontré etanol en PubChem.", references=[reference])
    async def model(messages, _tools):
        if messages[-1]["role"] == "user":
            name, args = "compute_properties", {"name": "CCO"}
        elif json.loads(messages[-1]["content"]).get("properties"):
            name, args = "show_property_comparison", {"cid": "702"}
        elif messages[-1].get("tool_call_id") == "show_property_comparison":
            name, args = "suggest_next_actions", {"actions": [{"kind": "compare_with_moldesign", "cid": 702, "text": "Compara con MolDesign"}, {"kind": "verify_drawing", "cid": 702, "text": "Verifica el dibujo"}]}
        else:
            assert json.loads(messages[-1]["content"])["status"] == "ok"
            return {"role": "assistant", "content": "Aquí está la comparación solicitada."}
        return {"role": "assistant", "content": None, "tool_calls": [{"id": name, "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)}}]}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        response = await client.post("/v1/chat", headers=headers, json={"text": "compara PubChem con MolDesign", "conversation_id": conv})
        result = next(e["result"] for e in events(response) if e["type"] == "result")
        assert result["comparison_cids"] == [702]
        assert result["suggested_actions"] == [{"kind": "verify_drawing", "cid": 702, "text": "Verifica el dibujo"}]
        assert result["references"][0]["cid"] == 702 and result["evidence"][0]["structure"]["pubchem_cid"] == 702
        restored = (await client.get(f"/v1/conversations/{conv}", headers=headers)).json()
        assert restored["messages"][-1]["comparison_cids"] == [702]
        assert restored["messages"][-1]["suggested_actions"] == result["suggested_actions"]


@pytest.mark.asyncio
async def test_comparison_marker_does_not_invent_missing_calculation(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    conv = state.memory.create_conversation("owner")
    state.memory.add_message(conv, "owner", "assistant", "Referencia PubChem.", references=[{"cid": 702, "name": "Ethanol",
        "source": "https://pubchem.ncbi.nlm.nih.gov/compound/702", "properties": {"SMILES": "CCO"}}])
    async def model(messages, _tools):
        if messages[-1]["role"] == "user":
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "cmp", "type": "function",
                "function": {"name": "show_property_comparison", "arguments": '{"cid":"702"}'}}]}
        assert json.loads(messages[-1]["content"])["status"] == "unavailable"
        return {"role": "assistant", "content": "Falta calcular las propiedades."}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        response = await client.post("/v1/chat", headers=headers, json={"text": "compara", "conversation_id": conv})
        result = next(e["result"] for e in events(response) if e["type"] == "result")
        assert result["comparison_cids"] == [] and not result["evidence"]


@pytest.mark.asyncio
@pytest.mark.parametrize("reference_status", ["missing", "ambiguous"])
async def test_suggestion_rejects_unknown_or_ambiguous_reference(tmp_path, monkeypatch, reference_status):
    state, registry, headers = state_for(tmp_path)
    conv = state.memory.create_conversation("owner")
    if reference_status == "ambiguous":
        state.memory.add_message(conv, "owner", "assistant", "Elige", references=[
            {"cid": 702, "name": "Uno", "properties": {"SMILES": "CCO"}},
            {"cid": 703, "name": "Otro", "properties": {"SMILES": "CCC"}}])
    async def model(messages, _tools):
        if messages[-1]["role"] == "user":
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "suggest", "type": "function",
                "function": {"name": "suggest_next_actions", "arguments": '{"actions":[{"kind":"verify_drawing","cid":702,"text":"Verifica el dibujo"}]}'}}]}
        assert json.loads(messages[-1]["content"])["status"] == "unavailable"
        return {"role": "assistant", "content": "Necesito una referencia inequívoca."}
    monkeypatch.setattr(registry.get("fake"), "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        response = await client.post("/v1/chat", headers=headers, json={"text": "propón un siguiente paso", "conversation_id": conv})
        result = next(e["result"] for e in events(response) if e["type"] == "result")
        assert result["suggested_actions"] == []


@pytest.mark.asyncio
async def test_suggestion_rejects_an_unrecognized_category(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    conv = state.memory.create_conversation("owner")
    state.memory.add_message(conv, "owner", "assistant", "Referencia", references=[{
        "cid": 702, "name": "Ethanol", "source": "https://pubchem.ncbi.nlm.nih.gov/compound/702", "properties": {"SMILES": "CCO"}}])
    async def model(messages, _tools):
        if messages[-1]["role"] == "user":
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "suggest", "type": "function",
                "function": {"name": "suggest_next_actions", "arguments": '{"actions":[{"kind":"dockear","text":"Dockea"}]}'}}]}
        assert "no se ejecutó" in json.loads(messages[-1]["content"])["error"]
        return {"role": "assistant", "content": "No hay una acción disponible para eso."}
    monkeypatch.setattr(registry.get("fake"), "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        response = await client.post("/v1/chat", headers=headers, json={"text": "recomienda un paso", "conversation_id": conv})
        result = next(e["result"] for e in events(response) if e["type"] == "result")
        assert result["suggested_actions"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 1, 2, 3, 4])
async def test_model_proposes_at_most_three_contextual_buttons(tmp_path, monkeypatch, count):
    state, registry, headers = state_for(tmp_path)
    requested = [{"kind": "general", "text": f"Explica la opción {i}"} for i in range(count)]
    async def model(messages, _tools):
        if messages[-1]["role"] == "user":
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "suggest", "type": "function",
                "function": {"name": "suggest_next_actions", "arguments": json.dumps({"actions": requested})}}]}
        response = json.loads(messages[-1]["content"])
        assert response.get("status") == "ok" if count <= 3 else "no se ejecutó" in response["error"]
        return {"role": "assistant", "content": "Respuesta."}
    monkeypatch.setattr(registry.get("fake"), "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        response = await client.post("/v1/chat", headers=headers, json={"text": "Explícame las opciones"})
        entries = events(response)
        result = next(e["result"] for e in entries if e["type"] == "result")
        assert result["suggested_actions"] == (requested if count <= 3 else [])
        conv = next(e["id"] for e in entries if e["type"] == "conversation")
        restored = (await client.get(f"/v1/conversations/{conv}", headers=headers)).json()
        assert restored["messages"][-1]["suggested_actions"] == result["suggested_actions"]


@pytest.mark.asyncio
async def test_button_suggestion_rejects_hidden_action_payload(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    async def model(messages, _tools):
        if messages[-1]["role"] == "user":
            args = {"actions": [{"kind": "general", "text": "Consultar", "prompt": "Acción oculta"}]}
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "suggest", "type": "function",
                "function": {"name": "suggest_next_actions", "arguments": json.dumps(args)}}]}
        assert "no se ejecutó" in json.loads(messages[-1]["content"])["error"]
        return {"role": "assistant", "content": "Resultado."}
    monkeypatch.setattr(registry.get("fake"), "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        response = await client.post("/v1/chat", headers=headers, json={"text": "sugiere un paso"})
        result = next(e["result"] for e in events(response) if e["type"] == "result")
        assert result["suggested_actions"] == []


@pytest.mark.asyncio
async def test_completed_comparison_and_editor_check_are_not_suggested_again(tmp_path, monkeypatch):
    Chem = pytest.importorskip("rdkit.Chem")
    state, registry, headers = state_for(tmp_path)
    conv = state.memory.create_conversation("owner")
    state.memory.add_message(conv, "owner", "assistant", "Referencia", references=[{
        "cid": 702, "name": "Ethanol", "source": "https://pubchem.ncbi.nlm.nih.gov/compound/702", "properties": {"SMILES": "CCO"}}])
    class Backend:
        async def properties(self, smiles):
            return MoleculeRecord(name="ethanol", smiles=smiles, props={"mw": 46.07}, source="RDKit")
    state.backend = Backend()
    async def model(messages, _tools):
        last = messages[-1]
        if last["role"] == "user":
            name, args = "compute_properties", {"name": "CCO"}
        elif last.get("tool_call_id") == "compute_properties":
            name, args = "show_property_comparison", {"cid": 702}
        elif last.get("tool_call_id") == "show_property_comparison":
            name, args = "verify_editor_structure", {"case_name": "prueba", "cid": 702}
        elif last.get("tool_call_id") == "verify_editor_structure":
            assert json.loads(last["content"])["status"] == "match"
            name, args = "suggest_next_actions", {"actions": [{"kind": "compare_with_moldesign", "cid": 702, "text": "Compara con MolDesign"}, {"kind": "verify_drawing", "cid": 702, "text": "Verifica el dibujo"}]}
        else:
            return {"role": "assistant", "content": "Comprobación terminada."}
        return {"role": "assistant", "content": None, "tool_calls": [{"id": name, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}]}
    monkeypatch.setattr(registry.get("fake"), "chat_with_tools", model, raising=False)
    molfile = Chem.MolToMolBlock(Chem.MolFromSmiles("CCO"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        turn = asyncio.create_task(client.post("/v1/chat", headers=headers, json={"text": "compara y verifica el dibujo", "conversation_id": conv}))
        for _ in range(300):
            if state.editor_requests: break
            await asyncio.sleep(0.01)
        first = next(iter(state.editor_requests))
        await client.post(f"/v1/editor-requests/{first}/result", headers=headers, json={"status": "ok", "molfile": molfile, "revision": "1:2"})
        for _ in range(300):
            pending = [key for key in state.editor_requests if key != first]
            if pending: break
            await asyncio.sleep(0.01)
        await client.post(f"/v1/editor-requests/{pending[0]}/result", headers=headers, json={"status": "ok"})
        result = next(e["result"] for e in events(await turn) if e["type"] == "result")
        assert result["comparison_cids"] == [702]
        assert result["suggested_actions"] == []
        restored = (await client.get(f"/v1/conversations/{conv}", headers=headers)).json()
        assert restored["messages"][-1]["suggested_actions"] == []


@pytest.mark.asyncio
async def test_requested_lookup_load_and_receptor_search_leave_comparison_optional(tmp_path, monkeypatch):
    pytest.importorskip("rdkit")
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    async def model(messages, tools):
        assert "no ejecutes cálculos de MolDesign ni compares fuentes por iniciativa propia" in messages[0]["content"]
        tool_responses = [item for item in messages if item.get("role") == "tool"]
        if not tool_responses:
            name, args = "pubchem_lookup", {"name": "atorvastatin"}
        elif len(tool_responses) == 1:
            name, args = "search_receptors", {"query": "*", "section": "verificado"}
        elif len(tool_responses) == 2:
            name, args = "load_case_smiles", {"case_name": "prueba2", "smiles": "CCO"}
        else:
            return {"role": "assistant", "content": "Referencia consultada. Encontré 8T69, pero no puedo asignarlo al caso."}
        return {"role": "assistant", "content": None, "tool_calls": [{"id": name, "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)}}]}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    async def registry_for_turn(_token): return registry
    monkeypatch.setattr(state, "registro_de_turno", registry_for_turn)
    async def host(request):
        if request.url.path == "/ai/consent/red":
            return httpx.Response(200, json={"modo_offline": False, "destinos": [{"servicio": "pubchem", "host": "pubchem.ncbi.nlm.nih.gov", "consentido": True}]})
        if request.url.path == "/targets/":
            return httpx.Response(200, json=[{"pdb_id": "8T69", "name": "VMAT2", "seccion_catalogo": "verificado", "disponible": True}])
        return httpx.Response(404)
    async def public(request):
        if "/name/" in request.url.path: return httpx.Response(200, json={"IdentifierList": {"CID": [60823]}})
        if "/property/" in request.url.path: return httpx.Response(200, json={"PropertyTable": {"Properties": [{"CID": 60823, "SMILES": "CCO"}]}})
        return httpx.Response(200, json={"InformationList": {"Information": [{"CID": 60823, "Title": "Atorvastatin"}]}})
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(host)) as host_client, \
               httpx.AsyncClient(transport=httpx.MockTransport(public)) as external:
        state.bridge = MolDesignBridge(client=host_client)
        state.pubchem_client = external
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
            turn = asyncio.create_task(client.post("/v1/chat", headers=headers, json={"text": "investiga atorvastatina, colócala en prueba2 junto con el receptor verificado"}))
            for _ in range(300):
                if state.smiles_requests: break
                await asyncio.sleep(0.01)
            assert state.smiles_requests
            request_id = next(iter(state.smiles_requests))
            await client.post(f"/v1/smiles-requests/{request_id}/result", headers=headers, json={"status": "applied"})
            entries = events(await turn)
            result = next(e["result"] for e in entries if e["type"] == "result")
            assert result["comparison_cids"] == []
            assert "no puedo asignarlo" in result["text"] and "SMILES cargado" in result["text"]
            assert not any(e["type"] == "case_create" for e in entries)
            job = (await client.get("/v1/harness-jobs", headers=headers)).json()[0]
            assert [item["tool"] for item in job["steps"]] == ["pubchem_lookup", "search_receptors", "load_case_smiles"]


@pytest.mark.asyncio
@pytest.mark.parametrize("reference_count", [1, 2])
async def test_no_provenance_for_wrong_or_ambiguous_previous_smiles(tmp_path, monkeypatch, reference_count):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    class Backend:
        async def properties(self, smiles):
            return MoleculeRecord(name="test", smiles=smiles, props={"mw": 1}, source="RDKit")
    state.backend = Backend()
    async def model(messages, _tools):
        if messages[-1]["role"] == "user":
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "calc", "type": "function",
                    "function": {"name": "compute_properties", "arguments": '{"name":"CCC"}'}}]}
        assert "pubchem_cid" not in json.loads(messages[-1]["content"])["structure"]
        return {"role": "assistant", "content": "Cálculo realizado."}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    conv = state.memory.create_conversation("owner")
    refs = [{"cid": i, "name": "test", "source": f"https://pubchem.ncbi.nlm.nih.gov/compound/{i}",
             "properties": {"SMILES": "CCO" if reference_count == 1 else "CCC"}} for i in range(1, reference_count + 1)]
    state.memory.add_message(conv, "owner", "assistant", "Resultados", references=refs)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        response = await client.post("/v1/chat", headers=headers, json={"text": "calcula", "conversation_id": conv})
        result = next(e["result"] for e in events(response) if e["type"] == "result")
        assert "pubchem_cid" not in result["evidence"][0]["structure"]
        assert result["references"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["created", "exists", "failed", "unknown"])
async def test_case_creation_waits_for_host(tmp_path, monkeypatch, status):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    async def model(messages, tools):
        if messages[-1]["role"] == "user":
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                    "function": {"name": "create_case", "arguments": '{"name":"hola"}'}}]}
        assert json.loads(messages[-1]["content"])["status"] == status
        return {"role": "assistant", "content": "Además, preparé la información solicitada."}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))),
                                 base_url="http://testserver") as client:
        turn = asyncio.create_task(client.post("/v1/chat", headers=headers, json={"text": "crea un caso hola"}))
        for _ in range(100):
            if state.case_requests:
                break
            await asyncio.sleep(0.01)
        assert len(state.case_requests) == 1 and not turn.done()
        request_id = next(iter(state.case_requests))
        assert (await client.post(f"/v1/case-requests/{request_id}/result", headers=headers, json={"status": status})).status_code == 200
        result = next(e["result"]["text"] for e in events(await turn) if e["type"] == "result")
        expected = {"created": "Se creó", "exists": "Ya existe", "failed": "no pudo", "unknown": "No pude confirmar"}
        assert expected[status] in result
        assert "Además, preparé la información solicitada." in result


@pytest.mark.asyncio
async def test_confirmed_case_is_not_announced_twice(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    async def model(messages, _tools):
        if messages[-1]["role"] == "user":
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                "function": {"name": "create_case", "arguments": '{"name":"prueba 2"}'}}]}
        return {"role": "assistant", "content": 'El caso **"prueba 2"** fue creado correctamente.'}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        turn = asyncio.create_task(client.post("/v1/chat", headers=headers, json={"text": 'crea "prueba 2"'}))
        for _ in range(100):
            if state.case_requests: break
            await asyncio.sleep(0.01)
        request_id = next(iter(state.case_requests))
        await client.post(f"/v1/case-requests/{request_id}/result", headers=headers, json={"status": "created"})
        answer = next(e["result"]["text"] for e in events(await turn) if e["type"] == "result")
        assert 'fue creado correctamente' in answer and 'Se creó el caso' not in answer


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["applied", "not_found", "ambiguous", "busy", "failed", "unknown"])
async def test_smiles_tool_waits_for_owner_scoped_host_result(tmp_path, monkeypatch, status):
    pytest.importorskip("rdkit")
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    async def model(messages, tools):
        if messages[-1]["role"] == "user":
            assert "load_case_smiles" in {item["function"]["name"] for item in tools}
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "load", "type": "function",
                "function": {"name": "load_case_smiles", "arguments": '{"case_name":"prueba","smiles":"CCO"}'}}]}
        assert json.loads(messages[-1]["content"])["status"] == status
        return {"role": "assistant", "content": "Recibí el resultado."}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        turn = asyncio.create_task(client.post("/v1/chat", headers=headers, json={"text": "carga CCO en el caso prueba"}))
        for _ in range(200):
            if state.smiles_requests: break
            await asyncio.sleep(0.01)
        request_id = next(iter(state.smiles_requests))
        assert not turn.done()
        bad = await client.post(f"/v1/smiles-requests/{request_id}/result", headers=headers, json={"status": "inventado"})
        assert bad.status_code == 400
        accepted = await client.post(f"/v1/smiles-requests/{request_id}/result", headers=headers, json={"status": status})
        assert accepted.status_code == 200
        entries = events(await turn)
        assert any(e.get("type") == "case_smiles" and e["case_name"] == "prueba" and e["smiles"] == "CCO" for e in entries)
        answer = next(e["result"]["text"] for e in entries if e["type"] == "result")
        assert ("SMILES cargado en el campo del caso «prueba»" in answer) == (status == "applied")
        jobs = (await client.get("/v1/harness-jobs", headers=headers)).json()
        assert jobs[0]["steps"] == [{"id": "load", "tool": "load_case_smiles", "status": status, "detail": "case_name: prueba"}]
        assert jobs[0]["state"] == ("completed" if status == "applied" else "partial")
        assert state.memory.list_harness_jobs("otra-cuenta") == []
        assert (await client.post(f"/v1/smiles-requests/{request_id}/result", headers=headers, json={"status": status})).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["applied", "already_selected", "case_not_found", "case_ambiguous", "receptor_not_found", "receptor_ambiguous", "unavailable", "locked", "busy", "save_failed", "failed", "unknown"])
async def test_receptor_assignment_waits_for_host_and_records_status(tmp_path, monkeypatch, status):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    async def model(messages, tools):
        if messages[-1]["role"] == "user":
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "assign", "type": "function", "function": {"name": "assign_case_receptor", "arguments": '{"case_name":"prueba","pdb_id":"7E2Y"}'}}]}
        assert json.loads(messages[-1]["content"])["status"] == status
        return {"role": "assistant", "content": "Resultado recibido."}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        turn = asyncio.create_task(client.post("/v1/chat", headers=headers, json={"text": "asigna el receptor 7E2Y al caso prueba"}))
        for _ in range(200):
            if state.receptor_requests: break
            await asyncio.sleep(0.01)
        request_id = next(iter(state.receptor_requests))
        assert not turn.done()
        assert (await client.post(f"/v1/receptor-requests/{request_id}/result", headers=headers, json={"status": "inventado"})).status_code == 400
        assert (await client.post(f"/v1/receptor-requests/{request_id}/result", headers=headers, json={"status": status})).status_code == 200
        entries = events(await turn)
        assert any(e.get("type") == "case_receptor" and e["pdb_id"] == "7E2Y" and e["case_name"] == "prueba" for e in entries)
        answer = next(e["result"]["text"] for e in entries if e["type"] == "result")
        assert ("asignado y guardado" in answer) == (status == "applied")
        job = (await client.get("/v1/harness-jobs", headers=headers)).json()[0]
        assert job["steps"][0]["tool"] == "assign_case_receptor"
        assert job["steps"][0]["status"] == status
        assert (await client.post(f"/v1/receptor-requests/{request_id}/result", headers=headers, json={"status": status})).status_code == 404


@pytest.mark.asyncio
async def test_receptor_assignment_requires_identified_receptor(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    async def model(messages, tools):
        if messages[-1]["role"] == "user":
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "assign", "type": "function", "function": {"name": "assign_case_receptor", "arguments": '{"case_name":"prueba","pdb_id":"7E2Y"}'}}]}
        assert json.loads(messages[-1]["content"])["status"] == "needs_selection"
        return {"role": "assistant", "content": "Elige un receptor."}
    monkeypatch.setattr(registry.get("fake"), "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        response = await client.post("/v1/chat", headers=headers, json={"text": "asigna un receptor al caso prueba"})
        assert not any(e.get("type") == "case_receptor" for e in events(response))
        assert not state.receptor_requests


@pytest.mark.asyncio
@pytest.mark.parametrize("wrong_first", [False, True])
async def test_random_receptor_can_be_assigned_without_substituting_another(tmp_path, monkeypatch, wrong_first):
    state, registry, headers = state_for(tmp_path)
    monkeypatch.setattr("molchat_agent.conversation.harness_tools.secrets.choice", lambda items: items[-1])
    async def model(messages, tools):
        if messages[-1]["role"] == "user":
            assert "pick_random_receptor" in {item["function"]["name"] for item in tools}
            name, args = "pick_random_receptor", {}
        elif messages[-1].get("tool_call_id") == "pick_random_receptor":
            selected = json.loads(messages[-1]["content"])
            assert selected["receptor"]["pdb_id"] == "1BN1" and selected["selection"] == "aleatoria"
            if wrong_first:
                return {"role": "assistant", "content": None, "tool_calls": [{"id": "different-search", "type": "function",
                    "function": {"name": "search_receptors", "arguments": '{"query":"1AJ6"}'}}]}
            name, args = "assign_case_receptor", {"case_name": "prueba2", "pdb_id": selected["receptor"]["pdb_id"]}
        elif messages[-1].get("tool_call_id") == "different-search":
            assert json.loads(messages[-1]["content"])["total"] == 1
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "wrong", "type": "function",
                "function": {"name": "assign_case_receptor", "arguments": '{"case_name":"prueba2","pdb_id":"1AJ6"}'}}]}
        elif messages[-1].get("tool_call_id") == "wrong":
            assert json.loads(messages[-1]["content"])["status"] == "needs_selection"
            name, args = "assign_case_receptor", {"case_name": "prueba2", "pdb_id": "1BN1"}
        else:
            assert json.loads(messages[-1]["content"])["status"] == "applied"
            return {"role": "assistant", "content": "Se seleccionó y asignó el receptor aleatorio."}
        return {"role": "assistant", "content": None, "tool_calls": [{"id": name, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}]}
    monkeypatch.setattr(registry.get("fake"), "chat_with_tools", model, raising=False)
    async def registry_for_turn(_token): return registry
    monkeypatch.setattr(state, "registro_de_turno", registry_for_turn)
    async def host(_request): return httpx.Response(200, json=[
        {"pdb_id": "1AJ6", "name": "Uno", "disponible": True, "seccion_catalogo": "demostracion"},
        {"pdb_id": "1BN1", "name": "Dos", "disponible": True, "seccion_catalogo": "demostracion"}])
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(host)) as host_client:
        state.bridge = MolDesignBridge(client=host_client)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
            turn = asyncio.create_task(client.post("/v1/chat", headers=headers, json={"text": "asigna un receptor random al caso prueba2"}))
            for _ in range(200):
                if state.receptor_requests: break
                await asyncio.sleep(0.01)
            request_id = next(iter(state.receptor_requests))
            await client.post(f"/v1/receptor-requests/{request_id}/result", headers=headers, json={"status": "applied"})
            entries = events(await turn)
            assert any(e.get("type") == "case_receptor" and e["pdb_id"] == "1BN1" for e in entries)
            result = next(e["result"] for e in entries if e["type"] == "result")
            assert "1BN1" in result["text"] and "asignado y guardado" in result["text"]
            assert any(item["tool"] == "pick_random_receptor" for item in result["evidence"])


@pytest.mark.asyncio
async def test_multistep_random_receptor_flow_finishes_with_a_model_answer(tmp_path, monkeypatch):
    Chem = pytest.importorskip("rdkit.Chem")
    state, registry, headers = state_for(tmp_path)
    monkeypatch.setattr("molchat_agent.conversation.harness_tools.secrets.choice", lambda items: items[-1])
    async def model(messages, _tools):
        last = messages[-1]
        if last["role"] == "user":
            call_id, name, args = "miss", "pubchem_lookup", {"name": "error-de-escritura"}
        elif last.get("tool_call_id") == "miss":
            assert json.loads(last["content"])["status"] == "not_found"
            call_id, name, args = "found", "pubchem_lookup", {"name": "ethanol"}
        elif last.get("tool_call_id") == "found":
            call_id, name, args = "random", "pick_random_receptor", {}
        elif last.get("tool_call_id") == "random":
            assert json.loads(last["content"])["receptor"]["pdb_id"] == "1BN1"
            call_id, name, args = "load", "load_case_smiles", {"case_name": "prueba2", "smiles": "CCO"}
        elif last.get("tool_call_id") == "load":
            call_id, name, args = "assign", "assign_case_receptor", {"case_name": "prueba2", "pdb_id": "1BN1"}
        elif last.get("tool_call_id") == "assign":
            assert json.loads(last["content"])["status"] == "applied"
            call_id, name, args = "verify", "verify_editor_structure", {"case_name": "prueba2", "cid": 702}
        elif last.get("tool_call_id") == "verify":
            assert json.loads(last["content"])["status"] == "match"
            call_id, name, args = "suggest", "suggest_next_actions", {"actions": [{"kind": "general", "text": "Explica el receptor seleccionado"}]}
        else:
            return {"role": "assistant", "content": "Consulta, selección y comprobación terminadas."}
        return {"role": "assistant", "content": None, "tool_calls": [{"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}
    monkeypatch.setattr(registry.get("fake"), "chat_with_tools", model, raising=False)
    async def registry_for_turn(_token): return registry
    monkeypatch.setattr(state, "registro_de_turno", registry_for_turn)
    async def host(request):
        if request.url.path == "/targets/":
            return httpx.Response(200, json=[{"pdb_id": "1AJ6", "disponible": True}, {"pdb_id": "1BN1", "disponible": True}])
        return httpx.Response(200, json={"modo_offline": False, "destinos": [{"servicio": "pubchem", "host": "pubchem.ncbi.nlm.nih.gov", "consentido": True}]})
    async def public(request):
        if "/name/error-de-escritura/" in request.url.path: return httpx.Response(404)
        if "/name/" in request.url.path: return httpx.Response(200, json={"IdentifierList": {"CID": [702]}})
        if "/property/" in request.url.path: return httpx.Response(200, json={"PropertyTable": {"Properties": [{"CID": 702, "SMILES": "CCO"}]}})
        return httpx.Response(200, json={"InformationList": {"Information": [{"CID": 702, "Title": "Ethanol"}]}})
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(host)) as host_client, httpx.AsyncClient(transport=httpx.MockTransport(public)) as external:
        state.bridge = MolDesignBridge(client=host_client)
        state.pubchem_client = external
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
            turn = asyncio.create_task(client.post("/v1/chat", headers=headers, json={"text": "investiga, carga en prueba2, asigna un receptor random y verifica el dibujo"}))
            for _ in range(300):
                if state.smiles_requests: break
                await asyncio.sleep(0.01)
            await client.post(f"/v1/smiles-requests/{next(iter(state.smiles_requests))}/result", headers=headers, json={"status": "applied"})
            for _ in range(300):
                if state.receptor_requests: break
                await asyncio.sleep(0.01)
            await client.post(f"/v1/receptor-requests/{next(iter(state.receptor_requests))}/result", headers=headers, json={"status": "applied"})
            for _ in range(300):
                if state.editor_requests: break
                await asyncio.sleep(0.01)
            first = next(iter(state.editor_requests))
            await client.post(f"/v1/editor-requests/{first}/result", headers=headers, json={"status": "ok", "molfile": Chem.MolToMolBlock(Chem.MolFromSmiles("CCO")), "revision": "1:2"})
            for _ in range(300):
                pending = [key for key in state.editor_requests if key != first]
                if pending: break
                await asyncio.sleep(0.01)
            await client.post(f"/v1/editor-requests/{pending[0]}/result", headers=headers, json={"status": "ok"})
            entries = events(await turn)
            result = next(e["result"] for e in entries if e["type"] == "result")
            assert "Consulta, selección y comprobación terminadas." in result["text"]
            assert "límite de pasos" not in result["text"]
            assert any(e.get("type") == "case_receptor" and e["pdb_id"] == "1BN1" for e in entries)
            assert not any(e.get("type") == "case_create" for e in entries)
            assert result["suggested_actions"][0]["text"] == "Explica el receptor seleccionado"


@pytest.mark.asyncio
async def test_unique_catalog_search_can_be_assigned_without_pdb_in_user_text(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    async def model(messages, tools):
        if messages[-1]["role"] == "user":
            name, args = "search_receptors", '{"query":"*","section":"verificado"}'
        elif json.loads(messages[-1]["content"]).get("receptors"):
            name, args = "assign_case_receptor", '{"case_name":"prueba","pdb_id":"7E2Y"}'
        else:
            assert json.loads(messages[-1]["content"])["status"] == "applied"
            return {"role": "assistant", "content": "Solicitud completada."}
        return {"role": "assistant", "content": None, "tool_calls": [{"id": name, "type": "function", "function": {"name": name, "arguments": args}}]}
    monkeypatch.setattr(registry.get("fake"), "chat_with_tools", model, raising=False)
    async def registry_for_turn(_token): return registry
    monkeypatch.setattr(state, "registro_de_turno", registry_for_turn)
    async def host(request):
        return httpx.Response(200, json=[{"pdb_id": "7E2Y", "name": "Receptor", "disponible": True, "seccion_catalogo": "verificado"}])
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(host)) as host_client:
        state.bridge = MolDesignBridge(client=host_client)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
            turn = asyncio.create_task(client.post("/v1/chat", headers=headers, json={"text": "asigna el único receptor verificado al caso prueba"}))
            for _ in range(200):
                if state.receptor_requests: break
                await asyncio.sleep(0.01)
            request_id = next(iter(state.receptor_requests))
            await client.post(f"/v1/receptor-requests/{request_id}/result", headers=headers, json={"status": "applied"})
            entries = events(await turn)
            assert any(e.get("type") == "case_receptor" and e["pdb_id"] == "7E2Y" for e in entries)
            assert "asignado y guardado" in next(e["result"]["text"] for e in entries if e["type"] == "result")


@pytest.mark.asyncio
async def test_chat_can_search_catalog_and_retain_receptor_identifier(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    async def model(messages, tools):
        if messages[-1]["role"] == "user":
            assert "search_receptors" in {item["function"]["name"] for item in tools}
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "find", "type": "function",
                "function": {"name": "search_receptors", "arguments": '{"query":"7E2Y"}'}}]}
        data = json.loads(messages[-1]["content"])
        assert data["receptors"][0]["seccion_catalogo"] == "demostracion"
        return {"role": "assistant", "content": "Encontré 7E2Y; está en demostración, sin calibración confirmada."}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    async def registry_for_turn(_token): return registry
    monkeypatch.setattr(state, "registro_de_turno", registry_for_turn)
    async def host(request):
        assert request.url.path == "/targets/" and request.headers["authorization"] == headers["Authorization"]
        return httpx.Response(200, json=[{"pdb_id": "7E2Y", "name": "Ejemplo", "disponible": True,
            "seccion_catalogo": "demostracion", "calibracion": None}])
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(host)) as host_client:
        state.bridge = MolDesignBridge(client=host_client)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
            response = await client.post("/v1/chat", headers=headers, json={"text": "busca 7E2Y"})
            result = next(e["result"] for e in events(response) if e["type"] == "result")
            assert "7E2Y" in result["text"] and result["evidence"][0]["tool"] == "search_receptors"
            assert (await client.get("/v1/harness-jobs", headers=headers)).json()[0]["steps"][0]["tool"] == "search_receptors"


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", [False, True])
@pytest.mark.parametrize("cid_arg", [702, "702"])
@pytest.mark.parametrize("bad_first", [False, True])
async def test_editor_verification_checks_revision_and_does_not_persist_molfile(tmp_path, monkeypatch, changed, cid_arg, bad_first):
    Chem = pytest.importorskip("rdkit.Chem")
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    molfile = Chem.MolToMolBlock(Chem.MolFromSmiles("CCO"))
    conv = state.memory.create_conversation("owner")
    state.memory.add_message(conv, "owner", "assistant", "Referencia", references=[{"cid": 702, "name": "Ethanol",
        "source": "https://pubchem.ncbi.nlm.nih.gov/compound/702", "properties": {"SMILES": "CCO"}}])
    async def model(messages, tools):
        if messages[-1]["role"] == "user":
            args = {"case_name": "prueba", "cid": cid_arg}
            if bad_first: args["smiles"] = "CCO"
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "verify", "type": "function",
                "function": {"name": "verify_editor_structure", "arguments": json.dumps(args)}}]}
        result = json.loads(messages[-1]["content"])
        if "error" in result:
            assert "case_name, cid" in result["error"] and "no se ejecutó" in result["error"]
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "verify-retry", "type": "function",
                "function": {"name": "verify_editor_structure", "arguments": json.dumps({"case_name": "prueba", "cid": cid_arg})}}]}
        if messages[-1].get("tool_call_id") == "suggest":
            assert result["status"] == "ok"
            return {"role": "assistant", "content": "Resultado de la comprobación."}
        assert result["status"] == ("changed" if changed else "match")
        assert "molfile" not in result
        return {"role": "assistant", "content": None, "tool_calls": [{"id": "suggest", "type": "function",
            "function": {"name": "suggest_next_actions", "arguments": '{"actions":[{"kind":"compare_with_moldesign","cid":702,"text":"Compara con MolDesign"},{"kind":"verify_drawing","cid":702,"text":"Verifica el dibujo"}]}'}}]}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        turn = asyncio.create_task(client.post("/v1/chat", headers=headers, json={"text": "verifica el dibujo en prueba con PubChem 702", "conversation_id": conv}))
        for _ in range(300):
            if state.editor_requests: break
            await asyncio.sleep(0.01)
        first = next(iter(state.editor_requests))
        assert (await client.post(f"/v1/editor-requests/{first}/result", headers=headers,
                                  json={"status": "ok", "molfile": molfile, "revision": "1:2"})).status_code == 200
        for _ in range(300):
            pending = [key for key in state.editor_requests if key != first]
            if pending: break
            await asyncio.sleep(0.01)
        assert pending
        await client.post(f"/v1/editor-requests/{pending[0]}/result", headers=headers,
                          json={"status": "changed" if changed else "ok"})
        result = next(e["result"] for e in events(await turn) if e["type"] == "result")
        assert {item["kind"] for item in result["suggested_actions"]} == ({"compare_with_moldesign", "verify_drawing"} if changed else {"compare_with_moldesign"})
        assert ("cambió durante" in result["text"]) == changed
        assert ("coincide con la referencia" in result["text"]) != changed
        if changed:
            assert "coincide exactamente" not in result["text"]
        def contains_molfile(value):
            if isinstance(value, str): return molfile in value
            if isinstance(value, dict): return any(contains_molfile(item) for item in value.values())
            if isinstance(value, (list, tuple)): return any(contains_molfile(item) for item in value)
            return False
        assert not contains_molfile(state.memory.get_conversation(conv, "owner").messages)
        assert not contains_molfile(state.memory.list_harness_jobs("owner"))
        assert not contains_molfile(list(state.structure_cache.values()))


@pytest.mark.asyncio
async def test_invalid_editor_call_cannot_be_presented_as_a_match(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    async def model(messages, _tools):
        if messages[-1]["role"] == "user":
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "verify", "type": "function",
                "function": {"name": "verify_editor_structure", "arguments": '{"case_name":"prueba2","cid":9887712,"extra":"valor"}'}}]}
        assert "no se ejecutó" in json.loads(messages[-1]["content"])["error"]
        return {"role": "assistant", "content": "El dibujo coincide exactamente con PubChem."}
    monkeypatch.setattr(registry.get("fake"), "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        response = await client.post("/v1/chat", headers=headers, json={"text": "verifica el dibujo del caso prueba2 con CID 9887712"})
        result = next(e["result"]["text"] for e in events(response) if e["type"] == "result")
        assert "No se pudo iniciar" in result and "coincide exactamente" not in result
        assert not state.editor_requests


@pytest.mark.asyncio
async def test_editor_verification_does_not_use_ambiguous_or_missing_reference(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    conv = state.memory.create_conversation("owner")
    state.memory.add_message(conv, "owner", "assistant", "elige", references=[
        {"cid": 702, "name": "one", "source": "https://pubchem.ncbi.nlm.nih.gov/compound/702", "properties": {"SMILES": "CCO"}},
        {"cid": 703, "name": "two", "source": "https://pubchem.ncbi.nlm.nih.gov/compound/703", "properties": {"SMILES": "CCC"}}])
    async def model(messages, _tools):
        if messages[-1]["role"] == "user":
            return {"role": "assistant", "content": None, "tool_calls": [{"id": "verify", "type": "function",
                "function": {"name": "verify_editor_structure", "arguments": '{"case_name":"prueba","cid":"702"}'}}]}
        assert json.loads(messages[-1]["content"])["status"] == "no_reference"
        return {"role": "assistant", "content": "Necesito una referencia."}
    monkeypatch.setattr(provider, "chat_with_tools", model, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))), base_url="http://testserver") as client:
        response = await client.post("/v1/chat", headers=headers, json={"text": "verifica", "conversation_id": conv})
        result = next(e["result"] for e in events(response) if e["type"] == "result")
        assert "referencia inequívoca" in result["text"]
        assert not state.editor_requests
