import { useEffect, useRef, useState } from "react";
import type { Cost } from "../types";

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

export function CostMeter({ cost, claims }: { cost: Cost; claims: Record<string, unknown> | null }) {
  const tokens = useCountUp(cost.tokens_in + cost.tokens_out);
  const usd = useCountUp(cost.usd);
  const ms = useCountUp(cost.ms);
  const claimBits = claims
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
      {claimBits.length > 0 && <span className="claims">eval: {claimBits.join(" · ")}</span>}
    </>
  );
}
