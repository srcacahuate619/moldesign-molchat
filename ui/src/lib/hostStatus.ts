/** What MolChat is doing, in one line, for the host's bubble when the panel is minimised.
 *
 * Several parts of the window report at once (the chat while it writes, each plan card while it runs). Each one reports
 * under its own name and the most important line wins: something waiting for the person first, then an error, then work
 * in progress, then a reply being written, then a finished result. Only changes are sent. A window that is not embedded
 * has no bubble, so nothing is sent. */
export const STATUS_ENVELOPE = "molchat-ui-status";

export type BubbleState = "attention" | "error" | "working" | "thinking" | "done";
export interface BubbleStatus { state: BubbleState; text: string }

const RANK: Record<BubbleState, number> = { attention: 5, error: 4, working: 3, thinking: 2, done: 1 };
const sources = new Map<string, { status: BubbleStatus; at: number }>();
let tick = 0;
let last = "";

/** The line that wins now, or ``null`` when nothing is going on. Ties go to the most recent report. */
export function currentStatus(): BubbleStatus | null {
  let best: { status: BubbleStatus; at: number } | null = null;
  for (const entry of sources.values()) {
    if (!best || RANK[entry.status.state] > RANK[best.status.state]
        || (RANK[entry.status.state] === RANK[best.status.state] && entry.at > best.at)) best = entry;
  }
  return best ? best.status : null;
}

export function reportStatus(source: string, status: BubbleStatus | null): void {
  const previous = sources.get(source);
  if (status === null) sources.delete(source);
  else if (!previous || previous.status.state !== status.state || previous.status.text !== status.text) sources.set(source, { status, at: ++tick });
  const now = currentStatus();
  const message = { type: STATUS_ENVELOPE, state: now ? now.state : "idle", text: now ? now.text.replace(/[\x00-\x1f]/g, " ").slice(0, 140) : "" };
  const key = `${message.state}\n${message.text}`;
  if (key === last) return;
  last = key;
  if (window.parent === window) return;
  window.parent.postMessage(message, "*");
}

/** Only for tests: forget every source. */
export function resetStatus(): void {
  sources.clear();
  last = "";
}
