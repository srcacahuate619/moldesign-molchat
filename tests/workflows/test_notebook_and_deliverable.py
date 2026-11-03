"""The notebook says only what the record says; the deliverable declares what is missing and never edits MolDesign's piece."""
from __future__ import annotations

import io
import zipfile
from hashlib import sha256
from typing import Any

import pytest

from molchat_agent.workflows.deliverable import build_deliverable, verify_deliverable
from molchat_agent.workflows.notebook import build_notebook, notebook_json, pdf_available, render_markdown, render_pdf
from molchat_agent.workflows.iteration import MoleculeRecord, IterationOutcome, IterationSpec

REQUEST = "molchat investiga esta lista y si alguna pasa el umbral de -9.5 kcal/mol la guardas en moldex"


def outcome(selected: int | None = 2) -> IterationOutcome:
    spec = IterationSpec.from_dict({
        "case_name": "hipotesis-8T69", "pdb_id": "8T69", "threshold_kcal": -9.5, "original_request": REQUEST,
        "molecules": [{"name": "A", "smiles": "CCO"}, {"name": "B", "smiles": "CCN"}, {"name": "C", "smiles": "CCC"}],
        "video": {"scene": "busqueda", "format": "previsualizacion"}, "preparation": True, "package": True})
    out = IterationOutcome(spec.as_dict(), spec.digest)
    out.records = [
        MoleculeRecord(1, "A", "CCO", "evaluated", "below_threshold", "t-1", "m-1", -7.1, "passed",
                       "Vina -7.1 kcal/mol no llega al umbral de -9.5.", 41.0),
        MoleculeRecord(2, "B", "CCN", "evaluated", "qualifies", "t-2", "m-2", -9.8, "passed",
                       "Vina -9.8 kcal/mol y controles físicos superados.", 52.5),
        MoleculeRecord(3, "C", "CCC", "skipped", None, None, None, None, None, "Ya se cumplió la regla de parada.")]
    out.state = "completed" if selected else "none_qualified"
    out.selected = selected
    out.saved = {"status": "saved", "task_id": "t-2"}
    out.video = {"status": "started", "job_id": "j-1", "final": "completo"}
    out.notes = ["El caso ya existía: se reutilizó con su nombre."]
    return out


def test_the_notebook_keeps_the_literal_request_and_every_molecule_with_its_numbers() -> None:
    nb = build_notebook(outcome(), approved_at="2026-11-03T10:00:00+00:00", finished_at="2026-11-03T10:09:00+00:00")
    assert nb["request"] == REQUEST and nb["plan_digest"].startswith("sha256:")
    assert [r["vina_kcal_mol"] for r in nb["molecules"]] == [-7.1, -9.8, None]
    assert nb["selected"]["name"] == "B" and nb["selected"]["task_id"] == "t-2"
    assert nb["molecules"][2]["status"] == "no se evaluó"
    assert any("Moldex" in line for line in nb["plan"])
    assert "energía libre" in nb["limits"] and "MolDesign calculó" not in nb["provenance"]


def test_the_notebook_is_the_same_bytes_for_the_same_record() -> None:
    first = notebook_json(build_notebook(outcome(), approved_at="a", finished_at="b"))
    second = notebook_json(build_notebook(outcome(), approved_at="a", finished_at="b"))
    assert first == second


def test_when_nothing_qualified_the_notebook_says_nothing_was_selected() -> None:
    out = outcome(selected=None)
    out.saved = out.video = None
    out.state = "none_qualified"
    md = render_markdown(build_notebook(out, approved_at="x"))
    assert "Ninguna molécula quedó seleccionada." in md and "ninguna molécula cumplió" in md.lower()
    assert "Moldex:" not in md and "Vídeo de Molcy:" not in md


def test_markdown_lists_the_exceptions_instead_of_hiding_them() -> None:
    md = render_markdown(build_notebook(outcome(), approved_at="x"))
    assert "Molécula 3 (C): Ya se cumplió la regla de parada." in md
    assert "El caso ya existía" in md and "| 2 | B | evaluada | -9.8 | passed | cumple la regla |" in md


@pytest.mark.skipif(not pdf_available(), reason="reportlab no instalado")
def test_the_pdf_is_deterministic_and_carries_the_text() -> None:
    nb = build_notebook(outcome(), approved_at="2026-11-03T10:00:00+00:00", finished_at="2026-11-03T10:09:00+00:00")
    first, second = render_pdf(nb), render_pdf(nb)
    assert first is not None and first.startswith(b"%PDF") and first == second
    pypdf = pytest.importorskip("pypdf")
    text = " ".join(page.extract_text() for page in pypdf.PdfReader(io.BytesIO(first)).pages)
    for expected in ("hipotesis-8T69", "umbral", "-9.8"):
        assert expected in text


def build(**over: Any) -> tuple[bytes, dict[str, Any]]:
    nb = build_notebook(outcome(), approved_at="x", finished_at="y")
    args: dict[str, Any] = {"notebook_pdf": b"%PDF-fake", "notebook_md": render_markdown(nb).encode(),
                            "notebook_json": notebook_json(nb), "preparation": ("caso_t-2.zip", b"PK-inner-as-delivered"),
                            "video": ("molcy_t-2.mp4", b"\x00\x00\x00 ftypmp4-fake")}
    args.update(over)
    return build_deliverable("hipotesis-8T69", outcome().digest, **args)


def test_the_deliverable_carries_all_three_pieces_and_verifies_against_its_manifest() -> None:
    blob, manifest = build()
    assert verify_deliverable(blob) == []
    paths = {piece["path"]: piece for piece in manifest["pieces"]}
    assert set(paths) == {"cuaderno/cuaderno.md", "cuaderno/cuaderno.json", "cuaderno/cuaderno.pdf",
                          "preparacion/caso_t-2.zip", "video/molcy_t-2.mp4"}
    assert paths["preparacion/caso_t-2.zip"]["origin"] == "MolDesign" and paths["cuaderno/cuaderno.pdf"]["origin"] == "MolChat"
    assert manifest["missing"] == []


def test_the_preparation_package_goes_in_exactly_as_it_was_received() -> None:
    inner = b"PK\x03\x04 a MolDesign package, byte for byte"
    blob, manifest = build(preparation=("paquete.zip", inner))
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        assert archive.read("preparacion/paquete.zip") == inner
    piece = next(p for p in manifest["pieces"] if p["kind"] == "preparation_package")
    assert piece["sha256"] == sha256(inner).hexdigest()


def test_a_missing_video_and_a_missing_preparation_are_declared_with_the_reason() -> None:
    blob, manifest = build(video=None, preparation=None,
                           missing={"video/": "El render terminó en fallido.", "preparacion/": "La auditoría quedó BLOCKED."})
    assert verify_deliverable(blob) == []
    reasons = {m["item"]: m["reason"] for m in manifest["missing"]}
    assert reasons["video/"] == "El render terminó en fallido." and reasons["preparacion/"] == "La auditoría quedó BLOCKED."
    assert not any(p["kind"] in {"video", "preparation_package"} for p in manifest["pieces"])


def test_without_reportlab_the_pdf_is_declared_missing_not_faked() -> None:
    _, manifest = build(notebook_pdf=None)
    assert any(m["item"] == "cuaderno/cuaderno.pdf" for m in manifest["missing"])
    assert not any(p["path"].endswith(".pdf") for p in manifest["pieces"])


def test_same_input_same_zip_bytes() -> None:
    assert build()[0] == build()[0]


def test_file_names_cannot_escape_the_archive() -> None:
    blob, manifest = build(video=("../../evil name.mp4", b"x"), preparation=("..\\p.zip", b"y"))
    assert all(".." not in p["path"] and not p["path"].startswith("/") for p in manifest["pieces"])
    assert verify_deliverable(blob) == []


def test_tampering_is_detected() -> None:
    blob, _ = build()
    source = zipfile.ZipFile(io.BytesIO(blob))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as tampered:
        for info in source.infolist():
            data = source.read(info.filename)
            tampered.writestr(info.filename, data + b"!" if info.filename.startswith("video/") else data)
    assert any("video/" in problem for problem in verify_deliverable(out.getvalue()))
