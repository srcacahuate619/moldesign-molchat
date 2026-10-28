"""Puente hacia MolDesign para proveedores: sesión propia, motivos sin claves, sin red sin llamar."""

import httpx
import pytest

from molchat_agent.bridge import BridgeError, BridgeTransportError, MolDesignBridge

URL = "http://127.0.0.1:8000"


def _puente(handler, token="mh1.sesion-de-prueba"):
    cliente = httpx.AsyncClient(base_url=URL, transport=httpx.MockTransport(handler))
    return MolDesignBridge(URL, token=token, client=cliente)


async def test_credencial_va_con_la_sesion_y_devuelve_la_clave():
    vistas = []

    def handler(request):
        vistas.append((request.method, request.url.path, request.headers["authorization"]))
        return httpx.Response(200, json={"proveedor": "openai", "modelo": "", "api_key": "sk-1"})

    datos = await _puente(handler).credencial("openai", "api.openai.com")
    assert datos["api_key"] == "sk-1"
    assert vistas == [("POST", "/molchat-host/credencial", "Bearer mh1.sesion-de-prueba")]


async def test_un_rechazo_lleva_su_motivo_y_ninguna_clave():
    def handler(request):
        return httpx.Response(403, json={"detail": {"motivo": "sin_autorizacion"}})

    with pytest.raises(BridgeError) as exc:
        await _puente(handler).credencial("openai", "api.openai.com")
    assert exc.value.status_code == 403
    assert exc.value.detail == "sin_autorizacion"
    assert "sk-" not in str(exc.value)


async def test_sin_respuesta_es_error_de_transporte():
    def handler(request):
        raise httpx.ConnectError("sin red", request=request)

    with pytest.raises(BridgeTransportError):
        await _puente(handler).proveedores_de_cuenta()


async def test_sin_sesion_no_se_llama_a_moldesign():
    llamadas = []

    def handler(request):
        llamadas.append(request)
        return httpx.Response(200, json={})

    with pytest.raises(BridgeError):
        await _puente(handler, token=None).proveedores_de_cuenta()
    assert llamadas == []
