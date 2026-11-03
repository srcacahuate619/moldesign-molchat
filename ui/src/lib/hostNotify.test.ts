import { afterEach, describe, expect, it, vi } from "vitest";
import { newNoticeId, notifyHost } from "./hostNotify";

afterEach(() => { Object.defineProperty(window, "parent", { configurable: true, value: window }); });

describe("notifyHost", () => {
  it("sends a closed notice to the host and nothing when there is no host", () => {
    const post = vi.fn();
    notifyHost("a".repeat(32), "done", "entrega.zip");
    expect(post).not.toHaveBeenCalled();
    Object.defineProperty(window, "parent", { configurable: true, value: { postMessage: post } });
    notifyHost("a".repeat(32), "started", "entrega.zip");
    expect(post).toHaveBeenCalledWith({ type: "molchat-host-message", kind: "notify_download", request_id: "a".repeat(32),
      phase: "started", name: "entrega.zip" }, "*");
  });
  it("makes ids the host accepts", () => {
    expect(newNoticeId()).toMatch(/^[a-f0-9]{32}$/);
  });
});
