"""Catálogo de proveedores: la URL la pone MolChat, y sólo lo que cumple el contrato entra."""

import json

import pytest

from molchat_agent.providers import catalogo


def _escribir(tmp_path, entradas):
    ruta = tmp_path / "catalogo.json"
    ruta.write_text(json.dumps({"schema": catalogo.ESQUEMA, "proveedores": entradas}),
                    encoding="utf-8")
    return ruta


BASE = {"nombre": "x", "familia": "openai_chat", "base_url": "https://api.openai.com/v1",
        "requiere_clave": True, "remoto": True}


def test_el_catalogo_de_la_llave_es_valido_y_openai_va_primero():
    entradas = catalogo.cargar()
    assert entradas[0].id == "openai"
    assert entradas[0].host == "api.openai.com"


def test_deepseek_solo_usa_su_propio_host_y_los_locales_son_loopback():
    deepseek = catalogo.por_id("deepseek")
    assert deepseek is not None and deepseek.host == "api.deepseek.com"
    for local in ("llama-server", "ollama"):
        entrada = catalogo.por_id(local)
        assert entrada is not None and not entrada.remoto and not entrada.requiere_clave
        assert entrada.host in ("127.0.0.1", "localhost")


def test_toda_familia_del_catalogo_tiene_adaptador():
    assert {e.familia for e in catalogo.ENTRADAS} <= catalogo.FAMILIAS


def test_un_proveedor_remoto_no_puede_ir_por_http_ni_a_loopback(tmp_path):
    for base in ("http://api.openai.com/v1", "https://127.0.0.1/v1"):
        ruta = _escribir(tmp_path, [{"id": "x1", **BASE, "base_url": base}])
        with pytest.raises(ValueError):
            catalogo.cargar(ruta)


def test_rechaza_familia_sin_adaptador_id_repetido_y_local_remoto(tmp_path):
    with pytest.raises(ValueError):
        catalogo.cargar(_escribir(tmp_path, [{"id": "x1", **BASE, "familia": "magia"}]))
    with pytest.raises(ValueError):
        catalogo.cargar(_escribir(tmp_path, [{"id": "x1", **BASE}, {"id": "x1", **BASE}]))
    local = {"id": "x2", **BASE, "remoto": False, "requiere_clave": False,
             "base_url": "http://10.0.0.5:8400/v1"}
    with pytest.raises(ValueError):
        catalogo.cargar(_escribir(tmp_path, [local]))


def test_esquema_desconocido_no_se_carga(tmp_path):
    ruta = tmp_path / "catalogo.json"
    ruta.write_text(json.dumps({"schema": "otro/1", "proveedores": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        catalogo.cargar(ruta)
