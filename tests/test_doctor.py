"""doctor: report, grant, and revoke without leaking secrets."""

import pytest

from molchat_agent.cli import _dispatch, build_parser

ENV_VARS = ("MOLDESIGN_BASE_URL", "MOLDESIGN_TOKEN", "MOLDESIGN_ALLOW_REMOTE",
            "MOLCHAT_PROFILE", "MOLCHAT_PROVIDER", "MODEL_API_KEY", "META_MODEL",
            "META_REASONING_EFFORT", "OPENAI_COMPAT_BASE_URL",
            "OPENAI_COMPAT_API_KEY", "OPENAI_COMPAT_MODEL", "LLAMA_SERVER_URL",
            "LLAMA_SERVER_MODEL", "OLLAMA_URL", "OLLAMA_MODEL",
            "MOLCHAT_CONSENTS_FILE", "MOLCHAT_OFFLINE")


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MOLCHAT_CONSENTS_FILE", str(tmp_path / "c.json"))
    return tmp_path


def _args(*argv):
    return build_parser().parse_args(list(argv))


@pytest.mark.asyncio
async def test_doctor_reports_without_backend_or_keys(clean_env, capsys):
    assert await _dispatch(_args("doctor")) == 0
    out = capsys.readouterr().out
    assert "Perfil: default" in out
    assert "fake [local]" in out
    assert "meta [remote]" in out
    assert "model_api_key: unset" in out
    assert "Puente MolDesign:" in out


@pytest.mark.asyncio
async def test_doctor_never_prints_secret_values(clean_env, monkeypatch, capsys):
    monkeypatch.setenv("MODEL_API_KEY", "super-secret-value")
    monkeypatch.setenv("MOLDESIGN_TOKEN", "token-secret-value")
    assert await _dispatch(_args("doctor")) == 0
    out = capsys.readouterr().out
    assert "super-secret-value" not in out
    assert "token-secret-value" not in out
    assert "model_api_key: set" in out


@pytest.mark.asyncio
async def test_grant_and_revoke_roundtrip(clean_env, capsys):
    assert await _dispatch(_args("doctor", "--grant-consent", "meta@api.meta.ai")) == 0
    assert "Autorizado meta@api.meta.ai" in capsys.readouterr().out
    assert await _dispatch(_args("doctor", "--consents")) == 0
    out = capsys.readouterr().out
    assert "meta@api.meta.ai" in out
    assert "Frontera de datos" in out
    assert await _dispatch(_args("doctor", "--revoke", "meta")) == 0
    assert "meta@api.meta.ai" in capsys.readouterr().out
    assert await _dispatch(_args("doctor", "--revoke", "meta")) == 0
    assert "no tenía consentimientos" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_grant_rejects_wrong_fingerprint(clean_env):
    with pytest.raises(ValueError, match="no coincide"):
        await _dispatch(_args("doctor", "--grant-consent", "meta@evil.example"))


@pytest.mark.asyncio
async def test_grant_content_requires_destination_first(clean_env, capsys):
    with pytest.raises(ValueError, match="Autoriza primero el destino"):
        await _dispatch(_args("doctor", "--grant-content", "meta@api.meta.ai"))
    assert await _dispatch(_args("doctor", "--grant-consent", "meta@api.meta.ai")) == 0
    capsys.readouterr()
    assert await _dispatch(_args("doctor", "--grant-content", "meta@api.meta.ai")) == 0
    out = capsys.readouterr().out
    assert "Autorizado contenido científico a meta@api.meta.ai" in out
    assert "Revócalo con --revoke meta" in out
    assert await _dispatch(_args("doctor", "--consents")) == 0
    out = capsys.readouterr().out
    assert "meta@api.meta.ai+history [+history]" in out
    assert await _dispatch(_args("doctor", "--revoke", "meta")) == 0
    assert "meta@api.meta.ai+history" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_grant_rejects_local_providers(clean_env):
    with pytest.raises(ValueError, match="nada que autorizar"):
        await _dispatch(_args("doctor", "--grant-consent", "fake@"))


@pytest.mark.asyncio
async def test_invalid_config_fails_doctor(clean_env, monkeypatch):
    monkeypatch.setenv("MOLCHAT_PROFILE", "nasa")
    with pytest.raises(ValueError, match="MOLCHAT_PROFILE"):
        await _dispatch(_args("doctor"))
