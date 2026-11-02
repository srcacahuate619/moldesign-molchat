"""A stand-in for the pieces of MolDesign that save a run in Moldex and queue a Molcy video.

It follows the shapes read from MolDesign's routers (``/molcy/fuentes``, ``/molcy/renderizador``,
``/molcy/trabajos``, ``/history/save``, ``/evaluation/status``), not a recorded session: what it proves is how
MolChat behaves against those shapes. It logs every call so a test can assert that a proposal wrote nothing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

MOLECULE = "3f2b8c1e-5a47-4d0e-9c1b-7e6a2d4f8b10"
VIDEO_JOB = "11111111-2222-4333-8444-555555555555"
TASK = "t-8t69"


@dataclass
class Call:
    method: str
    path: str
    params: dict[str, str]
    body: Any
    auth: str | None


@dataclass
class FakeMolDesign:
    saved: bool = False
    scenes: tuple[str, ...] = ("resultado", "receptor")
    source_available: bool = True
    renderer_available: bool = True
    gpu: bool = True
    job_status: str = "SUCCESS"
    save_status: int = 200
    video_status: int = 202
    video_reply: dict[str, Any] | None = None
    state_reply: dict[str, Any] | None = None
    calls: list[Call] = field(default_factory=list)

    def writes(self) -> list[Call]:
        return [call for call in self.calls if call.method != "GET"]

    def job(self) -> dict[str, Any]:
        result = {"molecule_id": MOLECULE, "affinity_kcal": -9.483, "target_name": "VMAT2", "vina_version": "1.2.7",
                  "vina_random_seed": 42} if self.job_status == "SUCCESS" else None
        return {"task_id": TASK, "status": self.job_status, "progress": 100 if result else 30, "result": result}

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.calls.append(Call(request.method, request.url.path, dict(request.url.params), body,
                               request.headers.get("authorization")))
        path = request.url.path
        if request.method == "GET" and path == f"/evaluation/status/{TASK}":
            return httpx.Response(200, json=self.job())
        if request.method == "GET" and path.startswith("/evaluation/status/"):
            return httpx.Response(404, json={"detail": "Tarea no encontrada"})
        if request.method == "GET" and path == "/molcy/fuentes":
            rows = [{"id": MOLECULE, "nombre": "VMAT2 · corrida", "receptor": "VMAT2", "task_id": TASK,
                     "caso": None, "disponible": self.source_available, "escenas_disponibles": list(self.scenes),
                     "motivo": None if self.source_available else "Esta corrida no conserva receptor, poses o caja verificables."}
                    ] if self.saved else []
            return httpx.Response(200, json={"moldex": rows, "receptores": []})
        if request.method == "GET" and path == "/molcy/renderizador":
            return httpx.Response(200, json={
                "disponible": self.renderer_available, "motivo": None if self.renderer_available else "Blender no está instalado.",
                "gpu_disponible": self.gpu, "motivo_gpu": None if self.gpu else "No hay una GPU compatible con Blender."})
        if request.method == "POST" and path == f"/history/save/{MOLECULE}":
            if self.save_status != 200:
                return httpx.Response(self.save_status, json={"detail": "Evaluación no encontrada."})
            self.saved = True
            return httpx.Response(200, json={"status": "saved", "molecule_id": MOLECULE, "task_id": TASK,
                                             "name": request.url.params.get("name") or "VMAT2"})
        if request.method == "POST" and path == "/molcy/trabajos":
            if self.video_status != 202:
                return httpx.Response(self.video_status, json=self.video_reply or {"detail": "Molcy rechazó la solicitud."})
            return httpx.Response(202, json=self.video_reply or {"id": VIDEO_JOB, "estado": "en_cola", "ajustes": {}})
        if request.method == "GET" and path == f"/molcy/trabajos/{VIDEO_JOB}":
            return httpx.Response(200, json=self.state_reply or {"id": VIDEO_JOB, "estado": "en_cola"})
        if request.method == "GET" and path.startswith("/molcy/trabajos/"):
            return httpx.Response(404, json={"detail": "Trabajo no encontrado."})
        return httpx.Response(404, json={"detail": "ruta no simulada"})
