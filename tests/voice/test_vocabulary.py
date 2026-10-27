"""Vocabulary lexicons, decoder prompt, and transcription scoring."""

from molchat_agent.voice.evaluate import score_transcript
from molchat_agent.voice.vocabulary import initial_prompt, lexicon


def test_lexicons_cover_both_languages_with_shared_core():
    es, en = set(lexicon("es")), set(lexicon("en"))
    assert len(es) >= 30 and len(en) >= 30
    assert {"SMILES", "docking", "ADMET", "EGFR"} <= es
    assert {"SMILES", "docking", "ADMET", "EGFR"} <= en
    assert "afinidad" in es and "affinity" in en
    assert lexicon("xx") == lexicon("es")  # unknown falls back to Spanish


def test_initial_prompt_mentions_lexicon_terms():
    prompt = initial_prompt("es")
    assert "SMILES" in prompt and "afinidad" in prompt
    assert "affinity" in initial_prompt("en")


def test_scoring_counts_word_boundaries_accent_insensitive():
    score = score_transcript(
        ["afinidad", "SMILES", "quinasa"],
        "La AFINIDAD del ligando (smiles CCO) es buena.")
    assert (score.expected, score.found) == (3, 2)
    assert score.missed == ("quinasa",)
    assert score.recall == 2 / 3
    assert score.as_dict()["recall"] == round(2 / 3, 3)


def test_scoring_ignores_substrings_and_empty_expectations():
    score = score_transcript(["pose"], "La superposición es buena.")
    assert score.found == 0  # substring is not a word hit
    assert score_transcript([], "cualquier texto").recall == 1.0


def test_local_backend_passes_decoder_prompt():
    from molchat_agent.voice.local_whisper import LocalWhisperSTT

    observed = {}

    class FakeModel:
        def transcribe(self, _audio, **kwargs):
            observed.update(kwargs)
            return [], {}

    stt = LocalWhisperSTT(model_factory=lambda *a, **k: FakeModel())
    assert stt._transcribe_sync(b"RIFF-x", "es") == ""
    assert "SMILES" in observed["initial_prompt"]
    assert observed["language"] == "es"
