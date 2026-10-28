from pathlib import Path

import pytest

from molchat_agent.config import (
    DEFAULT_PROFILE,
    HACKATHON_PROFILE,
    MolChatConfig,
    load_config,
)


def test_defaults_are_safe_and_product_first():
    config = load_config({})
    assert config.profile == "default"
    assert config.moldesign_base_url == "http://127.0.0.1:8000"
    assert config.moldesign_token is None
    assert config.moldesign_allow_remote is False
    assert config.meta_model == "muse-spark-1.3"
    assert config.meta_reasoning_effort == "medium"
    assert config.openai_compat_base_url == ""
    assert config.llama_server_url == "http://127.0.0.1:8400/v1"
    assert config.ollama_url == "http://127.0.0.1:11434"
    assert config.offline is False


def test_environment_overrides_and_empty_means_unset():
    config = load_config({
        "MOLDESIGN_BASE_URL": "https://lab.example ",
        "MOLDESIGN_TOKEN": "  ",
        "MOLDESIGN_ALLOW_REMOTE": "1",
        "MOLCHAT_PROFILE": DEFAULT_PROFILE,
        "MOLCHAT_PROVIDER": "fake",
        "MODEL_API_KEY": "key-1",
        "META_MODEL": "muse-spark-1.3",
        "META_REASONING_EFFORT": "high",
        "OLLAMA_MODEL": "gemma3:1b",
        "MOLCHAT_CONSENTS_FILE": "/tmp/c.json",
        "MOLCHAT_OFFLINE": "1",
    })
    assert config.moldesign_base_url == "https://lab.example"
    assert config.moldesign_token is None
    assert config.moldesign_allow_remote is True
    assert config.profile == DEFAULT_PROFILE
    assert config.provider == "fake"
    assert config.model_api_key == "key-1"
    assert config.meta_reasoning_effort == "high"
    assert config.ollama_model == "gemma3:1b"
    assert config.consents_file == Path("/tmp/c.json")
    assert config.offline is True


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError, match="MOLCHAT_PROFILE"):
        load_config({"MOLCHAT_PROFILE": "nasa"})


def test_redacted_never_contains_secret_values():
    config = load_config({"MODEL_API_KEY": "super-secret", "MOLDESIGN_TOKEN": "tok"})
    summary = MolChatConfig.redacted(config)
    assert summary["model_api_key"] == "set"
    assert summary["moldesign_token"] == "set"
    assert "super-secret" not in str(summary)
    assert summary["meta_model"] == "muse-spark-1.3"


def test_server_session_settings():
    config = load_config({"MOLCHAT_HOST_SECRET": "test-secret",
                          "MOLCHAT_ALLOWED_ORIGINS": "https://a.example, https://b.example",
                          "MOLCHAT_SESSION_TTL_S": "120"})
    assert config.redacted()["host_secret"] == "set"
    assert config.allowed_origins == ("https://a.example", "https://b.example")
    assert config.session_ttl_s == 120
    defaults = load_config({})
    assert defaults.host_secret is None
    assert defaults.allowed_origins == ()
    assert defaults.session_ttl_s == 3600
    with pytest.raises(ValueError, match="entero"):
        load_config({"MOLCHAT_SESSION_TTL_S": "pronto"})
    with pytest.raises(ValueError, match="positivo"):
        load_config({"MOLCHAT_SESSION_TTL_S": "0"})
