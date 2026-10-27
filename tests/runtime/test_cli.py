"""local-llm CLI: models, status and download wiring (no subprocess here)."""

import pytest

from molchat_agent.cli import _dispatch, build_parser


def _args(*argv):
    return build_parser().parse_args(list(argv))


@pytest.mark.asyncio
async def test_models_lists_installed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    models = tmp_path / "models" / "llm"
    models.mkdir(parents=True)
    (models / "tiny.gguf").write_bytes(b"x")
    assert await _dispatch(_args("local-llm", "models")) == 0
    assert "tiny.gguf" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_models_empty_reports_plainly(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("molchat_agent.runtime.models.Path.home",
                        lambda: tmp_path / "home")
    assert await _dispatch(_args("local-llm", "models")) == 0
    assert "Sin modelos" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_status_reports_down_without_server(capsys):
    assert await _dispatch(_args("local-llm", "status", "--port", "8499")) == 1
    assert "sin respuesta" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_download_rejects_plain_http(tmp_path):
    with pytest.raises(Exception, match="https"):
        await _dispatch(_args("local-llm", "download", "http://x/m.gguf",
                              "--out", str(tmp_path / "m.gguf")))
