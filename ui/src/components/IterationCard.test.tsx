import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import IterationCard, { validWorkflows } from "./IterationCard";
import { strings } from "../lib/i18n";

afterEach(cleanup);

const m = vi.hoisted(() => ({
  run: vi.fn(), cancel: vi.fn(), file: vi.fn(), createCase: vi.fn(), loadSmiles: vi.fn(), receptor: vi.fn(), evaluate: vi.fn(),
  reportCase: vi.fn(), reportSmiles: vi.fn(), reportReceptor: vi.fn(), reportEvaluation: vi.fn(),
  audit: vi.fn(), reportPreparation: vi.fn(), caseStatus: vi.fn(), reportCaseStatus: vi.fn(),
}));

vi.mock("../lib/caseStatusHost", () => ({ caseStatusInHost: m.caseStatus }));

vi.mock("../lib/preparationHost", () => ({ auditPreparationInHost: m.audit }));

vi.mock("../lib/caseHost", () => ({ createCaseInHost: m.createCase }));
vi.mock("../lib/smilesHost", () => ({ loadSmilesInHost: m.loadSmiles }));
vi.mock("../lib/receptorHost", () => ({ assignReceptorInHost: m.receptor }));
vi.mock("../lib/evaluationHost", () => ({ evaluateCaseInHost: m.evaluate }));
vi.mock("../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../lib/api")>();
  return {
    ...original, runWorkflow: m.run,
    api: { ...original.api, cancelWorkflow: m.cancel, workflowFile: m.file, reportCaseResult: m.reportCase,
      reportSmilesResult: m.reportSmiles, reportReceptorResult: m.reportReceptor, reportEvaluationResult: m.reportEvaluation,
      reportPreparationResult: m.reportPreparation, reportCaseStatusResult: m.reportCaseStatus },
  };
});

const t = (key: keyof ReturnType<typeof strings>) => strings("es")[key];
const proposal = {
  id: "a".repeat(32), kind: "iteration" as const, digest: "sha256:" + "b".repeat(64), title: "Iteración de moléculas",
  lines: ["Caso «hipotesis» · receptor 8T69", "3 moléculas, una por una: A, B, C"], molecules: ["A", "B", "C"],
};

let emit: (event: Record<string, unknown>) => void;
let fail: (error: Error) => void;

beforeEach(() => {
  Object.values(m).forEach((fn) => fn.mockReset());
  m.run.mockImplementation((_t, _id, _digest, onEvent, onError) => { emit = onEvent; fail = onError; return vi.fn(); });
  for (const fn of [m.createCase, m.loadSmiles, m.receptor, m.evaluate]) fn.mockResolvedValue({ status: "ok" });
  for (const fn of [m.reportCase, m.reportSmiles, m.reportReceptor, m.reportEvaluation]) fn.mockResolvedValue({});
});

const renderCard = () => render(<IterationCard proposal={proposal} token="test-session" t={t} onSessionInvalid={() => {}} />);

describe("IterationCard", () => {
  it("shows everything the plan will do and runs nothing until the one approval", () => {
    renderCard();
    expect(screen.getByText("3 moléculas, una por una: A, B, C")).toBeInTheDocument();
    expect(screen.getByText(/el único clic/)).toBeInTheDocument();
    expect(m.run).not.toHaveBeenCalled();
  });

  it("approves with the plan's digest, relays the host's actions and fills the table as molecules finish", async () => {
    renderCard();
    fireEvent.click(screen.getByText("Aprobar y ejecutar"));
    expect(m.run).toHaveBeenCalledWith("test-session", proposal.id, proposal.digest, expect.any(Function), expect.any(Function));
    m.loadSmiles.mockResolvedValue({ status: "applied" });
    m.evaluate.mockResolvedValue({ status: "started", task_id: "t-1" });
    act(() => {
      emit({ type: "case_create", request_id: "r1", name: "hipotesis" });
      emit({ type: "case_receptor", request_id: "r2", case_name: "hipotesis", pdb_id: "8T69" });
      emit({ type: "case_smiles", request_id: "r3", case_name: "hipotesis", smiles: "CCN" });
      emit({ type: "case_evaluation", request_id: "r4", case_name: "hipotesis" });
    });
    await waitFor(() => expect(m.reportEvaluation).toHaveBeenCalledWith("test-session", "r4", { status: "started", task_id: "t-1" }));
    expect(m.createCase).toHaveBeenCalledWith("r1", "hipotesis");
    expect(m.receptor).toHaveBeenCalledWith("r2", "hipotesis", "8T69");
    expect(m.loadSmiles).toHaveBeenCalledWith("r3", "hipotesis", "CCN");
    expect(m.reportSmiles).toHaveBeenCalledWith("test-session", "r3", { status: "applied" });

    act(() => {
      emit({ type: "workflow", event: "molecule_started", index: 1, name: "A" });
      emit({ type: "workflow", event: "molecule", record: { index: 1, status: "failed", outcome: null, reason: "No se cargó la molécula" } });
      emit({ type: "workflow", event: "molecule", record: { index: 2, status: "evaluated", outcome: "qualifies", affinity_kcal: -9.8, physical_status: "passed" } });
    });
    expect(screen.getByText("falló")).toBeInTheDocument();
    expect(screen.getByText("cumple la regla")).toBeInTheDocument();
    expect(screen.getByText("-9.8")).toBeInTheDocument();
    expect(screen.getByText("passed")).toBeInTheDocument();
    expect(screen.getAllByText("en espera")).toHaveLength(1);
  });

  it("relays the Preparación audit to the host and reports its answer to the sidecar", async () => {
    const answer = { status: "audited", molecule_id: "m-1", estado: "REVISION", projection: { case_id: "c" } };
    m.audit.mockResolvedValue(answer);
    m.reportPreparation.mockResolvedValue({});
    renderCard();
    fireEvent.click(screen.getByText("Aprobar y ejecutar"));
    act(() => emit({ type: "case_preparation", request_id: "p1", case_name: "hipotesis", task_id: "t-2" }));
    await waitFor(() => expect(m.reportPreparation).toHaveBeenCalledWith("test-session", "p1", answer));
    expect(m.audit).toHaveBeenCalledWith("p1", "hipotesis", "t-2");
  });

  it("relays the read-only case question to the host and its answer to the sidecar", async () => {
    m.caseStatus.mockResolvedValue({ status: "busy", run_state: "running" });
    m.reportCaseStatus.mockResolvedValue({});
    renderCard();
    fireEvent.click(screen.getByText("Aprobar y ejecutar"));
    act(() => emit({ type: "case_status", request_id: "s1", case_name: "hipotesis" }));
    await waitFor(() => expect(m.reportCaseStatus).toHaveBeenCalledWith("test-session", "s1", { status: "busy", run_state: "running" }));
    expect(m.caseStatus).toHaveBeenCalledWith("s1", "hipotesis");
  });

  it("ignores anything that is not one of the host requests", async () => {
    renderCard();
    fireEvent.click(screen.getByText("Aprobar y ejecutar"));
    act(() => {
      emit({ type: "something_else", request_id: "x" }); emit({ type: "case_smiles", request_id: "y", case_name: 3 });
      emit({ type: "case_preparation", request_id: "z", case_name: "c", task_id: 7 });
    });
    expect(m.loadSmiles).not.toHaveBeenCalled();
    expect(m.audit).not.toHaveBeenCalled();
  });

  it("ends with the outcome, offers the files the plan produced and downloads them with the session in a header", async () => {
    m.file.mockResolvedValue(new Blob(["zip"]));
    const create = vi.fn(() => "blob:x"); const revoke = vi.fn();
    Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    renderCard();
    fireEvent.click(screen.getByText("Aprobar y ejecutar"));
    act(() => emit({ type: "workflow", event: "done", summary: {
      state: "completed", counts: { evaluated: 2 }, selected: { name: "B", task_id: "t-2", vina_kcal_mol: -9.8, physical_status: "passed" },
      saved: "saved", video: "completo", preparation: "REVIEW", files: { "cuaderno.pdf": 10, "entrega.zip": 99 },
      paths: { "entrega.zip": "entregas/x/entrega.zip" }, notes: ["El caso ya existía"] } }));
    expect(screen.getByText(/Cumplió la regla: B/)).toBeInTheDocument();
    expect(screen.getByText("Preparación: REVIEW")).toBeInTheDocument();
    expect(screen.getByText("El caso ya existía")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Descargar la entrega (ZIP)"));
    await waitFor(() => expect(m.file).toHaveBeenCalledWith("test-session", proposal.id, "entrega.zip"));
  });

  it("says nothing was saved when no molecule met the rule", () => {
    renderCard();
    fireEvent.click(screen.getByText("Aprobar y ejecutar"));
    act(() => emit({ type: "workflow", event: "done", summary: { state: "none_qualified", counts: { evaluated: 3 }, selected: null,
      saved: null, video: null, preparation: null, files: { "cuaderno.md": 4 }, paths: {}, notes: [] } }));
    expect(screen.getByText(/Ninguna molécula cumplió la regla/)).toBeInTheDocument();
    expect(screen.getByText("Descargar el cuaderno (Markdown)")).toBeInTheDocument();
  });

  it("does not call a broken stream a finished plan", () => {
    renderCard();
    fireEvent.click(screen.getByText("Aprobar y ejecutar"));
    act(() => fail(new Error("network")));
    expect(screen.getByText(/se interrumpió antes de terminar/)).toBeInTheDocument();
    expect(screen.queryByText("Terminó")).not.toBeInTheDocument();
  });

  it("cancels before approval and then shows that nothing was done", async () => {
    m.cancel.mockResolvedValue({ id: proposal.id, state: "cancelled" });
    renderCard();
    fireEvent.click(screen.getByText("Cancelar"));
    await waitFor(() => expect(screen.getByText("Cancelado; no se hizo nada.")).toBeInTheDocument());
    expect(m.run).not.toHaveBeenCalled();
  });
});

describe("validWorkflows", () => {
  const good = { ...proposal };
  it("keeps a well-formed iteration and drops malformed ones", () => {
    expect(validWorkflows([good])).toEqual([good]);
    expect(validWorkflows("x")).toEqual([]);
    for (const bad of [{ ...good, id: "../x" }, { ...good, kind: "other" }, { ...good, digest: "nope" },
      { ...good, lines: [1] }, { ...good, molecules: new Array(13).fill("a") }, { ...good, title: "" }]) {
      expect(validWorkflows([bad])).toEqual([]);
    }
  });
  it("shows at most one card per turn", () => {
    expect(validWorkflows([good, { ...good, id: "c".repeat(32) }])).toHaveLength(1);
  });
});
