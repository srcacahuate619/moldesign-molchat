import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ActionProposalCard, { validProposals } from "./ActionProposalCard";
import { strings } from "../lib/i18n";

afterEach(cleanup);

const { mockConfirm, mockCancel, mockPost } = vi.hoisted(() => ({ mockConfirm: vi.fn(), mockCancel: vi.fn(), mockPost: vi.fn() }));

vi.mock("../lib/deeplinks", () => ({ postToHost: mockPost }));
vi.mock("../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../lib/api")>();
  return { ...original, api: { ...original.api, confirmAction: mockConfirm, cancelAction: mockCancel } };
});

const t = (key: keyof ReturnType<typeof strings>) => strings("es")[key];
const proposal = {
  id: "p-1", kind: "molcy_video" as const, title: "Generar vídeo con Molcy",
  lines: ["Corrida t-8t69 · receptor VMAT2", "Escena: resultado · Formato: horizontal (biblioteca)", "Título: Mi vídeo"],
};

function renderCard(onSessionInvalid = () => {}) {
  return render(<ActionProposalCard proposal={proposal} token="test-token" t={t} onSessionInvalid={onSessionInvalid} />);
}

beforeEach(() => { mockConfirm.mockReset(); mockCancel.mockReset(); mockPost.mockReset(); });

describe("ActionProposalCard", () => {
  it("shows what would happen and does nothing until the person confirms", () => {
    renderCard();
    expect(screen.getByText("Generar vídeo con Molcy")).toBeInTheDocument();
    expect(screen.getByText("Título: Mi vídeo")).toBeInTheDocument();
    expect(screen.getByText("Todavía no se hizo nada.")).toBeInTheDocument();
    expect(mockConfirm).not.toHaveBeenCalled();
    expect(mockCancel).not.toHaveBeenCalled();
  });

  it("confirms with the session and the proposal id, then shows MolDesign's own result and a way to open Molcy", async () => {
    mockConfirm.mockResolvedValue({ id: "p-1", state: "done", outcome: { status: "started", job_id: "j-1", message: "Vídeo en cola en Molcy." } });
    renderCard();
    fireEvent.click(screen.getByText("Confirmar"));
    await screen.findByText(/Vídeo en cola en Molcy\./);
    expect(mockConfirm).toHaveBeenCalledExactlyOnceWith("test-token", "p-1");
    expect(screen.queryByText("Confirmar")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Abrir Molcy"));
    expect(mockPost).toHaveBeenCalledWith({ kind: "open_molcy", job_id: "j-1" });
  });

  it("does not run twice when pressed twice while it is running", async () => {
    let finish: (value: unknown) => void = () => {};
    mockConfirm.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    renderCard();
    const button = screen.getByText("Confirmar");
    fireEvent.click(button);
    fireEvent.click(screen.getByText("Ejecutando…"));
    expect(mockConfirm).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Ejecutando…")).toBeDisabled();
    finish({ id: "p-1", state: "done", outcome: { status: "saved", message: "Corrida guardada en Moldex." } });
    await screen.findByText("Corrida guardada en Moldex.");
  });

  it("cancels without confirming, and says nothing was done", async () => {
    mockCancel.mockResolvedValue({ id: "p-1", state: "cancelled", outcome: { status: "cancelled" } });
    renderCard();
    fireEvent.click(screen.getByText("Cancelar"));
    await screen.findByText("Cancelado; no se hizo nada.");
    expect(mockCancel).toHaveBeenCalledExactlyOnceWith("test-token", "p-1");
    expect(mockConfirm).not.toHaveBeenCalled();
  });

  it("reports a refusal as a problem and offers no way to open Molcy", async () => {
    mockConfirm.mockResolvedValue({ id: "p-1", state: "done", outcome: { status: "rejected", message: "MolDesign rechazó la solicitud: No hay una GPU compatible." } });
    renderCard();
    fireEvent.click(screen.getByText("Confirmar"));
    const result = await screen.findByText(/No hay una GPU compatible\./);
    expect(result).toHaveClass("error");
    expect(screen.queryByText("Abrir Molcy")).not.toBeInTheDocument();
  });

  it("says a lost answer is not confirmed and lets the person try again, which asks the sidecar again", async () => {
    mockConfirm.mockRejectedValueOnce(new TypeError("fetch failed"))
      .mockResolvedValueOnce({ id: "p-1", state: "done", outcome: { status: "saved", message: "Corrida guardada en Moldex." } });
    renderCard();
    fireEvent.click(screen.getByText("Confirmar"));
    await screen.findByRole("alert");
    expect(screen.getByRole("alert")).toHaveTextContent("No se confirmó nada");
    fireEvent.click(screen.getByText("Confirmar"));
    await screen.findByText("Corrida guardada en Moldex.");
    expect(mockConfirm).toHaveBeenCalledTimes(2);
  });

  it("explains an expired proposal, and sends an invalid session to the reconnect flow", async () => {
    const { ApiError } = await import("../lib/api");
    mockConfirm.mockRejectedValueOnce(new ApiError(404, "propuesta no encontrada o caducada"));
    const invalid = vi.fn();
    renderCard(invalid);
    fireEvent.click(screen.getByText("Confirmar"));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("caducó"));
    expect(invalid).not.toHaveBeenCalled();
    mockConfirm.mockRejectedValueOnce(new ApiError(401, "sesión revocada"));
    fireEvent.click(screen.getByText("Confirmar"));
    await waitFor(() => expect(invalid).toHaveBeenCalledTimes(1));
  });
});

describe("validProposals", () => {
  const good = { id: "p-1", kind: "save_moldex", title: "Guardar en Moldex", lines: ["Corrida t-1"] };

  it("keeps a well-formed proposal and drops everything else", () => {
    expect(validProposals([good])).toEqual([good]);
    expect(validProposals(undefined)).toEqual([]);
    expect(validProposals("p-1")).toEqual([]);
    for (const broken of [
      { ...good, id: "" }, { ...good, id: "x".repeat(65) }, { ...good, kind: "borrar_todo" }, { ...good, title: "" },
      { ...good, lines: "una línea" }, { ...good, lines: [1, 2] }, { ...good, lines: Array(13).fill("x") },
      { ...good, lines: ["x".repeat(401)] }, null, 7,
    ]) {
      expect(validProposals([broken])).toEqual([]);
    }
  });

  it("does not let extra fields through to the card and shows at most two", () => {
    const [clean] = validProposals([{ ...good, execute: true, url: "http://evil" }]);
    expect(Object.keys(clean).sort()).toEqual(["id", "kind", "lines", "title"]);
    expect(validProposals([good, { ...good, id: "p-2" }, { ...good, id: "p-3" }])).toHaveLength(2);
  });
});
