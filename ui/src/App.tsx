import { useCallback, useState } from "react";
import { api } from "./lib/api";
import { strings, type Locale, type StringKey } from "./lib/i18n";
import Chat from "./components/Chat";
import Settings from "./components/Settings";
import Unlock from "./components/Unlock";
import "./styles.css";

const SESSION_KEY = "molchat.session";
const LOCALE_KEY = "molchat.locale";

type Tab = "chat" | "settings";

export default function App() {
  const [token, setToken] = useState<string | null>(() =>
    sessionStorage.getItem(SESSION_KEY),
  );
  const [unlockFailed, setUnlockFailed] = useState(false);
  const [locale, setLocale] = useState<Locale>(() =>
    localStorage.getItem(LOCALE_KEY) === "en" ? "en" : "es",
  );
  const [tab, setTab] = useState<Tab>("chat");
  const t = useCallback(
    (key: StringKey) => strings(locale)[key],
    [locale],
  );

  const connect = useCallback(async (candidate: string) => {
    try {
      await api.catalog(candidate); // validates the session, nothing else
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
            className={tab === "settings" ? "active" : ""}
            onClick={() => setTab("settings")}
          >
            {t("nav.settings")}
          </button>
        </nav>
      </header>
      {tab === "chat" ? (
        <Chat token={token} t={t} onSessionInvalid={sessionInvalid} />
      ) : (
        <Settings
          t={t}
          locale={locale}
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
