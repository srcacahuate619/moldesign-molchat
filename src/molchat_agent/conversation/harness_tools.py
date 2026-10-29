"""MolChat-owned tools, with product operations delegated through typed ports."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
import httpx

from ..bridge import BridgeError, MolDesignBridge
from .pubchem import PubChemError, search_compounds
from .tool_loop import Tool
from .intents import KNOWN_SMILES, find_name
from .tools import ToolBackend, ToolError


def _named_input(maximum: int) -> dict[str, Any]:
    return {"type": "object", "properties": {"name": {"type": "string", "maxLength": maximum}},
            "required": ["name"], "additionalProperties": False}


def pubchem_tool(bridge: MolDesignBridge, client: httpx.AsyncClient) -> Tool:
    async def lookup(args: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await search_compounds(args["name"], client=client, authorize=bridge.authorize_pubchem)
        except PermissionError:
            return {"status": "permission_denied", "message": "PubChem está desautorizado o sin red."}
        except (PubChemError, BridgeError):
            return {"status": "unavailable", "message": "No se pudo consultar PubChem o verificar el permiso."}
        return {"status": "ok" if result.matches else "not_found", "truncated": result.truncated,
                "matches": [{"cid": item.cid, "name": item.name, "source": item.source,
                             "properties": item.properties, "properties_available": item.properties_available}
                            for item in result.matches]}

    return Tool("pubchem_lookup", "Consulta identidad y propiedades públicas de un compuesto por nombre en PubChem. "
                "Devuelve la fuente y los datos disponibles; no modifica el editor.",
                _named_input(120), lookup)


def create_case_tool(request_case: Callable[[str], Awaitable[dict[str, Any]]]) -> Tool:
    """MolChat requests a product action; only the host can confirm its result."""
    async def create(args: dict[str, Any]) -> dict[str, Any]:
        result = await request_case(args["name"])
        if not isinstance(result, dict) or result.get("status") not in {"created", "exists", "failed", "unknown"}:
            return {"status": "unknown", "message": "No se confirmó el resultado en MolDesign."}
        return {"status": result["status"], "name": args["name"]}

    return Tool("create_case", "Solicita a MolDesign crear un caso nuevo. Informa éxito solo cuando "
                "el resultado del host sea created.", _named_input(100), create)


def properties_tool(backend: ToolBackend) -> Tool:
    """Use MolDesign's existing calculation, with no invented property values."""
    async def calculate(args: dict[str, Any]) -> dict[str, Any]:
        name = args["name"]
        known = find_name(name)
        smiles = KNOWN_SMILES.get(known, name) if known else name
        try:
            record = await backend.properties(smiles)
        except ToolError:
            return {"status": "unavailable", "message": "No se pudieron calcular propiedades para esa entrada."}
        return {"status": "ok", "name": name, "properties": record.props, "source": record.source}

    return Tool("compute_properties", "Calcula propiedades con MolDesign para un SMILES o un nombre "
                "reconocido. Los valores provienen del resultado de la herramienta.", _named_input(2000), calculate)
