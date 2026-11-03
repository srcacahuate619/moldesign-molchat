import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { auditPreparationInHost } from "./preparationHost";

vi.mock("./hostSession", () => ({ isTrustedHostOrigin: (origin: string) => origin === "http://127.0.0.1:3000" }));

const post = vi.fn();
const PROJECTION = { projection_version: 1, case_id: "c-1" };

beforeEach(() => {
  post.mockReset();
  Object.defineProperty(window, "parent", { configurable: true, value: { postMessage: post } });
});
afterEach(() => { Object.defineProperty(window, "parent", { configurable: true, value: window }); vi.useRealTimers(); });

function answer(data: Record<string, unknown>, origin = "http://127.0.0.1:3000") {
  window.dispatchEvent(new MessageEvent("message", { data, origin, source: window.parent as unknown as MessageEventSource }));
}

describe("auditPreparationInHost", () => {
  it("asks the host for exactly this run and resolves with the projection it built", async () => {
    const promise = auditPreparationInHost("r1", "hipotesis", "t-2");
    expect(post).toHaveBeenCalledWith({ type: "molchat-host-message", kind: "audit_case_preparation", request_id: "r1",
      case_name: "hipotesis", task_id: "t-2" }, "*");
    answer({ type: "molchat-preparation-result", request_id: "r1", status: "audited", molecule_id: "m-1", estado: "REVISION", projection: PROJECTION });
    await expect(promise).resolves.toEqual({ status: "audited", molecule_id: "m-1", estado: "REVISION", projection: PROJECTION });
  });

  it("ignores another request, another origin and a state outside the audit's contract", async () => {
    vi.useFakeTimers();
    const promise = auditPreparationInHost("r2", "c", "t");
    answer({ type: "molchat-preparation-result", request_id: "other", status: "failed" });
    answer({ type: "molchat-preparation-result", request_id: "r2", status: "failed" }, "https://evil.example.com");
    answer({ type: "molchat-preparation-result", request_id: "r2", status: "audited", molecule_id: "m", estado: "TODO_BIEN", projection: PROJECTION });
    answer({ type: "molchat-preparation-result", request_id: "r2", status: "audited", molecule_id: "../x", estado: "REVISION", projection: PROJECTION });
    answer({ type: "molchat-preparation-result", request_id: "r2", status: "audited", molecule_id: "m", estado: "REVISION", projection: [1] });
    vi.advanceTimersByTime(126000);
    await expect(promise).resolves.toEqual({ status: "unknown" });
  });

  it("passes a failure through with its reason, never with a projection", async () => {
    const promise = auditPreparationInHost("r3", "c", "t");
    answer({ type: "molchat-preparation-result", request_id: "r3", status: "audit_failed", reason: "el backend no respondió", projection: PROJECTION });
    await expect(promise).resolves.toEqual({ status: "audit_failed", reason: "el backend no respondió" });
  });

  it("fails at once when it is not embedded in a host", async () => {
    Object.defineProperty(window, "parent", { configurable: true, value: window });
    await expect(auditPreparationInHost("r4", "c", "t")).resolves.toEqual({ status: "failed" });
  });
});
