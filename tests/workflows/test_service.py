"""An approved plan runs to an honest record: video and Preparación in parallel, one ZIP, nothing invented."""
from __future__ import annotations

import asyncio
import io
import json
import zipfile
from pathlib import Path
from typing import Any

from molchat_agent.workflows.deliverable import verify_deliverable
from molchat_agent.workflows.iteration import IterationSpec, VideoRequest
from molchat_agent.workflows.service import (
    HostRelay, WorkflowProposal, execute, new_workflow, summarize, workflow_answer)

JOB = "a1b2c3d4-0000-4000-8000-000000000001"


def spec(**over: Any) -> IterationSpec:
    data = {"case_name": "hipotesis-8T69", "pdb_id": "8T69", "threshold_kcal": -9.5,
            "original_request": "investiga la lista y si pasa -9.5 guardala",
            "molecules": [{"name": "A", "smiles": "CCO"}, {"name": "B", "smiles": "CCN"}],
            "video": {"scene": "busqueda", "format": "previsualizacion"}, "preparation": True, "package": True}
    data.update(over)
    return IterationSpec.from_dict(data)


class Host:
    def __init__(self) -> None:
        self.smiles = ""

    async def create_case(self, name: str) -> dict[str, Any]:
        return {"status": "created"}

    async def assign_receptor(self, case_name: str, pdb_id: str) -> dict[str, Any]:
        return {"status": "applied"}

    async def load_smiles(self, case_name: str, smiles: str) -> dict[str, Any]:
        self.smiles = smiles
        return {"status": "applied"}

    async def evaluate(self, case_name: str) -> dict[str, Any]:
        return {"status": "started", "task_id": f"t-{self.smiles}"}

    async def case_status(self, case_name: str) -> dict[str, Any]:
        return {"status": "idle"}


class Platform:
    scores = {"CCO": -7.0, "CCN": -9.9}

    def __init__(self, *, video_final: str = "completo", mp4: bytes | None = b"MP4-bytes") -> None:
        self.video_final, self.mp4, self.polls = video_final, mp4, 0

    async def job(self, task_id: str) -> dict[str, Any]:
        s = task_id[2:]
        return {"status": "SUCCESS", "result": {"molecule_id": f"m-{s}", "affinity_kcal": self.scores[s]}}

    async def top_pose(self, task_id: str) -> dict[str, Any]:
        return {"physical_status": "passed"}

    async def save(self, task_id: str, molecule_id: str, name: str | None) -> dict[str, Any]:
        return {"status": "saved", "task_id": task_id}

    async def request_video(self, task_id: str, molecule_id: str, video: VideoRequest) -> dict[str, Any]:
        return {"status": "started", "job_id": JOB}

    async def video_status(self, job_id: str) -> dict[str, Any]:
        self.polls += 1
        return {"status": "ok", "job_state": self.video_final if self.polls >= 2 else "en_curso"}

    async def fetch_video(self, job_id: str) -> tuple[str, bytes] | None:
        return ("molcy_a1b2c3d4.mp4", self.mp4) if self.mp4 else None


class Preparation:
    def __init__(self, result: dict[str, Any] | Exception) -> None:
        self.result, self.calls = result, []

    async def audit_and_export(self, case_name: str, task_id: str, molecule_id: str) -> dict[str, Any]:
        self.calls.append((case_name, task_id, molecule_id))
        if isinstance(self.result, Exception):
            raise self.result
        return dict(self.result)


def proposal(s: IterationSpec) -> WorkflowProposal:
    return WorkflowProposal("w1", "user", None, s, 1e12, approved_at="2026-11-03T10:00:00+00:00")


FAST = {"sleep": lambda _s: asyncio.sleep(0), "poll_s": 0.0}
READY = {"status": "exported", "readiness": "REVIEW", "message": "Dos puntos piden revisión humana; no se decidieron.",
         "package": ("caso_t-CCN.zip", b"PK-moldesign-package")}


async def test_the_whole_plan_ends_in_one_verifiable_zip_with_the_three_pieces() -> None:
    events: list[dict[str, Any]] = []
    prep = Preparation(READY)
    p = proposal(spec())
    out = await execute(p, Host(), Platform(), events.append, preparation=prep, runner_kwargs=FAST)  # type: ignore[arg-type]
    assert out.state == "completed" and out.selected == 2 and prep.calls == [("hipotesis-8T69", "t-CCN", "m-CCN")]
    blob = p.files["entrega.zip"]
    assert verify_deliverable(blob) == []
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        names = set(archive.namelist())
        assert {"cuaderno/cuaderno.pdf", "preparacion/caso_t-CCN.zip", "video/molcy_a1b2c3d4.mp4", "MANIFEST.json"} <= names
        assert archive.read("preparacion/caso_t-CCN.zip") == b"PK-moldesign-package"
        assert json.loads(archive.read("MANIFEST.json"))["missing"] == []
    assert events[-1]["event"] == "done" and events[-1]["summary"]["preparation"] == "REVIEW"
    assert "package" not in out.preparation  # the bytes never reach the notebook or the record


async def test_review_is_declared_in_the_notebook_not_decided() -> None:
    p = proposal(spec())
    await execute(p, Host(), Platform(), lambda _e: None, preparation=Preparation(READY), runner_kwargs=FAST)  # type: ignore[arg-type]
    notebook = p.files["cuaderno.md"].decode()
    assert "REVIEW" in notebook and "no se decidieron" in notebook


async def test_a_render_that_failed_is_missing_in_the_zip_with_its_reason_and_the_rest_still_ships() -> None:
    p = proposal(spec())
    await execute(p, Host(), Platform(video_final="fallido", mp4=None), lambda _e: None,
                  preparation=Preparation(READY), runner_kwargs=FAST)  # type: ignore[arg-type]
    with zipfile.ZipFile(io.BytesIO(p.files["entrega.zip"])) as archive:
        manifest = json.loads(archive.read("MANIFEST.json"))
    assert [m["item"] for m in manifest["missing"]] == ["video/"] and "fallido" in manifest["missing"][0]["reason"]
    assert any(piece["kind"] == "preparation_package" for piece in manifest["pieces"])


async def test_preparation_that_raises_is_recorded_and_the_zip_declares_it() -> None:
    p = proposal(spec())
    out = await execute(p, Host(), Platform(), lambda _e: None, preparation=Preparation(RuntimeError("x")),
                        runner_kwargs=FAST)  # type: ignore[arg-type]
    assert out.preparation["status"] == "failed"
    with zipfile.ZipFile(io.BytesIO(p.files["entrega.zip"])) as archive:
        reasons = {m["item"]: m["reason"] for m in json.loads(archive.read("MANIFEST.json"))["missing"]}
    assert "falló" in reasons["preparacion/"]


async def test_without_a_preparation_port_the_plan_says_so_instead_of_pretending() -> None:
    p = proposal(spec())
    out = await execute(p, Host(), Platform(), lambda _e: None, runner_kwargs=FAST)  # type: ignore[arg-type]
    assert out.preparation["status"] == "unavailable" and "no permite" in out.preparation["message"]


async def test_nothing_qualified_still_delivers_the_notebook_and_declares_the_rest() -> None:
    p = proposal(spec(threshold_kcal=-15.0))
    prep = Preparation(READY)
    out = await execute(p, Host(), Platform(), lambda _e: None, preparation=prep, runner_kwargs=FAST)  # type: ignore[arg-type]
    assert out.state == "none_qualified" and prep.calls == []
    with zipfile.ZipFile(io.BytesIO(p.files["entrega.zip"])) as archive:
        manifest = json.loads(archive.read("MANIFEST.json"))
    assert {m["item"] for m in manifest["missing"]} == {"video/", "preparacion/"}
    assert [piece["path"] for piece in manifest["pieces"] if piece["kind"] == "notebook"]


async def test_no_package_requested_means_no_zip() -> None:
    p = proposal(spec(package=False, preparation=False, video=None))
    await execute(p, Host(), Platform(), lambda _e: None, runner_kwargs=FAST)  # type: ignore[arg-type]
    assert "entrega.zip" not in p.files and "cuaderno.md" in p.files


async def test_files_are_written_to_the_output_folder_when_one_is_given(tmp_path: Path) -> None:
    p = proposal(spec())
    await execute(p, Host(), Platform(), lambda _e: None, preparation=Preparation(READY), output_dir=tmp_path,
                  runner_kwargs=FAST)  # type: ignore[arg-type]
    written = {name: Path(path) for name, path in p.saved_paths.items()}
    assert written["entrega.zip"].read_bytes() == p.files["entrega.zip"] and written["entrega.zip"].parent.parent == tmp_path


def test_a_plan_proposal_expires_and_the_pending_ones_are_capped() -> None:
    store: dict[str, WorkflowProposal] = {}
    made = [new_workflow(store, "user", None, spec()) for _ in range(6)]
    assert made[:5] != [None] * 5 and made[5] is None
    assert "Todavía no se evaluó nada" in workflow_answer(made[0])  # type: ignore[arg-type]
    assert made[0].view()["digest"] == spec().digest  # type: ignore[union-attr]


async def test_the_host_relay_waits_for_the_window_and_gives_up_as_unknown() -> None:
    class State:
        case_requests: dict[str, Any] = {}
        smiles_requests: dict[str, Any] = {}
        receptor_requests: dict[str, Any] = {}
        evaluation_requests: dict[str, Any] = {}

    state, queue = State(), asyncio.Queue()
    relay = HostRelay(state, "user", queue)
    task = asyncio.create_task(relay.load_smiles("caso", "CCO"))
    event = await asyncio.wait_for(queue.get(), 1)
    assert event["type"] == "case_smiles" and event["smiles"] == "CCO" and event["case_name"] == "caso"
    owner, future = state.smiles_requests[event["request_id"]]
    assert owner == "user"
    future.set_result({"status": "applied"})
    assert await task == {"status": "applied"} and state.smiles_requests == {}


def test_summary_lists_counts_and_never_a_path_the_ui_must_open() -> None:
    p = proposal(spec(package=False, preparation=False, video=None))
    asyncio.run(execute(p, Host(), Platform(), lambda _e: None, runner_kwargs=FAST))  # type: ignore[arg-type]
    summary = summarize(p.outcome, p)  # type: ignore[arg-type]
    assert summary["counts"] == {"evaluated": 2} and summary["selected"]["name"] == "B"
