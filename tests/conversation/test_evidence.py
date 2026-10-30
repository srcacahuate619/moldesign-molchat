"""Evidence blocks: class, source, separation, and numeric verification."""

from molchat_agent.conversation.evidence import (
    EVIDENCE_END,
    EpistemicClass,
    Evidence,
    block_for_flow,
    context_literals,
    format_evidence,
    numbers_in,
    redact_unverified,
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


def test_quotation_and_ordinals_are_not_fabrication():
    assert numbers_in("que es 12345?") == ["12345"]
    assert verify_numbers("12345 es un número.", set(),
                          quotable=frozenset({"12345"})) == []
    assert verify_numbers("12345 es un número.", set()) != []
    assert verify_numbers("Usos:\n1. Identificar\n2. Comparar", set()) == []
    assert verify_numbers("1.5 Da cuesta.", set()) != []  # decimals count


def test_redact_keeps_quotable_and_verified():
    redacted, problems = redact_unverified(
        "MW 180.2 y 12345", {180.2}, quotable=frozenset({"12345"}))
    assert problems == [] and redacted == "MW 180.2 y 12345"
    redacted, problems = redact_unverified("MW 999.9 y 12345", set(),
                                           quotable=frozenset({"12345"}))
    assert problems != []
    assert "999.9" not in redacted and "12345" in redacted


def test_context_identifiers_survive_without_whitelisting_their_digits_as_measurements():
    prior = 'Caso "prueba 2". SMILES `CC(=O)OC1=CC=CC=C1C(=O)O`; MolDesign / RDKit 2025.09.6'
    answer = ('**1.** Caso "prueba 2"; `CC(=O)OC1=CC=CC=C1C(=O)O`. '
              'Fuente RDKit 2025.09.6. Peso inventado: 2025.09.')
    redacted, issues = redact_unverified(answer, set(), literals=frozenset(context_literals(prior)))
    assert '**1.**' in redacted and '"prueba 2"' in redacted
    assert 'CC(=O)OC1=CC=CC=C1C(=O)O' in redacted and '2025.09.6' in redacted
    assert 'Peso inventado: [dato no verificado]' in redacted and issues


def test_a_modified_structure_is_not_protected_by_context():
    prior = '`CC1=CC=CC=C1`'
    redacted, issues = redact_unverified('`CC2=CC=CC=C2`', set(), literals=frozenset(context_literals(prior)))
    assert issues and '[dato no verificado]' in redacted


def test_prompts_are_versioned_and_static():
    assert PROMPT_VERSION == "prompts/1"
    assert "NUNCA inventes" in CONCEPTUAL_SYSTEM_P1
    assert "{" not in CONCEPTUAL_SYSTEM_P1  # no format holes for user data
