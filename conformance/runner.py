"""Run the adapter conformance kit (§6.4) against cased capabilities.

Offline legs (default: deterministic, no network): catalog integrity (1a),
argument validation (2), reads without effect (3a), approval gating (4),
errors as abstention (5a). Live legs (``--live``): served-surface match via
the backend's OpenAPI document (1b), reads without mutation behind a state
oracle (3b), live errors as abstention (5b).

Usage (from the repo root)::

    PYTHONPATH=src python -m conformance.runner
    PYTHONPATH=src python -m conformance.runner --live
    MOLDESIGN_BASE_URL=http://127.0.0.1:18017 MOLDESIGN_TOKEN=... \\
        PYTHONPATH=src python -m conformance.runner --live

Exit 0 = no failures (skips are listed, never hidden); 1 = any failure.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import httpx  # noqa: E402

from molchat_agent.bridge import (  # noqa: E402
    BridgeError,
    MolDesignBridge,
    validate_base_url,
)
from molchat_agent.executor import AgentExecutor  # noqa: E402
from molchat_agent.plan import Plan  # noqa: E402
from molchat_agent.tools import EpistemicClass, PlanValidationError  # noqa: E402
from molchat_agent.tools import catalog as get_catalog  # noqa: E402
from molchat_agent.tools.catalog import RESPONSE_KINDS, RISKS  # noqa: E402

import molchat_agent.tools.molcy  # noqa: E402,F401 - registers the pack
import molchat_agent.tools.moldesign  # noqa: E402,F401 - registers the pack

CASES_DIR = ROOT / "conformance" / "cases"
ABSTAINED = ("failed", "blocked")
ENUM_PATH = re.compile(r"^[A-Za-z0-9_|-]+$")


@dataclass
class Verdict:
    check: str  # "1a", "1b", "2", "3a", "3b", "4", "5a", "5b", "cases"
    target: str
    status: str  # "pass" | "fail" | "skip"
    detail: str = ""


@dataclass
class Pack:
    name: str
    openapi: str = "/openapi.json"
    oracle: dict[str, Any] | None = None
    capabilities: list[dict[str, Any]] = field(default_factory=list)


class RecordingBridge:
    """Test double: records calls, answers scripted values or raises."""

    def __init__(self, script: Any = None, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, dict, dict]] = []
        self._script = script
        self._error = error

    async def call(self, capability: str, args: dict[str, Any], **kwargs: Any) -> Any:
        self.calls.append((capability, dict(args), dict(kwargs)))
        if self._error is not None:
            raise self._error
        if callable(self._script):
            return self._script(capability, args)
        if isinstance(self._script, dict):
            return dict(self._script)
        return {"ok": True}


def load_packs(cases_dir: Path) -> tuple[list[Pack], list[Verdict]]:
    packs: list[Pack] = []
    verdicts: list[Verdict] = []
    if not cases_dir.is_dir():
        return packs, [Verdict("cases", str(cases_dir), "fail", "cases dir missing")]
    for path in sorted(cases_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            caps = data["capabilities"]
            assert isinstance(caps, list) and caps
            for entry in caps:
                assert isinstance(entry.get("name"), str)
                assert isinstance(entry.get("valid_args"), dict)
        except (ValueError, OSError, KeyError, AssertionError) as exc:
            verdicts.append(Verdict("cases", path.name, "fail",
                                    f"unusable cases file: {exc}"))
            continue
        packs.append(Pack(name=str(data.get("pack", path.stem)),
                          openapi=str(data.get("openapi", "/openapi.json")),
                          oracle=data.get("state_oracle"),
                          capabilities=caps))
        verdicts.append(Verdict("cases", path.name, "pass",
                                f"{len(caps)} cased capabilities"))
    if not packs and not verdicts:
        verdicts.append(Verdict("cases", cases_dir.name, "fail", "no cases files"))
    return packs, verdicts


def check_catalog_integrity(packs: list[Pack]) -> list[Verdict]:
    """1a: every cased entry exists, is sound, and names its provenance."""
    verdicts: list[Verdict] = []
    cased: set[str] = set()
    for pack in packs:
        for entry in pack.capabilities:
            name = entry["name"]
            cased.add(name)
            try:
                cap = get_catalog()[name]
            except KeyError:
                verdicts.append(Verdict("1a", name, "fail",
                                        "cased but not registered (ghost)"))
                continue
            problems = []
            if cap.risk not in RISKS:
                problems.append(f"risk {cap.risk!r}")
            if not isinstance(cap.epistemic_class, EpistemicClass):
                problems.append("epistemic_class undeclared")
            if not cap.provenance.strip():
                problems.append("provenance empty")
            if not cap.version.strip() or not cap.method.strip() \
                    or not cap.path.strip():
                problems.append("version/method/path empty")
            if not isinstance(cap.outputs, tuple):
                problems.append("outputs not a tuple")
            if cap.response not in RESPONSE_KINDS:
                problems.append(f"response {cap.response!r}")
            verdicts.append(Verdict(
                "1a", name, "fail" if problems else "pass", "; ".join(problems)))
    for name in sorted(set(get_catalog()) - cased):
        verdicts.append(Verdict("1a", name, "skip",
                                "registered but uncased (no verdict claimed)"))
    return verdicts


def expand_templates(cap: Any) -> list[str]:
    """Path templates with pure-enum params expanded (e.g. {format} over
    ``export|csv``); every expansion must exist on the served surface."""
    templates = [cap.path]
    fields = cap.required | cap.optional
    for fname in cap.path_fields:
        spec = fields.get(fname)
        pattern = spec.pattern if spec else None
        if pattern and "|" in pattern and ENUM_PATH.fullmatch(pattern):
            templates = [t.replace("{%s}" % fname, alt)
                         for t in templates for alt in pattern.split("|")]
    return templates


def check_served_surface(packs: list[Pack], served: set[tuple[str, str]]) -> list[Verdict]:
    """1b: every cased (method, path) is served; pending notes skip loudly."""
    verdicts: list[Verdict] = []
    for pack in packs:
        for entry in pack.capabilities:
            name = entry["name"]
            try:
                cap = get_catalog()[name]
            except KeyError:
                continue  # 1a already failed it
            missing = [t for t in expand_templates(cap)
                       if (cap.method.upper(), t) not in served]
            if not missing:
                verdicts.append(Verdict("1b", name, "pass",
                                        f"{cap.method} {cap.path}"))
            elif entry.get("pending_surface"):
                verdicts.append(Verdict("1b", name, "skip",
                                        f"undeclared upstream: {entry['pending_surface']}"))
            else:
                verdicts.append(Verdict("1b", name, "fail",
                                        f"not served: {missing}"))
    return verdicts


def check_validation(packs: list[Pack]) -> tuple[list[Verdict], set[str]]:
    """2: valid args pass; extra/missing/wrong-typed args raise."""
    verdicts: list[Verdict] = []
    sound: set[str] = set()
    for pack in packs:
        for entry in pack.capabilities:
            name = entry["name"]
            try:
                cap = get_catalog()[name]
            except KeyError:
                continue
            args = entry["valid_args"]
            failures: list[str] = []
            try:
                cap.validate(args)
            except PlanValidationError as exc:
                failures.append(f"valid_args rejected: {exc}")
            else:
                sound.add(name)
            mutated = dict(args, zz_conformance_extra=1)
            try:
                cap.validate(mutated)
                failures.append("extra parameter accepted")
            except PlanValidationError:
                pass
            for dropped in cap.required:
                pruned = {k: v for k, v in args.items() if k != dropped}
                try:
                    cap.validate(pruned)
                    failures.append(f"missing {dropped} accepted")
                except PlanValidationError:
                    pass
            fields = cap.required | cap.optional
            for fname, spec in fields.items():
                probe = dict(args)
                probe[fname] = "no-entero" if spec.kind is int else 12345
                try:
                    cap.validate(probe)
                    failures.append(f"wrong type for {fname} accepted")
                except PlanValidationError:
                    pass
            try:
                cap.validate(["not", "a", "dict"])  # type: ignore[arg-type]
                failures.append("non-object args accepted")
            except PlanValidationError:
                pass
            verdicts.append(Verdict("2", name, "fail" if failures else "pass",
                                    "; ".join(failures)))
    return verdicts, sound


def _plan_for(name: str, args: dict[str, Any]) -> Plan:
    return Plan.from_dict({
        "goal": f"conformidad: {name}", "planner": "conformance",
        "steps": [{"id": "s1", "capability": name, "arguments": dict(args),
                   "rationale": "caso del kit"}],
    })


def _preflight_scripted(capability: str, _args: dict) -> dict:
    if capability == "check_preflight":
        return {"technical_blockers": [], "warnings": [], "not_evaluated": []}
    return {"ok": True, "capability": capability}


async def check_reads_no_effect(packs: list[Pack], sound: set[str]) -> list[Verdict]:
    """3a: reads complete with one call and no idempotency key."""
    verdicts: list[Verdict] = []
    for pack in packs:
        for entry in pack.capabilities:
            name = entry["name"]
            if name not in sound:
                continue
            cap = get_catalog()[name]
            if cap.risk != "read":
                continue
            bridge = RecordingBridge(script=_preflight_scripted)
            report = await AgentExecutor(bridge).execute(_plan_for(name, entry["valid_args"]))
            if report.state != "completed":
                verdicts.append(Verdict("3a", name, "fail",
                                        f"state {report.state}"))
            elif len(bridge.calls) != 1:
                verdicts.append(Verdict("3a", name, "fail",
                                        f"{len(bridge.calls)} backend calls"))
            elif bridge.calls[0][2].get("idempotency_key") is not None:
                verdicts.append(Verdict("3a", name, "fail",
                                        "read carried an idempotency key"))
            else:
                verdicts.append(Verdict("3a", name, "pass", "one keyless call"))
    return verdicts


async def check_gating(packs: list[Pack], sound: set[str]) -> list[Verdict]:
    """4: non-reads without approval wait; wrong digests wait too; zero sends."""
    verdicts: list[Verdict] = []
    for pack in packs:
        for entry in pack.capabilities:
            name = entry["name"]
            if name not in sound:
                continue
            if get_catalog()[name].risk == "read":
                continue
            plan = _plan_for(name, entry["valid_args"])
            bridge = RecordingBridge()
            first = await AgentExecutor(bridge).execute(plan)
            second = await AgentExecutor(bridge).execute(
                plan, approval_digest="sha256:" + "0" * 64, approved_steps={"s1"})
            if first.state != "awaiting_approval" or second.state != "awaiting_approval":
                verdicts.append(Verdict("4", name, "fail",
                                        f"{first.state}/{second.state}"))
            elif bridge.calls:
                verdicts.append(Verdict("4", name, "fail",
                                        f"sent {len(bridge.calls)} calls unapproved"))
            else:
                verdicts.append(Verdict("4", name, "pass", "gated, nothing sent"))
    return verdicts


async def check_abstention(packs: list[Pack], sound: set[str]) -> list[Verdict]:
    """5a: backend errors end failed/blocked with an error and no result."""
    verdicts: list[Verdict] = []
    for pack in packs:
        for entry in pack.capabilities:
            name = entry["name"]
            if name not in sound:
                continue
            cap = get_catalog()[name]
            bridge = RecordingBridge(error=BridgeError("falla conformada"))
            plan = _plan_for(name, entry["valid_args"])
            if cap.risk == "read":
                report = await AgentExecutor(bridge).execute(plan)
            else:
                report = await AgentExecutor(bridge).execute(
                    plan, approval_digest=plan.digest, approved_steps={"s1"})
            outcome = report.outcomes[0] if report.outcomes else None
            if report.state not in ABSTAINED:
                verdicts.append(Verdict("5a", name, "fail",
                                        f"state {report.state}"))
            elif outcome is None or outcome.result is not None \
                    or not (outcome.error or "").strip():
                verdicts.append(Verdict("5a", name, "fail",
                                        "error without abstention shape"))
            else:
                verdicts.append(Verdict("5a", name, "pass",
                                        f"{report.state} with error, no result"))
    return verdicts


async def fetch_served_routes(base_url: str, openapi_path: str) -> set[tuple[str, str]] | None:
    """(METHOD, path-template) from the backend's OpenAPI document, or None
    when the backend is unreachable or hides it (the caller skips then)."""
    try:
        async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
            response = await client.get(base_url.rstrip("/") + openapi_path)
            if response.status_code >= 400:
                return None
            paths = response.json().get("paths", {})
            return {(m.upper(), p) for p, ops in paths.items() for m in ops}
    except (httpx.RequestError, ValueError):
        return None


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


async def check_reads_no_mutation_live(packs: list[Pack], bridge: MolDesignBridge,
                                       oracle: dict[str, Any]) -> list[Verdict]:
    """3b: the state oracle is identical before and after the live reads."""
    try:
        before = await bridge.call(oracle["capability"], oracle.get("args", {}))
    except Exception as exc:  # noqa: BLE001 - oracle failure skips, never fails
        return [Verdict("3b", "batch", "skip", f"no oracle: {exc}")]
    lines: list[str] = []
    for pack in packs:
        for entry in pack.capabilities:
            if not entry.get("live_read"):
                continue
            report = await AgentExecutor(bridge).execute(
                _plan_for(entry["name"], entry["valid_args"]))
            lines.append(f"{entry['name']}={report.state}")
            # "blocked" is a completed read in this kit's contract: for a
            # preflight, blockers ARE the data (measured live: check_preflight
            # against MolDesign blocks on a fresh catalog and the executor
            # stops by design). What 3b certifies is that no mutation moved
            # the oracle; a failed or ambiguous read proves nothing and fails.
            if report.state not in ("completed", "blocked"):
                return [Verdict("3b", entry["name"], "fail",
                                f"live read did not complete: {report.state}")]
    try:
        after = await bridge.call(oracle["capability"], oracle.get("args", {}))
    except Exception as exc:  # noqa: BLE001 - same honesty as above
        return [Verdict("3b", "batch", "skip", f"oracle lost: {exc}")]
    if _canonical(before) != _canonical(after):
        return [Verdict("3b", "batch", "fail",
                        f"oracle moved: {'; '.join(lines)}")]
    return [Verdict("3b", "batch", "pass", f"oracle steady ({'; '.join(lines)})")]


async def check_abstention_live(packs: list[Pack], bridge: MolDesignBridge) -> list[Verdict]:
    """5b: live errors (bogus but well-formed entities) abstain, never invent."""
    verdicts: list[Verdict] = []
    for pack in packs:
        for entry in pack.capabilities:
            bogus = entry.get("bogus_args")
            if not bogus:
                continue
            name = entry["name"]
            report = await AgentExecutor(bridge).execute(_plan_for(name, bogus))
            outcome = report.outcomes[0] if report.outcomes else None
            if report.state not in ABSTAINED:
                verdicts.append(Verdict("5b", name, "fail",
                                        f"bogus entity {report.state}"))
            elif outcome is None or outcome.result is not None:
                verdicts.append(Verdict("5b", name, "fail",
                                        "error carried a result"))
            else:
                verdicts.append(Verdict("5b", name, "pass",
                                        f"{report.state}, nothing fabricated"))
    if not verdicts:
        verdicts.append(Verdict("5b", "batch", "skip", "no bogus cases cased"))
    return verdicts


def contract_required(adapter: str, registrations: list[str]) -> bool:
    """MolDesign always negotiates; a custom adapter must be explicit."""
    if adapter == "moldesign":
        return True
    if adapter == "generic" and registrations:
        return False
    if adapter == "generic":
        raise ValueError("el adaptador genérico exige registrar un pack explícito")
    raise ValueError("modo de adaptador desconocido")


async def check_platform_protocol(bridge: MolDesignBridge, required: bool) -> Verdict | None:
    """An incompatible MolDesign contract fails instead of hiding in skips."""
    if not required:
        return None
    try:
        await bridge.ensure_contract("platform-actions/1")
    except BridgeError as exc:
        return Verdict("protocol", "moldesign", "fail", str(exc))
    return Verdict("protocol", "moldesign", "pass", "moldesign.molchat/1")


async def run(cases_dir: Path, *, live: bool, base_url: str,
              token: str | None, allow_remote: bool,
              require_contract: bool = True) -> list[Verdict]:
    verdicts: list[Verdict] = []
    packs, case_verdicts = load_packs(cases_dir)
    verdicts.extend(case_verdicts)
    if not packs:
        return verdicts
    verdicts.extend(check_catalog_integrity(packs))
    validation, sound = check_validation(packs)
    verdicts.extend(validation)
    verdicts.extend(await check_reads_no_effect(packs, sound))
    verdicts.extend(await check_gating(packs, sound))
    verdicts.extend(await check_abstention(packs, sound))
    if not live:
        return verdicts
    openapi_path = next((p.openapi for p in packs if p.openapi), "/openapi.json")
    served = await fetch_served_routes(base_url, openapi_path)
    if served is None:
        verdicts.append(Verdict("1b", "batch", "skip",
                                f"{base_url}{openapi_path} unreachable"))
    else:
        verdicts.extend(check_served_surface(packs, served))
    if not token:
        verdicts.append(Verdict("3b", "batch", "skip", "MOLDESIGN_TOKEN unset"))
        verdicts.append(Verdict("5b", "batch", "skip", "MOLDESIGN_TOKEN unset"))
        return verdicts
    oracle = next((p.oracle for p in packs if p.oracle), None)
    async with MolDesignBridge(base_url, token=token,
                               allow_remote=allow_remote,
                               require_contract=require_contract) as bridge:
        protocol = await check_platform_protocol(bridge, require_contract)
        if protocol is not None:
            verdicts.append(protocol)
            if protocol.status == "fail":
                return verdicts
        if oracle is None:
            verdicts.append(Verdict("3b", "batch", "skip", "no oracle cased"))
        else:
            verdicts.extend(await check_reads_no_mutation_live(packs, bridge, oracle))
        verdicts.extend(await check_abstention_live(packs, bridge))
    return verdicts


def report(verdicts: list[Verdict]) -> int:
    counts = {"pass": 0, "fail": 0, "skip": 0}
    for verdict in verdicts:
        counts[verdict.status] += 1
        print(f"{verdict.status.upper():4} {verdict.check}:{verdict.target} "
              f"{verdict.detail}".rstrip())
    print(f"conformance: {counts['pass']} passed, {counts['fail']} failed, "
          f"{counts['skip']} skipped")
    return 1 if counts["fail"] else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true",
                        help="run the live legs too (1b/3b/5b)")
    parser.add_argument("--base-url", default=os.environ.get(
        "MOLDESIGN_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--cases", type=Path, default=CASES_DIR)
    parser.add_argument("--register", action="append", default=[],
                        help="dotted module registering extra capabilities (repeatable)")
    parser.add_argument("--adapter", choices=("moldesign", "generic"), default="moldesign",
                        help="generic es explícito y no negocia el contrato MolDesign")
    args = parser.parse_args(argv)
    try:
        exige_contrato = contract_required(args.adapter, args.register)
    except ValueError as exc:
        parser.error(str(exc))
    for module in args.register:
        importlib.import_module(module)
    token = os.environ.get("MOLDESIGN_TOKEN")
    allow_remote = os.environ.get("MOLDESIGN_ALLOW_REMOTE") == "1"
    if args.live:
        if not exige_contrato:
            print("conformance: adaptador genérico explícito; no se negocia el contrato MolDesign")
        try:
            validate_base_url(args.base_url, allow_remote=allow_remote)
        except ValueError as exc:
            print(f"conformance: bad base URL ({exc})", file=sys.stderr)
            return 1
    verdicts = asyncio.run(run(args.cases, live=args.live,
                               base_url=args.base_url, token=token,
                               allow_remote=allow_remote,
                               require_contract=exige_contrato))
    return report(verdicts)


if __name__ == "__main__":
    raise SystemExit(main())
