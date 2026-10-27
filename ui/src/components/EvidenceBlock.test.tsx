import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import EvidenceBlock from "./EvidenceBlock";

afterEach(cleanup);

const BASE = {
  tool: "compute_properties",
  label: "aspirina",
  epistemic_class: "cálculo",
  source: "demo dataset",
  values: { mw: "180.2", logp: "1.31" },
  error: null,
};

describe("EvidenceBlock", () => {
  it("renders tool, class, source and every value", () => {
    render(<EvidenceBlock evidence={BASE} />);
    expect(screen.getByTestId("evidence-block")).toBeInTheDocument();
    expect(screen.getByText("compute_properties")).toBeInTheDocument();
    expect(screen.getByText("cálculo")).toBeInTheDocument();
    expect(screen.getByText("demo dataset")).toBeInTheDocument();
    expect(screen.getByText("mw")).toBeInTheDocument();
    expect(screen.getByText("180.2")).toBeInTheDocument();
    expect(screen.getByText("logp")).toBeInTheDocument();
  });

  it("renders the error variant without values", () => {
    render(
      <EvidenceBlock
        evidence={{ ...BASE, values: {}, error: "sin datos registrados" }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("sin datos registrados");
    expect(screen.queryByText("mw")).not.toBeInTheDocument();
  });
});
