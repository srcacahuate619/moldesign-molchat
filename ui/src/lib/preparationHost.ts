import { isTrustedHostOrigin } from "./hostSession";

export type PreparationStatus = "audited" | "case_not_found" | "case_mismatch" | "not_auditable" | "audit_failed" | "busy" | "failed" | "unknown";

/**
 * What the host's Preparación tab answers: either the case projection it built for an audited run (with the state
 * MolDesign's audit dictated), or why it could not audit. Nothing here decides anything: the sidecar sends the
 * projection to MolDesign, which audits it and builds the package.
 */
export type PreparationResult =
  | { status: "audited"; molecule_id: string; estado: "BLOQUEADO" | "REVISION" | "TRANSFERIBLE"; projection: Record<string, unknown> }
  | { status: Exclude<PreparationStatus, "audited">; reason?: string };

const STATES = ["BLOQUEADO", "REVISION", "TRANSFERIBLE"];
const STATUSES: PreparationStatus[] = ["audited", "case_not_found", "case_mismatch", "not_auditable", "audit_failed", "busy", "failed", "unknown"];

export function auditPreparationInHost(requestId: string, caseName: string, taskId: string): Promise<PreparationResult> {
  if (window.parent === window) return Promise.resolve({ status: "failed" });
  return new Promise((resolve) => {
    const finish = (result: PreparationResult) => {
      window.clearTimeout(timer);
      window.removeEventListener("message", onMessage);
      resolve(result);
    };
    const onMessage = (event: MessageEvent) => {
      if (event.source !== window.parent || !isTrustedHostOrigin(event.origin)) return;
      const data = event.data;
      if (!data || data.type !== "molchat-preparation-result" || data.request_id !== requestId) return;
      if (!STATUSES.includes(data.status)) return;
      if (data.status === "audited") {
        if (typeof data.molecule_id !== "string" || !/^[A-Za-z0-9_.:-]{1,128}$/.test(data.molecule_id)) return;
        if (!STATES.includes(data.estado) || typeof data.projection !== "object" || data.projection === null || Array.isArray(data.projection)) return;
        finish({ status: "audited", molecule_id: data.molecule_id, estado: data.estado, projection: data.projection });
        return;
      }
      const reason = typeof data.reason === "string" && data.reason.length <= 300 && !/[\x00-\x1f]/.test(data.reason) ? data.reason : undefined;
      finish({ status: data.status, ...(reason ? { reason } : {}) });
    };
    const timer = window.setTimeout(() => finish({ status: "unknown" }), 125000);
    window.addEventListener("message", onMessage);
    window.parent.postMessage({ type: "molchat-host-message", kind: "audit_case_preparation", request_id: requestId, case_name: caseName, task_id: taskId }, "*");
  });
}
