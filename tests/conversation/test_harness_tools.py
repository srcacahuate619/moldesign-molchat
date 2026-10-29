import json
import httpx
import pytest

from molchat_agent.bridge import MolDesignBridge
from molchat_agent.conversation.harness_tools import create_case_tool, pubchem_tool
from molchat_agent.conversation.tool_loop import run_tool_loop


@pytest.mark.asyncio
async def test_harness_reads_pubchem_directly_and_returns_result_to_model():
    host_paths = []
    external_paths = []
    async def host(request):
        host_paths.append(request.url.path)
        return httpx.Response(200, json={"modo_offline": False, "destinos": [{
            "servicio": "pubchem", "host": "pubchem.ncbi.nlm.nih.gov", "consentido": True}]})
    async def public(request):
        external_paths.append(request.url.path)
        if "/name/" in request.url.path:
            return httpx.Response(200, json={"IdentifierList": {"CID": [2244]}})
        return httpx.Response(200, json={"InformationList": {"Information": [{"CID": 2244, "Title": "Aspirin"}]}})
    class Provider:
        async def chat_with_tools(self, messages, schemas):
            if messages[-1]["role"] == "user":
                assert schemas[0]["function"]["name"] == "pubchem_lookup"
                return {"role": "assistant", "content": None, "tool_calls": [{"id": "call-1", "type": "function",
                        "function": {"name": "pubchem_lookup", "arguments": '{"name":"aspirina"}'}}]}
            assert messages[0]["content"] == "Busca aspirina"
            assert json.loads(messages[-1]["content"])["matches"][0]["name"] == "Aspirin"
            return {"role": "assistant", "content": "Encontré una referencia en PubChem."}
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(host)) as host_client, \
               httpx.AsyncClient(transport=httpx.MockTransport(public), trust_env=False) as public_client:
        bridge = MolDesignBridge(token="account-token", client=host_client)
        result = await run_tool_loop(Provider(), [{"role": "user", "content": "Busca aspirina"}],
                                     [pubchem_tool(bridge, public_client)])
    assert "PubChem" in result.text
    assert host_paths == ["/ai/consent/red", "/ai/consent/red"]
    assert len(external_paths) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["created", "exists", "failed", "unknown"])
async def test_case_result_comes_from_product_bridge(status):
    calls = []
    async def request_case(name):
        calls.append(name)
        return {"status": status}
    result = await create_case_tool(request_case).execute({"name": "hola"})
    assert result == {"status": status, "name": "hola"}
    assert calls == ["hola"]
