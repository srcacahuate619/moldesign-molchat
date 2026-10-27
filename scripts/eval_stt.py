"""Operator-run STT evaluation (es/en): transcribe audios, score term recall.

Inputs: a directory of ``<name>.<lang>.wav`` files plus a JSON terms file
``{name: [terms...]}``. Without inputs it reports SKIP (exit 3), like the
contract suite without a backend. Uses the sidecar STT chain (local models
only unless MOLCHAT_CLOUD_STT=1 is set deliberately).

Usage:
  PYTHONPATH=src python scripts/eval_stt.py --audio-dir recordings/ \\
      --terms terms.json --lang es
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from molchat_agent.config import load_config  # noqa: E402
from molchat_agent.voice.evaluate import score_transcript  # noqa: E402
from molchat_agent.voice.local_whisper import (  # noqa: E402
    ChainSTT,
    LocalWhisperSTT,
    faster_whisper_available,
)

SKIP = 3


async def _transcribe(stt, audio: bytes, lang: str) -> str:
    return await stt.transcribe(audio, lang=lang)


async def main_async(args: argparse.Namespace) -> int:
    audio_dir = Path(args.audio_dir)
    terms_file = Path(args.terms)
    if not audio_dir.is_dir() or not terms_file.is_file():
        print("SKIP: sin audios o sin términos (ver --help).")
        return SKIP
    terms = json.loads(terms_file.read_text(encoding="utf-8"))
    config = load_config()
    backends = []
    if faster_whisper_available():
        backends.append(LocalWhisperSTT(config.whisper_model))
    if not backends:
        print("SKIP: faster-whisper no instalado; nada que evaluar en local.")
        return SKIP
    stt = backends[0] if len(backends) == 1 else ChainSTT(backends)
    recalls: list[float] = []
    for name, expected in sorted(terms.items()):
        audio_file = audio_dir / f"{name}.{args.lang}.wav"
        if not audio_file.is_file():
            print(f"  {name}: sin audio, omitido")
            continue
        try:
            text = await _transcribe(stt, audio_file.read_bytes(), args.lang)
        except Exception as exc:
            print(f"  {name}: ERROR {exc}")
            return 1
        score = score_transcript(expected, text)
        recalls.append(score.recall)
        print(f"  {name}: recall={score.recall:.2f} missed={list(score.missed)}")
    if not recalls:
        print("SKIP: ningún caso evaluable.")
        return SKIP
    print(f"Media recall ({args.lang}): {sum(recalls) / len(recalls):.2f} "
          f"sobre {len(recalls)} casos.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluar STT es/en")
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--terms", required=True)
    parser.add_argument("--lang", choices=["es", "en"], default="es")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
