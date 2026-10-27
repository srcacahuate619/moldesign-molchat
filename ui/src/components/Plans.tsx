import { useMemo, useState } from "react";
import { ApiError, api, type CatalogEntry, type Plan } from "../lib/api";
import type { StringKey } from "../lib/i18n";

export default function Plans({
  token,
  catalog,
  t,
  onSessionInvalid,
  onExecuted,
}: {
  token: string;
  catalog: CatalogEntry[];
  t: (key: StringKey) => string;
  onSessionInvalid: () => void;
  onExecuted: (execId: string) => void;
}) {
  const [goal, setGoal] = useState("");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [digest, setDigest] = useState("");
  const [approved, setApproved] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const risks = useMemo(() => {
    const map = new Map<string, string>();
    for (const entry of catalog) map.set(entry.name, entry.risk);
    return map;
  }, [catalog]);
  const sensitive = useMemo(
    () =>
      (plan?.steps ?? [])
        .filter((step) => (risks.get(step.capability) ?? "read") !== "read")
        .map((step) => step.id),
    [plan, risks],
  );

  const fail = (err: unknown) => {
    if (err instanceof ApiError && err.status === 401) onSessionInvalid();
    else setError(err instanceof Error ? err.message : t("error.generic"));
  };

  const propose = async () => {
    if (!goal.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.proposePlan(token, goal.trim());
      setPlan(result.plan);
      setDigest(result.digest);
      setApproved([]);
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  };

  const execute = async () => {
    if (!plan || busy) return;
    setBusy(true);
    setError(null);
    try {
      const submitted = await api.submitExecution(token, plan, {
        approval_digest: digest,
        approved_steps: approved,
      });
      onExecuted(submitted.id);
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  };

  const toggle = (id: string) =>
    setApproved((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id],
    );

  return (
    <section className="plans">
      <h2>{t("nav.plans")}</h2>
      <form
        className="chat-input"
        onSubmit={(event) => {
          event.preventDefault();
          void propose();
        }}
      >
        <label>
          <span className="visually-hidden">{t("plans.goal")}</span>
          <input
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            placeholder={t("plans.goal")}
            disabled={busy}
          />
        </label>
        <button type="submit" disabled={busy || !goal.trim()}>
          {t("plans.propose")}
        </button>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {plan && (
        <article className="plan-card">
          <p>
            <strong>{plan.goal}</strong>
          </p>
          <p>
            {t("plans.digest")}: <span className="digest">{digest}</span>
          </p>
          <ol>
            {plan.steps.map((step) => (
              <li key={step.id}>
                <strong>{step.id}</strong> {step.capability}{" "}
                <span className="muted">
                  [{t("plans.risk")}: {risks.get(step.capability) ?? "?"}]
                </span>
                <pre className="muted">
                  {JSON.stringify(step.arguments, null, 1)}
                </pre>
                {step.rationale && <p className="muted">{step.rationale}</p>}
              </li>
            ))}
          </ol>
          {sensitive.length === 0 ? (
            <p className="muted">{t("plans.readOnly")}</p>
          ) : (
            <>
              <p>{t("plans.sensitive")}</p>
              <p>{t("plans.approveSteps")}</p>
              {sensitive.map((id) => (
                <label key={id} className="approve-check">
                  <input
                    type="checkbox"
                    checked={approved.includes(id)}
                    onChange={() => toggle(id)}
                  />{" "}
                  {id}
                </label>
              ))}
            </>
          )}
          <p>
            <button onClick={() => void execute()} disabled={busy}>
              {t("plans.execute")}
            </button>
          </p>
        </article>
      )}
    </section>
  );
}
