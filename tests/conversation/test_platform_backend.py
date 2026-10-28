"""El chat usa el contrato real y nunca sustituye una respuesta por fixtures."""
import httpx
import pytest

from molchat_agent.bridge import MolDesignBridge
from molchat_agent.conversation.tools import PlatformBackend, ToolError


@pytest.mark.asyncio
async def test_propiedades_contrato_e_identidad_por_peticion():
    requests = []
    async def responder(request):
        requests.append((request.url.path, request.headers.get('authorization')))
        if request.url.path == '/molchat-host/contract':
            return httpx.Response(200, json={'contract': 'moldesign.molchat/1', 'capabilities': ['properties/1']})
        return httpx.Response(200, json={
            'contract': 'properties/1', 'canonical_smiles': 'CCOC(=O)c1ccccc1',
            'source': 'MolDesign / RDKit test', 'warnings': [],
            'properties': {'mw': 150.17, 'logp': 1.2, 'tpsa': 26.3,
                           'hbd': 0, 'hba': 2, 'rot_bonds': 3, 'heavy_atoms': 11, 'rings': 1},
        })
    async with httpx.AsyncClient(transport=httpx.MockTransport(responder), base_url='http://127.0.0.1:1234') as c:
        bridge = MolDesignBridge(client=c)
        record = await PlatformBackend(bridge.with_token('sesion-a')).properties('CCOC(=O)c1ccccc1')
    assert record.props['mw'] == 150.17
    assert record.source == 'MolDesign / RDKit test'
    assert requests == [('/molchat-host/contract', 'Bearer sesion-a'),
                        ('/molchat-host/properties', 'Bearer sesion-a')]


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [
    {'contract': 'moldesign.molchat/2', 'capabilities': ['properties/1']},
    {'contract': 'moldesign.molchat/1', 'capabilities': []},
])
async def test_contrato_desconocido_no_calcula_ni_finge(payload):
    async def responder(request):
        assert request.url.path == '/molchat-host/contract'
        return httpx.Response(200, json=payload)
    async with httpx.AsyncClient(transport=httpx.MockTransport(responder), base_url='http://127.0.0.1:1234') as c:
        with pytest.raises(ToolError):
            await PlatformBackend(MolDesignBridge(client=c, token='test-session')).properties('CCO')


@pytest.mark.asyncio
async def test_una_accion_no_puede_ejecutarse_con_contrato_desconocido():
    from molchat_agent.bridge import BridgeError
    requests = []
    async def responder(request):
        requests.append(request.url.path)
        return httpx.Response(200, json={'contract': 'moldesign.molchat/2', 'capabilities': ['platform-actions/1']})
    async with httpx.AsyncClient(transport=httpx.MockTransport(responder), base_url='http://127.0.0.1:1234') as c:
        bridge = MolDesignBridge(client=c, token='test-session')
        with pytest.raises(BridgeError):
            await bridge.call('list_targets', {})
    assert requests == ['/molchat-host/contract']
