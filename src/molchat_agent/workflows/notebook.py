"""The agent's notebook: what was asked, what was approved, what each step really did.

It is written by the host from the run's record, never by the model, so it cannot claim a deed that did not
happen. Every number carries the source that produced it (MolDesign's Vina energy, MolDesign's physical controls)
and every step that did not happen says why. The notebook is evidence of the run, not a result of the science.

The PDF needs ``reportlab`` (optional). Without it the notebook is still produced as JSON and Markdown and says
the PDF could not be written; nothing downstream pretends otherwise.
"""
from __future__ import annotations

import copy
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
                                "to_start_s": record.seconds_to_start, "to_result_s": record.seconds_to_result},
                     "source": copy.deepcopy(record.source), "run": copy.deepcopy(record.run)})
    selected = next((r for r in outcome.records if r.index == outcome.selected), None)
    runs = [row["run"] for row in rows if isinstance(row["run"], dict)]
    vina = sorted({run["vina_version"] for run in runs if run.get("vina_version")})
    if vina and not versions:
        versions = {"vina": ", ".join(vina)}
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
        "comparability": comparability(runs),
        "provenance": ("Las energías, los controles físicos, el protocolo, los avisos y la especie acoplada los dio "
                       "MolDesign; la identidad de cada molécula, la consulta de PubChem de esta conversación cuyo SMILES "
                       "coincide literalmente. MolChat ordenó las llamadas, anotó lo ocurrido y escribió este cuaderno "
                       "sin intervención del modelo."),
        "versions": versions or {}}


_COMPARED = (("receptor_sha256", "receptor preparado"), ("vina_version", "versión de Vina"))
_COMPARED_PROTOCOL = (("engine", "motor"), ("exhaustiveness", "exhaustividad"), ("num_poses", "poses"),
                      ("seed", "semilla"), ("box_center", "centro de la caja"), ("box_size", "tamaño de la caja"))


def comparability(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Whether the evaluated molecules ran under the same conditions, field by field, from what each run recorded.

    A field a run did not record is «not recorded», never assumed equal: comparing scores is only fair when the
    receptor, the engine and the search were the same, and that is exactly what a reader cannot see in a table.
    """
    if not runs:
        return {"runs": 0, "same": [], "different": [], "not_recorded": []}
    fields = [(key, label, lambda run, key=key: run.get(key)) for key, label in _COMPARED]
    fields += [(key, label, lambda run, key=key: (run.get("protocol") or {}).get(key)) for key, label in _COMPARED_PROTOCOL]
    same, different, missing = [], [], []
    for key, label, read in fields:
        values = [read(run) for run in runs]
        if any(value is None for value in values):
            missing.append(label)
            continue
        distinct = list(dict.fromkeys(json.dumps(value, sort_keys=True) for value in values))  # in the molecules' order
        if len(distinct) == 1:
            same.append({"field": label, "value": values[0]})
        else:
            different.append({"field": label, "values": [json.loads(text) for text in distinct]})
    return {"runs": len(runs), "same": same, "different": different, "not_recorded": missing}


def _plan_lines(spec: dict[str, Any]) -> list[str]:
    from .iteration import IterationSpec
    return IterationSpec.from_dict(spec).card_lines()


_MATCH = {"exact": "el SMILES coincide con el de PubChem",
          "connectivity_only": "el SMILES coincide sólo con la conectividad de PubChem: se usó sin su estereoquímica"}


def source_line(source: dict[str, Any] | None) -> str:
    if not isinstance(source, dict):
        return ("Procedencia: no registrada (el SMILES no coincide literalmente con ninguna consulta de PubChem de "
                "esta conversación).")
    if source.get("match") == "ambiguous":
        return f"Procedencia: ambigua; el SMILES coincide con varios compuestos de PubChem (CID {', '.join(map(str, source['cids']))})."
    query = f", búsqueda «{source['query']}»" if source.get("query") else ""
    return (f"Procedencia: PubChem CID {source['cid']} («{source.get('name') or 'sin nombre'}»{query}); "
            f"{_MATCH.get(source.get('match'), source.get('match') or '')}." + (f" {source['url']}" if source.get("url") else ""))


def _n(count: Any, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def run_lines(run: dict[str, Any] | None) -> list[str]:
    """What MolDesign recorded about one run, in plain lines; nothing derived, nothing added."""
    if not isinstance(run, dict):
        return []
    out: list[str] = []
    species = run.get("species") or {}
    written, docked = species.get("input_smiles"), species.get("docked_smiles_3d")
    if written or docked:
        same = written is not None and written == docked
        out.append(f"SMILES de entrada (canónico): {written or 'no registrado'}; especie acoplada (desde el 3D): "
                   f"{docked or 'no registrada'}" + (" (la misma)." if same else "."))
    proton, tauto, stereo = species.get("protonation") or {}, species.get("tautomer") or {}, species.get("stereo") or {}
    if proton.get("applied") is True:
        ph = proton.get("ph")
        out.append("Protonación: " + (f"a pH {ph:g}" if isinstance(ph, (int, float)) else "aplicada")
                   + (f", {_n(proton['alternatives'], 'alternativa', 'alternativas')}" if isinstance(proton.get("alternatives"), int) else "") + ".")
    elif proton.get("applied") is False:
        out.append("Protonación: no aplicada" + (f" ({proton['reason']})" if proton.get("reason") else "") + ".")
    if tauto.get("applied") is not None:
        out.append("Tautómero: " + ("canonicalizado" if tauto.get("applied") else "el de entrada")
                   + (f", {_n(tauto['alternatives'], 'alternativa', 'alternativas')}" if isinstance(tauto.get("alternatives"), int) else "") + ".")
    centers, doubles = stereo.get("unassigned_centers"), stereo.get("unassigned_double_bonds")
    if isinstance(centers, int) or isinstance(doubles, int):
        out.append(f"Estereoquímica sin asignar en la entrada: {centers if isinstance(centers, int) else '—'} centros y "
                   f"{doubles if isinstance(doubles, int) else '—'} dobles enlaces.")
    lost = stereo.get("lost_in_docked_species") or {}
    if lost.get("centros") or lost.get("dobles"):
        out.append("La especie acoplada perdió estereoquímica escrita: "
                   f"{_n(lost.get('centros', 0), 'centro', 'centros')} y {_n(lost.get('dobles', 0), 'doble enlace', 'dobles enlaces')}.")
    protocol = run.get("protocol") or {}
    if protocol:
        parts = [f"{protocol.get('engine') or 'motor no registrado'} {run.get('vina_version') or ''}".strip()]
        for key, label in (("exhaustiveness", "exhaustividad"), ("num_poses", "poses"), ("seed", "semilla")):
            parts.append(f"{label} {protocol[key]}" if protocol.get(key) is not None else f"{label} no registrada")
        if protocol.get("box_center") and protocol.get("box_size"):
            parts.append(f"caja centro {protocol['box_center']} tamaño {protocol['box_size']} Å")
        out.append("Protocolo ejecutado: " + ", ".join(parts) + ".")
        if protocol.get("requested"):
            out.append(f"Se pidió otra cosa y MolDesign ejecutó la de arriba: {protocol['requested']}.")
    warnings = run.get("warnings")
    if warnings is None:
        out.append("Avisos de la corrida: no registrados.")
    elif not warnings:
        out.append("Avisos de la corrida: ninguno.")
    else:
        out.append(f"Avisos de la corrida ({len(warnings)}):")
        out += [f"  - [{w.get('severity') or 'sin severidad'}] {w['message']}" + (f" ({w['code']})" if w.get("code") else "")
                for w in warnings]
    return out


def comparability_lines(c: dict[str, Any]) -> list[str]:
    if not c.get("runs"):
        return ["Ninguna molécula llegó a evaluarse: no hay condiciones que comparar."]
    out = [f"Sobre las {c['runs']} corridas evaluadas:"]
    if c["same"]:
        out.append("- Iguales en todas: " + "; ".join(f"{item['field']} {item['value']}" for item in c["same"]) + ".")
    for item in c["different"]:
        out.append(f"- Distinto entre corridas: {item['field']} ({' / '.join(map(str, item['values']))}). "
                   "Las energías no se comparan en las mismas condiciones.")
    if c["not_recorded"]:
        out.append("- Sin registrar en alguna corrida: " + ", ".join(c["not_recorded"]) + "; no se da por igual.")
    return out


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
    out += ["", "## Condiciones de las corridas", ""] + comparability_lines(nb.get("comparability") or {})
    out += ["", "## Registro por molécula", "",
            "Lo que MolDesign registró de cada corrida y de dónde salió cada SMILES, tal cual; nada se interpreta aquí.", ""]
    for row in nb["molecules"]:
        out.append(f"### {row['n']}. {row['name']}")
        out += ["", f"- SMILES del plan: `{row['smiles']}`", f"- {source_line(row.get('source'))}"]
        out += [f"- {line}" if not line.startswith("  ") else line for line in run_lines(row.get("run"))]
        if row.get("task_id"):
            out.append(f"- Tarea: {row['task_id']}")
        out.append("")
    out += ["## Lo que se hizo con la elegida", ""]
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
    story.append(Paragraph("Condiciones de las corridas", h2))
    story += [Paragraph(text(line), small) for line in comparability_lines(nb.get("comparability") or {})]
    story.append(Paragraph("Registro por molécula", h2))
    for row in nb["molecules"]:
        story.append(Paragraph(text(f"{row['n']}. {row['name']}"), ParagraphStyle("h3", parent=body, fontName=bold)))
        lines = [f"SMILES del plan: {row['smiles']}", source_line(row.get("source"))] + run_lines(row.get("run"))
        if row.get("task_id"):
            lines.append(f"Tarea: {row['task_id']}")
        story += [Paragraph(text(line.strip()), small) for line in lines]
        story.append(Spacer(1, 3))
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
