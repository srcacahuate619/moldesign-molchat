"""Model files: find, resolve, download with cap and hash."""

import hashlib

import httpx
import pytest

from molchat_agent.runtime.models import (
    ModelError,
    download_model,
    find_models,
    resolve_model,
)


def test_find_and_resolve_models(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("molchat_agent.runtime.models.Path.home",
                        lambda: tmp_path / "home")
    home_models = tmp_path / "home" / ".molchat" / "models"
    home_models.mkdir(parents=True)
    (home_models / "b.gguf").write_bytes(b"b" * 10)
    local = tmp_path / "models" / "llm"
    local.mkdir(parents=True)
    (local / "a.gguf").write_bytes(b"a")
    found = find_models()
    assert [m.name for m in found] == ["a.gguf", "b.gguf"]
    assert resolve_model("b.gguf") == home_models / "b.gguf"
    explicit = tmp_path / "x.gguf"
    explicit.write_bytes(b"x")
    assert resolve_model(explicit) == explicit
    with pytest.raises(ModelError, match="no encontrado"):
        resolve_model("missing.gguf")


def test_download_streams_with_cap_and_hash(tmp_path):
    payload = b"GGUF" * 1000
    digest = hashlib.sha256(payload).hexdigest()

    def handle(_request):
        return httpx.Response(200, content=payload,
                              headers={"Content-Length": str(len(payload))})

    dest = tmp_path / "models" / "m.gguf"
    out = download_model("https://example.com/m.gguf", dest, sha256_hex=digest,
                         transport=httpx.MockTransport(handle))
    assert out == dest and dest.read_bytes() == payload
    with pytest.raises(ModelError, match="SHA-256"):
        download_model("https://example.com/m.gguf", tmp_path / "bad.gguf",
                       sha256_hex="0" * 64, transport=httpx.MockTransport(handle))
    assert not (tmp_path / "bad.gguf").exists()
    with pytest.raises(ModelError, match="tope"):
        download_model("https://example.com/m.gguf", tmp_path / "big.gguf",
                       max_bytes=10, transport=httpx.MockTransport(handle))
    with pytest.raises(ModelError, match="https"):
        download_model("http://example.com/m.gguf", tmp_path / "x.gguf")
