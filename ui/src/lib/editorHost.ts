import { isTrustedHostOrigin } from "./hostSession";

type EditorResult = { status: string; molfile?: string; revision?: string };
export function readEditorInHost(requestId: string, caseName: string, operation: string, revision: string): Promise<EditorResult> {
  if (window.parent === window) return Promise.resolve({ status: "failed" });
  return new Promise((resolve) => {
    const finish = (result: EditorResult) => { clearTimeout(timer); window.removeEventListener("message", onMessage); resolve(result); };
    const onMessage = (event: MessageEvent) => {
      if (event.source !== window.parent || !isTrustedHostOrigin(event.origin)) return;
      const data = event.data;
      if (!data || data.type !== "molchat-editor-result" || data.request_id !== requestId ||
          !["ok", "not_ready", "not_found", "ambiguous", "changed", "too_large", "read_limit", "failed", "unknown"].includes(data.status)) return;
      if (data.molfile !== undefined && (typeof data.molfile !== "string" || new TextEncoder().encode(data.molfile).length > 262144)) return;
      if (data.revision !== undefined && (typeof data.revision !== "string" || data.revision.length > 100)) return;
      finish({ status: data.status, ...(data.molfile !== undefined ? { molfile: data.molfile } : {}),
               ...(data.revision !== undefined ? { revision: data.revision } : {}) });
    };
    const timer = setTimeout(() => finish({ status: "unknown" }), 30000);
    window.addEventListener("message", onMessage);
    window.parent.postMessage({ type: "molchat-host-message", kind: "read_editor", request_id: requestId,
      case_name: caseName, operation, revision }, "*");
  });
}
