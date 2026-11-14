import { useState } from "react";
import type { Element, Interval, ProofObject } from "../types";
import { bboxOf, polygonToPoints } from "../geometry";
import { UncertaintyBand } from "./UncertaintyBand";

type Method = "tap" | "type";

/** What the user told us: one door and its real width. The engine turns px_length / length_m into px per m. */
export interface ScaleAnswer {
  method: Method;
  element_id: string;
  px_length: number;
  length_m: number;
}

/** Door length in drawing units: the long side of its bounding box. */
export function doorLength(d: Element): number {
  const b = bboxOf([d], 0);
  return Math.max(b.width, b.height);
}

export interface ScaleAskProps {
  proof: ProofObject;
  doors: Element[];
  axis: Interval;
  onAnswer: (a: ScaleAnswer) => void;
  busy?: boolean;
  onClose: () => void;
}

export function ScaleAsk({ proof, doors, axis, onAnswer, onClose, busy = false }: ScaleAskProps) {
  const [method, setMethod] = useState<Method>("tap");
  const [sel, setSel] = useState<string | null>(null);
  const [metres, setMetres] = useState("0.9");
  const b = bboxOf(doors, 20);
  const ans = (method: Method, m: number) => {
    const d = doors.find((x) => x.id === sel);
    if (d) onAnswer({ method, element_id: d.id, px_length: doorLength(d), length_m: m });
  };
  const picker = (
    <svg viewBox={`${b.minX} ${b.minY} ${b.width} ${b.height}`} preserveAspectRatio="xMidYMid meet">
              {doors.map((d) => (
                <g key={d.id} className={`hit ${sel === d.id ? "hit--sel" : ""}`} tabIndex={0} role="button" aria-label={`door ${d.id}`} onClick={() => setSel(d.id)} onKeyDown={(e) => e.key === "Enter" && setSel(d.id)}>
                  <polygon points={polygonToPoints(d.polygon)} style={{ fill: sel === d.id ? "#7dd3fc" : "rgba(196,181,253,.3)", stroke: sel === d.id ? "#7dd3fc" : "#c4b5fd", strokeWidth: 2 }} />
                </g>
              ))}
            </svg>
  );
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Scale question" onClick={(e) => e.stopPropagation()}>
        <div className="steps" role="tablist">
          {(["tap", "type"] as Method[]).map((m, i) => (
            <span key={m} className={m === method ? "on" : ""} onClick={() => setMethod(m)} role="tab" aria-selected={m === method} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setMethod(m)}>
              {i + 1}. {m === "tap" ? "tap a door" : "type its width"}
            </span>
          ))}
        </div>
        {proof.interval && <UncertaintyBand interval={proof.interval} axis={axis} tier="amber" value={proof.value} unit={proof.unit} />}
        {method === "tap" && (
          <>
            <h3>Tap a door: is this 0.9 m?</h3>
            <p className="q">The cheapest question. One yes pins the scale.</p>
            {picker}
            <div className="btnrow">
              <button className="btn btn--primary" disabled={!sel || busy} onClick={() => sel && ans("tap", 0.9)}>
                Yes, 0.9 m
              </button>
              <button className="btn" onClick={() => setMethod("type")}>
                Not 0.9 m
              </button>
            </div>
          </>
        )}
        {method === "type" && (
          <>
            <h3>Type the width of the door you tapped</h3>
            <p className="q">Any door whose real width you know.</p>
            {picker}
            <div className="btnrow">
              <input aria-label="door width in metres" inputMode="decimal" value={metres} onChange={(e) => setMetres(e.target.value)} className="field" />
              <span>m</span>
              <button className="btn btn--primary" disabled={!sel || busy || !(Number(metres) > 0)} onClick={() => sel && ans("type", Number(metres))}>
                Apply
              </button>
            </div>
          </>
        )}
        <div className="btnrow">
          <button className="btn" onClick={onClose}>
            Not now
          </button>
        </div>
      </div>
    </div>
  );
}
