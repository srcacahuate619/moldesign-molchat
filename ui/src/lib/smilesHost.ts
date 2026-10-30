import { isTrustedHostOrigin } from "./hostSession";

export type SmilesStatus = "applied" | "not_found" | "ambiguous" | "busy" | "failed" | "unknown";

export function loadSmilesInHost(requestId: string, caseName: string, smiles: string): Promise<SmilesStatus> {
  if (window.parent === window) return Promise.resolve("failed");
  return new Promise((resolve) => {
    const finish = (status: SmilesStatus) => {
      window.clearTimeout(timer);
      window.removeEventListener("message", onMessage);
      resolve(status);
    };
    const onMessage = (event: MessageEvent) => {
      if (event.source !== window.parent || !isTrustedHostOrigin(event.origin)) return;
      const data = event.data;
      if (!data || data.type !== "molchat-smiles-result" || data.request_id !== requestId) return;
      if (["applied", "not_found", "ambiguous", "busy", "failed", "unknown"].includes(data.status)) finish(data.status as SmilesStatus);
    };
    const timer = window.setTimeout(() => finish("unknown"), 50000);
    window.addEventListener("message", onMessage);
    window.parent.postMessage({ type: "molchat-host-message", kind: "load_case_smiles", request_id: requestId, case_name: caseName, smiles }, "*");
  });
}
