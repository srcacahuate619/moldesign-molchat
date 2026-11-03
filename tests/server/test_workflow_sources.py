"""A plan remembers which PubChem lookup each SMILES came from, across lookups and across turns.

Each lookup used to replace the previous one, so a plan built over twelve lookups kept only the last: the notebook
could not cite a single CID. Now every lookup of the conversation is kept (identity only) and the plan links each
molecule to the lookup whose SMILES matches literally.
"""
import json

import httpx
import pytest

from molchat_agent.server.app import create_app
from tests.server.test_harness_chat import events, state_for

COMPOUNDS = {"etanol": (702, "Ethanol", "CCO"), "propanol": (1031, "1-Propanol", "CCCO")}


def call(name, args, n):
    return {"id": f"c{n}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


@pytest.mark.asyncio
async def test_each_molecule_of_the_plan_keeps_the_cid_it_came_from(tmp_path, monkeypatch):
    state, registry, headers = state_for(tmp_path)
    provider = registry.get("fake")
    script = {
        "busca etanol": [call("pubchem_lookup", {"name": "etanol"}, 1)],
        "busca propanol y evalúa la lista": [
            call("pubchem_lookup", {"name": "propanol"}, 2),
            call("propose_iteration", {"case_name": "c", "pdb_id": "8T69", "threshold_kcal": -9.0,
                                       "molecules": [{"name": "etanol", "smiles": "CCO"}, {"name": "propanol", "smiles": "CCCO"},
                                                     {"name": "inventada", "smiles": "CCCCO"}]}, 3)],
    }

    async def model(messages, tools):
        last_user = max(i for i, m in enumerate(messages) if m["role"] == "user")
        pending = script.get(messages[last_user]["content"], [])
        answered = sum(1 for m in messages[last_user:] if m["role"] == "tool")  # one tool call per step, in order
        if answered < len(pending):
            return {"role": "assistant", "content": None, "tool_calls": [pending[answered]]}
        return {"role": "assistant", "content": "Hecho."}

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
        name = request.url.path.split("/")[5] if "/name/" in request.url.path else None
        if name:
            return httpx.Response(200, json={"IdentifierList": {"CID": [COMPOUNDS[name][0]]}})
        cid = int(request.url.path.split("/")[5].split(",")[0])
        compound = next(v for v in COMPOUNDS.values() if v[0] == cid)
        if "/property/" in request.url.path:
            return httpx.Response(200, json={"PropertyTable": {"Properties": [{"CID": cid, "SMILES": compound[2]}]}})
        return httpx.Response(200, json={"InformationList": {"Information": [{"CID": cid, "Title": compound[1]}]}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(public)) as external:
        state.pubchem_client = external
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(state, allowed_hosts=("testserver",))),
                                     base_url="http://testserver") as client:
            first = events(await client.post("/v1/chat", headers=headers, json={"text": "busca etanol"}))
            conv_id = next(e["id"] for e in first if e["type"] == "conversation")
            await client.post("/v1/chat", headers=headers, json={"text": "busca propanol y evalúa la lista", "conversation_id": conv_id})

    (workflow,) = state.workflows.values()
    by_name = dict(zip((m.name for m in workflow.spec.molecules), workflow.sources))
    assert by_name["etanol"]["cid"] == 702 and by_name["etanol"]["query"] == "etanol"  # looked up in the previous turn
    assert by_name["propanol"]["cid"] == 1031 and by_name["propanol"]["match"] == "exact"  # looked up in this turn
    assert by_name["inventada"] is None  # no lookup gave this SMILES: the notebook says so, it does not guess
    # what the conversation keeps is identity only, small
    stored = [m for m in state.memory.get_conversation(conv_id, "owner").messages if m.get("pubchem_lookups")]
    assert [m["pubchem_lookups"][0]["query"] for m in stored] == ["etanol", "propanol"]
    assert set(stored[0]["pubchem_lookups"][0]["matches"][0]["properties"]) == {"SMILES"}
