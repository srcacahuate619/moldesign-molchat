import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Chat from "./Chat";
import { strings } from "../lib/i18n";

afterEach(cleanup);

const { mockList, mockStream } = vi.hoisted(() => ({
  mockList: vi.fn(),
  mockStream: vi.fn(),
}));

vi.mock("../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../lib/api")>();
  return {
    ...original,
    api: { ...original.api, listConversations: mockList },
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
