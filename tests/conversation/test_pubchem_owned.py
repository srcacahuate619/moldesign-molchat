import httpx
import pytest

from molchat_agent.bridge import MolDesignBridge
from molchat_agent.conversation.pubchem import PubChemError, search_compounds


@pytest.mark.asyncio
async def test_pubchem_is_queried_directly_after_account_permission():
    requests = []
    checks = []
    async def check():
        checks.append(True)
    async def handler(request):
        requests.append(str(request.url))
        assert request.url.host == "pubchem.ncbi.nlm.nih.gov"
        if "/name/" in request.url.path:
            return httpx.Response(200, json={"IdentifierList": {"CID": [2244]}})
        if "/property/" in request.url.path:
            return httpx.Response(200, json={"PropertyTable": {"Properties": [{"CID": 2244,
                "MolecularFormula": "C9H8O4", "MolecularWeight": "180.16"}]}})
        return httpx.Response(200, json={"InformationList": {"Information": [{"CID": 2244, "Title": "Aspirin"}]}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        result = await search_compounds("aspirina", client=client, authorize=check)
    assert len(checks) == len(requests) == 3
    assert result.matches[0].name == "Aspirin" and result.matches[0].cid == 2244
    assert result.matches[0].properties == {"MolecularFormula": "C9H8O4", "MolecularWeight": "180.16"}
    assert not result.truncated


@pytest.mark.asyncio
async def test_partial_properties_failure_preserves_identity():
    async def check():
        pass
    async def handler(request):
        if "/name/" in request.url.path:
            return httpx.Response(200, json={"IdentifierList": {"CID": [2244]}})
        if "/property/" in request.url.path:
            return httpx.Response(503)
        return httpx.Response(200, json={"InformationList": {"Information": [{"CID": 2244, "Title": "Aspirin"}]}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await search_compounds("aspirina", client=client, authorize=check)
    assert result.matches[0].name == "Aspirin"
    assert not result.matches[0].properties_available


@pytest.mark.asyncio
async def test_revoked_permission_prevents_further_requests():
    count = 0
    requests = []
    async def check():
        nonlocal count
        count += 1
        if count == 2:
            raise PermissionError("revocado")
    async def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"IdentifierList": {"CID": [2244]}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(PermissionError):
            await search_compounds("aspirina", client=client, authorize=check)
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_not_found_is_different_from_source_failure():
    async def check():
        pass
    for code in (404, 503):
        async def handler(_request):
            return httpx.Response(code)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            if code == 404:
                assert not (await search_compounds("unknown", client=client, authorize=check)).matches
            else:
                with pytest.raises(PubChemError):
                    await search_compounds("unknown", client=client, authorize=check)


@pytest.mark.asyncio
@pytest.mark.parametrize("offline,consented,allowed", [(False, True, True), (True, True, False),
                                                         (False, False, False), (None, True, False)])
async def test_permission_is_scoped_to_host_session(offline, consented, allowed):
    async def handler(request):
        assert request.url.path == "/ai/consent/red"
        assert request.headers["Authorization"] == "Bearer account-token"
        return httpx.Response(200, json={"modo_offline": offline, "destinos": [{
            "servicio": "pubchem", "host": "pubchem.ncbi.nlm.nih.gov", "consentido": consented}]})
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(handler)) as client:
        bridge = MolDesignBridge(client=client, token="account-token")
        if allowed:
            await bridge.authorize_pubchem()
        else:
            with pytest.raises(PermissionError):
                await bridge.authorize_pubchem()
