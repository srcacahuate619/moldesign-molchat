import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import IterationCard, { bubbleLine, planProgress, validWorkflows } from "./IterationCard";
import { strings } from "../lib/i18n";

afterEach(cleanup);

const m = vi.hoisted(() => ({
  run: vi.fn(), cancel: vi.fn(), file: vi.fn(), createCase: vi.fn(), loadSmiles: vi.fn(), receptor: vi.fn(), evaluate: vi.fn(),
  reportCase: vi.fn(), reportSmiles: vi.fn(), reportReceptor: vi.fn(), reportEvaluation: vi.fn(),
  audit: vi.fn(), reportPreparation: vi.fn(), caseStatus: vi.fn(), reportCaseStatus: vi.fn(), getWorkflow: vi.fn(), molcy: vi.fn(), reportMolcy: vi.fn(),
}));

vi.mock("../lib/caseStatusHost", () => ({ caseStatusInHost: m.caseStatus }));
vi.mock("../lib/molcyHost", () => ({ renderVideoInHost: m.molcy }));

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
      reportPreparationResult: m.reportPreparation, reportCaseStatusResult: m.reportCaseStatus, getWorkflow: m.getWorkflow, reportMolcyResult: m.reportMolcy },
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

  it("relays the video request to the Molcy tab and its answer to the sidecar", async () => {
    m.molcy.mockResolvedValue({ status: "started", job_id: "job-1abcdef" });
    m.reportMolcy.mockResolvedValue({});
    renderCard();
    fireEvent.click(screen.getByText("Aprobar y ejecutar"));
    act(() => emit({ type: "case_molcy", request_id: "v1", task_id: "t-2", scene: "busqueda", format: "horizontal", presentation: "{\"etiquetas\":false}" }));
    await waitFor(() => expect(m.reportMolcy).toHaveBeenCalledWith("test-session", "v1", { status: "started", job_id: "job-1abcdef" }));
    expect(m.molcy).toHaveBeenCalledWith("v1", "t-2", "busqueda", "horizontal", "{\"etiquetas\":false}");
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

  it("says the video is still rendering and shows the delivery once the background render is in it", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const base = { state: "completed", counts: { evaluated: 3 }, selected: { name: "B", task_id: "t-2", vina_kcal_mol: -9.6, physical_status: "passed" },
        saved: "saved", preparation: "REVISION", files: { "entrega.zip": 9 }, paths: {}, notes: [] };
      m.getWorkflow.mockResolvedValue({ id: proposal.id, state: "done", summary: { ...base, video: "completo", video_pending: false } });
      renderCard();
      fireEvent.click(screen.getByText("Aprobar y ejecutar"));
      act(() => emit({ type: "workflow", event: "done", summary: { ...base, video: "started", video_pending: true } }));
      expect(screen.getByText(/sigue renderizando el vídeo en segundo plano/)).toBeInTheDocument();
      expect(screen.getByText("Descargar ahora (sin el vídeo)")).toBeInTheDocument();
      expect(screen.getByText(/si descargas ahora, la entrega va sin él/)).toBeInTheDocument();
      await act(async () => { vi.advanceTimersByTime(8100); });
      await waitFor(() => expect(screen.getByText("El vídeo terminó y ya está dentro de la entrega.")).toBeInTheDocument());
      expect(m.getWorkflow).toHaveBeenCalledWith("test-session", proposal.id);
      expect(screen.queryByText(/sigue renderizando/)).not.toBeInTheDocument();
      expect(screen.getByText("Descargar la entrega (ZIP)")).toBeInTheDocument();
    } finally { vi.useRealTimers(); }
  });

  it("shows the plan's steps as a timeline that follows what really happened", () => {
    render(<IterationCard proposal={{ ...proposal, steps: ["case", "receptor", "molecules", "moldex", "video", "preparation", "deliverable"] }}
      token="test-session" t={t} onSessionInvalid={() => {}} />);
    fireEvent.click(screen.getByText("Aprobar y ejecutar"));
    const state = (label: string) => screen.getByText(label).closest("li")?.getAttribute("data-state");
    act(() => emit({ type: "workflow", event: "approved" }));
    expect(state("Caso")).toBe("running");
    act(() => { emit({ type: "workflow", event: "case_step", step: "crear el caso", status: "created" });
      emit({ type: "workflow", event: "case_step", step: "asignar el receptor", status: "applied" }); });
    expect(state("Caso")).toBe("done");
    expect(state("Receptor")).toBe("done");
    expect(state("Moléculas")).toBe("running");
    act(() => { emit({ type: "workflow", event: "saved", result: { status: "saved" } });
      emit({ type: "workflow", event: "video", result: { status: "started", job_id: "j" } });
      emit({ type: "workflow", event: "phase", phase: "preparation", message: "Auditando" }); });
    expect(state("Moldex")).toBe("done");
    expect(state("Vídeo de Molcy")).toBe("running");
    expect(state("Preparación")).toBe("running");
    act(() => emit({ type: "workflow", event: "done", summary: { state: "completed", counts: { evaluated: 3 },
      selected: { name: "B", task_id: "t-2", vina_kcal_mol: -9.6, physical_status: "passed" }, saved: "saved", video: "started",
      video_pending: true, video_progress: { fotogramas: 30, total: 120 }, preparation: "REVISION", files: { "entrega.zip": 9 }, paths: {}, notes: [] } }));
    expect(state("Moléculas")).toBe("done");
    expect(screen.getByText(/3\/3 · B/)).toBeInTheDocument();
    expect(state("Vídeo de Molcy")).toBe("running");
    expect(screen.getByText(/25 %/)).toBeInTheDocument();
    expect(state("Preparación")).toBe("done");
    expect(state("Entrega")).toBe("running"); // ready, but the video is still coming
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

describe("the bubble's line for a plan", () => {
  const row = (status: string, vina: number | null = null) => ({ status, outcome: null, vina, physical: null, reason: null });
  const steps = ["case", "receptor", "molecules", "moldex", "video", "preparation", "deliverable"] as const;
  const summary = (patch: Record<string, unknown>) => ({ state: "selected", counts: null, selected: null, saved: null, video: null, preparation: null,
    videoPending: false, videoProgress: null, files: {}, paths: {}, notes: [], ...patch });

  it("asks for the approval, then says which molecule is being evaluated and the last Vina", () => {
    expect(bubbleLine("pending", [], {}, null, null, [...steps], t)).toEqual({ state: "attention", text: "Un plan espera tu aprobación" });
    expect(bubbleLine("running", [row("evaluated", -7.24), row("running"), row("pending")], {}, null, null, [...steps], t))
      .toEqual({ state: "working", text: "Evaluando 2 de 3 · última Vina −7.2" });
  });

  it("between molecules it names the running step, and the video keeps the bubble busy after the plan ends", () => {
    expect(bubbleLine("running", [row("evaluated", -9.1)], { moldex: { state: "running", detail: null } }, null, null, [...steps], t)?.text)
      .toBe("Moldex… · última Vina −9.1");
    expect(bubbleLine("done", [], {}, summary({ videoPending: true, videoProgress: "40 %" }), null, [...steps], t))
      .toEqual({ state: "working", text: "Molcy renderiza el vídeo 40 %" });
  });

  it("ends with the chosen molecule, says when none met the rule, and an interruption is an error", () => {
    expect(bubbleLine("done", [], {}, summary({ selected: { name: "Mol 2", task_id: "x", vina_kcal_mol: -9.566, physical_status: "passed" } }), null, [...steps], t))
      .toEqual({ state: "done", text: "Listo: Mol 2 · Vina −9.6" });
    expect(bubbleLine("done", [], {}, summary({}), null, [...steps], t)?.text).toBe("Terminó: ninguna molécula cumplió la regla");
  });

  it("gives the host the plan to show who is driving: nothing while it waits for the person, then steps and molecules", () => {
    const proposal = { id: "a".repeat(32), kind: "iteration" as const, digest: `sha256:${"0".repeat(64)}`, title: "Iteración",
      lines: ["Caso «VMAT2» · receptor 8T69"], molecules: ["cafeína", "cetanserina", "valbenazina"] };
    expect(planProgress("pending", [], {}, null, null, proposal, [...steps], t)).toBeNull();
    const qualified = { ...row("evaluated", -11.2), outcome: "qualifies" };
    const progress = planProgress("running", [row("evaluated", -6.2), qualified, row("running")],
      { case: { state: "done", detail: null }, molecules: { state: "running", detail: null } }, null,
      { state: "working", text: "Evaluando 3 de 3" }, proposal, [...steps], t);
    expect(progress).toMatchObject({ title: "Caso «VMAT2» · receptor 8T69", phase: "running", now: "Evaluando 3 de 3" });
    expect(progress?.steps.slice(0, 3)).toEqual([{ label: "Caso", state: "done" }, { label: "Receptor", state: "pending" },
      { label: "Moléculas", state: "running" }]);
    expect(progress?.molecules).toEqual([{ name: "cafeína", state: "done", vina: -6.2, meets: false },
      { name: "cetanserina", state: "done", vina: -11.2, meets: true }, { name: "valbenazina", state: "running", vina: null, meets: false }]);
    expect(planProgress("done", [], {}, summary({ videoPending: true }), null, proposal, [...steps], t)?.phase).toBe("rendering");
    expect(planProgress("interrupted", [], {}, null, null, proposal, [...steps], t)?.phase).toBe("stopped");
    expect(bubbleLine("interrupted", [], {}, null, null, [...steps], t)?.state).toBe("error");
    expect(bubbleLine("cancelled", [], {}, null, null, [...steps], t)).toBeNull();
  });
});
