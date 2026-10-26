"""Evidence blocks: class, source, separation, and numeric verification."""

from molchat_agent.conversation.evidence import (
    EVIDENCE_END,
    EpistemicClass,
    Evidence,
    block_for_flow,
    format_evidence,
    split_flow,
    verify_numbers,
)
from molchat_agent.conversation.prompts import (
    CONCEPTUAL_SYSTEM_P1,
    PROMPT_VERSION,
)


def test_block_declares_class_source_and_label():
    text = format_evidence([Evidence(
        tool="compute_properties", label="aspirina",
        epistemic_class=EpistemicClass.CALCULATION,
        source="RDKit (descriptores sobre el SMILES dado)",
        values={"MW": "180.2 Da", "LogP": "1.31"})])
    assert "[cálculo · RDKit (descriptores sobre el SMILES dado)]" in text
    assert "compute_properties (aspirina): MW: 180.2 Da" in text


def test_error_renders_as_abstention_without_numbers():
    text = format_evidence([Evidence(
        tool="compute_properties", label="KILLMEnow",
        epistemic_class=EpistemicClass.CALCULATION,
        source="RDKit", error="SMILES inválido")])
    assert "no se obtuvo dato" in text
    assert "No inventes el valor" in text
    assert verify_numbers(text, set()) == []  # abstention makes no claims
    assert "180.2" not in text


def test_flow_block_is_closed_and_splittable():
    flow = block_for_flow("evidencia...") + "Propiedades de aspirina: ..."
    assert EVIDENCE_END in flow
    evidence, answer = split_flow(flow)
    assert evidence == "evidencia..."
    assert answer == "Propiedades de aspirina: ..."
    assert split_flow("sin marcador") == ("", "sin marcador")


def test_verify_numbers_marks_unbacked_and_clears_backed():
    assert verify_numbers("MW: 180.2 Da.", {180.2}) == []
    assert verify_numbers("MW: 180.2 Da.", set()) != []
    assert verify_numbers("sin números aquí", set()) == []
    assert verify_numbers("valor 151.19", {151.2}) == []  # tolerance


def test_prompts_are_versioned_and_static():
    assert PROMPT_VERSION == "prompts/1"
    assert "NUNCA inventes" in CONCEPTUAL_SYSTEM_P1
    assert "{" not in CONCEPTUAL_SYSTEM_P1  # no format holes for user data
