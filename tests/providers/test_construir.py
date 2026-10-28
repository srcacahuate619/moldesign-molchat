"""La fábrica de adaptadores: cada proveedor del catálogo recibe SU clave y SU URL."""

import pytest

from molchat_agent.config import load_config
from molchat_agent.providers import catalogo
from molchat_agent.providers.registry import build_registry, construir


def test_openai_usa_su_url_y_su_id_y_no_hereda_otras_claves():
    entrada = catalogo.por_id("openai")
    proveedor = construir(entrada, config=load_config({"OPENAI_COMPAT_API_KEY": "otra"}))
    assert proveedor.id == "openai"
    assert proveedor.config.base_url == "https://api.openai.com/v1"
    assert proveedor.config.api_key == ""  # sin clave propia: nunca la de otro proveedor


def test_deepseek_solo_llega_a_su_host():
    proveedor = construir(catalogo.por_id("deepseek"), api_key="test-deepseek-1234567890")
    assert proveedor.config.base_url == "https://api.deepseek.com"
    assert proveedor.config.api_key == "test-deepseek-1234567890"


def test_cada_clave_del_entorno_va_a_su_proveedor():
    registro = build_registry(load_config({
        "OPENAI_API_KEY": "sk-openai-aaaaaaaa",
        "DEEPSEEK_API_KEY": "sk-deepseek-bbbbbbbb",
        "ANTHROPIC_API_KEY": "sk-ant-cccccccc",
    }))
    assert registro.get("openai").config.api_key == "sk-openai-aaaaaaaa"
    assert registro.get("deepseek").config.api_key == "sk-deepseek-bbbbbbbb"
    assert registro.get("anthropic").config.api_key == "sk-ant-cccccccc"
    assert registro.get("nvidia").config.api_key == ""


def test_local_toma_la_url_del_entorno_y_remoto_no():
    registro = build_registry(load_config({"OLLAMA_URL": "http://127.0.0.1:9999"}))
    assert registro.get("ollama").config.base_url == "http://127.0.0.1:9999"
    registro = build_registry(load_config({"OPENAI_COMPAT_BASE_URL": "https://evil.example/v1"}))
    assert registro.get("openai").config.base_url == "https://api.openai.com/v1"


@pytest.mark.parametrize("proveedor", [p.id for p in catalogo.ENTRADAS])
def test_todo_proveedor_del_catalogo_se_registra(proveedor):
    registro = build_registry(load_config({}))
    assert type(registro.get(proveedor)).__name__ != "BrokenProvider"
