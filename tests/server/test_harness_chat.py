import asyncio
import json
from pathlib import Path

import httpx
import pytest

from molchat_agent.config import MolChatConfig
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
            assert {t["function"]["name"] for t in tools} == {"pubchem_lookup", "create_case", "compute_properties", "load_case_smiles"}
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
        assert ("confirmó que el SMILES" in answer) == (status == "applied")
        assert (await client.post(f"/v1/smiles-requests/{request_id}/result", headers=headers, json={"status": status})).status_code == 404
