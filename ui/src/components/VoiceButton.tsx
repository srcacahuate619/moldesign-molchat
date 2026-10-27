import { useRef, useState } from "react";
import { api } from "../lib/api";
import type { StringKey } from "../lib/i18n";
import { isVoiceSupported, startRecording, toWavMono16 } from "../lib/voice";

export default function VoiceButton({
  token,
  lang,
  t,
  disabled,
  onTranscript,
  onError,
}: {
  token: string;
  lang: string;
  t: (key: StringKey) => string;
  disabled: boolean;
  onTranscript: (text: string) => void;
  onError: (message: string) => void;
}) {
  const [recording, setRecording] = useState(false);
  const [working, setWorking] = useState(false);
  const active = useRef<Awaited<ReturnType<typeof startRecording>> | null>(null);

  if (!isVoiceSupported()) return null;

  const toggle = async () => {
    if (working) return;
    if (!recording) {
      try {
        active.current = await startRecording();
        setRecording(true);
      } catch {
        onError(t("voice.error"));
      }
      return;
    }
    setRecording(false);
    setWorking(true);
    try {
      const raw = await active.current?.stop();
      active.current = null;
      if (!raw || raw.size === 0) throw new Error("empty");
      const wav = await toWavMono16(raw);
      const text = await api.transcribe(token, wav, lang);
      onTranscript(text);
    } catch {
      onError(t("voice.error"));
    } finally {
      setWorking(false);
    }
  };

  return (
    <button
      type="button"
      onClick={() => void toggle()}
      disabled={disabled || working}
      aria-pressed={recording}
      title={recording ? t("voice.stop") : t("voice.record")}
    >
      {recording ? "⏹" : "🎙"}
    </button>
  );
}
