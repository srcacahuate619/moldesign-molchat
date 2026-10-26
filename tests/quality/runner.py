"""Quality runner: the 43 internal cases against the new engine.

Queries are verbatim from the internal ``quality_suite.py``; validators are
ported to our typed world: instead of parsing tool text out of the turn,
they check the response against recorded RDKit fixtures and the backend
calls the turn actually made. Coherence holds by construction (code builds
answers FROM tool values), and the suite proves it turn by turn.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from molchat_agent.conversation.deterministic import fmt
from molchat_agent.conversation.engine import ConversationEngine
from molchat_agent.conversation.evidence import VERIFICATION_NOTE

HERE = Path(__file__).parent
CASES_PATH = HERE / "cases.json"
FIXTURES_PATH = HERE / "fixtures" / "properties.json"

_KNOWN = ["aspirina", "ibuprofeno", "paracetamol", "cafeina", "morfina",
          "etanol", "dopamina", "glucosa"]


@dataclass
class CaseContext:
    fixtures: dict[str, dict[str, Any]]
    verified: set[float] = field(default_factory=set)
    query: str = ""


def load_cases() -> list[dict[str, Any]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]


def load_fixtures() -> dict[str, dict[str, Any]]:
    payload = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    return {m["name"]: m["properties"] for m in payload["molecules"]}


def _formatted(props: dict[str, Any]) -> dict[str, str]:
    return {"MW": fmt(float(props["mw"]), 1),
            "LogP": fmt(float(props["logp"]), 2),
            "TPSA": fmt(float(props["tpsa"]), 1)}


def v_no_correction(text: str, ctx: CaseContext) -> list[str]:
    return ["contiene nota de verificación"] if VERIFICATION_NOTE in text else []


def v_no_error(text: str, ctx: CaseContext) -> list[str]:
    if "Traceback" in text or "Exception" in text:
        return ["crash real en la respuesta"]
    return []


def v_reports_tool_values(text: str, ctx: CaseContext) -> list[str]:
    """Every mentioned molecule's fixture values appear in the response.

    Decimal-flexible like the internal validator: "1.20" matches "1.2".
    """
    problems = []
    mentioned = [name for name in _KNOWN if name in text.lower()]
    if not mentioned:
        return ["ninguna molécula conocida en la respuesta"]
    for name in mentioned:
        for key, rendered in _formatted(ctx.fixtures[name]).items():
            candidates = {rendered, rendered.rstrip("0").rstrip(".")}
            if not any(cand and cand in text for cand in candidates):
                problems.append(f"falta {key}={rendered} de {name}")
    return problems


def v_has_compare_structure(text: str, ctx: CaseContext) -> list[str]:
    names = {n for n in _KNOWN if n in ctx.query.lower()}
    if len(names) < 2:
        return ["el caso no compara 2 moléculas conocidas"]
    return [f"no menciona '{n}'" for n in names if n not in text.lower()]


def v_no_fabricated(text: str, ctx: CaseContext) -> list[str]:
    """Numbers near known names must come from the recorded fixtures."""
    problems = []
    for name in _KNOWN:
        if name not in text.lower():
            continue
        for match in re.finditer(rf"{name}.{{0,80}}?(-?\d+\.?\d*)",
                                 text, re.IGNORECASE):
            try:
                claimed = float(match.group(1))
            except (ValueError, IndexError):
                continue
            if not any(abs(claimed - value) <= 0.25 for value in ctx.verified):
                problems.append(f"valor {claimed} de '{name}' no verificado")
    return problems


def v_contains(text: str, ctx: CaseContext, needles: list[str]) -> list[str]:
    return [f"falta '{n}'" for n in needles if n.lower() not in text.lower()]


def v_anaphora(text: str, ctx: CaseContext, name: str) -> list[str]:
    return [] if name in text.lower() else [f"no menciona '{name}'"]


def apply_validator(spec: Any, text: str, ctx: CaseContext) -> list[str]:
    if spec == "no_correction":
        return v_no_correction(text, ctx)
    if spec == "no_error":
        return v_no_error(text, ctx)
    if spec == "reports_tool_values":
        return v_reports_tool_values(text, ctx)
    if spec == "has_compare_structure":
        return v_has_compare_structure(text, ctx)
    if spec == "no_fabricated":
        return v_no_fabricated(text, ctx)
    if isinstance(spec, dict) and "contains" in spec:
        return v_contains(text, ctx, spec["contains"])
    if isinstance(spec, dict) and "anaphora" in spec:
        return v_anaphora(text, ctx, spec["anaphora"])
    raise ValueError(f"validador desconocido: {spec!r}")


@dataclass
class CaseResult:
    id: str
    query: str
    ok: bool
    problems: list[str] = field(default_factory=list)
    latencies_ms: list[int] = field(default_factory=list)
    used_llm: list[bool] = field(default_factory=list)


def run_case(engine: ConversationEngine, conv_id: str, case: dict[str, Any],
             fixtures: dict[str, dict[str, Any]]) -> CaseResult:
    async def _run() -> CaseResult:
        ctx = CaseContext(fixtures=fixtures)
        texts: list[str] = []
        latencies: list[int] = []
        used: list[bool] = []
        problems: list[str] = []
        try:
            for query in case["seq"]:
                result = await engine.turn(conv_id, query)
                texts.append(result.text)
                latencies.append(result.latency_ms)
                used.append(result.used_llm)
                ctx.verified.update(result.verified_values)
        except Exception as exc:  # noqa: BLE001 - a crashing turn fails the case
            return CaseResult(id=case["id"], query=case["seq"][case["check"]],
                              ok=False, problems=[f"EXCEPCIÓN: {exc!r}"[:200]],
                              latencies_ms=latencies, used_llm=used)
        ctx.query = case["seq"][case["check"]]
        # Verified set: every tool value the conversation produced so far.
        for text in texts:
            for name in _KNOWN:
                if name in text.lower() and name in fixtures:
                    props = fixtures[name]
                    ctx.verified.update(float(props[k]) for k in ("mw", "logp", "tpsa"))
        text = texts[case["check"]]
        for spec in case["validators"]:
            problems.extend(apply_validator(spec, text, ctx))
        problems = list(dict.fromkeys(problems))
        return CaseResult(id=case["id"], query=ctx.query, ok=not problems,
                          problems=problems, latencies_ms=latencies, used_llm=used)

    return asyncio.run(_run())
