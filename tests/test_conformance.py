"""The conformance kit proves it can see (offline, mock-live, foreign pack).

Hermetic by rule: nothing here needs a backend. Live code paths run against
a real ``MolDesignBridge`` backed by ``httpx.MockTransport``; the only live
backend run is the operator's ``--live`` invocation, whose honesty (skip
without backend/token) is also pinned here against a refused connection.
"""

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "conformance_runner_under_test", ROOT / "conformance" / "runner.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_runner()

from molchat_agent.bridge import MolDesignBridge  # noqa: E402
from molchat_agent.tools import Capability, EpistemicClass, FieldSpec  # noqa: E402
from molchat_agent.tools import catalog as real_catalog  # noqa: E402


def _packs():
    packs, verdicts = runner.load_packs(ROOT / "conformance" / "cases")
    assert packs and not [v for v in verdicts if v.status == "fail"]
    return packs


def _by_check(verdicts, check):
    return [v for v in verdicts if v.check == check]


@pytest.mark.asyncio
async def test_offline_kit_passes_on_our_packs():
    verdicts = await runner.run(ROOT / "conformance" / "cases", live=False,
                                base_url="http://127.0.0.1:9", token=None,
                                allow_remote=False)
    assert not [v for v in verdicts if v.status == "fail"], \
        [v for v in verdicts if v.status == "fail"]
    assert _by_check(verdicts, "1a") and _by_check(verdicts, "2")
    assert _by_check(verdicts, "3a") and _by_check(verdicts, "4")
    assert _by_check(verdicts, "5a")
    assert runner.report(verdicts) == 0


def test_our_cases_cover_the_whole_catalog():
    cased = {e["name"] for p in _packs() for e in p.capabilities}
    assert cased == set(real_catalog()), \
        f"uncased: {sorted(set(real_catalog()) - cased)}"


def test_served_surface_matches_skips_pending_and_fails_ghosts():
    packs = _packs()
    served = set()
    for pack in packs:
        for entry in pack.capabilities:
            cap = real_catalog()[entry["name"]]
            for template in runner.expand_templates(cap):
                served.add((cap.method.upper(), template))
    # The main backend serves everything except the unmerged CR routes.
    served -= {("POST", "/ai/proposals"),
               ("GET", "/ai/idempotency/{idempotency_key}")}
    verdicts = runner.check_served_surface(packs, served)
    assert not [v for v in verdicts if v.status == "fail"]
    assert {v.target for v in verdicts if v.status == "skip"} == {
        "create_docking_proposal", "reconcile_operation"}
    # Drop one more route: that capability fails (no pending note to save it).
    verdicts = runner.check_served_surface(packs, served - {("GET", "/targets/")})
    failed = [v for v in verdicts if v.status == "fail"]
    assert [(v.check, v.target) for v in failed] == [("1b", "list_targets")]


def test_template_expansion_covers_enum_paths():
    cat = real_catalog()
    assert sorted(runner.expand_templates(cat["export_batch"])) == [
        "/evaluation/batch/{batch_id}/csv", "/evaluation/batch/{batch_id}/export"]
    assert sorted(runner.expand_templates(cat["get_case_dossier"])) == [
        "/evaluation/dossier/{molecule_id}/package",
        "/evaluation/dossier/{molecule_id}/preview"]
    assert runner.expand_templates(cat["list_targets"]) == ["/targets/"]


def test_malformed_cases_fail_without_crashing(tmp_path):
    (tmp_path / "broken.json").write_text("{no json", encoding="utf-8")
    (tmp_path / "empty.json").write_text("{}", encoding="utf-8")
    packs, verdicts = runner.load_packs(tmp_path)
    assert packs == []
    assert {v.status for v in verdicts} == {"fail"}


def test_foreign_pack_passes_the_pure_legs(monkeypatch):
    """Portability: the kit is data-driven, not MolDesign-hardcoded."""
    foreign = {
        "probe_status": Capability(
            "probe_status", "Foreign read", "GET", "/foreign/status/{tid}",
            {"tid": FieldSpec(str, max_length=32)}, {},
            path_fields=("tid",), epistemic_class=EpistemicClass.CALCULATION,
            provenance="Foreign GET /foreign/status/{tid}"),
        "probe_launch": Capability(
            "probe_launch", "Foreign gated write", "POST", "/foreign/launch",
            {"tid": FieldSpec(str, max_length=32)}, {}, risk="approval_required",
            epistemic_class=EpistemicClass.PERSISTED,
            provenance="Foreign POST /foreign/launch"),
    }
    monkeypatch.setattr(runner, "get_catalog", lambda: foreign)
    packs = [runner.Pack(name="foreign", capabilities=[
        {"name": "probe_status", "valid_args": {"tid": "t-1"}},
        {"name": "probe_launch", "valid_args": {"tid": "t-1"}},
    ])]
    assert not [v for v in runner.check_catalog_integrity(packs)
                if v.status == "fail"]
    validation, sound = runner.check_validation(packs)
    assert not [v for v in validation if v.status == "fail"]
    assert sound == {"probe_status", "probe_launch"}
    served = {("GET", "/foreign/status/{tid}"), ("POST", "/foreign/launch")}
    assert not [v for v in runner.check_served_surface(packs, served)
                if v.status == "fail"]
    assert not [v for v in runner.check_served_surface(packs, set())
                if v.status == "pass"]


def test_register_flag_imports_third_party_modules(tmp_path, monkeypatch, capsys):
    (tmp_path / "flagpack.py").write_text("VALUE = 41\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "flagpack", raising=False)
    code = runner.main(["--register", "flagpack", "--cases",
                        str(ROOT / "conformance" / "cases")])
    assert code == 0
    assert sys.modules["flagpack"].VALUE == 41
    capsys.readouterr()


def _live_bridge(handler):
    client = httpx.AsyncClient(base_url="http://127.0.0.1:18017",
                               transport=httpx.MockTransport(handler))
    return MolDesignBridge(base_url="http://127.0.0.1:18017",
                           token="test-token", client=client)


@pytest.mark.asyncio
async def test_live_no_mutation_passes_on_steady_oracle():
    seen = {"stats": 0}

    def handle(request):
        if request.url.path == "/history/stats":
            seen["stats"] += 1
            return httpx.Response(200, json={"runs": 7})
        return httpx.Response(200, json={"ok": True})

    packs = [runner.Pack(name="mini",
                         oracle={"capability": "get_history_stats", "args": {}},
                         capabilities=[
                             {"name": "list_targets", "valid_args": {},
                              "live_read": True}])]
    async with _live_bridge(handle) as bridge:
        verdicts = await runner.check_reads_no_mutation_live(packs, bridge, packs[0].oracle)
    assert [(v.status, v.target) for v in verdicts] == [("pass", "batch")]
    assert seen["stats"] == 2  # before and after


@pytest.mark.asyncio
async def test_live_no_mutation_fails_on_moved_oracle():
    calls = {"n": 0}

    def handle(request):
        if request.url.path == "/history/stats":
            calls["n"] += 1
            return httpx.Response(200, json={"runs": calls["n"]})
        return httpx.Response(200, json={"ok": True})

    packs = [runner.Pack(name="mini",
                         oracle={"capability": "get_history_stats", "args": {}},
                         capabilities=[
                             {"name": "list_targets", "valid_args": {},
                              "live_read": True}])]
    async with _live_bridge(handle) as bridge:
        verdicts = await runner.check_reads_no_mutation_live(packs, bridge, packs[0].oracle)
    assert [v.status for v in verdicts] == ["fail"]


@pytest.mark.asyncio
async def test_live_abstention_passes_on_404_and_fails_on_invention():
    def missing(_request):
        return httpx.Response(404, json={"detail": "no existe"})

    def inventing(_request):
        return httpx.Response(200, json={"affinity_kcal": -9.9})

    packs = [runner.Pack(name="mini", capabilities=[
        {"name": "evaluation_status",
         "valid_args": {"task_id": "task-1"},
         "bogus_args": {"task_id": "task-bogus-9"}}])]
    async with _live_bridge(missing) as bridge:
        verdicts = await runner.check_abstention_live(packs, bridge)
    assert [v.status for v in verdicts] == ["pass"]
    async with _live_bridge(inventing) as bridge:
        verdicts = await runner.check_abstention_live(packs, bridge)
    assert [v.status for v in verdicts] == ["fail"]


@pytest.mark.asyncio
async def test_live_legs_skip_honestly_without_backend_or_token():
    verdicts = await runner.run(ROOT / "conformance" / "cases", live=True,
                                base_url="http://127.0.0.1:9", token=None,
                                allow_remote=False)
    by_id = {(v.check, v.target): v.status for v in verdicts}
    assert by_id[("1b", "batch")] == "skip"
    assert by_id[("3b", "batch")] == "skip"
    assert by_id[("5b", "batch")] == "skip"
    assert not [v for v in verdicts if v.status == "fail"]
    assert runner.report(verdicts) == 0


def test_ghost_capability_fails_the_run(tmp_path):
    (tmp_path / "ghost.json").write_text(json.dumps({"pack": "ghost",
        "capabilities": [{"name": "no_existe", "valid_args": {}}]}),
        encoding="utf-8")
    assert runner.main(["--cases", str(tmp_path)]) == 1
