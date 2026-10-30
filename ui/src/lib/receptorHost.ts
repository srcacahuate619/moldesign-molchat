import { isTrustedHostOrigin } from "./hostSession";

export type ReceptorStatus = "applied" | "already_selected" | "case_not_found" | "case_ambiguous" | "receptor_not_found" | "receptor_ambiguous" | "unavailable" | "locked" | "busy" | "save_failed" | "failed" | "unknown";

export function assignReceptorInHost(requestId: string, caseName: string, pdbId: string): Promise<ReceptorStatus> {
  if (window.parent === window) return Promise.resolve("failed");
  return new Promise((resolve) => {
    const finish = (status: ReceptorStatus) => {
      window.clearTimeout(timer);
      window.removeEventListener("message", onMessage);
      resolve(status);
    };
    const onMessage = (event: MessageEvent) => {
      if (event.source !== window.parent || !isTrustedHostOrigin(event.origin)) return;
      const data = event.data;
      if (!data || data.type !== "molchat-receptor-result" || data.request_id !== requestId) return;
      if (["applied", "already_selected", "case_not_found", "case_ambiguous", "receptor_not_found", "receptor_ambiguous", "unavailable", "locked", "busy", "save_failed", "failed", "unknown"].includes(data.status)) finish(data.status as ReceptorStatus);
    };
    const timer = window.setTimeout(() => finish("unknown"), 50000);
    window.addEventListener("message", onMessage);
    window.parent.postMessage({ type: "molchat-host-message", kind: "assign_case_receptor", request_id: requestId, case_name: caseName, pdb_id: pdbId }, "*");
  });
}
