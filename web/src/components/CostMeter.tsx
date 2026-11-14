import { useEffect, useRef, useState } from "react";
import type { Cost } from "../types";
import { CORPUS_DRAWINGS, estimateSeconds, humanDuration } from "../derive";

function useCountUp(target: number, ms = 700): number {
  const [v, setV] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    const start = performance.now();
    const a = from.current;
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / ms);
      const val = a + (target - a) * (1 - Math.pow(1 - k, 3));
      setV(val);
      from.current = val;
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return v;
}

export function CostMeter({ cost, claims, extended = false, onScale }: { cost: Cost; claims: Record<string, unknown> | null; extended?: boolean; onScale?: () => void }) {
  const tokens = useCountUp(cost.tokens_in + cost.tokens_out);
  const usd = useCountUp(cost.usd);
  const ms = useCountUp(cost.ms);
  const cpu = claims && typeof claims.cpu_per_drawing_s === "number" ? claims.cpu_per_drawing_s : null;
  const claimBits = claims && !extended
    ? Object.entries(claims)
        .filter(([, v]) => typeof v === "number" || typeof v === "string")
        .slice(0, 3)
        .map(([k, v]) => `${k} ${v}`)
    : [];
  return (
    <>
      <span className="meter" data-testid="meter">
        <b>{Math.round(tokens)}</b> tokens · <b>${usd.toFixed(2)}</b> · <b>{Math.round(ms)}</b> ms
      </span>
      {extended && (
        <>
          <span className="claims" data-testid="llm-calls">
            LLM calls: <b>{cost.llm_calls}</b>
            {cost.planner_calls ? ` · planner calls: ${cost.planner_calls}` : ""}
          </span>
          {cpu != null && (
            <span className="claims" data-testid="cpu-estimate">
              estimate: {humanDuration(estimateSeconds(cpu, CORPUS_DRAWINGS))} CPU for {CORPUS_DRAWINGS.toLocaleString("en")} drawings
            </span>
          )}
          {onScale && (
            <button className="linkbtn" onClick={onScale}>
              How we scale
            </button>
          )}
        </>
      )}
      {claimBits.length > 0 && <span className="claims">eval: {claimBits.join(" · ")}</span>}
    </>
  );
}
