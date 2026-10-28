import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import VoiceButton from "./VoiceButton";
import { strings } from "../lib/i18n";

afterEach(cleanup);

const { mockSupported, mockStart, mockToWav, mockTranscribe } = vi.hoisted(() => ({
  mockSupported: vi.fn(),
  mockStart: vi.fn(),
  mockToWav: vi.fn(),
  mockTranscribe: vi.fn(),
}));

vi.mock("../lib/voice", () => ({
  isVoiceSupported: mockSupported,
  startRecording: mockStart,
  toWavMono16: mockToWav,
}));

vi.mock("../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../lib/api")>();
  return {
    ...original,
    api: { ...original.api, transcribe: mockTranscribe },
  };
});

function renderButton(hooks: { onTranscript: (text: string) => void; onError: (m: string) => void }) {
  return render(
    <VoiceButton
      token="test-token"
      lang="es"
      t={(key) => strings("es")[key]}
      disabled={false}
      onTranscript={hooks.onTranscript}
      onError={hooks.onError}
    />,
  );
}

describe("VoiceButton", () => {
  it("renders nothing when the browser cannot record", () => {
    mockSupported.mockReturnValue(false);
    const { container } = renderButton({ onTranscript: () => {}, onError: () => {} });
    expect(container).toBeEmptyDOMElement();
  });

  it("records, converts to WAV and hands the transcript for confirmation", async () => {
    mockSupported.mockReturnValue(true);
    const stop = vi.fn().mockResolvedValue(new Blob(["raw"], { type: "audio/webm" }));
    mockStart.mockResolvedValue({ stop });
    const wav = new Blob(["wav"], { type: "audio/wav" });
    mockToWav.mockResolvedValue(wav);
    mockTranscribe.mockResolvedValue("propiedades de la aspirina");
    const onTranscript = vi.fn();
    renderButton({ onTranscript, onError: () => {} });
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(mockStart).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(onTranscript).toHaveBeenCalledWith(
      "propiedades de la aspirina",
    ));
    expect(mockToWav).toHaveBeenCalledTimes(1);
    expect(mockTranscribe).toHaveBeenCalledWith("test-token", wav, "es");
  });

  it("reports recording failures without crashing", async () => {
    mockSupported.mockReturnValue(true);
    mockStart.mockRejectedValue(new Error("sin micrófono"));
    const onError = vi.fn();
    renderButton({ onTranscript: () => {}, onError });
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(onError).toHaveBeenCalled());
  });

  it("stops a recording when the trusted host closes the panel", async () => {
    mockSupported.mockReturnValue(true);
    const stop = vi.fn().mockResolvedValue(new Blob(["raw"]));
    mockStart.mockResolvedValue({ stop });
    renderButton({ onTranscript: () => {}, onError: () => {} });
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "true"));
    fireEvent(window, new MessageEvent("message", {
      source: window.parent, origin: "http://127.0.0.1:3000", data: { type: "molchat-host-hidden" },
    }));
    await waitFor(() => expect(stop).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "false");
  });
});
