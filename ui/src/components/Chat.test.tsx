import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Chat from "./Chat";
import { strings } from "../lib/i18n";

afterEach(() => { cleanup(); sessionStorage.clear(); });

const { mockList, mockGet, mockStream, mockCreateCase, mockReportCase, mockStartVoice, mockTranscribeVoice, mockSelectPubchem } = vi.hoisted(() => ({
  mockList: vi.fn(),
  mockGet: vi.fn(),
  mockStream: vi.fn(),
  mockCreateCase: vi.fn(),
  mockReportCase: vi.fn(),
  mockStartVoice: vi.fn(),
  mockTranscribeVoice: vi.fn(),
  mockSelectPubchem: vi.fn(),
}));

vi.mock("../lib/caseHost", () => ({ createCaseInHost: mockCreateCase }));
vi.mock("../lib/voice", () => ({ isVoiceSupported: () => true, startRecording: mockStartVoice, toWavMono16: vi.fn().mockResolvedValue(new Blob(["wav"])) }));

vi.mock("../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../lib/api")>();
  return {
    ...original,
    api: { ...original.api, listConversations: mockList, getConversation: mockGet, reportCaseResult: mockReportCase, transcribe: mockTranscribeVoice, selectPubchem: mockSelectPubchem },
    openChatStream: mockStream,
  };
});

function renderChat() {
  return render(
    <Chat
      token="test-token"
      lang="es"
      t={(key) => strings("es")[key]}
      onSessionInvalid={() => {}}
    />,
  );
}

describe("Chat error turn with idempotent retry", () => {
  beforeEach(() => { mockList.mockReset(); mockGet.mockReset(); mockStream.mockReset(); mockCreateCase.mockReset(); mockReportCase.mockReset(); mockStartVoice.mockReset(); mockTranscribeVoice.mockReset(); mockSelectPubchem.mockReset(); });
  it("reopens the current conversation without creating another", async () => {
    mockList.mockResolvedValue([]);
    mockGet.mockResolvedValue({ messages: [{ role: "user", content: "hola" }, { role: "assistant", content: "respuesta guardada" }] });
    mockStream.mockImplementation((_token: string, _body: unknown, onEvent: (e: Record<string, unknown>) => void) => {
      queueMicrotask(() => {
        onEvent({ type: "conversation", id: "saved-conversation" });
        onEvent({ type: "result", result: { text: "respuesta guardada", used_llm: true, latency_ms: 1, verified_values: [], evidence: [] } });
      });
      return () => {};
    });
    const rendered = renderChat();
    fireEvent.change(screen.getByPlaceholderText(/pregunta/i), { target: { value: "hola" } });
    fireEvent.click(screen.getByText("Enviar"));
    await screen.findByText("respuesta guardada");
    rendered.unmount();
    renderChat();
    expect(await screen.findByText("respuesta guardada")).toBeInTheDocument();
    expect(mockGet).toHaveBeenCalledWith("test-token", "saved-conversation");
    expect(mockStream).toHaveBeenCalledTimes(1);
  });
  it("restores selectable references when reopening a conversation", async () => {
    mockList.mockResolvedValue([{ id: "conv", summary: "Consulta", message_count: 2 }]);
    mockGet.mockResolvedValue({ messages: [{ role: "user", content: "aspirina" }, { role: "assistant", content: "Elige" }],
      pending_references: [{ cid: 2244, name: "Aspirin", source: "https://pubchem.ncbi.nlm.nih.gov/compound/2244" },
        { cid: 2245, name: "Otra", source: "https://pubchem.ncbi.nlm.nih.gov/compound/2245" }] });
    renderChat();
    fireEvent.click(screen.getByRole("button", { name: /mostrar historial/i }));
    fireEvent.click(await screen.findByText(/Consulta/));
    expect(await screen.findByRole("link", { name: /Aspirin/ })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Seleccionar" })).toHaveLength(2);
  });
  it("shows the properties of a single result without a select button", async () => {
    mockList.mockResolvedValue([]);
    mockStream.mockImplementation((_token: string, _body: unknown, onEvent: (e: Record<string, unknown>) => void) => {
      queueMicrotask(() => {
        onEvent({ type: "conversation", id: "single" });
        onEvent({ type: "result", result: { text: "Encontré una referencia.", used_llm: true, latency_ms: 1, verified_values: [], evidence: [], references: [{
          cid: 3672, name: "Ibuprofen", source: "https://pubchem.ncbi.nlm.nih.gov/compound/3672",
          properties_available: true, properties: { MolecularFormula: "C13H18O2", MolecularWeight: "206.28", SMILES: "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O", ConnectivitySMILES: "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O" } }] } });
      });
      return () => {};
    });
    renderChat();
    fireEvent.change(screen.getByPlaceholderText(/pregunta/i), { target: { value: "busca ibuprofeno" } });
    fireEvent.click(screen.getByText("Enviar"));
    expect(await screen.findByText("C13H18O2")).toBeInTheDocument();
    expect(screen.getByText("206.28 g/mol")).toBeInTheDocument();
    expect(screen.getByText("CC(C)CC1=CC=C(C=C1)C(C)C(=O)O")).toBeInTheDocument();
    expect(screen.queryByText(/SMILES de conectividad/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Seleccionar" })).not.toBeInTheDocument();
  });
  it("restores single-result properties after reopening the conversation", async () => {
    mockList.mockResolvedValue([{ id: "single-history", summary: "Ibuprofeno", message_count: 2 }]);
    mockGet.mockResolvedValue({ messages: [{ role: "user", content: "ibuprofeno" },
      { role: "assistant", content: "Resultado", references: [{ cid: 3672, name: "Ibuprofen",
        source: "https://pubchem.ncbi.nlm.nih.gov/compound/3672", properties_available: true,
        properties: { MolecularFormula: "C13H18O2" } }] }], pending_references: [] });
    renderChat();
    fireEvent.click(screen.getByRole("button", { name: /mostrar historial/i }));
    fireEvent.click(await screen.findByText(/Ibuprofeno/));
    expect(await screen.findByText("C13H18O2")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Seleccionar" })).not.toBeInTheDocument();
  });
  it("shows source choices and records only the user's selection", async () => {
    mockList.mockResolvedValue([]);
    mockSelectPubchem.mockResolvedValue({ text: "Seleccionaste Aspirin." });
    mockStream.mockImplementation((_token: string, _body: unknown, onEvent: (e: Record<string, unknown>) => void) => {
      queueMicrotask(() => {
        onEvent({ type: "conversation", id: "conversation-1" });
        onEvent({ type: "result", result: { text: "Coincidencias", used_llm: true, latency_ms: 1, verified_values: [], evidence: [], references: [
          { cid: 2244, name: "Aspirin", source: "https://pubchem.ncbi.nlm.nih.gov/compound/2244" },
          { cid: 2245, name: "Otra", source: "https://pubchem.ncbi.nlm.nih.gov/compound/2245" }] } });
      });
      return () => {};
    });
    renderChat();
    fireEvent.change(screen.getByPlaceholderText(/pregunta/i), { target: { value: "busca aspirina en PubChem" } });
    fireEvent.click(screen.getByText("Enviar"));
    expect(await screen.findByRole("link", { name: /Aspirin/ })).toHaveAttribute("href", "https://pubchem.ncbi.nlm.nih.gov/compound/2244");
    expect(mockSelectPubchem).not.toHaveBeenCalled();
    fireEvent.click(screen.getAllByRole("button", { name: "Seleccionar" })[0]);
    await screen.findByText("Seleccionaste Aspirin.");
    expect(mockSelectPubchem).toHaveBeenCalledWith("test-token", "conversation-1", 2244);
  });
  it("discarding a voice transcription never resends the previous message", async () => {
    mockList.mockResolvedValue([]);
    mockStartVoice.mockResolvedValue({ stop: vi.fn().mockResolvedValue(new Blob(["audio"])) });
    mockTranscribeVoice.mockResolvedValue("texto transcrito");
    mockStream.mockImplementation((_token: string, _body: unknown, onEvent: (e: Record<string, unknown>) => void) => {
      queueMicrotask(() => onEvent({ type: "result", result: { text: "respuesta anterior", used_llm: true, latency_ms: 1, verified_values: [], evidence: [] } }));
      return () => {};
    });
    renderChat();
    fireEvent.change(screen.getByPlaceholderText(/pregunta/i), { target: { value: "mensaje anterior" } });
    fireEvent.click(screen.getByText("Enviar"));
    await screen.findByText("respuesta anterior");
    fireEvent.click(screen.getByRole("button", { name: /grabar/i }));
    await screen.findByRole("button", { name: /detener grabación/i });
    fireEvent.click(screen.getByRole("button", { name: /detener grabación/i }));
    fireEvent.click(await screen.findByRole("button", { name: "Descartar" }));
    expect(screen.queryByRole("button", { name: "Descartar" })).not.toBeInTheDocument();
    expect(mockStream).toHaveBeenCalledTimes(1);
  });
  it("does not offer a retry of the previous chat message when microphone permission fails", async () => {
    mockList.mockResolvedValue([]);
    mockStartVoice.mockRejectedValue(new DOMException("denied", "NotAllowedError"));
    mockStream.mockImplementation((_token: string, _body: unknown, onEvent: (e: Record<string, unknown>) => void) => {
      queueMicrotask(() => onEvent({ type: "result", result: { text: "hola", used_llm: true, latency_ms: 1, verified_values: [], evidence: [] } }));
      return () => {};
    });
    renderChat();
    fireEvent.change(screen.getByPlaceholderText(/pregunta/i), { target: { value: "mensaje anterior" } });
    fireEvent.click(screen.getByText("Enviar"));
    await screen.findByText("hola");
    fireEvent.click(screen.getByRole("button", { name: /grabar/i }));
    await screen.findByText(/no se permitió el acceso al micrófono/i);
    expect(screen.queryByText("Reintentar")).not.toBeInTheDocument();
    expect(mockStream).toHaveBeenCalledTimes(1);
  });
  it("reports the actual host result for a case request", async () => {
    mockList.mockResolvedValue([]);
    mockCreateCase.mockResolvedValue("created");
    mockReportCase.mockResolvedValue({ accepted: true });
    mockStream.mockImplementation((_token: string, _body: unknown, onEvent: (event: Record<string, unknown>) => void) => {
      queueMicrotask(() => onEvent({ type: "case_create", request_id: "case-id", name: "holamundo" }));
      return () => {};
    });
    renderChat();
    fireEvent.change(screen.getByPlaceholderText(/pregunta/i), { target: { value: 'crea el caso "holamundo"' } });
    fireEvent.click(screen.getByText("Enviar"));
    await waitFor(() => expect(mockCreateCase).toHaveBeenCalledWith("case-id", "holamundo"));
    await waitFor(() => expect(mockReportCase).toHaveBeenCalledWith("test-token", "case-id", "created"));
  });
  it("keeps history closed until requested in the compact panel", async () => {
    mockList.mockResolvedValue([{ id: "test-conversation", summary: "Mi conversación", message_count: 2 }]);
    renderChat();
    await waitFor(() => expect(mockList).toHaveBeenCalled());
    expect(screen.queryByText(/Mi conversación/)).not.toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: /mostrar historial/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(screen.getByText(/Mi conversación/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /ocultar historial/i })).toHaveAttribute("aria-expanded", "true");
  });
  it("shows retry after a failed turn and resends once", async () => {
    mockList.mockResolvedValue([]);
    mockStream.mockImplementation(
      (
        _token: string,
        _body: unknown,
        _onEvent: (event: Record<string, unknown>) => void,
        onError: (error: Error) => void,
      ) => {
        queueMicrotask(() => onError(new Error("sidecar caído")));
        return () => {};
      },
    );
    renderChat();
    await waitFor(() => expect(mockList).toHaveBeenCalled());
    fireEvent.change(screen.getByPlaceholderText(/pregunta/i), {
      target: { value: "hola" },
    });
    fireEvent.click(screen.getByText("Enviar"));
    await waitFor(() =>
      expect(screen.getByText("Reintentar")).toBeInTheDocument(),
    );
    expect(mockStream).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByText("Reintentar"));
    await waitFor(() => expect(mockStream).toHaveBeenCalledTimes(2));
    // The failed user text is resent verbatim, not duplicated in the input.
    const echoes = screen.getAllByText("hola");
    expect(echoes.length).toBe(2); // one message per attempt, both visible
  });
});
