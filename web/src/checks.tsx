/** Checks block: confidence meter + short yes/no questions for things that change the numbers. */
import { CheckCircle2, CircleHelp, TriangleAlert, XCircle } from "lucide-react";
import type { Check } from "./api";

export type Band = "good" | "caution" | "low";
export const bandOf = (c: number): Band => (c >= 0.8 ? "good" : c >= 0.5 ? "caution" : "low");
const BAND_WORD: Record<Band, string> = { good: "Sure", caution: "Fairly sure", low: "Not sure" };
export const pct = (c: number) => Math.round(Math.max(0, Math.min(1, c)) * 100);
const KIND_WORD: Record<Check["kind"], string> = { scale: "Scale", sheet_type: "Sheet type", plan_view: "Plan view", units: "Units" };
export const kindWord = (k: Check["kind"]) => KIND_WORD[k] ?? k;

function BandIcon({ band }: { band: Band }) {
  const p = { size: 14, strokeWidth: 2, "aria-hidden": true };
  return band === "good" ? <CheckCircle2 {...p} /> : band === "caution" ? <TriangleAlert {...p} /> : <CircleHelp {...p} />;
}

export function Meter({ value, label }: { value: number; label: string }) {
  const band = bandOf(value);
  return (
    <span className={`cmeter ${band}`}>
      <span className="cbar" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct(value)} aria-valuetext={`${pct(value)} percent, ${BAND_WORD[band]}`} aria-label={`${label} confidence`}>
        <i style={{ width: `${pct(value)}%` }} />
      </span>
      <span className="cword"><BandIcon band={band} />{pct(value)}% · {BAND_WORD[band]}</span>
    </span>
  );
}

/** Short wording of the scale in force, for the line under a size: `1" = 40'-0"`. */
export function scaleBrief(items: Check[] | undefined): { text: string; conf: number } | null {
  const c = (items ?? []).find((x) => x.kind === "scale" && (x.status === "confirmed" || x.status === "auto")) ?? (items ?? []).find((x) => x.kind === "scale" && x.status === "open");
  if (!c) return null;
  const m = c.summary.match(/\d+(?:\.\d+)?\s*(?:"|in|mm|cm|m)\s*=\s*\d[^\s,;()]*(?:\s*(?:ft|m|mm|cm))?/);
  const short = (m ? m[0] : c.summary.replace(/ \(.*$/, "").replace(/\.$/, "")).trim();
  return { text: short, conf: c.confidence };
}
export const sizeKinds = new Set(["area", "length", "volume"]);

export function ChecksBlock(p: {
  items: Check[] | null;
  busyId: string | null;
  note: string | null;
  err: string | null;
  onAnswer: (c: Check, a: "yes" | "no") => void;
  onType: () => void;
  onHover: (c: Check | null) => void;
}) {
  if (!p.items || !p.items.length) return null;
  const open = p.items.filter((c) => c.status === "open" && c.question);
  const shown = open.slice(0, 3);
  const rest = p.items.filter((c) => !shown.includes(c) && c.status !== "rejected");
  const more = open.length - shown.length;
  const hov = (c: Check | null) => ({ onMouseEnter: () => p.onHover(c), onMouseLeave: () => p.onHover(null), onFocus: () => p.onHover(c), onBlur: () => p.onHover(null) });
  return (
    <section className="checks" aria-label="Checks">
      <div className="chead"><span className="lbl">Checks</span><span className="muted sm">{open.length ? `${open.length} to confirm` : "nothing to confirm"}</span></div>
      <div className="cnote" role="status" aria-live="polite">{p.note}</div>
      {p.err && <div className="errline" role="alert">Could not save that answer: {p.err}</div>}
      <ul className="clist">
        {shown.map((c, i) => {
          const band = bandOf(c.confidence);
          const busy = p.busyId === c.id;
          return (
            <li key={c.id} className={`crow open ${band}`} tabIndex={c.evidence.length ? 0 : undefined} {...hov(c)} aria-label={`${kindWord(c.kind)} check, ${pct(c.confidence)} percent, question open`}>
              <div className="ctop"><span className="lbl">{kindWord(c.kind)}</span><Meter value={c.confidence} label={kindWord(c.kind)} /></div>
              {i === 0 && <p className="csum">{c.summary}</p>}
              <p className={`cq ${i ? "sm2" : ""}`}>{c.question}</p>
              {i === 0 && c.impact && <p className="cimp muted">{c.impact}</p>}
              <div className="cact">
                <button className="cbtn yes" disabled={!!p.busyId} onClick={() => p.onAnswer(c, "yes")}>{busy ? "Saving…" : "Yes"}</button>
                <button className="cbtn" disabled={!!p.busyId} onClick={() => p.onAnswer(c, "no")}>No</button>
                {c.kind === "scale" && <button className="linkbtn" disabled={!!p.busyId} onClick={p.onType}>Type a length instead</button>}
                {i === 0 && c.evidence.length > 0 && <span className="muted sm cev">{c.evidence.length} place{c.evidence.length > 1 ? "s" : ""} marked on the drawing</span>}
              </div>
            </li>
          );
        })}
        {rest.map((c) => {
          const band = bandOf(c.confidence);
          const Ic = c.status === "confirmed" ? CheckCircle2 : c.status === "open" ? CircleHelp : CheckCircle2;
          return (
            <li key={c.id} className={`crow done ${band}`} tabIndex={c.evidence.length ? 0 : undefined} {...hov(c)}>
              <span className="cdi"><Ic size={14} aria-hidden /></span>
              <span className="ctext"><span><b>{kindWord(c.kind)}</b> · {c.status === "confirmed" ? "confirmed by you" : c.status === "auto" ? "read from the drawing" : "waiting"}</span><small>{c.summary}</small></span>
              <span className="cpct mono">{pct(c.confidence)}%</span>
            </li>
          );
        })}
        {p.items.filter((c) => c.status === "rejected").map((c) => (
          <li key={c.id} className="crow done rej">
            <span className="cdi"><XCircle size={14} aria-hidden /></span>
            <span className="ctext"><span><b>{kindWord(c.kind)}</b> · you said no</span><small>{c.summary.replace(/ \(.*$/, "")}</small></span>
          </li>
        ))}
        {more > 0 && <li className="cmore muted sm">{more} more question{more > 1 ? "s" : ""} after these.</li>}
      </ul>
    </section>
  );
}
