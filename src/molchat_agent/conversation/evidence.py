"""Evidence blocks and numeric verification (the anti-hallucination guard).

Reimplemented from ``tool_registry.format_tool_results`` (epistemic classes,
abstention wording, ``FIN_DE_EVIDENCIA`` marker) and the numerical-claim
verification of the internal 5-layer guard. Same UI contract: the frontend
``BloqueDeEvidencia`` splits on the same marker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re

#: Closes the evidence block in flow text. The model never sees it in
#: history; the UI splits evidence from answer on it.
EVIDENCE_END = "<!--__FIN_DE_EVIDENCIA__-->"

#: Prefix the engine adds when it flags LLM output. Validators treat its
#: presence as a corrected (not silent) turn.
VERIFICATION_NOTE = "Nota de verificación:"


class EpistemicClass(Enum):
    CALCULATION = "cálculo"
    PERSISTED = "dato persistido"
    INFERENCE = "inferencia (predicción de modelo, no medida)"
    EXTERNAL = "recuperación externa"
    EXPLANATION = "explicación"


@dataclass
class Evidence:
    tool: str
    label: str  # which molecule (or "A=x | B=y") this block is about
    epistemic_class: EpistemicClass
    source: str
    values: dict[str, str] = field(default_factory=dict)
    error: str | None = None


_NUMBER_RE = re.compile(r"-?\d+\.?\d*")


def format_evidence(results: list[Evidence]) -> str:
    """Render tool results declaring what each one is and where it is from.

    Errors render as abstention ("no se obtuvo dato"), never as numbers.
    """
    if not results:
        return ""
    lines = ["[Sistema: resultados de herramientas ejecutadas. Cada bloque "
             "declara QUÉ es y DE DÓNDE sale:]"]
    for result in results:
        header = (f"[{result.epistemic_class.value} · {result.source}] "
                  f"{result.tool} ({result.label})")
        if result.error is not None:
            lines.append(f"{header}: no se obtuvo dato ({result.error}). "
                         "No inventes el valor: dilo y ofrece cómo obtenerlo.")
        else:
            body = ", ".join(f"{key}: {value}"
                             for key, value in result.values.items())
            lines.append(f"{header}: {body}")
    return "\n".join(lines)


def block_for_flow(evidence_text: str) -> str:
    """Evidence as emitted to the flow: closed by the end marker."""
    if not evidence_text:
        return ""
    return f"\n\n{evidence_text}\n{EVIDENCE_END}\n"


def split_flow(text: str) -> tuple[str, str]:
    """Split flow text into (evidence, answer) on the end marker."""
    if EVIDENCE_END not in text:
        return "", text
    evidence, _, answer = text.partition(EVIDENCE_END)
    return evidence.strip(), answer.strip()


def verify_numbers(text: str, verified: set[float], tolerance: float = 0.25) -> list[str]:
    """Every number in ``text`` must match a verified tool value.

    Returns problem descriptions (empty = clean). Deterministic answers
    never fail this: they are built FROM the verified values.
    """
    problems: list[str] = []
    for match in _NUMBER_RE.finditer(text):
        try:
            claimed = float(match.group(0))
        except ValueError:
            continue
        if not any(abs(claimed - value) <= tolerance for value in verified):
            problems.append(f"número {match.group(0)} sin herramienta que lo respalde")
    return problems
