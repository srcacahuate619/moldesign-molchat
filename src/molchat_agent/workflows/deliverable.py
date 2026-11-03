"""The single ZIP MolChat hands over: notebook + video + MolDesign's own Preparación package.

This is a separate tool on purpose. MolDesign's package is reproducible byte for byte and it declares what it
contains; MolChat does not open it, change it or re-pack it. It goes in whole, as one file, and the manifest records
its SHA-256 as received. What is not there (the render failed, Preparación was not exported) is listed under
``missing`` with the reason, the same way MolDesign's package lists what it could not build: a piece that is absent
is declared, never replaced by something that looks like it.

Same input, same bytes: entries are sorted and carry a fixed timestamp.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import io
import json
import re
import zipfile
from typing import Any

DELIVERABLE_SCHEMA = "moldesign.molchat.deliverable/1"
_FIXED_TIME = (1980, 1, 1, 0, 0, 0)
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")

README = """Entrega de MolChat
==================

Este ZIP junta lo que produjo un plan aprobado. Nada de lo que contiene lo inventó el modelo.

cuaderno/      Lo pedido, lo aprobado y lo que ocurrió con cada molécula (escrito por MolChat, no por el modelo).
preparacion/   El paquete de Preparación TAL COMO lo entregó MolDesign, sin abrir ni cambiar (su hash está en MANIFEST.json).
video/         El vídeo que renderizó Molcy de MolDesign, con su cierre.
MANIFEST.json  Cada pieza con su SHA-256, quién la produjo y lo que falta con su motivo.

Cómo comprobarlo: calcula el SHA-256 de cada archivo y compáralo con MANIFEST.json.
La energía de Vina no es una energía libre ni una medida de actividad.
"""


@dataclass(frozen=True)
class Piece:
    path: str  # inside the ZIP
    data: bytes
    origin: str  # "MolDesign" | "MolChat"
    kind: str


def _safe_name(name: str, fallback: str) -> str:
    cleaned = _SAFE.sub("-", name).strip("-._")[:80]
    return cleaned or fallback


def build_deliverable(case: str, plan_digest: str, *, notebook_pdf: bytes | None, notebook_md: bytes,
                      notebook_json: bytes, preparation: tuple[str, bytes] | None, video: tuple[str, bytes] | None,
                      missing: dict[str, str] | None = None) -> tuple[bytes, dict[str, Any]]:
    """``(zip bytes, manifest)``. ``preparation`` and ``video`` are ``(file name, bytes)`` as received, or ``None``."""
    pieces = [Piece("cuaderno/cuaderno.md", notebook_md, "MolChat", "notebook"),
              Piece("cuaderno/cuaderno.json", notebook_json, "MolChat", "notebook")]
    absent = dict(missing or {})
    if notebook_pdf is not None:
        pieces.append(Piece("cuaderno/cuaderno.pdf", notebook_pdf, "MolChat", "notebook"))
    else:
        absent.setdefault("cuaderno/cuaderno.pdf", "reportlab no está instalado en este equipo; el cuaderno va en Markdown y JSON.")
    if preparation is not None:
        pieces.append(Piece("preparacion/" + _safe_name(preparation[0], "preparacion.zip"), preparation[1], "MolDesign",
                            "preparation_package"))
    else:
        absent.setdefault("preparacion/", "No hay paquete de Preparación en esta entrega.")
    if video is not None:
        pieces.append(Piece("video/" + _safe_name(video[0], "video.mp4"), video[1], "MolDesign", "video"))
    else:
        absent.setdefault("video/", "No hay vídeo en esta entrega.")
    pieces.sort(key=lambda piece: piece.path)
    if len({piece.path for piece in pieces}) != len(pieces):
        raise ValueError("dos piezas con el mismo nombre en la entrega")
    manifest = {"schema": DELIVERABLE_SCHEMA, "case": case, "plan_digest": plan_digest,
                "pieces": [{"path": p.path, "bytes": len(p.data), "sha256": sha256(p.data).hexdigest(),
                            "origin": p.origin, "kind": p.kind} for p in pieces],
                "missing": [{"item": item, "reason": reason} for item, reason in sorted(absent.items())],
                "note": ("El paquete de Preparación entra tal como lo entregó MolDesign; su contenido y su hash no se "
                         "modificaron aquí.")}
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path, data in sorted([("LEEME.txt", README.encode("utf-8")), ("MANIFEST.json", manifest_bytes),
                                  *[(p.path, p.data) for p in pieces]]):
            info = zipfile.ZipInfo(path, _FIXED_TIME)
            info.compress_type = zipfile.ZIP_STORED if path.endswith((".zip", ".mp4")) else zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return buffer.getvalue(), manifest


def verify_deliverable(blob: bytes) -> list[str]:
    """Problems found re-reading a deliverable against its own manifest (empty when it checks out)."""
    problems: list[str] = []
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        try:
            manifest = json.loads(archive.read("MANIFEST.json"))
        except (KeyError, ValueError):
            return ["MANIFEST.json falta o no es JSON."]
        names = set(archive.namelist()) - {"MANIFEST.json", "LEEME.txt"}
        listed = {piece["path"] for piece in manifest.get("pieces", [])}
        for extra in sorted(names - listed):
            problems.append(f"{extra} está en el ZIP pero no en el manifiesto.")
        for piece in manifest.get("pieces", []):
            try:
                data = archive.read(piece["path"])
            except KeyError:
                problems.append(f"{piece['path']} está en el manifiesto pero no en el ZIP.")
                continue
            if sha256(data).hexdigest() != piece["sha256"] or len(data) != piece["bytes"]:
                problems.append(f"{piece['path']} no coincide con su hash.")
    return problems
