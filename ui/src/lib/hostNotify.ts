/** Notices for the host's activity panel: what MolChat downloads, and when the background video reached the delivery.
 * Fire and forget: the host only shows them. A window that is not embedded has no panel, so nothing is sent. */
export type DownloadPhase = "started" | "done" | "failed" | "video_ready";

export function newNoticeId(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function notifyHost(requestId: string, phase: DownloadPhase, name: string): void {
  if (window.parent === window) return;
  window.parent.postMessage({ type: "molchat-host-message", kind: "notify_download", request_id: requestId, phase, name }, "*");
}
