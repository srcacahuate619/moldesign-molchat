"""MolChat-owned tools, with product operations delegated through typed ports."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import asyncio
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
                "methodology": {"source": "https://pubchem.ncbi.nlm.nih.gov/docs/glossary",
                    "hba": "PubChem refiere una clasificación de 1997; las reglas detalladas y su aplicación a esta molécula no se han comprobado aquí.",
                    "xlogp": "XLogP de PubChem; no es necesariamente el LogP de RDKit."},
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


def load_case_smiles_tool(request_load: Callable[[str, str], Awaitable[dict[str, Any]]]) -> Tool:
    """Validate a structure, then ask the host to apply it to one named case."""
    async def load(args: dict[str, Any]) -> dict[str, Any]:
        case_name, smiles = args["case_name"].strip(), args["smiles"].strip()
        try:
            from rdkit import Chem
            molecule = await asyncio.to_thread(Chem.MolFromSmiles, smiles)
        except ImportError:
            return {"status": "unavailable", "message": "No está disponible la validación de SMILES."}
        except Exception:
            return {"status": "invalid_smiles", "message": "No se pudo interpretar el SMILES."}
        if molecule is None:
            return {"status": "invalid_smiles", "message": "El SMILES no es válido; no se modificó el caso."}
        result = await request_load(case_name, smiles)
        valid = {"applied", "not_found", "ambiguous", "busy", "failed", "unknown"}
        status = result.get("status") if isinstance(result, dict) else "unknown"
        if status not in valid:
            status = "unknown"
        return {"status": status, "case_name": case_name, "smiles": smiles}

    schema = {"type": "object", "properties": {
        "case_name": {"type": "string", "maxLength": 100},
        "smiles": {"type": "string", "maxLength": 2000}},
        "required": ["case_name", "smiles"], "additionalProperties": False}
    return Tool("load_case_smiles", "Carga un SMILES explícito en el campo del caso indicado en MolDesign. "
                "Úsala solo si el usuario pide cargarlo y se conocen el caso y el SMILES exactos. "
                "Si no son inequívocos pregunta. Confirma únicamente status=applied; no afirma que Ketcher "
                "dibujó o que se guardó en disco sin confirmación adicional.", schema, load)


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
        identity = "unverified"
        verifier = None
        if smiles == record.smiles:
            identity = "same"
            verifier = "SMILES idéntico"
        else:
            try:
                from rdkit import Chem, rdBase
                left, right = Chem.MolFromSmiles(smiles), Chem.MolFromSmiles(record.smiles)
                if left is not None and right is not None:
                    a = Chem.MolToSmiles(left, canonical=True, isomericSmiles=True)
                    b = Chem.MolToSmiles(right, canonical=True, isomericSmiles=True)
                    identity = "same" if a == b else "changed"
                    verifier = f"SMILES canónico isomérico RDKit {rdBase.rdkitVersion}"
            except ImportError:
                pass
        return {"status": "ok", "name": name, "properties": record.props, "source": record.source,
                "methods": record.methods, "structure": {"input_smiles": smiles,
                    "canonical_smiles": record.smiles, "identity": identity,
                    "verifier": verifier, "warnings": record.warnings}}

    return Tool("compute_properties", "Calcula propiedades con MolDesign para un SMILES o un nombre "
                "reconocido. Para comparar con PubChem usa exactamente su SMILES devuelto, no el nombre. "
                "Devuelve identidad y transformaciones comprobables.", _named_input(2000), calculate)
