/** Sidecar API client: same origin, Bearer session, JSON errors as ApiError. */

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export interface Evidence {
  tool: string;
  label: string;
  epistemic_class: string;
  source: string;
  values: Record<string, string>;
  error: string | null;
  methods?: Record<string, string>;
  structure?: {
    input_smiles: string;
    canonical_smiles: string;
    identity: "same" | "changed" | "unverified";
    verifier?: string | null;
    warnings?: string[];
    pubchem_cid?: number;
    pubchem_source?: string;
  };
}

export interface PubChemReference {
  cid: number;
  name: string;
  source: string;
  properties?: Record<string, string | number>;
  properties_available?: boolean;
}

export interface TurnResult {
  text: string;
  intent: string;
  evidence: Evidence[];
  latency_ms: number;
  used_llm: boolean;
  verified_values: number[];
  references?: PubChemReference[];
  comparison_cids?: number[];
}

export interface ConversationSummary {
  id: string;
  summary: string;
  updated_at: number;
  message_count: number;
}

export interface HarnessJob {
  id: string;
  conversation_id: string;
  state: string;
  steps: { id: string; tool: string; status: string; detail?: string }[];
  created_at: number;
  updated_at: number;
}

export interface PlanStep {
  id: string;
  capability: string;
  arguments: Record<string, unknown>;
  rationale: string;
}

export interface Plan {
  goal: string;
  steps: PlanStep[];
  planner: string;
  schema: string;
}

export interface CatalogEntry {
  name: string;
  description: string;
  risk: string;
  epistemic_class: string;
}

async function request(
  token: string,
  path: string,
  init: RequestInit = {},
): Promise<unknown> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const payload = (await response.json()) as { error?: string };
      if (payload.error) message = payload.error;
    } catch {
      // Keep the generic message.
    }
    throw new ApiError(response.status, message);
  }
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return null;
  return (await response.json()) as unknown;
}

const postJson = (token: string, path: string, body: unknown) =>
  request(token, path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

export const api = {
  version: async (): Promise<{ stt?: string }> => {
    const response = await fetch("/v1/version");
    if (!response.ok) return {};
    return (await response.json()) as { stt?: string };
  },
  catalog: (t: string) => request(t, "/v1/catalog") as Promise<CatalogEntry[]>,
  pubchemPermission: (t: string) => request(t, "/v1/pubchem/permission") as Promise<{ authorized: boolean; offline: boolean }>,
  setPubchemPermission: (t: string, grant: boolean) => request(t, "/v1/pubchem/permission", { method: grant ? "POST" : "DELETE" }) as Promise<{ authorized: boolean; offline: boolean }>,
  selectPubchem: (t: string, conversation: string, cid: number) =>
    postJson(t, `/v1/conversations/${encodeURIComponent(conversation)}/pubchem-selection`, { cid }) as Promise<{ text: string }>,
  reportCaseResult: (t: string, id: string, status: "created" | "exists" | "failed" | "unknown") =>
    postJson(t, `/v1/case-requests/${encodeURIComponent(id)}/result`, { status }),
  reportSmilesResult: (t: string, id: string, status: "applied" | "not_found" | "ambiguous" | "busy" | "failed" | "unknown") =>
    postJson(t, `/v1/smiles-requests/${encodeURIComponent(id)}/result`, { status }),
  reportEditorResult: (t: string, id: string, result: { status: string; molfile?: string; revision?: string }) =>
    postJson(t, `/v1/editor-requests/${encodeURIComponent(id)}/result`, result),
  createConversation: (t: string) =>
    postJson(t, "/v1/conversations", {}) as Promise<{ id: string }>,
  listConversations: (t: string) =>
    request(t, "/v1/conversations") as Promise<ConversationSummary[]>,
  listHarnessJobs: (t: string) => request(t, "/v1/harness-jobs") as Promise<HarnessJob[]>,
  getConversation: (t: string, id: string) =>
    request(t, `/v1/conversations/${id}`) as Promise<{
      messages: { role: string; content: string; references?: PubChemReference[]; evidence?: Evidence[]; comparison_cids?: number[] }[];
      pending_references?: PubChemReference[];
    }>,
  deleteConversation: (t: string, id: string) =>
    request(t, `/v1/conversations/${id}`, { method: "DELETE" }),
  proposePlan: (t: string, goal: string) =>
    postJson(t, "/v1/plans", { goal }) as Promise<{ plan: Plan; digest: string }>,
  submitExecution: (
    t: string,
    plan: Plan,
    approval?: { approval_digest: string; approved_steps: string[] },
  ) =>
    postJson(t, "/v1/executions", { plan, ...approval }) as Promise<{
      id: string;
      digest: string;
      state: string;
    }>,
  getExecution: (t: string, id: string) =>
    request(t, `/v1/executions/${id}`) as Promise<{
      id: string;
      digest: string;
      state: string;
      report: Record<string, unknown> | null;
    }>,
  cancelExecution: (t: string, id: string) =>
    postJson(t, `/v1/executions/${id}/cancel`, {}) as Promise<{
      cancelled: boolean;
      detail: string;
    }>,
  transcribe: async (t: string, audio: Blob, lang: string): Promise<string> => {
    const payload = (await request(t, `/v1/transcribe?lang=${lang}`, {
      method: "POST",
      headers: { "Content-Type": "audio/wav" },
      body: audio,
    })) as { text: string };
    return payload.text;
  },
  revoke: (t: string) => postJson(t, "/v1/session/revoke", {}),
};

/** Open an SSE POST stream; returns an aborter. Events flow to onEvent. */
export function openChatStream(
  token: string,
  body: { text: string; conversation_id?: string },
  onEvent: (event: Record<string, unknown>) => void,
  onError: (error: Error) => void,
): () => void {
  const controller = new AbortController();
  (async () => {
    try {
      const response = await fetch("/v1/chat", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        let message = `HTTP ${response.status}`;
        try {
          const payload = (await response.json()) as { error?: string };
          if (payload.error) message = payload.error;
        } catch {
          // Keep the generic message.
        }
        onError(new ApiError(response.status, message));
        return;
      }
      const { createSseParser } = await import("./sse");
      const parser = createSseParser();
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const event of parser.push(decoder.decode(value, { stream: true }))) {
          onEvent(event);
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") return;
      onError(error instanceof Error ? error : new Error(String(error)));
    }
  })();
  return () => controller.abort();
}

/** Open an SSE GET stream (execution snapshots); returns an aborter. */
export function openEventStream(
  token: string,
  path: string,
  onEvent: (event: Record<string, unknown>) => void,
  onError: (error: Error) => void,
): () => void {
  const controller = new AbortController();
  (async () => {
    try {
      const response = await fetch(path, {
        headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        onError(new ApiError(response.status, `HTTP ${response.status}`));
        return;
      }
      const { createSseParser } = await import("./sse");
      const parser = createSseParser();
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const event of parser.push(decoder.decode(value, { stream: true }))) {
          onEvent(event);
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") return;
      onError(error instanceof Error ? error : new Error(String(error)));
    }
  })();
  return () => controller.abort();
}
