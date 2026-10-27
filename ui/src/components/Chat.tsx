import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  api,
  openChatStream,
  type ConversationSummary,
  type Evidence,
  type TurnResult,
} from "../lib/api";
import type { StringKey } from "../lib/i18n";
import EvidenceBlock from "./EvidenceBlock";

interface Message {
  role: "user" | "assistant";
  content: string;
  evidence: Evidence[];
  meta: string;
}

export default function Chat({
  token,
  t,
  onSessionInvalid,
}: {
  token: string;
  t: (key: StringKey) => string;
  onSessionInvalid: () => void;
}) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastText, setLastText] = useState<string | null>(null);
  const aborter = useRef<(() => void) | null>(null);
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
      try {
        const detail = await api.getConversation(token, id);
        setMessages(
          detail.messages.map((m) => ({
            role: m.role === "assistant" ? "assistant" : "user",
            content: m.content,
            evidence: [],
            meta: "",
          })),
        );
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) onSessionInvalid();
        else setError(t("error.generic"));
      }
    },
    [token, t, onSessionInvalid],
  );

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
            void refreshList();
          } else if (kind === "intent") {
            setStatus(t("chat.streaming"));
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
      <aside className="chat-side">
        <button
          onClick={() => {
            aborter.current?.();
            setActiveId(null);
            setMessages([]);
            setError(null);
            setStatus(null);
          }}
        >
          {t("chat.new")}
        </button>
        <ul>
          {conversations.map((conv) => (
            <li key={conv.id}>
              <button
                className={conv.id === activeId ? "active" : ""}
                onClick={() => void select(conv.id)}
              >
                {conv.summary || conv.id.slice(0, 8)} ({conv.message_count})
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <section className="chat-main">
        <ol className="messages" aria-live="polite">
          {messages.length === 0 && !streaming && (
            <li className="muted">{t("chat.empty")}</li>
          )}
          {messages.map((message, index) => (
            <li key={index} className={`message ${message.role}`}>
              <p className="message-who">
                {message.role === "user" ? t("chat.you") : t("chat.molchat")}
                {message.meta && <span className="muted"> · {message.meta}</span>}
              </p>
              {message.evidence.length > 0 ? (
                <>
                  <details open>
                    <summary>{t("chat.evidence")}</summary>
                    {message.evidence.map((item, i) => (
                      <EvidenceBlock key={i} evidence={item} />
                    ))}
                  </details>
                  <p className="message-text">{message.content}</p>
                </>
              ) : (
                <p className="message-text">{message.content}</p>
              )}
            </li>
          ))}
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
              <button onClick={() => send(lastText)}>{t("chat.retry")}</button>
            )}
          </p>
        )}
        <form
          className="chat-input"
          onSubmit={(event) => {
            event.preventDefault();
            send(input);
          }}
        >
          <label>
            <span className="visually-hidden">{t("chat.input")}</span>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder={t("chat.input")}
              disabled={streaming}
            />
          </label>
          <button type="submit" disabled={streaming || !input.trim()}>
            {t("chat.send")}
          </button>
        </form>
      </section>
    </div>
  );
}
