import { describe, expect, it, vi } from "vitest";
import {
  announceReady,
  isLoopbackOrigin,
  isTrustedHostOrigin,
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

  it("accepts the Tauri host origin without accepting lookalikes", () => {
    expect(isTrustedHostOrigin("http://tauri.localhost")).toBe(true);
    expect(isTrustedHostOrigin("https://tauri.localhost")).toBe(true);
    expect(isTrustedHostOrigin("https://tauri.localhost.evil.example")).toBe(false);
  });

  it("validates the closed session shape", () => {
    expect(
      isSessionMessage({ type: "molchat-host-session", token: "test-mh1.x.y" }),
    ).toBe(true);
    expect(isSessionMessage({ type: "molchat-host-session" })).toBe(false);
    expect(
      isSessionMessage({ type: "molchat-host-session", token: "" }),
    ).toBe(false);
    expect(
      isSessionMessage({ type: "nope", token: "test-mh1.x.y" }),
    ).toBe(false);
    expect(
      isSessionMessage({
        type: "molchat-host-session",
        token: "test-mh1.x.y",
        extra: 1,
      }),
    ).toBe(false);
    expect(isSessionMessage(null)).toBe(false);
    expect(isSessionMessage({ type: "molchat-host-session", token: "test-mh1.x.y", locale: "en" })).toBe(true);
    expect(isSessionMessage({ type: "molchat-host-session", token: "test-mh1.x.y", locale: "fr" })).toBe(false);
  });

  it("passes the host language only from the verified parent", () => {
    const listeners: Array<(event: unknown) => void> = [];
    const scope = {
      addEventListener: (_t: string, l: (event: unknown) => void) => listeners.push(l),
      removeEventListener: () => {},
    };
    const parent = { postMessage: vi.fn() };
    const onToken = vi.fn();
    listenForSession(onToken, scope as unknown as Parameters<typeof listenForSession>[1], parent);
    listeners.forEach(l => l({ origin: "http://tauri.localhost", source: parent,
      data: { type: "molchat-host-session", token: "test-mh1.x.y", locale: "en" } }));
    expect(onToken).toHaveBeenCalledWith("test-mh1.x.y", "en");
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
    const parent = { postMessage: vi.fn() };
    const stranger = { postMessage: vi.fn() };
    const unlisten = listenForSession(
      onToken,
      scope as unknown as Parameters<typeof listenForSession>[1],
      parent,
    );
    const emit = (origin: string, data: unknown, source = parent) =>
      listeners.forEach((l) => l({ origin, data, source }));
    emit("https://evil.example.com", {
      type: "molchat-host-session",
      token: "test-mh1.evil.y",
    });
    emit("http://127.0.0.1:18017", { type: "otra-cosa" });
    emit("http://tauri.localhost", {
      type: "molchat-host-session",
      token: "test-mh1.bien.firma",
    });
    emit("http://tauri.localhost", { type: "molchat-host-session", token: "test-mh1.ajena.firma" }, stranger);
    expect(onToken).toHaveBeenCalledTimes(1);
    expect(onToken).toHaveBeenCalledWith("test-mh1.bien.firma");
    unlisten();
    emit("http://127.0.0.1:18017", {
      type: "molchat-host-session",
      token: "test-mh1.tarde.firma",
    });
    expect(onToken).toHaveBeenCalledTimes(1);
  });
});
