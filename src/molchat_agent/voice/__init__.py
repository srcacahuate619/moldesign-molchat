"""Voice: speech-to-text behind one port (Fase 4).

Transcription never executes anything: it returns text, and the UI shows it
for confirmation before it enters a turn as normal input (§12).
"""

from .moldesign_whisper import MolDesignWhisper
from .stt import SpeechToText

__all__ = ["MolDesignWhisper", "SpeechToText"]
