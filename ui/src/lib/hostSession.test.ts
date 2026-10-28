import { describe, expect, it, vi } from "vitest";
import {
  announceReady,
  isLoopbackOrigin,
  isSessionMessage,
  listenForSession,
} from "./hostSession";

describe("host session handshake", () => {
  it("accepts loopback origins only", () => {
    expect(isLoopbackOrigin("http://127.0.0.1:52368")).toBe(true);
    expect(isLoopbackOrigin("http://localhost:8771")).toBe(true);
    expect(isLoopbackOrigin("https://127.0.0.1:1")).toBe(true);
    expect(isLoopbackOrigin("https://evil.example.com")).toBe(false);
    expect(isLoopbackOrigin("http://127.0.0.1.evil.com")).toBe(false);
    expect(isLoopbackOrigin("not a url")).toBe(false);
    expect(isLoopbackOrigin("")).toBe(false);
  });

  it("validates the closed session shape", () => {
    expect(
      isSessionMessage({ type: "molchat-host-session", token: "mh1.x.y" }),
    ).toBe(true);
    expect(isSessionMessage({ type: "molchat-host-session" })).toBe(false);
    expect(
      isSessionMessage({ type: "molchat-host-session", token: "" }),
    ).toBe(false);
    expect(
      isSessionMessage({ type: "nope", token: "mh1.x.y" }),
    ).toBe(false);
    expect(
      isSessionMessage({
        type: "molchat-host-session",
        token: "mh1.x.y",
        extra: 1,
      }),
    ).toBe(false);
    expect(isSessionMessage(null)).toBe(false);
  });

  it("announces readiness to the parent frame", () => {
    const parent = { postMessage: vi.fn() };
    expect(announceReady(parent)).toBe(true);
    expect(parent.postMessage).toHaveBeenCalledWith(
      { type: "molchat-ui-ready" },
      "*",
    );
    expect(announceReady(null)).toBe(false);
  });

  it("connects on a valid host session, ignores the rest", () => {
    const listeners: Array<(event: unknown) => void> = [];
    const scope = {
      addEventListener: (_t: string, l: (event: unknown) => void) => {
        listeners.push(l);
      },
      removeEventListener: (_t: string, l: (event: unknown) => void) => {
        const at = listeners.indexOf(l);
        if (at >= 0) listeners.splice(at, 1);
      },
    };
    const onToken = vi.fn();
    const unlisten = listenForSession(
      onToken,
      scope as unknown as Parameters<typeof listenForSession>[1],
    );
    const emit = (origin: string, data: unknown) =>
      listeners.forEach((l) => l({ origin, data }));
    emit("https://evil.example.com", {
      type: "molchat-host-session",
      token: "mh1.evil.y",
    });
    emit("http://127.0.0.1:18017", { type: "otra-cosa" });
    emit("http://127.0.0.1:18017", {
      type: "molchat-host-session",
      token: "mh1.bien.firma",
    });
    expect(onToken).toHaveBeenCalledTimes(1);
    expect(onToken).toHaveBeenCalledWith("mh1.bien.firma");
    unlisten();
    emit("http://127.0.0.1:18017", {
      type: "molchat-host-session",
      token: "mh1.tarde.firma",
    });
    expect(onToken).toHaveBeenCalledTimes(1);
  });
});
