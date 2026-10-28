import { useCallback, useEffect, useState } from "react";
import { api, type CatalogEntry } from "./lib/api";
import { strings, type Locale, type StringKey } from "./lib/i18n";
import { announceReady, listenForSession } from "./lib/hostSession";
import Chat from "./components/Chat";
import Jobs from "./components/Jobs";
import Plans from "./components/Plans";
import Settings from "./components/Settings";
import Unlock from "./components/Unlock";
import "./styles.css";

const SESSION_KEY = "molchat.session";
const LOCALE_KEY = "molchat.locale";

type Tab = "chat" | "plans" | "jobs" | "settings";

export default function App() {
  const [token, setToken] = useState<string | null>(() =>
    sessionStorage.getItem(SESSION_KEY),
  );
  const [unlockFailed, setUnlockFailed] = useState(false);
  const [catalog, setCatalog] = useState<CatalogEntry[]>([]);
  const [stt, setStt] = useState("none");
  const [focusId, setFocusId] = useState<string | null>(null);
  const [locale, setLocale] = useState<Locale>(() =>
    localStorage.getItem(LOCALE_KEY) === "en" ? "en" : "es",
  );
  const [tab, setTab] = useState<Tab>("chat");
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  const t = useCallback(
    (key: StringKey) => strings(locale)[key],
    [locale],
  );

  const connect = useCallback(async (candidate: string) => {
    try {
      setCatalog(await api.catalog(candidate)); // validates the session, nothing else
      const info = await api.version();
      setStt(typeof info.stt === "string" ? info.stt : "none");
      sessionStorage.setItem(SESSION_KEY, candidate);
      setUnlockFailed(false);
      setToken(candidate);
    } catch {
      setUnlockFailed(true);
    }
  }, []);

  const disconnect = useCallback(async () => {
    if (token) {
      try {
        await api.revoke(token);
      } catch {
        // Session ends locally even if the revoke call fails.
      }
    }
    sessionStorage.removeItem(SESSION_KEY);
    setToken(null);
    setTab("chat");
  }, [token]);

  const sessionInvalid = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY);
    setToken(null);
  }, []);

  // Hosted in MolDesign: announce readiness once; the desktop answers with
  // our session token (loopback postMessage, never URL). Standalone: inert.
  useEffect(() => {
    const unlisten = listenForSession((candidate, hostLocale) => {
      if (hostLocale) {
        localStorage.setItem(LOCALE_KEY, hostLocale);
        setLocale(hostLocale);
      }
      void connect(candidate);
    });
    announceReady();
    return unlisten;
  }, [connect]);

  if (!token) {
    return <Unlock t={t} failed={unlockFailed} onConnect={(v) => void connect(v)} />;
  }
  return (
    <div className="app">
      <header className="app-header">
        <h1>{t("app.title")}</h1>
        <nav>
          <button
            className={tab === "chat" ? "active" : ""}
            onClick={() => setTab("chat")}
          >
            {t("nav.chat")}
          </button>
          <button
            className={tab === "plans" ? "active" : ""}
            onClick={() => setTab("plans")}
          >
            {t("nav.plans")}
          </button>
          <button
            className={tab === "jobs" ? "active" : ""}
            onClick={() => setTab("jobs")}
          >
            {t("nav.jobs")}
          </button>
          <button
            className={tab === "settings" ? "active" : ""}
            onClick={() => setTab("settings")}
          >
            {t("nav.settings")}
          </button>
        </nav>
      </header>
      {tab === "chat" && (
        <Chat token={token} lang={locale} t={t} onSessionInvalid={sessionInvalid} />
      )}
      {tab === "plans" && (
        <Plans
          token={token}
          catalog={catalog}
          t={t}
          onSessionInvalid={sessionInvalid}
          onExecuted={(id) => {
            setFocusId(id);
            setTab("jobs");
          }}
        />
      )}
      {tab === "jobs" && (
        <Jobs
          token={token}
          t={t}
          focusId={focusId}
          onSessionInvalid={sessionInvalid}
        />
      )}
      {tab === "settings" && (
        <Settings
          t={t}
          locale={locale}
          stt={stt}
          onLocale={(next) => {
            localStorage.setItem(LOCALE_KEY, next);
            setLocale(next);
          }}
          onRevoke={() => void disconnect()}
        />
      )}
    </div>
  );
}
