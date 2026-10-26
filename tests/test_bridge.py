import json

import httpx
import pytest

from molchat_agent.bridge import BridgeError, MolDesignBridge, validate_base_url


@pytest.mark.parametrize("url", [
    "http://intranet.example:8000", "https://intranet.example",
    "file:///etc/passwd", "http://user:password@127.0.0.1:8000",
    "http://127.0.0.1:8000/ai", "http://127.0.0.1:8000?next=evil",
])
def test_deny_unsafe_base_urls_by_default(url):
    with pytest.raises(ValueError):
        validate_base_url(url)


def test_remote_requires_explicit_optin_and_tls():
    assert validate_base_url("https://lab.example", allow_remote=True) == "https://lab.example"
    with pytest.raises(ValueError):
        validate_base_url("http://lab.example", allow_remote=True)


@pytest.mark.asyncio
async def test_bridge_uses_existing_contract_and_bearer_token():
    seen = []

    def handle(request):
        seen.append((request.method, request.url.path, request.headers.get("Authorization")))
        return httpx.Response(200, json={"blocking": False})

    transport = httpx.MockTransport(handle)
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=transport) as client:
        bridge = MolDesignBridge(token="secret_local", client=client)
        result = await bridge.call("check_preflight", {"smiles": "CCO", "target_pdb_id": "1HSG"})
    assert result == {"blocking": False}
    assert seen == [("POST", "/evaluation/preflight", "Bearer secret_local")]


@pytest.mark.asyncio
async def test_bridge_refuses_redirect_and_does_not_follow():
    seen = []

    def handle(request):
        seen.append(request.url.path)
        return httpx.Response(302, headers={"Location": "https://elsewhere.example/collect"})

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000",
                                 transport=httpx.MockTransport(handle),
                                 follow_redirects=False) as client:
        bridge = MolDesignBridge(token="secret", client=client)
        with pytest.raises(BridgeError, match="redirección"):
            await bridge.call("list_targets", {})
    assert seen == ["/targets/"]


@pytest.mark.asyncio
async def test_approval_requires_authenticated_session():
    bridge = MolDesignBridge()
    try:
        with pytest.raises(BridgeError, match="sesión autenticada"):
            await bridge.call("approve_docking_proposal", {
                "proposal_id": "proposal123", "proposal_hash": "sha256:" + "a" * 64,
            })
    finally:
        await bridge.__aexit__()


@pytest.mark.asyncio
async def test_voice_uses_local_endpoint_only_and_returns_transcript():
    def handle(request):
        assert request.url.path == "/ai/speech-to-text"
        assert request.headers["content-type"] == "audio/wav"
        assert request.url.params["lang"] == "es"
        assert request.content == b"RIFF-valid-demo"
        return httpx.Response(200, json={"text": "Preparar el receptor", "lang": "es"})

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000",
                                 transport=httpx.MockTransport(handle)) as client:
        bridge = MolDesignBridge(token="test", client=client)
        assert await bridge.transcribe_local(b"RIFF-valid-demo") == "Preparar el receptor"

