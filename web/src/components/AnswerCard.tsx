import type { Effective, Ruling } from "../derive";
import { TIER_ICON, TIER_WORD, chipNumber, disputedIds, fmt, querySentence, unitLabel } from "../derive";
import type { Interval, ProofObject } from "../types";
import { UncertaintyBand } from "./UncertaintyBand";

export interface AnswerCardProps {
  proof: ProofObject;
  eff: Effective;
  ruling: Ruling;
  axis: Interval | null;
  canAsk: boolean;
  onRule: (r: Ruling) => void;
  onHover: (ids: string[]) => void;
  onPin: (id: string | null) => void;
  onAsk: () => void;
}

export function AnswerCard({ proof, eff, ruling, axis, canAsk, onRule, onHover, onPin, onAsk }: AnswerCardProps) {
  const dis = disputedIds(proof);
  const allIds = proof.evidence.map((e) => e.id);
  const c = proof.cost;
  const value = eff.value;
  return (
    <>
      <div className="card" data-testid="answer">
        <p className="q">{proof.question}</p>
        <div className="answer">
          <button
            className="num"
            aria-label={`answer ${value ?? "none"}; show its evidence`}
            onMouseEnter={() => onHover(allIds)}
            onMouseLeave={() => onHover([])}
            onFocus={() => onHover(allIds)}
            onBlur={() => onHover([])}
            onClick={() => onPin(null)}
          >
            {value == null ? "–" : typeof value === "number" ? fmt(value) : value}
          </button>
          <span className="unit">{proof.unit === "count" ? "" : unitLabel(proof.unit)}</span>
          <span className={`tier tier--${eff.tier}`}>
            <span aria-hidden="true">{TIER_ICON[eff.tier]}</span> {TIER_WORD[eff.tier]}
          </span>
        </div>
        {proof.interval && axis && (
          <UncertaintyBand interval={proof.interval} axis={axis} tier={eff.tier} value={proof.value} unit={proof.unit} />
        )}
        <p className="why">{eff.why}</p>
        {proof.query_spec && (
          <>
            <p className="queryline">counted {querySentence(proof.query_spec)}</p>
            <span className="planned">◆ planned by LLM, computed by code</span>
          </>
        )}
        {proof.voters.length > 0 && (
          <div className="voters">
            {proof.voters.map((v) => (
              <button
                key={v.name}
                className="voter"
                onMouseEnter={() => onHover(v.element_ids)}
                onMouseLeave={() => onHover([])}
                onFocus={() => onHover(v.element_ids)}
                onBlur={() => onHover([])}
                onClick={() => onPin(v.element_ids[0] ?? null)}
              >
                <span className="name">{v.name}</span>
                <br />
                <span className="val">{v.value ?? "–"}</span>
                {v.runs.length > 0 && (
                  <span className="dots" aria-label={`runs: ${v.runs.join(", ")}`}>
                    {v.runs.map((r, i) => (
                      <i key={i} className={r === v.value ? "same" : "diff"}>
                        {r}
                      </i>
                    ))}
                  </span>
                )}
                {v.note && <span className="note">{v.note}</span>}
              </button>
            ))}
          </div>
        )}
        <p className="costline">
          {c.ms.toFixed(0)} ms · {c.tokens_in + c.tokens_out} tokens · ${c.usd.toFixed(2)}
        </p>
      </div>

      {dis.length > 0 && (
        <div className={`duel ${ruling ? "duel--ok" : ""}`} role="group" aria-label="resolve disagreement">
          <h4>▲ Item {dis.map((d) => chipNumber(proof, d)).join(", ")} is disputed</h4>
          {ruling ? (
            <p>
              Settled: {ruling === "yes" ? "counted as a door" : "not counted"}.{" "}
              <button className="btn" onClick={() => onRule(null)}>
                undo
              </button>
            </p>
          ) : (
            <>
              <p>Is this a door? The two readers never saw each other's answer.</p>
              <div className="btnrow">
                <button className="btn btn--primary" onClick={() => onRule("yes")} onMouseEnter={() => onHover(dis)} onMouseLeave={() => onHover([])}>
                  Yes, a door
                </button>
                <button className="btn" onClick={() => onRule("no")}>
                  No
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {canAsk && (
        <div className="duel">
          <h4>▲ Range is wide</h4>
          <p>One cheap question narrows it.</p>
          <div className="btnrow">
            <button className="btn btn--primary" onClick={onAsk}>
              Narrow the range
            </button>
          </div>
        </div>
      )}
    </>
  );
}
