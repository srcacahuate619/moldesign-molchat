"""Cloud STT: explicit https contract, caps, failures (mocked, live-pending)."""

import httpx
import pytest

from molchat_agent.voice import CloudSTT, STTError


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_transcribes_via_audio_transcriptions_multipart():
    observed = {}

    def handle(request):
        assert request.url.host == "stt.example.com"
        assert request.url.path == "/v1/audio/transcriptions"
        assert request.headers["authorization"] == "Bearer test-key"
        assert "multipart/form-data" in request.headers["content-type"]
        observed["body"] = request.content
        return httpx.Response(200, json={"text": "abrir el caso"})

    async with _client(handle) as client:
        async with CloudSTT(base_url="https://stt.example.com/v1",
                            api_key="test-key", model="whisper-1",
                            client=client) as stt:
            assert stt.destination == "stt.example.com"
            assert await stt.transcribe(b"RIFF-test-audio", lang="es") == "abrir el caso"
    assert b"whisper-1" in observed["body"]
    assert b'"es"' in observed["body"] or b"es" in observed["body"]


@pytest.mark.asyncio
async def test_http_error_and_bad_shape_are_stt_errors():
    async with _client(lambda r: httpx.Response(500, json={})) as client:
        stt = CloudSTT(base_url="https://stt.example.com/v1", api_key="test-key",
                       model="w", client=client)
        with pytest.raises(STTError):
            await stt.transcribe(b"RIFF-x")
    async with _client(lambda r: httpx.Response(200, json={"text": 42})) as client:
        stt = CloudSTT(base_url="https://stt.example.com/v1", api_key="test-key",
                       model="w", client=client)
        with pytest.raises(STTError):
            await stt.transcribe(b"RIFF-x")


def test_constructor_rejects_plain_http_missing_key_or_model():
    with pytest.raises(ValueError, match="https"):
        CloudSTT(base_url="http://stt.example.com/v1", api_key="test-key", model="w")
    with pytest.raises(ValueError, match="clave"):
        CloudSTT(base_url="https://stt.example.com/v1", api_key="", model="w")
    with pytest.raises(ValueError, match="modelo"):
        CloudSTT(base_url="https://stt.example.com/v1", api_key="test-key", model=" ")


@pytest.mark.asyncio
async def test_caps_and_languages():
    async with _client(lambda r: httpx.Response(200, json={"text": "x"})) as client:
        stt = CloudSTT(base_url="https://stt.example.com/v1", api_key="test-key",
                       model="w", client=client)
        with pytest.raises(ValueError, match="15 MB"):
            await stt.transcribe(b"")
        with pytest.raises(ValueError, match="es/en"):
            await stt.transcribe(b"RIFF-x", lang="fr")
