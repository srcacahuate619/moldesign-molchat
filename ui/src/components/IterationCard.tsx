import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, runWorkflow, type WorkflowProposal } from "../lib/api";
import { createCaseInHost } from "../lib/caseHost";
import { caseStatusInHost } from "../lib/caseStatusHost";
import { evaluateCaseInHost } from "../lib/evaluationHost";
import type { StringKey } from "../lib/i18n";
import { auditPreparationInHost } from "../lib/preparationHost";
import { assignReceptorInHost } from "../lib/receptorHost";
import { loadSmilesInHost } from "../lib/smilesHost";

type Phase = "pending" | "running" | "done" | "cancelled" | "interrupted";

interface Row {
  status: string;
  outcome: string | null;
  vina: number | null;
  physical: string | null;
  reason: string | null;
}

interface Summary {
  state: string;
  counts: Record<string, number> | null;
  selected: { name: string; task_id: string; vina_kcal_mol: number | null; physical_status: string | null } | null;
  saved: string | null;
  video: string | null;
  preparation: string | null;
  files: Record<string, number>;
  paths: Record<string, string>;
  notes: string[];
}

/** Keep only well-formed iterations: the card renders what the sidecar says, so it checks the shape first. */
export function validWorkflows(value: unknown): WorkflowProposal[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item): WorkflowProposal[] => {
    if (typeof item !== "object" || item === null) return [];
    const p = item as Record<string, unknown>;
    if (typeof p["id"] !== "string" || !/^[a-f0-9]{32}$/.test(p["id"])) return [];
    if (p["kind"] !== "iteration" || typeof p["digest"] !== "string" || !/^sha256:[a-f0-9]{64}$/.test(p["digest"])) return [];
    if (typeof p["title"] !== "string" || p["title"].length === 0 || p["title"].length > 120) return [];
    if (!Array.isArray(p["lines"]) || p["lines"].length > 16 || !p["lines"].every((l) => typeof l === "string" && l.length <= 500)) return [];
    if (!Array.isArray(p["molecules"]) || p["molecules"].length > 12 || !p["molecules"].every((m) => typeof m === "string" && m.length <= 80)) return [];
    return [{ id: p["id"], kind: "iteration", digest: p["digest"], title: p["title"], lines: p["lines"] as string[], molecules: p["molecules"] as string[] }];
  }).slice(0, 1);
}

const blank = (): Row => ({ status: "pending", outcome: null, vina: null, physical: null, reason: null });
const text = (value: unknown): string | null => (typeof value === "string" ? value : null);
const num = (value: unknown): number | null => (typeof value === "number" && Number.isFinite(value) ? value : null);

function summaryOf(value: unknown): Summary | null {
  if (typeof value !== "object" || value === null) return null;
  const s = value as Record<string, unknown>;
  const selected = s["selected"] as Record<string, unknown> | null;
  return {
    state: text(s["state"]) ?? "unknown",
    counts: typeof s["counts"] === "object" ? (s["counts"] as Record<string, number> | null) : null,
    selected: selected && typeof selected === "object"
      ? { name: text(selected["name"]) ?? "", task_id: text(selected["task_id"]) ?? "", vina_kcal_mol: num(selected["vina_kcal_mol"]),
          physical_status: text(selected["physical_status"]) } : null,
    saved: text(s["saved"]), video: text(s["video"]), preparation: text(s["preparation"]),
    files: typeof s["files"] === "object" && s["files"] ? (s["files"] as Record<string, number>) : {},
    paths: typeof s["paths"] === "object" && s["paths"] ? (s["paths"] as Record<string, string>) : {},
    notes: Array.isArray(s["notes"]) ? s["notes"].filter((n): n is string => typeof n === "string") : [],
  };
}

/**
 * The approval card of an iteration. The model only proposes; the person's click binds the plan's digest and runs it.
 * From then on this card is the window the plan uses to act on MolDesign (create the case, load a molecule, start a
 * run), so it relays those requests exactly as a chat turn does, and shows each molecule as it is evaluated.
 */
export default function IterationCard({
  proposal, token, t, onSessionInvalid,
}: {
  proposal: WorkflowProposal;
  token: string;
  t: (key: StringKey) => string;
  onSessionInvalid: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("pending");
  const [rows, setRows] = useState<Row[]>(() => proposal.molecules.map(blank));
  const [message, setMessage] = useState<string | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const stop = useRef<(() => void) | null>(null);
  const finished = useRef(false);

  useEffect(() => () => { stop.current?.(); }, []);

  const update = (index: number, patch: Partial<Row>) =>
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));

  const fail = useCallback((err: unknown) => {
    if (err instanceof ApiError && err.status === 401) onSessionInvalid();
    else if (err instanceof ApiError && err.status === 404) setProblem(t("iteration.expired"));
    else if (err instanceof ApiError) setProblem(err.message);
    else setProblem(t("iteration.unreachable"));
    setPhase((current) => (current === "running" && !finished.current ? "interrupted" : "pending"));
  }, [onSessionInvalid, t]);

  const relay = useCallback((event: Record<string, unknown>) => {
    const id = event["request_id"];
    if (typeof id !== "string") return;
    const name = event["case_name"];
    const report = (promise: Promise<unknown>) => void promise.catch(() => setProblem(t("iteration.unreachable")));
    if (event["type"] === "case_create" && typeof event["name"] === "string") {
      report(createCaseInHost(id, event["name"]).then((r) => api.reportCaseResult(token, id, r)));
    } else if (event["type"] === "case_smiles" && typeof name === "string" && typeof event["smiles"] === "string") {
      report(loadSmilesInHost(id, name, event["smiles"]).then((r) => api.reportSmilesResult(token, id, r)));
    } else if (event["type"] === "case_receptor" && typeof name === "string" && typeof event["pdb_id"] === "string") {
      report(assignReceptorInHost(id, name, event["pdb_id"]).then((r) => api.reportReceptorResult(token, id, r)));
    } else if (event["type"] === "case_evaluation" && typeof name === "string") {
      report(evaluateCaseInHost(id, name).then((r) => api.reportEvaluationResult(token, id, r)));
    } else if (event["type"] === "case_status" && typeof name === "string") {
      report(caseStatusInHost(id, name).then((r) => api.reportCaseStatusResult(token, id, r)));
    } else if (event["type"] === "case_preparation" && typeof name === "string" && typeof event["task_id"] === "string") {
      report(auditPreparationInHost(id, name, event["task_id"]).then((r) => api.reportPreparationResult(token, id, r)));
    }
  }, [token, t]);

  const onEvent = useCallback((event: Record<string, unknown>) => {
    if (event["type"] !== "workflow") { relay(event); return; }
    const kind = event["event"];
    if (kind === "molecule_started" && typeof event["index"] === "number") {
      update(event["index"] - 1, { status: "running" });
    } else if (kind === "molecule" && typeof event["record"] === "object" && event["record"]) {
      const record = event["record"] as Record<string, unknown>;
      if (typeof record["index"] === "number") {
        update(record["index"] - 1, { status: text(record["status"]) ?? "unknown", outcome: text(record["outcome"]),
          vina: num(record["affinity_kcal"]), physical: text(record["physical_status"]), reason: text(record["reason"]) });
      }
    } else if (kind === "phase") {
      setMessage(text(event["message"]));
    } else if (kind === "done") {
      finished.current = true;
      const result = summaryOf(event["summary"]);
      setSummary(result);
      setMessage(null);
      setPhase(result && (result.state === "interrupted" || result.state === "failed") ? "interrupted" : "done");
    }
  }, [relay]);

  const approve = () => {
    setProblem(null);
    setPhase("running");
    finished.current = false;
    stop.current = runWorkflow(token, proposal.id, proposal.digest, onEvent, fail);
  };

  const cancel = async () => {
    setProblem(null);
    try {
      const result = await api.cancelWorkflow(token, proposal.id);
      if (result.state === "cancelled") setPhase("cancelled");
    } catch (err) { fail(err); }
  };

  const download = async (name: string) => {
    try {
      const blob = await api.workflowFile(token, proposal.id, name);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = name;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch { setProblem(t("iteration.downloadFailed")); }
  };

  const label = (row: Row) => (row.outcome ? t(`iteration.reading.${row.outcome}` as StringKey) : t(`iteration.state.${row.status}` as StringKey));
  const files = summary ? Object.keys(summary.files) : [];
  return (
    <div className="action-card iteration-card" role="group" aria-label={t("iteration.group")} data-phase={phase}>
      <p className="action-title"><strong>{proposal.title}</strong></p>
      {phase === "pending" && <ul>{proposal.lines.map((line, index) => <li key={index}>{line}</li>)}</ul>}
      {phase !== "pending" && phase !== "cancelled" && (
        <table className="iteration-table">
          <thead><tr><th>{t("iteration.colMolecule")}</th><th>{t("iteration.colState")}</th><th>{t("iteration.colVina")}</th><th>{t("iteration.colControls")}</th></tr></thead>
          <tbody>
            {proposal.molecules.map((name, index) => (
              <tr key={index} data-outcome={rows[index].outcome ?? rows[index].status} title={rows[index].reason ?? undefined}>
                <td>{name}</td><td>{label(rows[index])}</td>
                <td>{rows[index].vina === null ? "—" : rows[index].vina}</td><td>{rows[index].physical ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {phase === "pending" && (
        <>
          <p className="muted">{t("iteration.pending")}</p>
          <div className="action-buttons">
            <button type="button" onClick={approve}>{t("iteration.approve")}</button>
            <button type="button" onClick={() => void cancel()}>{t("iteration.cancel")}</button>
          </div>
        </>
      )}
      {phase === "running" && <p role="status" className="muted">{message ?? t("iteration.running")}</p>}
      {phase === "cancelled" && <p className="muted">{t("iteration.cancelled")}</p>}
      {phase === "interrupted" && <p role="alert" className="error">{t("iteration.interrupted")}</p>}
      {summary && (phase === "done" || phase === "interrupted") && (
        <div className="iteration-summary" role="status">
          <p><strong>{t("iteration.done")}</strong></p>
          {summary.selected ? (
            <ul>
              <li>{t("iteration.selected")}: {summary.selected.name} · Vina {summary.selected.vina_kcal_mol ?? "—"} kcal/mol · {summary.selected.physical_status ?? "—"}</li>
              {summary.saved && <li>{t("iteration.saved")}: {summary.saved}</li>}
              {summary.video && <li>{t("iteration.video")}: {summary.video}</li>}
              {summary.preparation && <li>{t("iteration.preparation")}: {summary.preparation}</li>}
            </ul>
          ) : summary.state !== "interrupted" && summary.state !== "failed" ? <p>{t("iteration.noneQualified")}</p> : null}
          {summary.notes.length > 0 && <ul>{summary.notes.map((note, index) => <li key={index} className="muted">{note}</li>)}</ul>}
          <div className="action-buttons">
            {files.includes("cuaderno.pdf") && <button type="button" onClick={() => void download("cuaderno.pdf")}>{t("iteration.notebook")}</button>}
            {files.includes("cuaderno.md") && !files.includes("cuaderno.pdf") && <button type="button" onClick={() => void download("cuaderno.md")}>{t("iteration.notebookMd")}</button>}
            {files.includes("entrega.zip") && <button type="button" onClick={() => void download("entrega.zip")}>{t("iteration.deliverable")}</button>}
          </div>
          {summary.paths["entrega.zip"] && <p className="muted">{t("iteration.savedAt")}: {summary.paths["entrega.zip"]}</p>}
        </div>
      )}
      {problem && <p role="alert" className="error">{problem}</p>}
    </div>
  );
}
