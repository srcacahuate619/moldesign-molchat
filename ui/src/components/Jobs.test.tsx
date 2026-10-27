import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Jobs from "./Jobs";
import { strings } from "../lib/i18n";

afterEach(cleanup);

const { mockGet, mockCancel, mockStream } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockCancel: vi.fn(),
  mockStream: vi.fn(),
}));

vi.mock("../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../lib/api")>();
  return {
    ...original,
    api: {
      ...original.api,
      getExecution: mockGet,
      cancelExecution: mockCancel,
    },
    openEventStream: mockStream,
  };
});

const DONE = {
  id: "e-1",
  digest: "sha256:test-digest",
  state: "completed",
  report: {
    outcomes: [
      {
        id: "s1",
        capability: "list_targets",
        state: "completed",
        result_sha256: "sha256:test-outcome",
      },
    ],
  },
};

function renderJobs(focusId: string | null = "e-1") {
  return render(
    <Jobs
      token="test-token"
      t={(key) => strings("es")[key]}
      focusId={focusId}
      onSessionInvalid={() => {}}
    />,
  );
}

describe("Jobs", () => {
  it("shows the empty state without executions", () => {
    renderJobs(null);
    expect(screen.getByText(/Sin trabajos/)).toBeInTheDocument();
  });

  it("renders the terminal report with outcome hashes", async () => {
    mockGet.mockResolvedValue(DONE);
    renderJobs();
    await waitFor(() => expect(screen.getByText("completed")).toBeInTheDocument());
    expect(screen.getByText("sha256:test-outcome")).toBeInTheDocument();
    expect(screen.queryByText(/Cancelar/)).not.toBeInTheDocument();
  });

  it("cancels running executions explicitly", async () => {
    mockGet.mockResolvedValue({ ...DONE, state: "running", report: null });
    mockCancel.mockResolvedValue({ cancelled: true, detail: "cancelling" });
    mockStream.mockReturnValue(() => {});
    renderJobs();
    await waitFor(() =>
      expect(screen.getByText("Cancelar trabajo")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText("Cancelar trabajo"));
    await waitFor(() => expect(mockCancel).toHaveBeenCalledWith("test-token", "e-1"));
  });
});
