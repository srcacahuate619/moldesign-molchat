import type { Locale, StringKey } from "../lib/i18n";

export default function Settings({
  t,
  locale,
  stt,
  onLocale,
  onRevoke,
}: {
  t: (key: StringKey) => string;
  locale: Locale;
  stt: string;
  onLocale: (locale: Locale) => void;
  onRevoke: () => void;
}) {
  const sttNote =
    stt === "platform"
      ? t("settings.sttPlatform")
      : stt === "cloud"
      ? t("settings.sttCloud")
      : stt === "local"
        ? t("settings.sttLocal")
        : t("settings.sttNone");
  return (
    <section className="settings">
      <h2>{t("nav.settings")}</h2>
      <label>
        {t("settings.language")}{" "}
        <select
          value={locale}
          onChange={(event) => onLocale(event.target.value as Locale)}
        >
          <option value="es">Español</option>
          <option value="en">English</option>
        </select>
      </label>
      <h3>{t("settings.data")}</h3>
      <p className="muted">{t("settings.dataNote")}</p>
      <h3>{t("settings.consents")}</h3>
      <p className="muted">{t("settings.consentsNote")}</p>
      <h3>{t("settings.stt")}</h3>
      {stt === "cloud" ? (
        <p role="alert" className="error">
          {sttNote}
        </p>
      ) : (
        <p className="muted">{sttNote}</p>
      )}
      <h3>{t("settings.session")}</h3>
      <button onClick={onRevoke}>{t("settings.revoke")}</button>
    </section>
  );
}
