"""Modo alojado: la clave llega de MolDesign para una llamada y no se guarda en el registro base."""

from molchat_agent.bridge import BridgeError
from molchat_agent.config import load_config
from molchat_agent.providers.alojado import registro_del_turno
from molchat_agent.providers.registry import build_registry


class PuenteFalso:
    """Un MolDesign de prueba: dice el activo y entrega (o niega) la credencial."""

    def __init__(self, activo, credencial=None, error=None):
        self.activo = activo
        self._credencial = credencial
        self._error = error
        self.llamadas = []

    async def proveedores_de_cuenta(self):
        return {"activo": self.activo}

    async def credencial(self, proveedor, host):
        self.llamadas.append((proveedor, host))
        if self._error is not None:
            raise self._error
        return self._credencial


def _base():
    return build_registry(load_config({}))


async def test_sin_proveedor_activo_no_hay_respuesta_remota():
    registro = await registro_del_turno(_base(), PuenteFalso(None))
    assert registro.active_id is None


async def test_la_clave_viaja_solo_en_la_llamada_y_no_queda_en_la_base():
    base = _base()
    puente = PuenteFalso("openai", credencial={
        "proveedor": "openai", "modelo": "gpt-4o-mini", "api_key": "sk-prueba-0123456789"})
    registro = await registro_del_turno(base, puente)
    assert registro.active_id == "openai"
    assert registro.get("openai").config.api_key == "sk-prueba-0123456789"
    assert base.get("openai").config.api_key == ""
    assert puente.llamadas == [("openai", "api.openai.com")]
    assert registro.block_reason("openai") == ""
    assert registro.content_granted("openai") is True


async def test_sin_autorizacion_la_llamada_no_sale_y_se_dice_donde_autorizar():
    puente = PuenteFalso("deepseek", error=BridgeError(
        "no entregada", status_code=403, detail="sin_autorizacion"))
    registro = await registro_del_turno(_base(), puente)
    motivo = registro.block_reason("deepseek")
    assert "Autoriza el envío a api.deepseek.com" in motivo
    assert puente.llamadas == [("deepseek", "api.deepseek.com")]


async def test_el_motivo_de_clave_y_destino_se_traduce():
    base = _base()
    falta = await registro_del_turno(base, PuenteFalso("gemini", error=BridgeError(
        "no", status_code=403, detail="sin_clave")))
    assert "Falta la clave de Google Gemini" in falta.block_reason("gemini")
    otro = await registro_del_turno(base, PuenteFalso("gemini", error=BridgeError(
        "no", status_code=403, detail="destino_distinto")))
    assert "no es el que MolDesign autorizó" in otro.block_reason("gemini")


async def test_local_no_pide_credencial():
    puente = PuenteFalso("llama-server")
    registro = await registro_del_turno(_base(), puente)
    assert puente.llamadas == []
    assert registro.active_id == "llama-server"
    assert registro.get("llama-server") is not None


async def test_un_activo_fuera_del_catalogo_se_declara():
    registro = await registro_del_turno(_base(), PuenteFalso("proveedor-inventado"))
    assert "no existe en esta versión de MolChat" in registro.block_reason("proveedor-inventado")
