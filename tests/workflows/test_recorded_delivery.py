"""The delivery from the recorded demo run is published as it came out, and still checks against its own manifest."""
import hashlib
import zipfile
from pathlib import Path

from molchat_agent.workflows.deliverable import verify_deliverable

RUN = Path(__file__).resolve().parents[2] / "kit" / "vmat2-run"
#: The ZIP the run wrote on 2026-11-03; the docs quote this hash.
RECORDED_SHA256 = "277e1a99c9a523e124adc6099e13ad440733b771cb7d6e028c411f9e14483573"


def test_the_recorded_delivery_is_the_one_the_docs_quote_and_checks_against_its_manifest() -> None:
    blob = (RUN / "delivery.zip").read_bytes()
    assert hashlib.sha256(blob).hexdigest() == RECORDED_SHA256
    assert verify_deliverable(blob) == []


def test_the_copies_next_to_it_are_the_bytes_inside_it() -> None:
    with zipfile.ZipFile(RUN / "delivery.zip") as archive:
        for copy, inside in (("MANIFEST.json", "MANIFEST.json"), ("notebook.md", "notebook/notebook.md"),
                             ("notebook.pdf", "notebook/notebook.pdf")):
            assert (RUN / copy).read_bytes() == archive.read(inside), copy


def test_the_notebook_says_what_the_docs_say_about_the_run() -> None:
    notebook = (RUN / "notebook.md").read_text(encoding="utf-8")
    assert "| 5 | ketanserin | docked | -11.2 | passed | meets the rule |" in notebook
    assert "| 6 | valbenazine | not docked |" in notebook
    assert "0 blockers and 6 requirements under review" in notebook
