import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Plans from "./Plans";
import { strings } from "../lib/i18n";

afterEach(cleanup);

const { mockPropose, mockSubmit } = vi.hoisted(() => ({
  mockPropose: vi.fn(),
  mockSubmit: vi.fn(),
}));

vi.mock("../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../lib/api")>();
  return {
    ...original,
    api: {
      ...original.api,
      proposePlan: mockPropose,
      submitExecution: mockSubmit,
    },
  };
});

const CATALOG = [
  { name: "list_targets", description: "", risk: "read", epistemic_class: "dato persistido" },
  { name: "cancel_evaluation", description: "", risk: "write", epistemic_class: "dato persistido" },
];

const PLAN = {
  goal: "Cancelar",
  steps: [
    { id: "s1", capability: "cancel_evaluation", arguments: { task_id: "t-1" }, rationale: "" },
  ],
  planner: "fake",
  schema: "/1",
};

function renderPlans() {
  return render(
    <Plans
      token="test-token"
      catalog={CATALOG}
      t={(key) => strings("es")[key]}
      onSessionInvalid={() => {}}
      onExecuted={() => {}}
    />,
  );
}

describe("Plans", () => {
  it("shows the digest, risks and per-step approval for sensitive plans", async () => {
    mockPropose.mockResolvedValue({ plan: PLAN, digest: "sha256:test-digest" });
    renderPlans();
    fireEvent.change(screen.getByPlaceholderText(/Objetivo/), {
      target: { value: "cancela t-1" },
    });
    fireEvent.click(screen.getByText("Proponer plan"));
    await waitFor(() =>
      expect(screen.getByText("sha256:test-digest")).toBeInTheDocument(),
    );
    expect(screen.getByText(/write/)).toBeInTheDocument();
    expect(screen.getByText(/exige tu aprobación/)).toBeInTheDocument();
    const check = screen.getByRole("checkbox");
    expect(check).not.toBeChecked();
    fireEvent.click(check);
    expect(check).toBeChecked();
  });

  it("submits the shown digest with the checked steps only", async () => {
    mockPropose.mockResolvedValue({ plan: PLAN, digest: "sha256:test-digest" });
    mockSubmit.mockResolvedValue({ id: "e-1", digest: "sha256:test-digest", state: "queued" });
    const onExecuted = vi.fn();
    render(
      <Plans
        token="test-token"
        catalog={CATALOG}
        t={(key) => strings("es")[key]}
        onSessionInvalid={() => {}}
        onExecuted={onExecuted}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/Objetivo/), {
      target: { value: "cancela t-1" },
    });
    fireEvent.click(screen.getByText("Proponer plan"));
    await waitFor(() =>
      expect(screen.getByText("sha256:test-digest")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByText("Ejecutar con esta aprobación"));
    await waitFor(() => expect(mockSubmit).toHaveBeenCalledTimes(1));
    expect(mockSubmit).toHaveBeenCalledWith("test-token", PLAN, {
      approval_digest: "sha256:test-digest",
      approved_steps: ["s1"],
    });
    expect(onExecuted).toHaveBeenCalledWith("e-1");
  });
});
