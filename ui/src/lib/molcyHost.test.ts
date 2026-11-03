import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderVideoInHost } from "./molcyHost";

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

describe("renderVideoInHost", () => {
  it("asks the Molcy tab for exactly this run, scene and format and keeps only the job it started", async () => {
    const promise = renderVideoInHost("v1", "task-9", "busqueda", "horizontal");
    expect(post).toHaveBeenCalledWith({ type: "molchat-host-message", kind: "molcy_render", request_id: "v1", task_id: "task-9",
      scene: "busqueda", format: "horizontal" }, "*");
    answer({ type: "molchat-molcy-result", request_id: "v1", status: "started", job_id: "d2b13faf-3185-4aa1", extra: 1 });
    await expect(promise).resolves.toEqual({ status: "started", job_id: "d2b13faf-3185-4aa1" });
  });

  it("passes a refusal through with its reason; silence is unknown", async () => {
    const promise = renderVideoInHost("v2", "t", "busqueda", "horizontal");
    answer({ type: "molchat-molcy-result", request_id: "v2", status: "unavailable", reason: "sin GPU" });
    await expect(promise).resolves.toEqual({ status: "unavailable", reason: "sin GPU" });
    vi.useFakeTimers();
    const silent = renderVideoInHost("v3", "t", "busqueda", "horizontal");
    answer({ type: "molchat-molcy-result", request_id: "v3", status: "started", job_id: "../x" });
    answer({ type: "molchat-molcy-result", request_id: "v3", status: "started", job_id: "abcdefgh" }, "https://evil.example.com");
    vi.advanceTimersByTime(96000);
    await expect(silent).resolves.toEqual({ status: "unknown" });
  });
});
