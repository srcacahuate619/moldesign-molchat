import { useState } from "react";
import type { StringKey } from "../lib/i18n";

export default function Unlock({
  t,
  failed,
  onConnect,
}: {
  t: (key: StringKey) => string;
  failed: boolean;
  onConnect: (token: string) => void;
}) {
  const [value, setValue] = useState("");
  return (
    <main className="unlock">
      <h1>{t("app.title")}</h1>
      <p className="muted">{t("app.subtitle")}</p>
      <h2>{t("unlock.title")}</h2>
      <p className="muted">{t("unlock.help")}</p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (value.trim()) onConnect(value.trim());
        }}
      >
        <label>
          <span className="visually-hidden">{t("unlock.title")}</span>
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            placeholder={t("unlock.placeholder")}
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
        </label>
        <button type="submit" disabled={!value.trim()}>
          {t("unlock.button")}
        </button>
      </form>
      {failed && (
        <p role="alert" className="error">
          {t("unlock.error")}
        </p>
      )}
    </main>
  );
}
