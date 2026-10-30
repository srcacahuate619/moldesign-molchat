import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import PropertyComparison from "./PropertyComparison";
import { strings } from "../lib/i18n";

afterEach(cleanup);
it("contrasts cited values and warns when the structure changed", () => {
  render(<PropertyComparison t={(key) => strings("es")[key]} reference={{ cid: 2519, name: "Caffeine", source: "https://pubchem.ncbi.nlm.nih.gov/compound/2519", properties: { HBondAcceptorCount: 3 } }} evidence={{ tool: "compute_properties", label: "caffeine", source: "RDKit", epistemic_class: "cálculo", error: null, values: { hba: "6" }, methods: { hba: "Lipinski.NOCount" }, structure: { input_smiles: "C.N", canonical_smiles: "C", identity: "changed", warnings: ["Sal retirada"], pubchem_cid: 2519 } }} />);
  expect(screen.getByText(/difiere de la entrada/)).toBeInTheDocument();
  expect(screen.getByText("3").closest("tr")).toHaveClass("comparison-different");
  expect(screen.getByText("6")).toBeInTheDocument();
  expect(screen.getByText("Lipinski.NOCount")).toBeInTheDocument();
  expect(screen.getByText("Sal retirada")).toBeInTheDocument();
});
