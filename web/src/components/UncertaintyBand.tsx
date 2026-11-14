import { fmt, unitLabel } from "../derive";
import type { Interval, Tier } from "../types";

export function UncertaintyBand({ interval, axis, tier, value, unit }: { interval: Interval; axis: Interval; tier: Tier; value?: number | string | null; unit?: string | null }) {
  const span = axis.hi - axis.lo || 1;
  const left = ((interval.lo - axis.lo) / span) * 100;
  const width = Math.max(((interval.hi - interval.lo) / span) * 100, 1.2);
  const mid = typeof value === "number" ? ((value - axis.lo) / span) * 100 : null;
  const pct = typeof value === "number" && value !== 0 ? Math.round(((interval.hi - interval.lo) / 2 / value) * 100) : null;
  return (
    <div className="band" role="img" aria-label={`range ${fmt(interval.lo)} to ${fmt(interval.hi)} ${unitLabel(unit)}`}>
      <div className="band-axis">
        <div className={`band-fill band-fill--${tier}`} style={{ left: `${left}%`, width: `${width}%` }} />
        {mid !== null && <div className="band-mark" style={{ left: `${mid}%` }} />}
      </div>
      <div className="band-lab">
        <span>{fmt(axis.lo)}</span>
        <span>
          {fmt(interval.lo)} to {fmt(interval.hi)} {unitLabel(unit)}
          {pct !== null ? ` (±${pct}%)` : ""}
        </span>
        <span>{fmt(axis.hi)}</span>
      </div>
    </div>
  );
}
