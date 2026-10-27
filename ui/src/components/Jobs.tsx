import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, openEventStream } from "../lib/api";
import { linksForReport, postToHost } from "../lib/deeplinks";
import type { StringKey } from "../lib/i18n";

interface ExecutionView {
  id: string;
  digest: string;
  state: string;
  report: Record<string, unknown> | null;
}

const TERMINAL = new Set([
  "completed",
  "failed",
  "blocked",
  "awaiting_approval",
  "ambiguous",
  "cancelled",
]);

export default function Jobs({
  token,
  t,
  focusId,
  onSessionInvalid,
}: {
  token: string;
  t: (key: StringKey) => string;
  focusId: string | null;
  onSessionInvalid: () => void;
}) {
  const [ids, setIds] = useState<string[]>([]);
  const [views, setViews] = useState<Record<string, ExecutionView>>({});
  const [error, setError] = useState<string | null>(null);
  const [hostNote, setHostNote] = useState(false);
  const aborters = useRef<Record<string, () => void>>({});

  useEffect(() => {
    if (focusId) setIds((prev) => (prev.includes(focusId) ? prev : [focusId, ...prev]));
  }, [focusId]);

  useEffect(() => () => Object.values(aborters.current).forEach((stop) => stop()), []);

  const watch = useCallback(
    (id: string) => {
      aborters.current[id]?.();
      const stop = openEventStream(
        token,
        `/v1/executions/${id}/events`,
        (event) => {
          const view = event as unknown as ExecutionView;
          setViews((prev) => ({ ...prev, [id]: view }));
          if (TERMINAL.has(view.state)) {
            aborters.current[id]?.();
            delete aborters.current[id];
          }
        },
        (err) => {
          if (err instanceof ApiError && err.status === 401) onSessionInvalid();
          else setError(err.message || t("error.generic"));
        },
      );
      aborters.current[id] = stop;
    },
    [token, t, onSessionInvalid],
  );

  useEffect(() => {
    for (const id of ids) {
      if (!views[id] && !aborters.current[id]) {
        void api
          .getExecution(token, id)
          .then((view) => {
            setViews((prev) => ({ ...prev, [id]: view }));
            if (!TERMINAL.has(view.state)) watch(id);
          })
          .catch((err: unknown) => {
            if (err instanceof ApiError && err.status === 401) onSessionInvalid();
            else setError(t("error.generic"));
          });
      }
    }
  }, [ids, views, token, watch, t, onSessionInvalid]);

  const cancel = async (id: string) => {
    try {
      await api.cancelExecution(token, id);
      watch(id); // re-watch: the stream lands "cancelled" with the report
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onSessionInvalid();
      else setError(err instanceof Error ? err.message : t("error.generic"));
    }
  };

  if (ids.length === 0) return <p className="muted">{t("jobs.empty")}</p>;

  return (
    <section className="jobs">
      <h2>{t("nav.jobs")}</h2>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {hostNote && <p className="muted">{t("jobs.unhosted")}</p>}
      {ids.map((id) => {
        const view = views[id];
        if (!view) return null;
        const outcomes = Array.isArray(view.report?.["outcomes"])
          ? (view.report?.["outcomes"] as Record<string, unknown>[])
          : [];
        return (
          <article key={id} className="job-card">
            <p>
              <strong>{id}</strong> · {t("jobs.state")}: <strong>{view.state}</strong>
            </p>
            <p className="muted">
              <span className="digest">{view.digest}</span>
            </p>
            {!TERMINAL.has(view.state) && (
              <p>
                <button onClick={() => void cancel(id)}>{t("jobs.cancel")}</button>
              </p>
            )}
            {outcomes.length > 0 && (
              <>
                <h3>{t("jobs.report")}</h3>
                <ol>
                  {outcomes.map((outcome, index) => (
                    <li key={index}>
                      <strong>{String(outcome["id"])}</strong>{" "}
                      {String(outcome["capability"])} · {String(outcome["state"])}
                      {typeof outcome["error"] === "string" && outcome["error"] && (
                        <span className="error"> · {outcome["error"]}</span>
                      )}
                      {typeof outcome["result_sha256"] === "string" && (
                        <div className="muted digest">{outcome["result_sha256"]}</div>
                      )}
                    </li>
                  ))}
                </ol>
                {linksForReport(view.report).map((link, index) => (
                  <button
                    key={index}
                    onClick={() => {
                      if (!postToHost(link)) setHostNote(true);
                    }}
                  >
                    {link.kind} ↗
                  </button>
                ))}
              </>
            )}
          </article>
        );
      })}
    </section>
  );
}
