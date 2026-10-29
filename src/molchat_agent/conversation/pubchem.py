"""PubChem reference lookup owned by MolChat; the caller supplies authorization."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import quote

import httpx

ROOT = "https://pubchem.ncbi.nlm.nih.gov"
MAX_RESULTS = 10
MAX_BYTES = 256_000


class PubChemError(RuntimeError):
    """The source could not be queried or returned an invalid response."""


@dataclass(frozen=True)
class CompoundReference:
    cid: int
    name: str
    source: str


@dataclass(frozen=True)
class LookupResult:
    matches: list[CompoundReference]
    truncated: bool


async def search_compounds(name: str, *, client: httpx.AsyncClient,
                           authorize: Callable[[], Awaitable[None]]) -> LookupResult:
    """Read references only; recheck authorization before every external request."""
    if not isinstance(name, str):
        raise ValueError("Nombre de compuesto no válido")
    name = name.strip()
    if not name or len(name) > 120 or any(ord(char) < 32 for char in name):
        raise ValueError("Nombre de compuesto no válido")
    try:
        await authorize()
        response = await client.get(f"{ROOT}/rest/pug/compound/name/{quote(name, safe='')}/cids/JSON",
                                    timeout=10, follow_redirects=False)
        if response.status_code == 404:
            return LookupResult([], False)
        if response.status_code != 200 or len(response.content) > MAX_BYTES:
            raise PubChemError("PubChem no devolvió una búsqueda válida")
        ids = response.json()["IdentifierList"]["CID"]
        if not isinstance(ids, list) or not all(type(cid) is int and cid > 0 for cid in ids):
            raise PubChemError("PubChem devolvió identificadores inválidos")
        unique = list(dict.fromkeys(ids))
        references = []
        for cid in unique[:MAX_RESULTS]:
            await authorize()
            detail = await client.get(f"{ROOT}/rest/pug/compound/cid/{cid}/description/JSON",
                                      timeout=10, follow_redirects=False)
            if detail.status_code != 200 or len(detail.content) > MAX_BYTES:
                raise PubChemError("PubChem no devolvió la identificación del compuesto")
            descriptions = detail.json()["InformationList"]["Information"]
            title = next((row.get("Title") for row in descriptions if isinstance(row, dict)
                          and row.get("CID") == cid and row.get("Title")), None)
            if not isinstance(title, str) or len(title) > 500:
                raise PubChemError("PubChem devolvió un nombre inválido")
            references.append(CompoundReference(cid, title, f"{ROOT}/compound/{cid}"))
        return LookupResult(references, len(unique) > MAX_RESULTS)
    except (httpx.RequestError, KeyError, TypeError, ValueError) as exc:
        raise PubChemError("No se pudo consultar PubChem") from exc
