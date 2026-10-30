/**
 * Push-to-talk: MediaRecorder capture, decoded and re-encoded as 16-bit
 * mono WAV in the browser, so the bytes match the audio/wav contract the
 * sidecar forwards to MolDesign Whisper. No cloud, no dependencies.
 */

export function isVoiceSupported(): boolean {
  return (
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined" &&
    typeof AudioContext !== "undefined"
  );
}

export interface Recording {
  stop: () => Promise<Blob>;
}

/** Capture microphone audio until stop() resolves with the raw chunks. */
export async function startRecording(): Promise<Recording> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  let recorder: MediaRecorder;
  try {
    recorder = new MediaRecorder(stream);
  } catch (error) {
    stream.getTracks().forEach((track) => track.stop());
    throw error;
  }
  const chunks: Blob[] = [];
  const stopped = new Promise<Blob>((resolve) => {
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      resolve(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
    };
  });
  recorder.ondataavailable = (event: BlobEvent) => {
    if (event.data.size > 0) chunks.push(event.data);
  };
  try {
    recorder.start();
  } catch (error) {
    stream.getTracks().forEach((track) => track.stop());
    throw error;
  }
  return {
    stop: async () => {
      const done = stopped;
      recorder.stop();
      return done;
    },
  };
}

/** Decode any browser audio blob and re-encode it as mono 16 kHz WAV. */
export async function toWavMono16(blob: Blob): Promise<Blob> {
  const buffer = await blob.arrayBuffer();
  const context = new AudioContext();
  try {
    const decoded = await context.decodeAudioData(buffer.slice(0));
    const targetRate = 16000;
    const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * targetRate), targetRate);
    const source = offline.createBufferSource();
    source.buffer = decoded;
    source.connect(offline.destination);
    source.start();
    const rendered = await offline.startRendering();
    const samples = rendered.getChannelData(0);
    return new Blob([encodeWav(samples, targetRate)], { type: "audio/wav" });
  } finally {
    await context.close();
  }
}

/** Pure 16-bit PCM mono WAV encoder (header + samples, little-endian). */
export function encodeWav(samples: Float32Array, sampleRate: number): ArrayBuffer {
  const dataBytes = samples.length * 2;
  const buffer = new ArrayBuffer(44 + dataBytes);
  const view = new DataView(buffer);
  const writeAscii = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
  };
  writeAscii(0, "RIFF");
  view.setUint32(4, 36 + dataBytes, true);
  writeAscii(8, "WAVE");
  writeAscii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeAscii(36, "data");
  view.setUint32(40, dataBytes, true);
  for (let i = 0; i < samples.length; i++) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, Math.round(clamped * 32767), true);
  }
  return buffer;
}
