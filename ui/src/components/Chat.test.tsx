import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Chat from "./Chat";
import { strings } from "../lib/i18n";

afterEach(cleanup);

const { mockList, mockStream, mockCreateCase, mockReportCase } = vi.hoisted(() => ({
  mockList: vi.fn(),
  mockStream: vi.fn(),
  mockCreateCase: vi.fn(),
  mockReportCase: vi.fn(),
}));

vi.mock("../lib/caseHost", () => ({ createCaseInHost: mockCreateCase }));

vi.mock("../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../lib/api")>();
  return {
    ...original,
    api: { ...original.api, listConversations: mockList, reportCaseResult: mockReportCase },
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
  beforeEach(() => { mockList.mockReset(); mockStream.mockReset(); mockCreateCase.mockReset(); mockReportCase.mockReset(); });
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
