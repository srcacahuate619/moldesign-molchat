import { useState } from "react";
import { ApiError, api, type ActionOutcome, type ActionProposal } from "../lib/api";
import { postToHost } from "../lib/deeplinks";
import type { StringKey } from "../lib/i18n";

type Phase = "pending" | "running" | "done" | "cancelled";

const KINDS = ["save_moldex", "molcy_video"];

/** Keep only well-formed proposals: the card renders what the sidecar says, so it checks the shape first. */
export function validProposals(value: unknown): ActionProposal[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item): ActionProposal[] => {
    if (typeof item !== "object" || item === null) return [];
    const p = item as Record<string, unknown>;
    if (typeof p["id"] !== "string" || p["id"].length === 0 || p["id"].length > 64) return [];
    if (typeof p["kind"] !== "string" || !KINDS.includes(p["kind"])) return [];
    if (typeof p["title"] !== "string" || p["title"].length === 0 || p["title"].length > 120) return [];
    if (!Array.isArray(p["lines"]) || p["lines"].length > 12 || !p["lines"].every((line) => typeof line === "string" && line.length <= 400)) return [];
    return [{ id: p["id"], kind: p["kind"] as ActionProposal["kind"], title: p["title"], lines: p["lines"] as string[] }];
  }).slice(0, 2);
}

/**
 * A confirmation card. The model only proposes: nothing happens until the person presses Confirm, and the
 * sidecar (not this card) is what calls MolDesign. A lost answer is not a failure: pressing again returns
 * what happened instead of repeating it.
 */
export default function ActionProposalCard({
  proposal, token, t, onSessionInvalid,
}: {
  proposal: ActionProposal;
  token: string;
  t: (key: StringKey) => string;
  onSessionInvalid: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("pending");
  const [outcome, setOutcome] = useState<ActionOutcome | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const settle = (state: "done" | "cancelled", result: ActionOutcome | null) => {
    setOutcome(result);
    setPhase(state);
  };

  const fail = (err: unknown) => {
    if (err instanceof ApiError && err.status === 401) onSessionInvalid();
    else if (err instanceof ApiError && err.status === 404) setProblem(t("action.expired"));
    else if (err instanceof ApiError && err.status === 409) setProblem(t("action.busy"));
    else setProblem(t("action.unreachable"));
    setPhase("pending");
  };

  const run = async (decision: "confirm" | "cancel") => {
    setProblem(null);
    setPhase("running");
    try {
      const resolution = decision === "confirm"
        ? await api.confirmAction(token, proposal.id)
        : await api.cancelAction(token, proposal.id);
      settle(resolution.state, resolution.outcome);
    } catch (err) {
      fail(err);
    }
  };

  const done = outcome !== null && (outcome.status === "started" || outcome.status === "saved");
  const jobId = outcome?.status === "started" && typeof outcome.job_id === "string" ? outcome.job_id : null;
  return (
    <div className="action-card" role="group" aria-label={t("action.group")} data-phase={phase}>
      <p className="action-title"><strong>{proposal.title}</strong></p>
      <ul>{proposal.lines.map((line, index) => <li key={index}>{line}</li>)}</ul>
      {phase === "pending" || phase === "running" ? (
        <>
          <p className="muted">{t("action.pending")}</p>
          <div className="action-buttons">
            <button type="button" disabled={phase === "running"} onClick={() => void run("confirm")}>
              {phase === "running" ? t("action.running") : t("action.confirm")}
            </button>
            <button type="button" disabled={phase === "running"} onClick={() => void run("cancel")}>{t("action.cancel")}</button>
          </div>
        </>
      ) : phase === "cancelled" ? (
        <p className="muted">{t("action.cancelled")}</p>
      ) : (
        <p role="status" className={done ? "action-result" : "action-result error"}>
          {outcome?.message ?? ""}
          {jobId && <> <button type="button" onClick={() => postToHost({ kind: "open_molcy", job_id: jobId })}>{t("action.openMolcy")}</button></>}
        </p>
      )}
      {problem && <p role="alert" className="error">{problem}</p>}
    </div>
  );
}
