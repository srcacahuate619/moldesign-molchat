"""The agent's notebook: what was asked, what was approved, what each step really did.

It is written by the host from the run's record, never by the model, so it cannot claim a deed that did not
happen. Every number carries the source that produced it (MolDesign's Vina energy, MolDesign's physical controls)
and every step that did not happen says why. The notebook is evidence of the run, not a result of the science.

The PDF needs ``reportlab`` (optional). Without it the notebook is still produced as JSON and Markdown and says
the PDF could not be written; nothing downstream pretends otherwise.
"""
from __future__ import annotations

import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .iteration import SCHEMA, IterationOutcome

NOTEBOOK_SCHEMA = "moldesign.molchat.notebook/1"

_STATUS = {"evaluated": "evaluada", "failed": "falló", "timeout": "sin terminar a tiempo",
           "unknown": "sin confirmar", "skipped": "no se evaluó", "pending": "pendiente"}
_OUTCOME = {"qualifies": "cumple la regla", "near": "energía suficiente, controles físicos no superados",
            "below_threshold": "no llega al umbral"}
_STATE = {"completed": "Terminó: hay una molécula que cumple la regla.",
          "none_qualified": "Terminó: ninguna molécula cumplió la regla.",
          "blocked": "Se detuvo antes de evaluar: el caso no quedó preparado.",
          "budget_exhausted": "Se agotó el tiempo total del plan; lo no evaluado queda declarado."}
LIMITS = ("La energía de Vina es la de la mejor pose según Vina: no es una energía libre, ni un Ki, ni una medida de "
          "actividad. Una iteración sobre pocas moléculas no ordena fármacos. Los controles físicos son los de PoseBusters "
          "tal como los declara MolDesign.")


def _fmt(value: Any, unit: str = "") -> str:
    return "—" if value is None else f"{value:g}{unit}"


def build_notebook(outcome: IterationOutcome, *, approved_at: str | None, finished_at: str | None = None,
                   versions: dict[str, str] | None = None) -> dict[str, Any]:
    """The notebook as data. Same input, same output: the timestamps are arguments, not read from the clock."""
    spec = outcome.spec
    rows = []
    for record in outcome.records:
        rows.append({"n": record.index, "name": record.name, "smiles": record.smiles,
                     "status": _STATUS.get(record.status, record.status),
                     "vina_kcal_mol": record.affinity_kcal, "physical_controls": record.physical_status,
                     "reading": _OUTCOME.get(record.outcome or "", record.reason or ""), "reason": record.reason,
                     "task_id": record.task_id, "seconds": record.seconds,
                     "timing": {"waiting_case_s": record.seconds_waiting_case, "case_state_before": record.case_state_before,
                                "to_start_s": record.seconds_to_start, "to_result_s": record.seconds_to_result}})
    selected = next((r for r in outcome.records if r.index == outcome.selected), None)
    return {
        "schema": NOTEBOOK_SCHEMA, "iteration_schema": SCHEMA, "case": spec["case_name"], "receptor": spec["pdb_id"],
        "request": spec.get("original_request") or "", "approved_at": approved_at, "finished_at": finished_at,
        "plan_digest": outcome.digest, "plan": _plan_lines(spec), "state": outcome.state,
        "state_text": _STATE.get(outcome.state, outcome.state),
        "rule": {"threshold_kcal_mol": spec["threshold_kcal"], "require_physical": spec["require_physical"],
                 "stop": spec["stop"]},
        "molecules": rows,
        "selected": None if selected is None else {"n": selected.index, "name": selected.name, "task_id": selected.task_id,
                                                   "vina_kcal_mol": selected.affinity_kcal,
                                                   "physical_controls": selected.physical_status},
        "saved": outcome.saved, "video": outcome.video, "preparation": outcome.preparation,
        "deliverable": outcome.deliverable, "notes": list(outcome.notes), "limits": LIMITS,
        "provenance": ("Las energías y los controles físicos los calculó MolDesign; MolChat ordenó las llamadas, "
                       "anotó lo ocurrido y escribió este cuaderno sin intervención del modelo."),
        "versions": versions or {}}


def _plan_lines(spec: dict[str, Any]) -> list[str]:
    from .iteration import IterationSpec
    return IterationSpec.from_dict(spec).card_lines()


def render_markdown(nb: dict[str, Any]) -> str:
    out = [f"# Cuaderno del agente — {nb['case']}", ""]
    out += [f"- Receptor: {nb['receptor']}", f"- Aprobado: {nb['approved_at'] or 'sin registrar'}",
            f"- Terminó: {nb['finished_at'] or 'sin registrar'}", f"- Huella del plan: `{nb['plan_digest']}`", ""]
    out += ["## Lo que se pidió", "", nb["request"] or "(no se guardó el texto original)", ""]
    out += ["## Lo que se aprobó", ""] + [f"- {line}" for line in nb["plan"]] + [""]
    out += ["## Qué ocurrió", "", nb["state_text"], ""]
    out += ["| # | Molécula | Estado | Vina (kcal/mol) | Controles físicos | Lectura |", "|---|---|---|---|---|---|"]
    for row in nb["molecules"]:
        out.append(f"| {row['n']} | {row['name']} | {row['status']} | {_fmt(row['vina_kcal_mol'])} | "
                   f"{row['physical_controls'] or '—'} | {row['reading']} |")
    out.append("")
    for row in nb["molecules"]:
        if row["reason"] and row["status"] != "evaluada":
            out.append(f"- Molécula {row['n']} ({row['name']}): {row['reason']}")
    timed = [row for row in nb["molecules"] if any(v is not None for v in (row.get("timing") or {}).values())]
    if timed:
        out += ["", "### Tiempos medidos", "",
                "Espera del caso: hasta que la ventana dijo que la corrida anterior había cerrado. Resultado: desde que "
                "arrancó la corrida hasta que el backend la dio por terminada con su energía.", ""]
        for row in timed:
            t = row["timing"]
            out.append(f"- Molécula {row['n']} ({row['name']}): espera del caso {_fmt(t['waiting_case_s'], ' s')} "
                       f"(«{t['case_state_before'] or 'sin respuesta'}»), arranque {_fmt(t['to_start_s'], ' s')}, "
                       f"resultado {_fmt(t['to_result_s'], ' s')}, total {_fmt(row['seconds'], ' s')}.")
    out += ["", "## Lo que se hizo con la elegida", ""]
    sel = nb["selected"]
    out.append("Ninguna molécula quedó seleccionada." if sel is None else
               f"{sel['name']} (tarea {sel['task_id']}): Vina {_fmt(sel['vina_kcal_mol'], ' kcal/mol')}, "
               f"controles físicos {sel['physical_controls'] or 'no evaluados'}.")
    for label, key in (("Moldex", "saved"), ("Vídeo de Molcy", "video"), ("Preparación", "preparation"),
                       ("Entrega", "deliverable")):
        item = nb[key]
        if item is not None:
            out.append(f"- {label}: {_describe(item)}")
    if nb["notes"]:
        out += ["", "## Anotaciones", ""] + [f"- {note}" for note in nb["notes"]]
    out += ["", "## Límites y procedencia", "", nb["limits"], "", nb["provenance"], ""]
    return "\n".join(out)


def _describe(item: dict[str, Any]) -> str:
    parts = [str(item.get("status") or item.get("final") or item.get("job_state") or "sin estado")]
    for key in ("message", "job_id", "readiness", "file", "sha256"):
        if item.get(key):
            parts.append(f"{key}: {item[key]}")
    return " · ".join(parts)


def notebook_json(nb: dict[str, Any]) -> bytes:
    return (json.dumps(nb, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


# ── PDF (optional) ──────────────────────────────────────────────────────────────────────────────────

_TRANSLIT = {"≤": "<=", "≥": ">=", "−": "-", "—": "-", "–": "-", "·": "-", "“": '"', "”": '"', "’": "'", "→": "->"}


def _system_fonts() -> tuple[tuple[str, str], ...]:
    """Regular and bold font files to try, in order. The Windows folder comes from the environment, never a literal path."""
    root = os.environ.get("SystemRoot")
    windows = ((str(Path(root) / "Fonts" / "arial.ttf"), str(Path(root) / "Fonts" / "arialbd.ttf")),) if root else ()
    return windows + (("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),)


_FONT_CANDIDATES = _system_fonts()


def pdf_available() -> bool:
    try:
        import reportlab  # noqa: F401
    except ImportError:
        return False
    return True


def render_pdf(nb: dict[str, Any]) -> bytes | None:
    """The notebook as a PDF, or ``None`` when ``reportlab`` is not installed. Deterministic for equal input."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        from xml.sax.saxutils import escape
    except ImportError:
        return None

    regular, bold, unicode_ok = "Helvetica", "Helvetica-Bold", False
    for normal_path, bold_path in _FONT_CANDIDATES:
        if Path(normal_path).is_file() and Path(bold_path).is_file():
            try:
                pdfmetrics.registerFont(TTFont("MolChatSans", normal_path))
                pdfmetrics.registerFont(TTFont("MolChatSans-Bold", bold_path))
                regular, bold, unicode_ok = "MolChatSans", "MolChatSans-Bold", True
                break
            except Exception:  # noqa: BLE001 - an unreadable font falls back to the built-in one
                continue

    def text(value: Any) -> str:
        shown = "" if value is None else str(value)
        if not unicode_ok:
            for char, replacement in _TRANSLIT.items():
                shown = shown.replace(char, replacement)
        return escape(shown)

    body = ParagraphStyle("body", fontName=regular, fontSize=9.5, leading=13)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=10.5)
    h1 = ParagraphStyle("h1", parent=body, fontName=bold, fontSize=16, leading=20, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=body, fontName=bold, fontSize=11.5, leading=15, spaceBefore=10, spaceAfter=3)

    story: list[Any] = [Paragraph(text(f"Cuaderno del agente — {nb['case']}"), h1)]
    meta = [f"Receptor: {nb['receptor']}", f"Aprobado: {nb['approved_at'] or 'sin registrar'}",
            f"Terminó: {nb['finished_at'] or 'sin registrar'}", f"Huella del plan: {nb['plan_digest']}"]
    story += [Paragraph(text(line), small) for line in meta]
    story += [Paragraph("Lo que se pidió", h2), Paragraph(text(nb["request"] or "(no se guardó el texto original)"), body),
              Paragraph("Lo que se aprobó", h2)]
    story += [Paragraph(text("• " + line), body) for line in nb["plan"]]
    story += [Paragraph("Qué ocurrió", h2), Paragraph(text(nb["state_text"]), body), Spacer(1, 4)]

    head = ["#", "Molécula", "Estado", "Vina", "Controles", "Lectura"]
    data = [[Paragraph(text(h), ParagraphStyle("th", parent=small, fontName=bold)) for h in head]]
    for row in nb["molecules"]:
        data.append([Paragraph(text(cell), small) for cell in (
            row["n"], row["name"], row["status"], _fmt(row["vina_kcal_mol"]), row["physical_controls"] or "—",
            row["reading"])])
    table = Table(data, colWidths=[8 * mm, 32 * mm, 26 * mm, 16 * mm, 24 * mm, 64 * mm], repeatRows=1)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF4")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(table)
    for row in nb["molecules"]:
        if row["reason"] and row["status"] != "evaluada":
            story.append(Paragraph(text(f"Molécula {row['n']} ({row['name']}): {row['reason']}"), small))
    story.append(Paragraph("Lo que se hizo con la elegida", h2))
    sel = nb["selected"]
    story.append(Paragraph(text("Ninguna molécula quedó seleccionada." if sel is None else
                                f"{sel['name']} (tarea {sel['task_id']}): Vina {_fmt(sel['vina_kcal_mol'], ' kcal/mol')}, "
                                f"controles físicos {sel['physical_controls'] or 'no evaluados'}."), body))
    for label, key in (("Moldex", "saved"), ("Vídeo de Molcy", "video"), ("Preparación", "preparation"),
                       ("Entrega", "deliverable")):
        if nb[key] is not None:
            story.append(Paragraph(text(f"{label}: {_describe(nb[key])}"), body))
    if nb["notes"]:
        story.append(Paragraph("Anotaciones", h2))
        story += [Paragraph(text("• " + note), small) for note in nb["notes"]]
    story += [Paragraph("Límites y procedencia", h2), Paragraph(text(nb["limits"]), small), Spacer(1, 3),
              Paragraph(text(nb["provenance"]), small)]

    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                                 bottomMargin=16 * mm, title=f"Cuaderno del agente — {nb['case']}",
                                 author="MolChat", invariant=1)
    document.build(story)
    return buffer.getvalue()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
