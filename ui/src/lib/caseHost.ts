import { isTrustedHostOrigin } from "./hostSession";

export type CaseStatus = "created" | "failed" | "unknown";

/** Request one host operation. Timeouts never imply that the write failed. */
export function createCaseInHost(requestId: string, name: string): Promise<CaseStatus> {
  if (window.parent === window) return Promise.resolve("failed");
  return new Promise((resolve) => {
    const finish = (status: CaseStatus) => {
      window.clearTimeout(timer);
      window.removeEventListener("message", onMessage);
      resolve(status);
    };
    const onMessage = (event: MessageEvent) => {
      if (event.source !== window.parent || !isTrustedHostOrigin(event.origin)) return;
      const data = event.data;
      if (!data || data.type !== "molchat-case-result" || data.request_id !== requestId) return;
      if (data.status === "created" || data.status === "failed" || data.status === "unknown") finish(data.status);
    };
    const timer = window.setTimeout(() => finish("unknown"), 50000);
    window.addEventListener("message", onMessage);
    window.parent.postMessage({ type: "molchat-host-message", kind: "create_case", request_id: requestId, name }, "*");
  });
}
