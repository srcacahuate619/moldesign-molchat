import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Settings from "./Settings";
import { strings } from "../lib/i18n";

afterEach(cleanup);

vi.mock("../lib/api", () => ({ api: {
  pubchemPermission: vi.fn().mockResolvedValue({ authorized: false, offline: false }),
  setPubchemPermission: vi.fn().mockResolvedValue({ authorized: true, offline: false }),
} }));

function renderSettings(stt: string) {
  return render(
    <Settings
      token="test-token"
      t={(key) => strings("es")[key]}
      locale="es"
      stt={stt}
      onLocale={() => {}}
      onRevoke={() => {}}
    />,
  );
}

describe("Settings STT declaration", () => {
  it("requires an explicit click to authorize PubChem", async () => {
    const { api } = await import("../lib/api");
    renderSettings("none");
    const button = await screen.findByRole("button", { name: "Autorizar búsquedas en PubChem" });
    expect(api.setPubchemPermission).not.toHaveBeenCalled();
    fireEvent.click(button);
    await waitFor(() => expect(api.setPubchemPermission).toHaveBeenCalledWith("test-token", true));
    expect(await screen.findByRole("button", { name: "Retirar autorización de PubChem" })).toBeInTheDocument();
  });
  it("warns loudly when transcription is cloud", () => {
    renderSettings("cloud");
    expect(screen.getByRole("alert")).toHaveTextContent(/NUBE.*sale de este equipo/);
  });

  it("declares local without alarm", () => {
    renderSettings("local");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText(/no sale de este equipo/)).toBeInTheDocument();
  });

  it("declares absence honestly", () => {
    renderSettings("none");
    expect(screen.getByText(/Sin transcripción disponible/)).toBeInTheDocument();
  });
});
