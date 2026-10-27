import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import Settings from "./Settings";
import { strings } from "../lib/i18n";

afterEach(cleanup);

function renderSettings(stt: string) {
  return render(
    <Settings
      t={(key) => strings("es")[key]}
      locale="es"
      stt={stt}
      onLocale={() => {}}
      onRevoke={() => {}}
    />,
  );
}

describe("Settings STT declaration", () => {
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
