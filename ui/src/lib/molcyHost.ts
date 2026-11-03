import { isTrustedHostOrigin } from "./hostSession";

export type MolcyStatus = "started" | "not_found" | "unavailable" | "busy" | "failed" | "unknown";

/** What the Molcy tab answers: the render job it started from its own button, or why it could not. */
export type MolcyResult = { status: "started"; job_id: string } | { status: Exclude<MolcyStatus, "started">; reason?: string };

const STATUSES: MolcyStatus[] = ["started", "not_found", "unavailable", "busy", "failed", "unknown"];

/**
 * Ask the host's Molcy tab to prepare the video in view (run, scene, format) and press «Generate». A silent host is
 * «unknown»: the tab may have started a render, so the caller never asks again.
 */
export function renderVideoInHost(requestId: string, taskId: string, scene: string, format: string): Promise<MolcyResult> {
  if (window.parent === window) return Promise.resolve({ status: "failed" });
  return new Promise((resolve) => {
    const finish = (result: MolcyResult) => {
      window.clearTimeout(timer);
      window.removeEventListener("message", onMessage);
      resolve(result);
    };
    const onMessage = (event: MessageEvent) => {
      if (event.source !== window.parent || !isTrustedHostOrigin(event.origin)) return;
      const data = event.data;
      if (!data || data.type !== "molchat-molcy-result" || data.request_id !== requestId) return;
      if (!STATUSES.includes(data.status)) return;
      if (data.status === "started") {
        if (typeof data.job_id !== "string" || !/^[A-Za-z0-9-]{8,64}$/.test(data.job_id)) return;
        finish({ status: "started", job_id: data.job_id });
        return;
      }
      const reason = typeof data.reason === "string" && data.reason.length <= 300 && !/[\x00-\x1f]/.test(data.reason) ? data.reason : undefined;
      finish({ status: data.status, ...(reason ? { reason } : {}) });
    };
    const timer = window.setTimeout(() => finish({ status: "unknown" }), 95000);
    window.addEventListener("message", onMessage);
    window.parent.postMessage({ type: "molchat-host-message", kind: "molcy_render", request_id: requestId, task_id: taskId, scene, format }, "*");
  });
}
