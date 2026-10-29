import type { Locale, StringKey } from "../lib/i18n";

export default function Settings({
  token,
  t,
  locale,
  stt,
  onLocale,
  onRevoke,
}: {
  token: string;
  t: (key: StringKey) => string;
  locale: Locale;
  stt: string;
  onLocale: (locale: Locale) => void;
  onRevoke: () => void;
}) {
  const [pubchem, setPubchem] = useState<{ authorized: boolean; offline: boolean } | null>(null);
  const [permissionError, setPermissionError] = useState(false);
  useEffect(() => {
    let active = true;
    void api.pubchemPermission(token).then((value) => { if (active) setPubchem(value); })
      .catch(() => { if (active) setPermissionError(true); });
    return () => { active = false; };
  }, [token]);
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
      <h3>PubChem</h3>
      <p className="muted">{t("settings.pubchemNote")}</p>
      {pubchem && <>
        <p className="muted">{t(pubchem.offline ? "settings.pubchemOffline" : pubchem.authorized ? "settings.pubchemAllowed" : "settings.pubchemDenied")}</p>
        <button type="button" onClick={() => {
          void api.setPubchemPermission(token, !pubchem.authorized)
            .then((value) => { setPubchem(value); setPermissionError(false); })
            .catch(() => setPermissionError(true));
        }}>{t(pubchem.authorized ? "settings.pubchemRevoke" : "settings.pubchemAllow")}</button>
      </>}
      {permissionError && <p role="alert" className="error">{t("settings.pubchemError")}</p>}
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
import { useEffect, useState } from "react";
import { api } from "../lib/api";
