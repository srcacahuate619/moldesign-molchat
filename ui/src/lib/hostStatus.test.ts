import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { currentProgress, currentStatus, reportProgress, reportStatus, resetStatus, type PlanProgress } from "./hostStatus";

describe("the bubble's line", () => {
  let posted: unknown[];
  beforeEach(() => {
    resetStatus();
    posted = [];
    // Embedded: the window has a parent that is not itself.
    vi.spyOn(window, "parent", "get").mockReturnValue({ postMessage: (message: unknown) => posted.push(message) } as unknown as Window);
  });
  afterEach(() => vi.restoreAllMocks());

  it("something waiting for the person wins over work in progress and a reply being written", () => {
    reportStatus("chat", { state: "thinking", text: "Escribiendo…" });
    reportStatus("iteration:a", { state: "working", text: "Evaluando 2 de 3" });
    reportStatus("action:b", { state: "attention", text: "Una acción espera tu confirmación" });
    expect(currentStatus()).toEqual({ state: "attention", text: "Una acción espera tu confirmación" });
    reportStatus("action:b", null);
    expect(currentStatus()?.text).toBe("Evaluando 2 de 3");
  });

  it("only changes are sent, and an empty window says idle", () => {
    reportStatus("iteration:a", { state: "working", text: "Evaluando 1 de 3" });
    reportStatus("iteration:a", { state: "working", text: "Evaluando 1 de 3" });
    reportStatus("iteration:a", null);
    expect(posted).toEqual([
      { type: "molchat-ui-status", state: "working", text: "Evaluando 1 de 3" },
      { type: "molchat-ui-status", state: "idle", text: "" },
    ]);
  });

  it("the text is one short line", () => {
    reportStatus("chat", { state: "thinking", text: `a\nb${"x".repeat(300)}` });
    const sent = posted[0] as { text: string };
    expect(sent.text.startsWith("a b")).toBe(true);
    expect(sent.text.length).toBe(140);
  });

  it("a window that is not embedded sends nothing", () => {
    vi.spyOn(window, "parent", "get").mockReturnValue(window);
    reportStatus("chat", { state: "thinking", text: "Escribiendo…" });
    expect(posted).toEqual([]);
  });

  it("the plan's progress goes on its own envelope, a running plan wins over a finished one, and only changes are sent", () => {
    const plan = (phase: PlanProgress["phase"], now: string): PlanProgress => ({ title: "Caso «x» · receptor 8T69", phase, now,
      steps: [{ label: "Caso", state: "done" }], molecules: [{ name: "cafeína", state: "done", vina: -6.2, meets: false }] });
    reportProgress("iteration:old", plan("done", "Listo"));
    reportProgress("iteration:new", plan("running", "Evaluando 2 de 6"));
    reportProgress("iteration:new", plan("running", "Evaluando 2 de 6"));
    expect(currentProgress()?.now).toBe("Evaluando 2 de 6");
    reportProgress("iteration:new", null);
    reportProgress("iteration:old", null);
    expect(posted).toEqual([
      { type: "molchat-ui-progress", progress: plan("done", "Listo") },
      { type: "molchat-ui-progress", progress: plan("running", "Evaluando 2 de 6") },
      { type: "molchat-ui-progress", progress: plan("done", "Listo") },
      { type: "molchat-ui-progress", progress: null },
    ]);
  });
});
