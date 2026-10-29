import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  api,
  openChatStream,
  type ConversationSummary,
  type Evidence,
  type PubChemReference,
  type TurnResult,
} from "../lib/api";
import type { StringKey } from "../lib/i18n";
import EvidenceBlock from "./EvidenceBlock";
import MessageText from "./MessageText";
import PropertyComparison from "./PropertyComparison";
import VoiceButton from "./VoiceButton";
import { createCaseInHost } from "../lib/caseHost";
import { loadSmilesInHost } from "../lib/smilesHost";
import { readEditorInHost } from "../lib/editorHost";
import { BotIcon, HistoryIcon, PlusIcon, SendIcon } from "./Icons";

interface Message {
  role: "user" | "assistant";
  content: string;
  evidence: Evidence[];
  meta: string;
  references?: PubChemReference[];
  selectable?: boolean;
  comparisonCids?: number[];
}

const ACTIVE_CONVERSATION = "molchat.activeConversation";
function rememberConversation(id: string | null) {
  try {
    if (id) sessionStorage.setItem(ACTIVE_CONVERSATION, id);
    else sessionStorage.removeItem(ACTIVE_CONVERSATION);
  } catch { /* Storage may be disabled; chat remains usable. */ }
}

export default function Chat({
  token,
  lang,
  t,
  onSessionInvalid,
}: {
  token: string;
  lang: string;
  t: (key: StringKey) => string;
  onSessionInvalid: () => void;
}) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const activeIdRef = useRef<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastText, setLastText] = useState<string | null>(null);
  const [pendingVoice, setPendingVoice] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const aborter = useRef<(() => void) | null>(null);
  const restored = useRef(false);
  const streaming = status !== null;

  const refreshList = useCallback(async () => {
    try {
      setConversations(await api.listConversations(token));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onSessionInvalid();
    }
  }, [token, onSessionInvalid]);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  useEffect(() => () => aborter.current?.(), []);

  const select = useCallback(
    async (id: string) => {
      aborter.current?.();
      setStatus(null);
      setError(null);
      setActiveId(id);
      activeIdRef.current = id;
      rememberConversation(id);
      try {
        const detail = await api.getConversation(token, id);
        const lastAssistant = detail.messages.reduce((found, m, index) =>
          m.role === "assistant" ? index : found, -1);
        setMessages(
          detail.messages.map((m, index) => ({
            role: m.role === "assistant" ? "assistant" : "user",
            content: m.content,
            evidence: m.evidence ?? [],
            meta: "",
            references: m.references ?? (index === lastAssistant ? detail.pending_references : undefined),
            comparisonCids: m.comparison_cids,
            selectable: index === lastAssistant && (detail.pending_references?.length ?? 0) > 1,
          })),
        );
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) onSessionInvalid();
        else setError(t("error.generic"));
      }
    },
    [token, t, onSessionInvalid],
  );

  useEffect(() => {
    if (restored.current) return;
    restored.current = true;
    try {
      const id = sessionStorage.getItem(ACTIVE_CONVERSATION);
      if (id) void select(id);
    } catch { /* No saved conversation is available. */ }
  }, [select]);

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || streaming) return;
      aborter.current?.();
      setError(null);
      setLastText(trimmed);
      setMessages((prev) => [
        ...prev,
        { role: "user", content: trimmed, evidence: [], meta: "" },
      ]);
      setInput("");
      setStatus(t("chat.thinking"));
      const finish = (updater: (prev: Message[]) => Message[]) => {
        setMessages(updater);
        setStatus(null);
      };
      aborter.current = openChatStream(
        token,
        { text: trimmed, ...(activeId ? { conversation_id: activeId } : {}) },
        (event) => {
          const kind = event["type"] as string;
          if (kind === "conversation") {
            const id = event["id"] as string;
            setActiveId(id);
            activeIdRef.current = id;
            rememberConversation(id);
            void refreshList();
          } else if (kind === "intent") {
            setStatus(t("chat.streaming"));
          } else if (kind === "case_create") {
            const id = event["request_id"];
            const name = event["name"];
            if (typeof id === "string" && typeof name === "string") {
              void createCaseInHost(id, name).then((result) => api.reportCaseResult(token, id, result))
                .catch(() => setError(t("error.generic")));
            }
          } else if (kind === "case_smiles") {
            const id = event["request_id"], name = event["case_name"], smiles = event["smiles"];
            if (typeof id === "string" && typeof name === "string" && typeof smiles === "string") {
              void loadSmilesInHost(id, name, smiles).then((result) => api.reportSmilesResult(token, id, result))
                .catch(() => setError(t("error.generic")));
            }
          } else if (kind === "editor_read") {
            const id = event["request_id"], name = event["case_name"], operation = event["operation"], revision = event["revision"];
            if ([id, name, operation, revision].every((value) => typeof value === "string")) {
              void readEditorInHost(id as string, name as string, operation as string, revision as string)
                .then((result) => api.reportEditorResult(token, id as string, result))
                .catch(() => setError(t("error.generic")));
            }
          } else if (kind === "result") {
            const result = event["result"] as TurnResult;
            const meta = [
              result.used_llm ? t("chat.usedLlm") : t("chat.deterministic"),
              `${result.latency_ms} ms`,
              result.verified_values.length > 0
                ? `${result.verified_values.length} ${t("chat.verified")}`
                : "",
            ]
              .filter(Boolean)
              .join(" · ");
            finish((prev) => [
              ...prev,
              {
                role: "assistant",
                content: result.text,
                evidence: result.evidence,
                meta,
                references: result.references,
                comparisonCids: result.comparison_cids,
                selectable: (result.references?.length ?? 0) > 1,
              },
            ]);
          } else if (kind === "error") {
            finish((prev) => prev);
            setError((event["error"] as string) || t("error.generic"));
          }
        },
        (err) => {
          setStatus(null);
          if (err instanceof ApiError && err.status === 401) onSessionInvalid();
          else setError(err.message || t("error.generic"));
        },
      );
    },
    [token, activeId, streaming, refreshList, t, onSessionInvalid],
  );

  const stop = useCallback(() => {
    aborter.current?.();
    aborter.current = null;
    setStatus(null);
  }, []);

  return (
    <div className="chat">
      <div className="chat-toolbar">
        <button type="button" className="tool-button" onClick={() => setShowHistory(!showHistory)}
          aria-expanded={showHistory} aria-controls="chat-history"
          aria-label={t(showHistory ? "chat.hideHistory" : "chat.showHistory")}>
          <HistoryIcon /><span>{t("chat.history")}</span>
        </button>
        <button
          type="button" className="tool-button"
          onClick={() => {
            aborter.current?.();
            setActiveId(null);
            activeIdRef.current = null;
            rememberConversation(null);
            setMessages([]);
            setError(null);
            setStatus(null);
            setShowHistory(false);
          }}
        >
          <PlusIcon /><span>{t("chat.new")}</span>
        </button>
      </div>
      {showHistory && <aside className="chat-side" id="chat-history" aria-label={t("chat.history")}>
        {conversations.length === 0 && <p className="muted history-empty">{t("chat.historyEmpty")}</p>}
        <ul>
          {conversations.map((conv) => (
            <li key={conv.id}>
              <button
                className={conv.id === activeId ? "active" : ""}
                onClick={() => { void select(conv.id); setShowHistory(false); }}
              >
                {conv.summary || conv.id.slice(0, 8)} ({conv.message_count})
              </button>
            </li>
          ))}
        </ul>
      </aside>}
      <section className="chat-main">
        <ol className="messages" aria-live="polite">
          {messages.length === 0 && !streaming && (
            <li className="chat-empty"><span className="empty-icon"><BotIcon /></span><strong>{t("app.title")}</strong><span>{t("chat.empty")}</span></li>
          )}
          {messages.map((message, index) => {
            const splitAt = message.role === "assistant" && message.content.length > 400
              ? message.content.indexOf("\n\n") : -1;
            const summary = splitAt > 0 && splitAt < 350 ? message.content.slice(0, splitAt) : message.content;
            const remainder = summary !== message.content ? message.content.slice(splitAt + 2) : "";
            const comparisons = message.evidence.flatMap((item) => {
              const reference = message.references?.find((ref) => ref.cid === item.structure?.pubchem_cid);
              return reference && (message.comparisonCids === undefined || message.comparisonCids.includes(reference.cid)) ? [{ item, reference }] : [];
            });
            return (
            <li key={index} className={`message ${message.role}`}>
              <p className="message-who">
                {message.role === "user" ? t("chat.you") : t("chat.molchat")}
                {message.meta && <span className="muted"> · {message.meta}</span>}
              </p>
              {message.evidence.length > 0 ? (
                <>
                  <details>
                    <summary>{t("chat.evidence")}</summary>
                    {message.evidence.map((item, i) => (
                      <EvidenceBlock key={i} evidence={item} />
                    ))}
                  </details>
                  <MessageText text={summary} />
                </>
              ) : (
                message.role === "assistant" ? <MessageText text={summary} /> : <p className="message-text">{message.content}</p>
              )}
              {remainder && <details><summary>{t("chat.moreAnswer")}</summary><MessageText text={remainder} /></details>}
              {comparisons.map(({ item, reference }, i) => <PropertyComparison key={`${reference.cid}-${i}`} evidence={item} reference={reference} t={t} />)}
              {message.references && message.references.length > 0 && (
                <ul>
                  {message.references.map((reference) => (
                    <li key={reference.cid}>
                      <a href={reference.source} target="_blank" rel="noreferrer">{reference.name} · PubChem {reference.cid}</a>{" "}
                      {reference.properties && Object.keys(reference.properties).length > 0 && (
                        <details open={Object.values(reference.properties).filter((value) => String(value).length >= 3 && message.content.includes(String(value))).length < 2}>
                        <summary>{t("chat.pubchemDetails")}</summary>
                        <dl className="pubchem-properties">
                          {([
                            ["MolecularFormula", t("chat.pubchemFormula")],
                            ["MolecularWeight", t("chat.pubchemWeight")],
                            ["IUPACName", t("chat.pubchemIupac")],
                            ["SMILES", t("chat.pubchemSmiles")],
                            ["ConnectivitySMILES", t("chat.pubchemConnectivity")],
                            ["XLogP", t("chat.pubchemXlogp")],
                            ["TPSA", t("chat.pubchemTpsa")],
                            ["HBondDonorCount", t("chat.pubchemDonors")],
                            ["HBondAcceptorCount", t("chat.pubchemAcceptors")],
                          ] as const).map(([key, label]) => reference.properties?.[key] != null &&
                            !(key === "ConnectivitySMILES" && reference.properties?.[key] === reference.properties?.SMILES) && (
                            <div key={key}><dt>{label}</dt><dd>{reference.properties?.[key]}{key === "MolecularWeight" ? " g/mol" : ""}</dd></div>
                          ))}
                        </dl>
                        </details>
                      )}
                      {reference.properties_available === false && <p>{t("chat.pubchemPartial")}</p>}
                      {message.selectable && message.references && message.references.length > 1 && <button type="button" onClick={() => {
                        const id = activeIdRef.current;
                        if (!id) return;
                        void api.selectPubchem(token, id, reference.cid).then((result) => {
                          if (activeIdRef.current !== id) return;
                          setMessages((prev) => [...prev.map((entry) => ({ ...entry, selectable: false })),
                            { role: "assistant", content: result.text, evidence: [], meta: "", references: [reference] }]);
                        }).catch(() => { setLastText(null); setError(t("error.generic")); });
                      }}>{t("chat.selectReference")}</button>}
                    </li>
                  ))}
                </ul>
              )}
              {message.role === "assistant" && message.references?.length === 1 && !message.selectable &&
                typeof message.references[0].properties?.SMILES === "string" && message.references[0].properties.SMILES.length > 0 && (
                <div className="context-actions" role="group" aria-label={t("chat.actions")}>
                  <button type="button" disabled={streaming} onClick={() => {
                    const reference = message.references![0];
                    send(`${t("chat.compareRequest")} ${reference.name} (PubChem CID ${reference.cid}).`);
                  }}>{t("chat.compareWithMolDesign")}</button>
                  <button type="button" disabled={streaming} onClick={() => {
                    const reference = message.references![0];
                    send(`${t("chat.verifyRequest")} PubChem CID ${reference.cid}.`);
                  }}>{t("chat.verifyDrawing")}</button>
                </div>
              )}
            </li>
          ); })}
          {streaming && (
            <li className="muted">
              {status} <button onClick={stop}>{t("chat.stop")}</button>
            </li>
          )}
        </ol>
        {error && (
          <p role="alert" className="error">
            {error}{" "}
            {lastText && (
              <button type="button" onClick={() => send(lastText)}>{t("chat.retry")}</button>
            )}
          </p>
        )}
        {pendingVoice !== null && (
          <div className="plan-card" role="group" aria-label={t("voice.confirm")}>
            <p className="muted">{t("voice.confirm")}</p>
            <p>
              <textarea
                rows={2}
                value={pendingVoice}
                onChange={(event) => setPendingVoice(event.target.value)}
                aria-label={t("voice.confirm")}
              />
            </p>
            <p>
              <button
                type="button"
                onClick={() => {
                  const text = pendingVoice;
                  setPendingVoice(null);
                  send(text);
                }}
                disabled={!pendingVoice.trim() || streaming}
              >
                {t("voice.send")}
              </button>{" "}
              <button type="button" onClick={() => setPendingVoice(null)}>
                {t("voice.discard")}
              </button>
            </p>
          </div>
        )}
        <form
          className="chat-input"
          onSubmit={(event) => {
            event.preventDefault();
            send(input);
          }}
        >
          <VoiceButton
            token={token}
            lang={lang}
            t={t}
            disabled={streaming}
            onTranscript={(text) => setPendingVoice(text)}
            onError={(message) => { setLastText(null); setError(message); }}
          />
          <label>
            <span className="visually-hidden">{t("chat.input")}</span>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder={t("chat.input")}
              disabled={streaming}
            />
          </label>
          <button type="submit" className="send-button" aria-label={t("chat.send")} title={t("chat.send")} disabled={streaming || !input.trim()}>
            <SendIcon /><span className="visually-hidden">{t("chat.send")}</span>
          </button>
        </form>
      </section>
    </div>
  );
}
