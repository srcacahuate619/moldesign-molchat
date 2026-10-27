/**
 * Host bridge (§11.3): the UI may only ask the host these five actions.
 * Messages go out via postMessage; nothing inbound is ever listened to,
 * so any other message is ignored by construction. The host verifies our
 * origin; we never receive the platform token and never call MolDesign.
 */

export type HostMessage =
  | { kind: "open_evaluation"; molecule_id: string }
  | { kind: "open_report"; molecule_id: string }
  | { kind: "open_case"; case_id: string }
  | { kind: "open_molcy"; job_id: string }
  | { kind: "request_platform_approval"; proposal_id: string };

export const HOST_ENVELOPE = "molchat-host-message";

const SHAPES: Record<HostMessage["kind"], string[]> = {
  open_evaluation: ["molecule_id"],
  open_report: ["molecule_id"],
  open_case: ["case_id"],
  open_molcy: ["job_id"],
  request_platform_approval: ["proposal_id"],
};

export function isHostMessage(value: unknown): value is HostMessage {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  if (typeof record["kind"] !== "string") return false;
  const fields = SHAPES[record["kind"] as HostMessage["kind"]];
  if (!fields) return false;
  const keys = Object.keys(record);
  if (keys.length !== fields.length + 1) return false;
  return fields.every(
    (field) =>
      typeof record[field] === "string" && (record[field] as string).length > 0,
  );
}

/**
 * Post a closed-schema message to the embedding host.
 * Returns false when unhosted (standalone demo: no parent frame).
 */
export function postToHost(
  message: HostMessage,
  target: { postMessage: (data: unknown, origin: string) => void } | null = null,
): boolean {
  const parent =
    target ?? (typeof window !== "undefined" ? window.parent : null);
  if (!parent || (typeof window !== "undefined" && parent === window)) {
    return false;
  }
  if (!isHostMessage(message)) return false;
  parent.postMessage({ type: HOST_ENVELOPE, ...message }, "*");
  return true;
}

/** Extract host actions referenced by an execution report (ids it cites). */
export function linksForReport(report: unknown): HostMessage[] {
  if (typeof report !== "object" || report === null) return [];
  const outcomes = (report as Record<string, unknown>)["outcomes"];
  if (!Array.isArray(outcomes)) return [];
  const links: HostMessage[] = [];
  const seen = new Set<string>();
  for (const outcome of outcomes) {
    const result = (outcome as Record<string, unknown>)?.["result"];
    if (typeof result !== "object" || result === null) continue;
    const flat = result as Record<string, unknown>;
    const molecule =
      typeof flat["molecule_id"] === "string" ? flat["molecule_id"] : null;
    if (molecule && !seen.has(molecule)) {
      seen.add(molecule);
      links.push({ kind: "open_evaluation", molecule_id: molecule });
      links.push({ kind: "open_report", molecule_id: molecule });
    }
    // Task ids alone open nothing: the closed schema has no task action,
    // and guessing a molecule from a task would be invention.
  }
  return links;
}
