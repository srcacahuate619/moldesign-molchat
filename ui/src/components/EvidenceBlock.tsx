import type { Evidence } from "../lib/api";

export default function EvidenceBlock({ evidence }: { evidence: Evidence }) {
  return (
    <section className="evidence" aria-label="evidence" data-testid="evidence-block">
      <header>
        <strong>{evidence.tool}</strong>
        <span className="evidence-label">{evidence.label}</span>
      </header>
      <p className="evidence-class">{evidence.epistemic_class}</p>
      <p className="muted evidence-source">{evidence.source}</p>
      {evidence.error ? (
        <p role="alert" className="error">
          {evidence.error}
        </p>
      ) : (
        <dl>
          {Object.entries(evidence.values).map(([key, value]) => (
            <div key={key} className="evidence-row">
              <dt>{key}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
