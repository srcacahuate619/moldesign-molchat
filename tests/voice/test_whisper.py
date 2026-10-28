"""MolDesign Whisper backend: contract, caps, failures."""

import httpx
import pytest

from molchat_agent.voice import MolDesignWhisper, STTError


@pytest.mark.asyncio
async def test_no_transcribe_si_el_contrato_no_es_compatible():
    calls = []
    async def responder(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={'text': 'no debería llegar'})
    async def incompatible():
        raise STTError('contrato incompatible')
    async with httpx.AsyncClient(transport=httpx.MockTransport(responder), base_url='http://127.0.0.1') as client:
        with pytest.raises(STTError, match='contrato'):
            await MolDesignWhisper(client, 'test-token', ensure_contract=incompatible).transcribe(b'RIFF-x')
    assert calls == []


def _client(handler):
    return httpx.AsyncClient(base_url="http://127.0.0.1:8000",
                             transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_transcribes_with_auth_and_wav_content_type():
    def handle(request):
        assert request.url.path == "/ai/speech-to-text"
        assert request.url.params["lang"] == "es"
        assert request.headers["authorization"] == "Bearer test-token-1"
        assert request.headers["content-type"] == "audio/wav"
        assert request.content == b"RIFF-test-audio"
        return httpx.Response(200, json={"text": "abrir el caso", "lang": "es"})

    async with _client(handle) as client:
        stt = MolDesignWhisper(client, "test-token-1")
        assert await stt.transcribe(b"RIFF-test-audio") == "abrir el caso"


@pytest.mark.asyncio
async def test_http_error_and_bad_shape_are_stt_errors():
    async with _client(lambda r: httpx.Response(500, json={})) as client:
        with pytest.raises(STTError):
            await MolDesignWhisper(client, "test-token-1").transcribe(b"RIFF-x")
    async with _client(lambda r: httpx.Response(200, json={"text": 42})) as client:
        with pytest.raises(STTError):
            await MolDesignWhisper(client, "test-token-1").transcribe(b"RIFF-x")


@pytest.mark.asyncio
async def test_caps_and_languages():
    async with _client(lambda r: httpx.Response(200, json={"text": "x"})) as client:
        stt = MolDesignWhisper(client, "test-token-1")
        with pytest.raises(ValueError, match="15 MB"):
            await stt.transcribe(b"")
        with pytest.raises(ValueError, match="15 MB"):
            await stt.transcribe(b"x" * (15_000_000 + 1))
        with pytest.raises(ValueError, match="es/en"):
            await stt.transcribe(b"RIFF-x", lang="fr")
