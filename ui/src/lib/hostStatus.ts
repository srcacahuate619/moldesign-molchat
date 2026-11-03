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

/** A running plan, in a few fields, for the host to show that MolChat is the one driving: the steps, each molecule with
 * its Vina as it arrives, and what it is doing now. Sent on its own envelope, so a host that does not know it ignores
 * it and keeps the one-line bubble. */
export const PROGRESS_ENVELOPE = "molchat-ui-progress";

export type ProgressPhase = "running" | "rendering" | "done" | "stopped";
export type ProgressStepState = "pending" | "running" | "done" | "failed" | "skipped";
export interface PlanProgress {
  title: string;
  phase: ProgressPhase;
  now: string;
  steps: { label: string; state: ProgressStepState }[];
  molecules: { name: string; state: ProgressStepState; vina: number | null; meets: boolean }[];
}

const PHASE_RANK: Record<ProgressPhase, number> = { running: 4, rendering: 3, stopped: 2, done: 1 };
const plans = new Map<string, { progress: PlanProgress; at: number }>();
let lastProgress = "";

/** The plan that wins now: one at work before one that finished; ties go to the most recent report. */
export function currentProgress(): PlanProgress | null {
  let best: { progress: PlanProgress; at: number } | null = null;
  for (const entry of plans.values()) {
    if (!best || PHASE_RANK[entry.progress.phase] > PHASE_RANK[best.progress.phase]
        || (PHASE_RANK[entry.progress.phase] === PHASE_RANK[best.progress.phase] && entry.at > best.at)) best = entry;
  }
  return best ? best.progress : null;
}

const clean = (text: string, max: number) => text.replace(/[\x00-\x1f]/g, " ").slice(0, max);

export function reportProgress(source: string, progress: PlanProgress | null): void {
  if (progress === null) plans.delete(source);
  else plans.set(source, { progress, at: ++tick });
  const now = currentProgress();
  const message = { type: PROGRESS_ENVELOPE, progress: now && {
    title: clean(now.title, 140), phase: now.phase, now: clean(now.now, 140),
    steps: now.steps.slice(0, 10).map((step) => ({ label: clean(step.label, 60), state: step.state })),
    molecules: now.molecules.slice(0, 12).map((m) => ({ name: clean(m.name, 80), state: m.state, vina: m.vina, meets: m.meets })),
  } };
  const key = JSON.stringify(message);
  if (key === lastProgress) return;
  lastProgress = key;
  if (window.parent === window) return;
  window.parent.postMessage(message, "*");
}

/** Only for tests: forget every source. */
export function resetStatus(): void {
  sources.clear();
  last = "";
  plans.clear();
  lastProgress = "";
}
