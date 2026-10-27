"""Local STT fallback and chain (supervisor completion, Fase 4 gate).

The platform Whisper endpoint of the review instance answered 501 (no
faster-whisper in that build); the sidecar must still transcribe locally.
These tests use a fake model factory: no model download, no audio files.
"""

from dataclasses import dataclass

import pytest

from molchat_agent.bridge import BridgeError
from molchat_agent.voice.local_whisper import ChainSTT, LocalWhisperSTT


@dataclass
class _Segment:
    text: str


class _FakeModel:
    def __init__(self, *args, **kwargs):
        self.calls = []

    def transcribe(self, stream, language=None, **kwargs):
        self.calls.append((language, kwargs.get("initial_prompt")))
        return [_Segment("lista los "), _Segment("receptores")], object()


@pytest.mark.asyncio
async def test_local_whisper_joins_segments():
    stt = LocalWhisperSTT(model_factory=_FakeModel)
    assert await stt.transcribe(b"RIFF-fake-audio", lang="es") == "lista los receptores"
    _language, prompt = stt._model.calls[-1]
    assert "SMILES" in prompt  # chemical decoder bias travels with the call


@pytest.mark.asyncio
async def test_local_whisper_validates_before_loading():
    def forbidden_factory(*args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("no debe cargar el modelo")

    stt = LocalWhisperSTT(model_factory=forbidden_factory)
    with pytest.raises(ValueError, match="vacío"):
        await stt.transcribe(b"")
    with pytest.raises(ValueError, match="es/en"):
        await stt.transcribe(b"RIFF", lang="fr")


class _Failing:
    def __init__(self, exc):
        self._exc = exc

    async def transcribe(self, audio_bytes, *, lang="es"):
        raise self._exc


class _Ok:
    async def transcribe(self, audio_bytes, *, lang="es"):
        return "texto"


@pytest.mark.asyncio
async def test_chain_falls_back_when_platform_cannot():
    chain = ChainSTT([_Failing(BridgeError("HTTP 501")), _Ok()])
    assert await chain.transcribe(b"RIFF") == "texto"


@pytest.mark.asyncio
async def test_chain_propagates_last_error_when_all_fail():
    chain = ChainSTT([_Failing(BridgeError("HTTP 501")),
                      _Failing(ValueError("audio vacío"))])
    with pytest.raises(ValueError, match="vacío"):
        await chain.transcribe(b"RIFF")


@pytest.mark.asyncio
async def test_chain_first_success_wins():
    chain = ChainSTT([_Ok(), _Failing(AssertionError("no debe llamarse"))])
    assert await chain.transcribe(b"RIFF") == "texto"
