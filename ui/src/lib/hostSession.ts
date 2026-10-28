/**
 * Host session handshake (§15.2): when embedded in MolDesign, the desktop
 * passes our session token via postMessage (never via URL) after we announce
 * readiness. Inbound we accept exactly one message shape, from loopback
 * origins only; anything else is ignored. Standalone (no parent frame):
 * announcing is a no-op and nobody ever answers.
 */

export const READY_ENVELOPE = "molchat-ui-ready";
export const SESSION_ENVELOPE = "molchat-host-session";

type PostTarget = {
  postMessage: (data: unknown, origin: string) => void;
};

type ListenScope = {
  addEventListener: (
    type: string,
    listener: (event: { origin: string; data: unknown }) => void,
  ) => void;
  removeEventListener: (
    type: string,
    listener: (event: { origin: string; data: unknown }) => void,
  ) => void;
};

export function isLoopbackOrigin(origin: string): boolean {
  try {
    const url = new URL(origin);
    return (
      (url.protocol === "http:" || url.protocol === "https:") &&
      (url.hostname === "127.0.0.1" ||
        url.hostname === "localhost" ||
        url.hostname === "::1" ||
        url.hostname === "[::1]")
    );
  } catch {
    return false;
  }
}

export function isSessionMessage(
  value: unknown,
): value is { type: string; token: string } {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  if (record["type"] !== SESSION_ENVELOPE) return false;
  if (typeof record["token"] !== "string" || record["token"].length === 0)
    return false;
  return Object.keys(record).length === 2;
}

/**
 * Announce readiness to the embedding host.
 * Returns false when unhosted (standalone demo: no parent frame).
 */
export function announceReady(target: PostTarget | null = null): boolean {
  const parent =
    target ?? (typeof window !== "undefined" ? window.parent : null);
  if (!parent || (typeof window !== "undefined" && parent === window)) {
    return false;
  }
  parent.postMessage({ type: READY_ENVELOPE }, "*");
  return true;
}

/**
 * Listen for the one host message (session token). Returns an unlisten
 * function for effect cleanup.
 */
export function listenForSession(
  onToken: (token: string) => void,
  scope: ListenScope | null = null,
): () => void {
  const holder =
    scope ?? (typeof window !== "undefined" ? window : null);
  if (!holder) return () => {};
  const listener = (event: { origin: string; data: unknown }) => {
    if (!isLoopbackOrigin(event.origin)) return;
    if (!isSessionMessage(event.data)) return;
    onToken(event.data.token);
  };
  holder.addEventListener("message", listener);
  return () => holder.removeEventListener("message", listener);
}
