"""The number guard reads Spanish: decimal comma, typographic minus, ranges.

Measured on 2026-11-02 against the previous tokenizer: "-9,48" was cut in two and both halves hidden,
"−9.5" lost its sign and was compared as +9.5, and "0.22-0.54" was read as 0.22 and -0.54.
"""
import pytest

from molchat_agent.conversation.evidence import (
    numbers_in,
    numeric_leaves,
    redact_unverified,
    to_float,
    verify_numbers,
)

FACTS = {"affinity": -9.483, "rho": 0.39, "ci95": [0.22, 0.54], "n": 89, "level": 95, "seed": 42}
EXACT = numeric_leaves(FACTS)


@pytest.mark.parametrize("text, tokens", [
    ("fue -9,48 kcal/mol", ["-9,48"]),
    ("fue −9,48 kcal/mol", ["−9,48"]),
    ("IC 0,22–0,54", ["0,22", "0,54"]),
    ("IC 0.22-0.54", ["0.22", "0.54"]),          # a range, not 0.22 and -0.54
    ("IC [-0.16; 0.41]", ["-0.16", "0.41"]),      # a sign after a bracket is a sign
    ("rho=-0.3", ["-0.3"]),
    ("n = 89, semilla 42.", ["89", "42"]),         # a sentence period is not part of the number
])
def test_tokens_follow_the_spanish_conventions(text, tokens):
    assert numbers_in(text) == tokens


def test_to_float_reads_comma_and_typographic_minus():
    assert to_float("−9,48") == -9.48 and to_float("0,5") == 0.5 and to_float("-3") == -3.0


@pytest.mark.parametrize("claim", [
    "La afinidad fue -9,483 kcal/mol.", "La afinidad fue -9,48 kcal/mol.", "La afinidad fue −9,5 kcal/mol.",
    "La ρ es 0,39 (IC 95 % 0,22–0,54) con n = 89.", "La ρ es 0.39 (IC 95 % 0.22-0.54).",
    "Semilla 42.",
])
def test_exact_facts_back_the_values_in_the_precision_the_answer_writes(claim):
    text, problems = redact_unverified(claim, set(), exact=EXACT)
    assert problems == [] and text == claim


@pytest.mark.parametrize("claim", [
    "La ρ es 0,3.",                 # 0.39 rounds to 0.4, not to 0.3
    "Con n = 90 compuestos.",
    "La afinidad fue de -9,3 kcal/mol.",
    "La afinidad fue de 9,48 kcal/mol.",  # the sign is part of the value
])
def test_exact_facts_do_not_back_a_near_miss(claim):
    text, problems = redact_unverified(claim, set(), exact=EXACT)
    assert problems and "[dato no verificado]" in text


def test_the_guard_sees_the_old_failure_it_was_fixed_for():
    # Control: the same text with the facts missing must be hidden, or the tests above prove nothing.
    text, problems = redact_unverified("La afinidad fue -9,48 kcal/mol.", set())
    assert problems and "-9,48" not in text


def test_a_hidden_number_is_replaced_whole_with_its_sign():
    text, _ = redact_unverified("Valor −7,1 kcal/mol.", set(), exact=EXACT)
    assert text == "Valor [dato no verificado] kcal/mol."


def test_verified_keeps_its_wide_tolerance_for_the_values_that_never_had_a_precision():
    assert verify_numbers("valor 151.19", {151.2}) == []         # unchanged, pinned by test_evidence too
    assert verify_numbers("valor 151,19", {151.2}) == []         # and now with a decimal comma


def test_quotation_survives_with_a_decimal_comma():
    quoted = frozenset(numbers_in("compara con 3,5"))
    assert verify_numbers("Usaste 3,5.", set(), quotable=quoted) == []


def test_numeric_leaves_read_values_and_texts_but_not_keys_or_booleans():
    leaves = numeric_leaves({"ic95": [0.2, True], "note": "a 6,09 Å del sitio", "nested": {"n": 3}})
    assert leaves == {0.2, 6.09, 3.0}
    assert 95.0 not in leaves and 1.0 not in leaves
