import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { StringKey } from "../lib/i18n";
import { isVoiceSupported, startRecording, toWavMono16 } from "../lib/voice";
import { MicIcon, StopIcon } from "./Icons";
import { isTrustedHostOrigin } from "../lib/hostSession";

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
  const generation = useRef(0);

  useEffect(() => {
    const stop = () => {
      generation.current += 1;
      const current = active.current;
      active.current = null;
      setRecording(false);
      if (current) void current.stop().catch(() => {});
    };
    const onMessage = (event: MessageEvent) => {
      if (event.source === window.parent && isTrustedHostOrigin(event.origin) &&
          event.data?.type === "molchat-host-hidden") stop();
    };
    window.addEventListener("message", onMessage);
    return () => { window.removeEventListener("message", onMessage); stop(); };
  }, []);

  if (!isVoiceSupported()) return null;

  const toggle = async () => {
    if (working) return;
    if (!recording) {
      setWorking(true);
      try {
        const started = generation.current;
        const recording = await startRecording();
        if (started !== generation.current) {
          await recording.stop();
          return;
        }
        active.current = recording;
        setRecording(true);
      } catch (error) {
        const errorName = typeof error === "object" && error !== null && "name" in error ? error.name : "";
        onError(t(typeof errorName === "string" && ["NotAllowedError", "SecurityError"].includes(errorName)
          ? "voice.permission" : "voice.error"));
      } finally {
        setWorking(false);
      }
      return;
    }
    setRecording(false);
    setWorking(true);
    const started = generation.current;
    try {
      const current = active.current;
      active.current = null;
      const raw = await current?.stop();
      if (started !== generation.current) return;
      if (!raw || raw.size === 0) throw new Error("empty");
      const wav = await toWavMono16(raw);
      if (started !== generation.current) return;
      const text = await api.transcribe(token, wav, lang);
      if (started !== generation.current) return;
      if (!text.trim()) onError(t("voice.noSpeech"));
      else onTranscript(text);
    } catch {
      if (started === generation.current) onError(t("voice.transcribeError"));
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
      title={working ? t("voice.working") : recording ? t("voice.stop") : t("voice.record")}
      aria-label={working ? t("voice.working") : recording ? t("voice.stop") : t("voice.record")}
      className={recording ? "voice-button recording" : "voice-button"}
    >
      {recording ? <StopIcon /> : <MicIcon />}
    </button>
  );
}
