import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { caseStatusInHost } from "./caseStatusHost";

vi.mock("./hostSession", () => ({ isTrustedHostOrigin: (origin: string) => origin === "http://127.0.0.1:3000" }));

const post = vi.fn();

beforeEach(() => {
  post.mockReset();
  Object.defineProperty(window, "parent", { configurable: true, value: { postMessage: post } });
});
afterEach(() => { Object.defineProperty(window, "parent", { configurable: true, value: window }); vi.useRealTimers(); });

function answer(data: Record<string, unknown>, origin = "http://127.0.0.1:3000") {
  window.dispatchEvent(new MessageEvent("message", { data, origin, source: window.parent as unknown as MessageEventSource }));
}

describe("caseStatusInHost", () => {
  it("asks about exactly this case and keeps only the state, the run state and the task", async () => {
    const promise = caseStatusInHost("s1", "hipotesis");
    expect(post).toHaveBeenCalledWith({ type: "molchat-host-message", kind: "case_status", request_id: "s1", case_name: "hipotesis" }, "*");
    answer({ type: "molchat-case-status-result", request_id: "s1", status: "busy", run_state: "running", task_id: "task-7", extra: "x" });
    await expect(promise).resolves.toEqual({ status: "busy", run_state: "running", task_id: "task-7" });
  });

  it("ignores other requests, other origins and states outside the contract; silence is unknown, never idle", async () => {
    vi.useFakeTimers();
    const promise = caseStatusInHost("s2", "c");
    answer({ type: "molchat-case-status-result", request_id: "other", status: "idle" });
    answer({ type: "molchat-case-status-result", request_id: "s2", status: "idle" }, "https://evil.example.com");
    answer({ type: "molchat-case-status-result", request_id: "s2", status: "free" });
    vi.advanceTimersByTime(16000);
    await expect(promise).resolves.toEqual({ status: "unknown" });
  });

  it("drops a malformed task id but keeps the state", async () => {
    const promise = caseStatusInHost("s3", "c");
    answer({ type: "molchat-case-status-result", request_id: "s3", status: "idle", task_id: "../x" });
    await expect(promise).resolves.toEqual({ status: "idle" });
  });

  it("is unknown at once when it is not embedded in a host", async () => {
    Object.defineProperty(window, "parent", { configurable: true, value: window });
    await expect(caseStatusInHost("s4", "c")).resolves.toEqual({ status: "unknown" });
  });
});
