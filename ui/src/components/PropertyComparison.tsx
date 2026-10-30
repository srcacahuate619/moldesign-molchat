import type { Evidence, PubChemReference } from "../lib/api";
import type { StringKey } from "../lib/i18n";

export default function PropertyComparison({ evidence, reference, t }: {
  evidence: Evidence; reference: PubChemReference; t: (key: StringKey) => string;
}) {
  const structure = evidence.structure!;
  const rows = [
    [t("comparison.weight"), "MolecularWeight", "mw"],
    ["LogP / XLogP", "XLogP", "logp"],
    ["TPSA (Å²)", "TPSA", "tpsa"],
    ["HBD", "HBondDonorCount", "hbd"],
    ["HBA", "HBondAcceptorCount", "hba"],
  ] as const;
  return <section className="comparison" aria-label={t("comparison.title")}>
    <details open>
      <summary>{t("comparison.title")}</summary>
      <p className="muted">{t(structure.identity === "same" ? "comparison.same" : structure.identity === "changed" ? "comparison.changed" : "comparison.unverified")}</p>
      <div className="comparison-scroll"><table>
        <thead><tr><th>{t("comparison.property")}</th><th>PubChem</th><th>MolDesign / RDKit</th></tr></thead>
        <tbody>{rows.map(([label, publicKey, localKey]) => {
          const pub = reference.properties?.[publicKey];
          const local = evidence.values[localKey];
          const different = pub != null && local != null && Number.isFinite(Number(pub)) && Number.isFinite(Number(local)) && Number(pub) !== Number(local);
          return <tr key={localKey} className={different ? "comparison-different" : undefined}>
            <th scope="row">{label}</th><td>{pub ?? "—"}</td><td>{local ?? "—"}</td>
          </tr>;
        })}</tbody>
      </table></div>
      <p className="muted">{t("comparison.difference")}</p>
      <details><summary>{t("comparison.methods")}</summary>
        <p>PubChem: XLogP, TPSA, HBD, HBA · <a href="https://pubchem.ncbi.nlm.nih.gov/docs/glossary" target="_blank" rel="noreferrer">{t("comparison.sourceMethods")}</a></p>
        <p>{t("comparison.pubchemHba")}</p>
        {Object.keys(evidence.methods ?? {}).length ? <dl>{Object.entries(evidence.methods!).map(([key, method]) => <div key={key}><dt>{key.toUpperCase()}</dt><dd>{method}</dd></div>)}</dl> : <p>{t("comparison.unknownMethods")}</p>}
        <p>{t("comparison.hypothesis")}</p>
      </details>
      <details><summary>{t("comparison.structure")}</summary>
        <p>{t("comparison.original")}: <code>{structure.input_smiles}</code></p>
        <p>{t("comparison.canonical")}: <code>{structure.canonical_smiles}</code></p>
        <p>{t("comparison.verifier")}: {structure.verifier ?? t("comparison.unavailable")}</p>
        <p>{t("comparison.processing")}</p>
        {structure.warnings?.map((warning, index) => <p key={index}>{warning}</p>)}
      </details>
    </details>
  </section>;
}
