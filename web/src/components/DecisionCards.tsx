import { topDecisions } from "../derive";
import type { Interval, ProofObject, Scalar } from "../types";
import { UncertaintyBand } from "./UncertaintyBand";

export const VIBES = ["Budget", "Standard", "Premium", "Nordic"];

export interface DecisionCardsProps {
  proof: ProofObject;
  chosen: Record<string, Scalar>;
  vibe: string | null;
  axis: Interval | null;
  onChoose: (key: string, v: Scalar) => void;
  onVibe: (v: string | null) => void;
}

export function DecisionCards({ proof, chosen, vibe, axis, onChoose, onVibe }: DecisionCardsProps) {
  const decs = topDecisions(proof);
  const maxImpact = Math.max(...decs.map((d) => d.impact), 0.0001);
  return (
    <>
      {proof.interval && axis && (
        <div className="card">
          <p className="sect">Uncertainty band</p>
          <UncertaintyBand interval={proof.interval} axis={axis} tier={proof.tier} value={proof.value} unit={proof.unit} />
        </div>
      )}
      <p className="sect">Decide before ordering</p>
      {decs.length === 0 && <p className="why">Nothing open. Every input is drawn, specified or chosen.</p>}
      {decs.map((d) => (
        <section key={d.key} className="card dec" data-testid="decision">
          <h4>{d.question}</h4>
          <div className="impact" aria-hidden="true">
            <i style={{ width: `${(d.impact / maxImpact) * 100}%` }} />
          </div>
          <p className="impactlab">
            {d.impact > 0 ? `impact ${d.impact.toFixed(2)}` : "no measured impact on this answer yet"}
            {d.decide_by ? ` · decide by ${d.decide_by}` : ""}
          </p>
          <div className="chips">
            {d.options.map((o) => (
              <button
                key={String(o.value)}
                className="optchip"
                aria-pressed={chosen[d.key] === o.value}
                aria-disabled={!o.fits}
                title={o.note ?? undefined}
                onClick={() => o.fits && onChoose(d.key, o.value)}
              >
                {o.label}
                {!o.fits && <span className="optnote">✕ doesn't fit: {o.note}</span>}
                {o.fits && o.total_delta != null && (
                  <span className="optnote">
                    {o.total_delta > 0 ? "+" : ""}
                    {o.total_delta}
                  </span>
                )}
              </button>
            ))}
          </div>
        </section>
      ))}
      <p className="sect">Or choose a vibe</p>
      <div className="chips">
        {VIBES.map((v) => (
          <button key={v} className="optchip" aria-pressed={vibe === v} onClick={() => onVibe(vibe === v ? null : v)}>
            {v}
          </button>
        ))}
      </div>
    </>
  );
}
