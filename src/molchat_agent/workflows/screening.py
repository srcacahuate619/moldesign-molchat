"""A screening the person approved once: a fixed list of molecules, a stop rule and a deterministic loop.

The model never loops. It reads the request, extracts the parameters (case, receptor, molecules, threshold) and
proposes a ``ScreeningSpec``; the host validates it, shows it on a card and runs it only after one click that is
bound to the spec's digest. From then on nothing waits for a person: every molecule is its own attempt, a failure
is recorded and the loop goes on, and the stop rule is written down before the first molecule is evaluated.

What the loop decides is narrow and stated on the card: a molecule qualifies when Vina's energy for its best pose
is at or below the threshold AND (unless the person turned it off) MolDesign's physical controls for that pose
passed. Energy alone is never enough: a pose that Vina likes and PoseBusters rejects is recorded as ``near``
and does not stop the loop. MolChat computes nothing; both numbers are read from MolDesign.

Science stays in the lock. This module only orders calls, keeps the record and says what happened.
"""
from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass, field
from hashlib import sha256
import json
import math
import re
import time
import unicodedata
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

SCHEMA = "moldesign.molchat.screening/1"
MAX_MOLECULES = 12
MAX_NAME = 80
MAX_SMILES = 500
THRESHOLD_RANGE = (-30.0, 0.0)
STOPS = ("first", "all")
SCENES = ("resultado", "receptor", "busqueda", "ensamble")
FORMATS = ("horizontal", "vertical", "previsualizacion")

_PDB = re.compile(r"[A-Za-z0-9_-]{1,64}")
_TERMINAL = frozenset({"SUCCESS", "FAILURE", "FAILED", "CANCELLED", "CANCELED", "REVOKED"})
_CASE_OK = frozenset({"created", "exists"})
_RECEPTOR_OK = frozenset({"applied", "already_selected"})


class SpecError(ValueError):
    """The proposed screening is not valid; the message says which field and why."""


def _clean(text: Any, field_name: str, maximum: int) -> str:
    if not isinstance(text, str):
        raise SpecError(f"{field_name} debe ser texto.")
    value = text.strip()
    if not value or len(value) > maximum:
        raise SpecError(f"{field_name} debe tener entre 1 y {maximum} caracteres.")
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in value):
        raise SpecError(f"{field_name} contiene caracteres de control.")
    return value


@dataclass(frozen=True)
class Molecule:
    name: str
    smiles: str


@dataclass(frozen=True)
class VideoRequest:
    scene: str
    format: str
    title: str | None = None


@dataclass(frozen=True)
class ScreeningSpec:
    case_name: str
    pdb_id: str
    molecules: tuple[Molecule, ...]
    threshold_kcal: float
    stop: str = "first"
    require_physical: bool = True
    save: bool = True
    video: VideoRequest | None = None
    preparation: bool = False
    package: bool = False
    original_request: str = ""
    per_molecule_timeout_s: int = 420
    budget_s: int = 2400

    @classmethod
    def from_dict(cls, data: Any) -> "ScreeningSpec":
        if not isinstance(data, dict):
            raise SpecError("El cribado debe ser un objeto.")
        known = {"case_name", "pdb_id", "molecules", "threshold_kcal", "stop", "require_physical", "save", "video",
                 "preparation", "package", "original_request", "per_molecule_timeout_s", "budget_s"}
        if set(data) - known:
            raise SpecError(f"Campos desconocidos: {sorted(set(data) - known)}.")
        for required in ("case_name", "pdb_id", "molecules", "threshold_kcal"):
            if required not in data:
                raise SpecError(f"Falta {required}.")
        case_name = _clean(data["case_name"], "case_name", 100)
        pdb_id = _clean(data["pdb_id"], "pdb_id", 64).upper()
        if not _PDB.fullmatch(pdb_id):
            raise SpecError("pdb_id no es un identificador de receptor válido.")
        raw = data["molecules"]
        if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_MOLECULES:
            raise SpecError(f"La lista debe tener entre 1 y {MAX_MOLECULES} moléculas.")
        molecules: list[Molecule] = []
        for index, item in enumerate(raw, start=1):
            if not isinstance(item, dict) or set(item) - {"name", "smiles"} or "smiles" not in item:
                raise SpecError(f"Molécula {index}: indica name (opcional) y smiles.")
            smiles = _clean(item["smiles"], f"smiles de la molécula {index}", MAX_SMILES)
            if re.search(r"\s", smiles):
                raise SpecError(f"smiles de la molécula {index} no puede llevar espacios.")
            name = _clean(item.get("name") or f"molécula {index}", f"name de la molécula {index}", MAX_NAME)
            molecules.append(Molecule(name, smiles))
        if len({m.smiles for m in molecules}) != len(molecules):
            raise SpecError("La lista repite un SMILES: cada molécula se evalúa una sola vez.")
        threshold = data["threshold_kcal"]
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold):
            raise SpecError("threshold_kcal debe ser un número.")
        if not THRESHOLD_RANGE[0] <= threshold < THRESHOLD_RANGE[1]:
            raise SpecError("threshold_kcal debe ser negativo (la energía de Vina buena es más baja) y no menor que -30.")
        stop = data.get("stop", "first")
        if stop not in STOPS:
            raise SpecError("stop debe ser first o all.")
        for key in ("require_physical", "save", "preparation", "package"):
            if key in data and not isinstance(data[key], bool):
                raise SpecError(f"{key} debe ser verdadero o falso.")
        video = None
        if data.get("video") is not None:
            raw_video = data["video"]
            if not isinstance(raw_video, dict) or set(raw_video) - {"scene", "format", "title"}:
                raise SpecError("video admite scene, format y title.")
            if raw_video.get("scene") not in SCENES or raw_video.get("format") not in FORMATS:
                raise SpecError("video necesita una escena y un formato válidos.")
            title = _clean(raw_video["title"], "title del vídeo", 80) if raw_video.get("title") is not None else None
            video = VideoRequest(raw_video["scene"], raw_video["format"], title)
        save = data.get("save", True)
        if video is not None and not save:
            save = True  # a video can only come from a run saved in Moldex: say it on the card, not silently
        request = data.get("original_request", "")
        if not isinstance(request, str) or len(request) > 4000:
            raise SpecError("original_request debe ser texto de hasta 4000 caracteres.")
        timeout = data.get("per_molecule_timeout_s", 420)
        budget = data.get("budget_s", 2400)
        for label, value, low, high in (("per_molecule_timeout_s", timeout, 30, 1800), ("budget_s", budget, 60, 7200)):
            if type(value) is not int or not low <= value <= high:
                raise SpecError(f"{label} debe ser un entero entre {low} y {high}.")
        return cls(case_name, pdb_id, tuple(molecules), float(threshold), stop, data.get("require_physical", True), save,
                   video, data.get("preparation", False), data.get("package", False), request, timeout, budget)

    def as_dict(self) -> dict[str, Any]:
        return {"case_name": self.case_name, "pdb_id": self.pdb_id,
                "molecules": [{"name": m.name, "smiles": m.smiles} for m in self.molecules],
                "threshold_kcal": self.threshold_kcal, "stop": self.stop, "require_physical": self.require_physical,
                "save": self.save,
                "video": None if self.video is None else {"scene": self.video.scene, "format": self.video.format,
                                                          "title": self.video.title},
                "preparation": self.preparation, "package": self.package, "original_request": self.original_request,
                "per_molecule_timeout_s": self.per_molecule_timeout_s, "budget_s": self.budget_s}

    @property
    def digest(self) -> str:
        normal = json.dumps({"schema": SCHEMA, **self.as_dict()}, sort_keys=True, ensure_ascii=False,
                            separators=(",", ":"))
        return "sha256:" + sha256(normal.encode("utf-8")).hexdigest()

    def card_lines(self) -> list[str]:
        """What the approval card shows: everything the run will do, and the rule that stops it."""
        rule = f"Vina ≤ {self.threshold_kcal:g} kcal/mol"
        if self.require_physical:
            rule += " y controles físicos de la mejor pose superados"
        lines = [f"Caso «{self.case_name}» · receptor {self.pdb_id}",
                 f"{len(self.molecules)} moléculas, una por una: " + ", ".join(m.name for m in self.molecules),
                 f"Se detiene {'en la primera que cumple' if self.stop == 'first' else 'al recorrer la lista entera'}: {rule}",
                 "Si una molécula falla, se anota y se sigue con la siguiente."]
        if self.save:
            lines.append("La que cumpla se guarda en Moldex.")
        if self.video is not None:
            lines.append(f"Vídeo de Molcy (solo GPU): escena {self.video.scene}, formato {self.video.format}; "
                         "el cierre de MolDesign se añade siempre.")
        if self.preparation:
            lines.append("Se audita la corrida en Preparación; si queda en revisión, se declara, no se decide.")
        if self.package:
            lines.append("Al final se junta todo en un único ZIP.")
        lines.append(f"Tope: {self.per_molecule_timeout_s // 60} min por molécula y {self.budget_s // 60} min en total.")
        return lines


# ── Ports: what the loop needs from the host's interface and from MolDesign ─────────────────────────


class HostPort(Protocol):
    """The interface in the person's window. Each call returns the host's closed status vocabulary."""
    async def create_case(self, name: str) -> dict[str, Any]: ...
    async def assign_receptor(self, case_name: str, pdb_id: str) -> dict[str, Any]: ...
    async def load_smiles(self, case_name: str, smiles: str) -> dict[str, Any]: ...
    async def evaluate(self, case_name: str) -> dict[str, Any]: ...


class PlatformPort(Protocol):
    """MolDesign over HTTP, with the person's session."""
    async def job(self, task_id: str) -> dict[str, Any]: ...
    async def top_pose(self, task_id: str) -> dict[str, Any]: ...
    async def save(self, task_id: str, molecule_id: str, name: str | None) -> dict[str, Any]: ...
    async def request_video(self, task_id: str, molecule_id: str, video: VideoRequest) -> dict[str, Any]: ...
    async def video_status(self, job_id: str) -> dict[str, Any]: ...


Emit = Callable[[dict[str, Any]], None]


@dataclass
class MoleculeRecord:
    index: int
    name: str
    smiles: str
    status: str = "pending"  # pending | evaluated | failed | timeout | unknown | skipped
    outcome: str | None = None  # qualifies | near | below_threshold (only when evaluated)
    task_id: str | None = None
    molecule_id: str | None = None
    affinity_kcal: float | None = None
    physical_status: str | None = None
    reason: str | None = None
    seconds: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class ScreeningOutcome:
    spec: dict[str, Any]
    digest: str
    state: str = "running"  # completed | none_qualified | blocked | budget_exhausted
    records: list[MoleculeRecord] = field(default_factory=list)
    selected: int | None = None  # index of the molecule the rest of the plan used
    saved: dict[str, Any] | None = None
    video: dict[str, Any] | None = None
    preparation: dict[str, Any] | None = None
    deliverable: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "spec": copy.deepcopy(self.spec), "digest": self.digest, "state": self.state,
                "records": [r.as_dict() for r in self.records], "selected": self.selected, "saved": self.saved,
                "video": self.video, "preparation": self.preparation, "deliverable": self.deliverable,
                "notes": list(self.notes)}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def judge(spec: ScreeningSpec, affinity: float | None, physical: str | None) -> tuple[str, str]:
    """``(outcome, reason)`` for one evaluated molecule, from numbers MolDesign returned."""
    if affinity is None:
        return "below_threshold", "MolDesign no devolvió la energía de Vina."
    if affinity > spec.threshold_kcal:
        return "below_threshold", f"Vina {affinity:g} kcal/mol no llega al umbral de {spec.threshold_kcal:g}."
    if spec.require_physical and physical != "passed":
        shown = physical or "no evaluados"
        return "near", (f"Vina {affinity:g} kcal/mol llega al umbral, pero los controles físicos de la mejor pose "
                        f"quedaron «{shown}»: no cumple la regla.")
    return "qualifies", f"Vina {affinity:g} kcal/mol y controles físicos superados."


async def _noop_sleep(_: float) -> None:
    return None


class ScreeningRunner:
    def __init__(self, spec: ScreeningSpec, host: HostPort, platform: PlatformPort, emit: Emit | None = None, *,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 poll_s: float = 3.0, busy_retries: int = 3, busy_wait_s: float = 5.0) -> None:
        self.spec, self.host, self.platform = spec, host, platform
        self._emit = emit or (lambda _event: None)
        self._clock, self._sleep = clock, sleep
        self._poll_s, self._busy_retries, self._busy_wait_s = poll_s, busy_retries, busy_wait_s
        self.outcome = ScreeningOutcome(spec.as_dict(), spec.digest,
                                        records=[MoleculeRecord(i, m.name, m.smiles)
                                                 for i, m in enumerate(spec.molecules, start=1)])

    def emit(self, kind: str, **data: Any) -> None:
        self._emit({"type": "workflow", "event": kind, **data})

    def _record(self, index: int) -> MoleculeRecord:
        return self.outcome.records[index - 1]

    async def run(self) -> ScreeningOutcome:
        out, spec = self.outcome, self.spec
        started = self._clock()
        self.emit("started", digest=out.digest, molecules=len(spec.molecules))
        if not await self._prepare_case():
            out.state = "blocked"
            for record in out.records:
                record.status, record.reason = "skipped", "El caso no quedó preparado: no se evaluó nada."
            self.emit("finished", state=out.state)
            return out
        qualifiers: list[MoleculeRecord] = []
        for record in out.records:
            if qualifiers and spec.stop == "first":
                record.status, record.reason = "skipped", "Ya se cumplió la regla de parada."
                continue
            if self._clock() - started >= spec.budget_s:
                record.status, record.reason = "skipped", "Se agotó el tiempo total del plan."
                out.state = "budget_exhausted"
                continue
            await self._screen_one(record)
            self.emit("molecule", record=record.as_dict())
            if record.outcome == "qualifies":
                qualifiers.append(record)
        if qualifiers:
            best = min(qualifiers, key=lambda r: (r.affinity_kcal if r.affinity_kcal is not None else 0.0, r.index))
            out.selected = best.index
            if out.state == "running":
                out.state = "completed"
            await self._after_selection(best)
        elif out.state == "running":
            out.state = "none_qualified"
            out.notes.append("Ninguna molécula cumplió la regla: no se guardó nada ni se pidió el vídeo.")
        self.emit("finished", state=out.state)
        return out

    async def _prepare_case(self) -> bool:
        spec, out = self.spec, self.outcome
        for label, call, ok in (("crear el caso", lambda: self.host.create_case(spec.case_name), _CASE_OK),
                                ("asignar el receptor", lambda: self.host.assign_receptor(spec.case_name, spec.pdb_id),
                                 _RECEPTOR_OK)):
            try:
                result = await call()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - the plan must end with an honest state, never hang
                out.notes.append(f"No se pudo {label}: {type(exc).__name__}.")
                return False
            status = result.get("status") if isinstance(result, dict) else None
            self.emit("case_step", step=label, status=status)
            if status not in ok:
                out.notes.append(f"No se pudo {label}: el host respondió «{status or 'sin respuesta'}».")
                return False
            if status == "exists":
                out.notes.append("El caso ya existía: se reutilizó con su nombre; sus inputs se reemplazan molécula a molécula.")
        return True

    async def _screen_one(self, record: MoleculeRecord) -> None:
        began = self._clock()
        self.emit("molecule_started", index=record.index, name=record.name)
        try:
            await self._evaluate(record)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - one molecule never stops the others
            record.status, record.reason = "failed", f"Error inesperado ({type(exc).__name__}); se siguió con la siguiente."
        record.seconds = round(self._clock() - began, 1)

    async def _evaluate(self, record: MoleculeRecord) -> None:
        spec = self.spec
        loaded = await self.host.load_smiles(spec.case_name, record.smiles)
        if loaded.get("status") != "applied":
            record.status, record.reason = "failed", f"No se cargó la molécula en el caso («{loaded.get('status')}»)."
            return
        started: dict[str, Any] = {}
        for attempt in range(self._busy_retries + 1):
            started = await self.host.evaluate(spec.case_name)
            if started.get("status") != "busy" or attempt == self._busy_retries:
                break
            await self._sleep(self._busy_wait_s)
        status = started.get("status")
        task_id = started.get("task_id")
        if status == "unknown":
            record.status = "unknown"
            record.reason = "No se pudo confirmar si la evaluación empezó; no se repitió para no duplicarla."
            return
        if status not in {"started", "started_unregistered"} or not isinstance(task_id, str):
            reason = started.get("reason") if isinstance(started.get("reason"), str) else None
            record.status = "failed"
            record.reason = f"MolDesign no inició la evaluación («{status}»)" + (f": {reason}" if reason else ".")
            return
        record.task_id = task_id
        job = await self._follow(task_id, spec.per_molecule_timeout_s)
        if job is None:
            record.status, record.reason = "timeout", f"La evaluación no terminó en {spec.per_molecule_timeout_s} s."
            return
        if job.get("status") != "SUCCESS" or not isinstance(job.get("result"), dict):
            error = job.get("error") if isinstance(job.get("error"), str) else None
            record.status = "failed"
            record.reason = f"La evaluación terminó en {job.get('status')}" + (f": {error[:200]}" if error else ".")
            return
        result = job["result"]
        record.affinity_kcal = _number(result.get("affinity_kcal"))
        molecule_id = result.get("molecule_id")
        record.molecule_id = molecule_id if isinstance(molecule_id, str) else None
        top = await self.platform.top_pose(task_id)
        record.physical_status = top.get("physical_status") if isinstance(top.get("physical_status"), str) else None
        record.status = "evaluated"
        record.outcome, record.reason = judge(spec, record.affinity_kcal, record.physical_status)

    async def _follow(self, task_id: str, timeout_s: int) -> dict[str, Any] | None:
        deadline = self._clock() + timeout_s
        while True:
            job = await self.platform.job(task_id)
            if isinstance(job, dict) and job.get("status") in _TERMINAL:
                return job
            if self._clock() >= deadline:
                return None
            await self._sleep(self._poll_s)

    async def _after_selection(self, best: MoleculeRecord) -> None:
        """Save, ask for the video and follow it. Each step is its own attempt and its own line in the record."""
        spec, out = self.spec, self.outcome
        if spec.save and best.task_id and best.molecule_id:
            out.saved = await self._guarded("guardar en Moldex", self.platform.save(best.task_id, best.molecule_id, best.name))
            self.emit("saved", result=out.saved)
        if spec.video is not None and best.task_id and best.molecule_id:
            if out.saved is None or out.saved.get("status") not in {"saved", "already_saved"}:
                out.video = {"status": "not_requested", "message": "No se pidió el vídeo porque la corrida no quedó guardada en Moldex."}
            else:
                out.video = await self._guarded("pedir el vídeo", self.platform.request_video(best.task_id, best.molecule_id, spec.video))
            self.emit("video", result=out.video)
        # Preparation and the package are added by the callers that own those ports (see runner_extras).

    async def _guarded(self, what: str, call: Awaitable[dict[str, Any]]) -> dict[str, Any]:
        try:
            result = await call
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            self.outcome.notes.append(f"No se pudo {what}: {type(exc).__name__}.")
            return {"status": "failed", "message": f"No se pudo {what}."}
        return result if isinstance(result, dict) else {"status": "failed", "message": f"No se pudo {what}."}

    async def follow_video(self, timeout_s: int = 1800) -> dict[str, Any] | None:
        """Wait for the Molcy job the loop started; the video is the slow step and Preparación runs meanwhile."""
        video = self.outcome.video
        job_id = video.get("job_id") if isinstance(video, dict) else None
        if not isinstance(job_id, str):
            return video
        deadline = self._clock() + timeout_s
        while True:
            status = await self._guarded("consultar el vídeo", self.platform.video_status(job_id))
            video.update({"job_state": status.get("job_state"), "phase": status.get("phase"),
                          "progress": status.get("progress")})
            if status.get("job_state") in {"completo", "fallido", "cancelado"} or status.get("status") in {"not_found", "invalid"}:
                video["final"] = status.get("job_state") or status.get("status")
                return video
            if self._clock() >= deadline:
                video["final"] = "timeout"
                return video
            await self._sleep(self._poll_s * 2)
