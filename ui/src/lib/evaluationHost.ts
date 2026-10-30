import { isTrustedHostOrigin } from "./hostSession";

export type EvaluationStatus = "started" | "started_unregistered" | "case_not_found" | "case_ambiguous" | "busy" | "blocked" | "needs_review" | "failed" | "unknown";
export interface EvaluationResult { status: EvaluationStatus; task_id?: string; reason?: string }

export function evaluateCaseInHost(requestId: string, caseName: string): Promise<EvaluationResult> {
  if (window.parent === window) return Promise.resolve({ status: "failed" });
  return new Promise((resolve) => {
    const finish = (result: EvaluationResult) => {
      window.clearTimeout(timer);
      window.removeEventListener("message", onMessage);
      resolve(result);
    };
    const onMessage = (event: MessageEvent) => {
      if (event.source !== window.parent || !isTrustedHostOrigin(event.origin)) return;
      const data = event.data;
      if (!data || data.type !== "molchat-evaluation-result" || data.request_id !== requestId) return;
      if (!["started", "started_unregistered", "case_not_found", "case_ambiguous", "busy", "blocked", "needs_review", "failed", "unknown"].includes(data.status)) return;
      if (["started", "started_unregistered"].includes(data.status) && (typeof data.task_id !== "string" || !/^[A-Za-z0-9_.:-]{1,128}$/.test(data.task_id))) return;
      const result: EvaluationResult = { status: data.status };
      if (typeof data.task_id === "string") result.task_id = data.task_id;
      if (typeof data.reason === "string" && data.reason.length <= 500 && !/[\x00-\x1f]/.test(data.reason)) result.reason = data.reason;
      finish(result);
    };
    const timer = window.setTimeout(() => finish({ status: "unknown" }), 140000);
    window.addEventListener("message", onMessage);
    window.parent.postMessage({ type: "molchat-host-message", kind: "evaluate_case", request_id: requestId, case_name: caseName }, "*");
  });
}
