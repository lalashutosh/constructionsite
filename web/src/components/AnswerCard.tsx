import type { Effective, Ruling } from "../derive";
import { TIER_ICON, TIER_WORD, anchorWeight, calibrationSentence, chipNumber, disputedIds, fmt, querySentence, refusalWords, unitLabel } from "../derive";
import type { Interval, ProofObject } from "../types";
import { UncertaintyBand } from "./UncertaintyBand";
import { useState } from "react";

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
  claims?: Record<string, unknown> | null;
  /** The disputed element the Yes/No card is about (pinned one, else the first). */
  focus?: string | null;
  /** Live mode: a verdict has been recorded with the engine and the proof is already recomputed. */
  settled?: boolean;
  busy?: boolean;
  sheetType?: string | null;
  onUndo?: () => void;
}

export function AnswerCard({ proof, eff, ruling, axis, canAsk, onRule, onHover, onPin, onAsk, claims = null, focus = null, settled = false, busy = false, sheetType = null, onUndo }: AnswerCardProps) {
  const [how, setHow] = useState(false);
  const dis = disputedIds(proof);
  const allIds = proof.evidence.map((e) => e.id);
  const c = proof.cost;
  const value = eff.value;
  const focusId = focus && dis.includes(focus) ? focus : dis[0];
  const isSettled = Boolean(ruling) || (settled && dis.length === 0);
  const calib = calibrationSentence(eff.tier, claims);
  const histNote = proof.notes.find((n) => n.toLowerCase().startsWith("historically"));
  if (proof.tier === "grey") {
    const w = refusalWords(proof, sheetType);
    return (
      <div className="card card--grey" data-testid="answer">
        <p className="q">{proof.question}</p>
        <div className="answer">
          <span className="nonum" aria-label="no number">no number</span>
          <span className="tier tier--grey">
            <span aria-hidden="true">{TIER_ICON.grey}</span> {TIER_WORD.grey}
          </span>
        </div>
        <p className="why">{w.reason}</p>
        <div className="fix">
          <b>What would make it answerable</b>
          <p>{w.fix}</p>
        </div>
        <RunStrip proof={proof} />
        {(calib || histNote) && (
          <p className="calib" data-testid="calibration">
            {calib ?? histNote}
            {calib && histNote ? <span className="calib-sub">{histNote}</span> : null}
          </p>
        )}
        <p className="costline">
          {c.ms.toFixed(0)} ms · {c.tokens_in + c.tokens_out} tokens · ${c.usd.toFixed(2)} · it would rather say "I can't" than guess
        </p>
      </div>
    );
  }
  return (
    <>
      <div className="card" data-testid="answer">
        <p className="q">{proof.question}</p>
        <div className="answer">
          <button
            key={String(value)}
            className="num num--flash"
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

      {(dis.length > 0 || isSettled) && (
        <div className={`duel ${isSettled ? "duel--ok" : ""}`} role="group" aria-label="resolve disagreement">
          {isSettled ? (
            <>
              <h4>✓ Settled by you</h4>
              <p>
                {ruling ? (ruling === "yes" ? "Counted as a door." : "Not counted.") : "Your verdict is on the receipt as a chosen line."}{" "}
                <button className="btn" onClick={onUndo} disabled={busy}>
                  undo
                </button>
              </p>
            </>
          ) : (
            <>
              <h4>
                ▲ Item {chipNumber(proof, focusId)} is disputed{dis.length > 1 ? ` (1 of ${dis.length})` : ""}
              </h4>
              <p>Is this a door? The two readers never saw each other's answer.</p>
              <div className="btnrow">
                <button className="btn btn--primary" disabled={busy} onClick={() => onRule("yes")} onMouseEnter={() => onHover([focusId])} onMouseLeave={() => onHover([])}>
                  Yes, a door
                </button>
                <button className="btn" disabled={busy} onClick={() => onRule("no")} onMouseEnter={() => onHover([focusId])} onMouseLeave={() => onHover([])}>
                  No
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {proof.kind === "area" && proof.scale && proof.scale.anchors.length > 0 && (
        <div className="how">
          <button className="btn" aria-expanded={how} onClick={() => setHow((v) => !v)}>
            {how ? "Hide" : "Show"} how this was computed
          </button>
          {how && (
            <div className="how-body" data-testid="how">
              <p>
                Area = polygon area in pixels ÷ (px per m)². The scale is the weighted mean of the anchors below, each weighted 1 / σ² (σ is its relative uncertainty).
              </p>
              <table>
                <thead>
                  <tr>
                    <th>anchor</th>
                    <th>px/m</th>
                    <th>σ</th>
                    <th>weight</th>
                  </tr>
                </thead>
                <tbody>
                  {proof.scale.anchors.map((a, i) => (
                    <tr key={i}>
                      <td>
                        {a.kind.replace(/_/g, " ")} <i>{a.tag}</i>
                      </td>
                      <td>{a.px_per_m.toFixed(1)}</td>
                      <td>{(a.rel_sigma * 100).toFixed(1)}%</td>
                      <td>{anchorWeight(a.rel_sigma).toFixed(0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {proof.scale.px_per_m != null && (
                <p>
                  Combined: {proof.scale.px_per_m.toFixed(1)} px/m{proof.scale.rel_sigma != null ? ` ± ${(proof.scale.rel_sigma * 100).toFixed(1)}%` : ""}
                  {proof.scale.widths_relative ? " · widths are relative (door prior only)" : ""}
                </p>
              )}
            </div>
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

/** Test-time augmentation strip: the per-run values of every reader as dots; the spread is the uncertainty. */
export function RunStrip({ proof }: { proof: ProofObject }) {
  const rows = proof.voters
    .map((v) => ({ name: v.name, vals: v.runs.length > 0 ? v.runs : v.value != null ? [v.value] : [] }))
    .filter((r) => r.vals.length > 0);
  if (rows.length === 0) return null;
  const nums = rows.flatMap((r) => r.vals).filter((x): x is number => typeof x === "number");
  if (nums.length === 0) return null;
  const lo = Math.min(...nums);
  const hi = Math.max(...nums);
  const span = hi - lo;
  const pos = (v: number) => (span === 0 ? 50 : 8 + ((v - lo) / span) * 84);
  return (
    <div className="runs" data-testid="runs" aria-label={`values from each reader and run: ${lo} to ${hi}`}>
      <span className="runs-title">
        Spread across runs and readers: {span === 0 ? `all ${lo}` : `${lo} to ${hi}`}
      </span>
      {rows.map((r) => (
        <div key={r.name} className="runs-row">
          <span className="runs-name">{r.name.replace(/_/g, " ")}</span>
          <span className="runs-axis">
            {r.vals.map((v, i) => (typeof v === "number" ? <i key={i} style={{ left: `${pos(v)}%` }} title={String(v)} /> : null))}
          </span>
          <span className="runs-n">{r.vals.length > 1 ? `${r.vals.length} runs` : "1 value"}</span>
        </div>
      ))}
    </div>
  );
}
