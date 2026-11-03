import { isTrustedHostOrigin } from "./hostSession";

export type CaseState = "idle" | "busy" | "not_found" | "ambiguous" | "failed" | "unknown";

/** What the window says about a case: whether it can take another molecule, and the state of its last run. */
export interface CaseStatusResult { status: CaseState; run_state?: string; task_id?: string }

const STATES: CaseState[] = ["idle", "busy", "not_found", "ambiguous", "failed", "unknown"];

/**
 * Read-only question to the host: can this case take another molecule now? The iteration asks it before loading the
 * next one instead of guessing from a refused load. A silent host is «unknown», never «idle».
 */
export function caseStatusInHost(requestId: string, caseName: string): Promise<CaseStatusResult> {
  if (window.parent === window) return Promise.resolve({ status: "unknown" });
  return new Promise((resolve) => {
    const finish = (result: CaseStatusResult) => {
      window.clearTimeout(timer);
      window.removeEventListener("message", onMessage);
      resolve(result);
    };
    const onMessage = (event: MessageEvent) => {
      if (event.source !== window.parent || !isTrustedHostOrigin(event.origin)) return;
      const data = event.data;
      if (!data || data.type !== "molchat-case-status-result" || data.request_id !== requestId) return;
      if (!STATES.includes(data.status)) return;
      const result: CaseStatusResult = { status: data.status };
      if (typeof data.run_state === "string" && /^[a-z_]{1,32}$/.test(data.run_state)) result.run_state = data.run_state;
      if (typeof data.task_id === "string" && /^[A-Za-z0-9_.:-]{1,128}$/.test(data.task_id)) result.task_id = data.task_id;
      finish(result);
    };
    const timer = window.setTimeout(() => finish({ status: "unknown" }), 15000);
    window.addEventListener("message", onMessage);
    window.parent.postMessage({ type: "molchat-host-message", kind: "case_status", request_id: requestId, case_name: caseName }, "*");
  });
}
