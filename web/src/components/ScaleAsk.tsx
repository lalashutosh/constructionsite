import { useState } from "react";
import type { Element, Interval, ProofObject } from "../types";
import { bboxOf, polygonToPoints } from "../geometry";
import { UncertaintyBand } from "./UncertaintyBand";

type Method = "tap" | "line" | "type";

export interface ScaleAskProps {
  proof: ProofObject;
  doors: Element[];
  axis: Interval;
  onAnswer: (method: Method, detail: string) => void;
  onClose: () => void;
}

export function ScaleAsk({ proof, doors, axis, onAnswer, onClose }: ScaleAskProps) {
  const [method, setMethod] = useState<Method>("tap");
  const [sel, setSel] = useState<string | null>(null);
  const [ratio, setRatio] = useState("1:100");
  const b = bboxOf(doors, 20);
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label="Scale question" onClick={(e) => e.stopPropagation()}>
        <div className="steps" role="tablist">
          {(["tap", "line", "type"] as Method[]).map((m, i) => (
            <span key={m} className={m === method ? "on" : ""} onClick={() => setMethod(m)} role="tab" aria-selected={m === method} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setMethod(m)}>
              {i + 1}. {m === "tap" ? "tap a door" : m === "line" ? "draw a line" : "type the scale"}
            </span>
          ))}
        </div>
        {proof.interval && <UncertaintyBand interval={proof.interval} axis={axis} tier="amber" value={proof.value} unit={proof.unit} />}
        {method === "tap" && (
          <>
            <h3>Tap a door: is this 0.9 m?</h3>
            <p className="q">The cheapest question. One yes pins the scale.</p>
            <svg viewBox={`${b.minX} ${b.minY} ${b.width} ${b.height}`} preserveAspectRatio="xMidYMid meet">
              {doors.map((d) => (
                <g key={d.id} className={`hit ${sel === d.id ? "hit--sel" : ""}`} tabIndex={0} role="button" aria-label={`door ${d.id}`} onClick={() => setSel(d.id)} onKeyDown={(e) => e.key === "Enter" && setSel(d.id)}>
                  <polygon points={polygonToPoints(d.polygon)} style={{ fill: sel === d.id ? "#7dd3fc" : "rgba(196,181,253,.3)", stroke: sel === d.id ? "#7dd3fc" : "#c4b5fd", strokeWidth: 2 }} />
                </g>
              ))}
            </svg>
            <div className="btnrow">
              <button className="btn btn--primary" disabled={!sel} onClick={() => onAnswer("tap", `door ${sel} = 0.9 m`)}>
                Yes, 0.9 m
              </button>
              <button className="btn" onClick={() => setMethod("line")}>
                Not sure
              </button>
            </div>
          </>
        )}
        {method === "line" && (
          <>
            <h3>Draw a line over a known length</h3>
            <p className="q">Drag across any wall or opening whose length you know, then type it.</p>
            <div className="btnrow">
              <button className="btn btn--primary" onClick={() => onAnswer("line", "drawn line")}>
                Use a drawn line
              </button>
              <button className="btn" onClick={() => setMethod("type")}>
                Type it instead
              </button>
            </div>
          </>
        )}
        {method === "type" && (
          <>
            <h3>Type the printed scale</h3>
            <p className="q">For example 1:100, as printed in the title block.</p>
            <div className="btnrow">
              <input aria-label="scale ratio" value={ratio} onChange={(e) => setRatio(e.target.value)} style={{ background: "#18202b", color: "inherit", border: "1px solid #263040", borderRadius: 8, padding: "6px 10px" }} />
              <button className="btn btn--primary" onClick={() => onAnswer("type", ratio)}>
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
