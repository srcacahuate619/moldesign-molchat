"""A stand-in for the pieces of MolDesign that save a run in Moldex and queue a Molcy video.

It follows the shapes read from MolDesign's routers (``/molcy/fuentes``, ``/molcy/renderizador``,
``/molcy/trabajos``, ``/history/save``, ``/evaluation/status``), not a recorded session: what it proves is how
MolChat behaves against those shapes. It logs every call so a test can assert that a proposal wrote nothing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

MOLECULE = "3f2b8c1e-5a47-4d0e-9c1b-7e6a2d4f8b10"
VIDEO_JOB = "11111111-2222-4333-8444-555555555555"
TASK = "t-8t69"
VIDEO_BYTES = b"\x00\x00\x00\x18ftypisom-a-fake-mp4-for-tests"
PACKAGE_BYTES = b"PK\x03\x04-a-moldesign-package-exactly-as-delivered"


def comparison_fixture(name: str) -> dict[str, Any]:
    path = Path(__file__).parent / "fixtures" / "pose_comparison.json"
    return json.loads(path.read_text(encoding="utf-8"))["responses"][name]


def interactions_report(rank: int, contacts: list[tuple]) -> dict[str, Any]:
    """The shape of MolDesign's ``InteractionResponse`` (``routers/interactions.py``), with the fields the key reads.

    A contact is ``(type, residue, distance)`` or ``(type, residue, distance, extra)``; ``extra`` replaces fields of the
    interaction: the atoms, their indices and the ProLIF geometry that MolDesign reports for a real contact."""
    interactions = [{"type": kind, "residue": residue, "residue_name": residue[:3], "residue_chain": residue[-1],
                     "ligand_atom": "C1", "protein_atom": "CA", "distance": distance, "angle": None, "strength": "weak",
                     "ligand_coords": {"x": 0.0, "y": 0.0, "z": 0.0}, "protein_coords": {"x": 1.0, "y": 1.0, "z": 1.0},
                     **(extra[0] if extra else {})}
                    for kind, residue, distance, *extra in contacts]
    summary: dict[str, int] = {}
    for kind, *_rest in contacts:
        summary[kind] = summary.get(kind, 0) + 1
    return {"molecule_id": MOLECULE, "task_id": TASK, "target_pdb_id": "8T69", "pose_rank": rank,
            "pose_source_path": "run/poses.sdf", "pose_source_kind": "stored", "pose_source_sha256": "a" * 64,
            "protein_source_path": "run/receptor.pdb", "protein_source_sha256": "b" * 64, "protein_filter": "ATOM_only",
            "engine": "prolif", "hydrogen_model": "rdkit_addhs",
            "contact_coverage": "first_match_per_type_and_residue", "receptor_chemistry": "standard_residue_templates",
            "pose_identity_verification": "stored_run_path_and_current_file_hash",
            "total_interactions": len(contacts), "summary": summary, "interactions_by_type": {}, "pharmacophore_features": {},
            "interactions": interactions}


#: The contacts MolDesign measured for poses 2 and 3 of the stored 8T69 run (clopidogrel; ProLIF 2.1.0 with the receptor's
#: residue chemistry), with the atom indices and angles it reports. Pose 3's hydrogen bond and salt bridge with GLU312A rest on
#: the same N12···O768 pair, and its "halogen" contact points at a ring carbon of PHE429A: both were re-measured by hand in
#: MolDesign's ``backend/tests/test_contactos_reales_8t69.py``.
REAL_8T69_POSE_2 = [
    ("salt_bridge", "GLU312A", 4.34, {"ligand_atom": "N12", "protein_atom": "O769", "ligand_atom_indices": [12], "protein_atom_indices": [769], "geometry": {"distance": 4.34}}),
    ("hydrophobic", "ILE395A", 4.39, {"ligand_atom": "S16", "protein_atom": "C1132", "ligand_atom_indices": [16], "protein_atom_indices": [1132], "geometry": {}}),
    ("hydrophobic", "PHE135A", 4.37, {"ligand_atom": "C8", "protein_atom": "C238", "ligand_atom_indices": [8], "protein_atom_indices": [238], "geometry": {}}),
    ("hydrophobic", "PHE334A", 4.48, {"ligand_atom": "C6", "protein_atom": "C879", "ligand_atom_indices": [6], "protein_atom_indices": [879], "geometry": {}}),
    ("pi_stacking", "PHE334A", 4.73, {"ligand_atom": "C5", "protein_atom": "C879", "ligand_atom_indices": [5, 6, 7, 8, 9, 10], "protein_atom_indices": [879, 880, 882, 884, 883, 881], "geometry": {"plane_angle": 148.8, "normal_to_centroid_angle": 29.9}}),
    ("hydrophobic", "PHE429A", 4.09, {"ligand_atom": "C17", "protein_atom": "C1260", "ligand_atom_indices": [17], "protein_atom_indices": [1260], "geometry": {}}),
    ("hydrophobic", "TYR341A", 4.47, {"ligand_atom": "S16", "protein_atom": "C940", "ligand_atom_indices": [16], "protein_atom_indices": [940], "geometry": {}}),
]
REAL_8T69_POSE_3 = [
    ("hbond", "GLU312A", 3.24, {"ligand_atom": "N12", "protein_atom": "O768", "ligand_atom_indices": [12, 29], "protein_atom_indices": [768], "geometry": {"distance": 3.2423328021657496, "DHA_angle": 139.29022857667943}}),
    ("salt_bridge", "GLU312A", 3.24, {"ligand_atom": "N12", "protein_atom": "O768", "ligand_atom_indices": [12], "protein_atom_indices": [768], "geometry": {"distance": 3.24}}),
    ("hydrophobic", "LEU37A", 4.43, {"ligand_atom": "C8", "protein_atom": "C96", "ligand_atom_indices": [8], "protein_atom_indices": [96], "geometry": {}}),
    ("hydrophobic", "PHE135A", 4.15, {"ligand_atom": "C6", "protein_atom": "C238", "ligand_atom_indices": [6], "protein_atom_indices": [238], "geometry": {}}),
    ("halogen", "PHE429A", 3.38, {"ligand_atom": "C10", "protein_atom": "C1259", "ligand_atom_indices": [10, 11], "protein_atom_indices": [1259, 1261], "geometry": {"distance": 3.382702174297932, "AXD_angle": 159.74850700583985, "XAR_angle": 109.04096398835406}}),
    ("hydrophobic", "TYR341A", 3.94, {"ligand_atom": "S16", "protein_atom": "C937", "ligand_atom_indices": [16], "protein_atom_indices": [937], "geometry": {}}),
    ("hydrophobic", "TYR433A", 4.16, {"ligand_atom": "C5", "protein_atom": "C1291", "ligand_atom_indices": [5], "protein_atom_indices": [1291], "geometry": {}}),
    ("pi_stacking", "TYR433A", 4.08, {"ligand_atom": "C5", "protein_atom": "C1290", "ligand_atom_indices": [5, 6, 7, 8, 9, 10], "protein_atom_indices": [1290, 1291, 1293, 1295, 1294, 1292], "geometry": {"plane_angle": 173.6, "normal_to_centroid_angle": 28.0}}),
    ("hydrophobic", "VAL232A", 3.74, {"ligand_atom": "C18", "protein_atom": "C589", "ligand_atom_indices": [18], "protein_atom_indices": [589], "geometry": {}}),
]


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
    #: Which response of ``fixtures/pose_comparison.json`` (generated by MolDesign's own derivation) to serve.
    comparison_case: str = "todas_pasan"
    comparison_status: int = 200
    #: What MolDesign's Preparación audit says for the run, and whether its package endpoint answers.
    preparation_state: str = "REVISION"
    package_status: int = 200
    #: Contacts per pose rank: a list of ``(type, residue, distance)``, or an HTTP status to fail with.
    contacts: dict[int, list[tuple[str, str, float]] | int] = field(default_factory=dict)
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
        if request.method == "GET" and path == f"/evaluation/pose-comparison/{TASK}":
            if self.comparison_status != 200:
                return httpx.Response(self.comparison_status, json={"detail": "no disponible"})
            return httpx.Response(200, json=comparison_fixture(self.comparison_case))
        if request.method == "GET" and path.startswith("/evaluation/pose-comparison/"):
            return httpx.Response(404, json={"detail": "La evaluación no existe o ya no está disponible."})
        if request.method == "GET" and path == f"/evaluation/interactions/{MOLECULE}":
            rank = int(request.url.params.get("pose_rank", "1"))
            outcome = self.contacts.get(rank, 404)
            if isinstance(outcome, int):
                return httpx.Response(outcome, json={"detail": "sin contactos"})
            return httpx.Response(200, json=interactions_report(rank, outcome))
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
        if request.method == "POST" and path == f"/evaluation/dossier/{MOLECULE}/preparacion":
            return httpx.Response(200, json={"schema": "preparacion/v1", "estado": self.preparation_state,
                                             "razon": "Dos requisitos piden revisión.", "bloqueantes": [],
                                             "en_revision": ["Aguas del sitio", "Estado de protonación"]})
        if request.method == "POST" and path == f"/evaluation/dossier/{MOLECULE}/package":
            if self.package_status != 200:
                return httpx.Response(self.package_status, json={"detail": "No se pudo armar el paquete."})
            return httpx.Response(200, content=PACKAGE_BYTES, headers={
                "content-type": "application/zip", "content-disposition": 'attachment; filename="dossier_t-8t69.zip"'})
        if request.method == "GET" and path == f"/molcy/trabajos/{VIDEO_JOB}/video":
            return httpx.Response(200, content=VIDEO_BYTES, headers={"content-type": "video/mp4"})
        if request.method == "GET" and path.startswith("/molcy/trabajos/"):
            return httpx.Response(404, json={"detail": "Trabajo no encontrado."})
        return httpx.Response(404, json={"detail": "ruta no simulada"})
