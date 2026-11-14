/**
 * "Why?" sheet proof view: the drawing cropped to what the answer counted, with a numbered circle per evidence
 * element (numbers = position in proof.evidence, same as the chips and the 3D pins), and the gist of the argument:
 * which check said what, whether they agreed and which one the answer follows. Everything shown comes from the
 * ProofObject; nothing is invented.
 */
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { Element, ProofObject, Voter } from "./types";
import { ScanSearch } from "lucide-react";
import { fmtNum, verdict, voterWord } from "./logic";

const WHO: Record<string, string> = {
  detector: "Symbol detector (neural net)",
  doors_arc: "Arc geometry",
  arc_geometry: "Arc geometry",
  label_reader: "AI label reader",
  ocr_labels: "Printed-label reader (OCR)",
  dxf_exact: "Exact CAD read",
  ifc_exact: "Exact IFC read",
  printed_area: "Printed room areas",
  polygon_shoelace: "Room-outline geometry",
  planner_query: "Planned query",
};
const who = (name: string) => {
  const w = WHO[name] ?? voterWord(name);
  return w.charAt(0).toUpperCase() + w.slice(1);
};
const UNITS: Record<string, string> = { m2: "m²", m3: "m³", m: "m" };
const RASTER = /\.(png|jpe?g|webp)$/i;

const has = (v: Voter) => v.value !== null && v.value !== undefined && v.value !== "";
const same = (a: unknown, b: unknown) => {
  const na = Number(a), nb = Number(b);
  return Number.isFinite(na) && Number.isFinite(nb) ? Math.abs(na - nb) < 1e-9 : String(a) === String(b);
};

/** "5 doors" / "1 toilet" / "41.2 m²", from the proof's own intent and unit. */
function amount(p: ProofObject, v: unknown): string {
  const s = fmtNum(v as number | string);
  if (p.kind === "count") {
    const noun = (p.intent ?? "").replace(/_/g, " ").trim();
    if (!noun) return s;
    return `${s} ${Number(v) === 1 && noun.endsWith("s") ? noun.slice(0, -1) : noun}`;
  }
  const u = UNITS[p.unit ?? ""] ?? (p.unit && p.unit !== "count" ? p.unit : "");
  return u ? `${s} ${u}` : s;
}

function bbox(poly: [number, number][]) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of poly) {
    if (x < x0) x0 = x;
    if (y < y0) y0 = y;
    if (x > x1) x1 = x;
    if (y > y1) y1 = y;
  }
  return { x0, y0, x1, y1 };
}

/** The checks whose value is the answer (the ones it follows), and the elements they counted. */
function deciders(p: ProofObject) {
  const valued = p.voters.filter(has);
  const dec = valued.filter((v) => same(v.value, p.value));
  const counted = new Set(dec.flatMap((v) => v.element_ids));
  return { valued, dec, counted };
}

function Picture(p: {
  proof: ProofObject;
  src: string;
  counted: Set<string>;
  hover: number | null;
  onHover: (i: number | null) => void;
  compact?: boolean;
}) {
  const ev = p.proof.evidence;
  const [dims, setDims] = useState<{ w: number; h: number } | null>(null);
  const [failed, setFailed] = useState(false);
  const [boxW, setBoxW] = useState(340);
  const wrap = useRef<HTMLElement>(null);

  useEffect(() => {
    setDims(null);
    setFailed(false);
    if (!p.src) return;
    const im = new Image();
    im.onload = () => setDims({ w: im.naturalWidth, h: im.naturalHeight });
    im.onerror = () => setFailed(true);
    im.src = p.src;
    return () => {
      im.onload = null;
      im.onerror = null;
    };
  }, [p.src]);

  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setBoxW(el.clientWidth || 340));
    ro.observe(el);
    return () => ro.disconnect();
  }, [dims]);

  if (failed || !p.src) return null;
  if (!dims) return <div className={`pv-pic pv-wait muted${p.compact ? " sm" : ""}`}>Loading the drawing…</div>;

  const boxes = ev.map((e) => bbox(e.polygon as [number, number][]));
  const all = boxes.reduce((a, b) => ({ x0: Math.min(a.x0, b.x0), y0: Math.min(a.y0, b.y0), x1: Math.max(a.x1, b.x1), y1: Math.max(a.y1, b.y1) }));
  // sanity: the evidence must sit inside the image, else these are not image pixels
  const tol = 0.05 * Math.max(dims.w, dims.h);
  if (!(all.x0 > -tol && all.y0 > -tol && all.x1 < dims.w + tol && all.y1 < dims.h + tol)) return null;

  const bw = all.x1 - all.x0, bh = all.y1 - all.y0;
  let w = Math.min(dims.w, Math.max(bw * 1.24, 300));
  let h = Math.min(dims.h, Math.max(bh * 1.24, w * 0.5));
  if (h > dims.h) h = dims.h;
  w = Math.min(dims.w, Math.max(w, 1));
  const cx = (all.x0 + all.x1) / 2, cy = (all.y0 + all.y1) / 2;
  const x = Math.max(0, Math.min(dims.w - w, cx - w / 2));
  const y = Math.max(0, Math.min(dims.h - h, cy - h / 2));
  const u = w / Math.max(boxW, 1); // drawing units per screen pixel
  const mixed = p.counted.size > 0 && ev.some((e) => !p.counted.has(e.id));

  return (
    <figure className={`pv-pic${p.compact ? " sm" : ""}`} ref={wrap}>
      <svg viewBox={`${x} ${y} ${w} ${h}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label={`Drawing with ${ev.length} numbered elements circled`}>
        <image href={p.src} x={0} y={0} width={dims.w} height={dims.h} />
        {ev.map((e, i) => {
          const b = boxes[i];
          const n = i + 1;
          const ccx = (b.x0 + b.x1) / 2, ccy = (b.y0 + b.y1) / 2;
          const r = Math.max(Math.hypot(b.x1 - b.x0, b.y1 - b.y0) / 2 + 2 * u, 10 * u);
          const tx = ccx + r * 0.72, ty = ccy - r * 0.72;
          const hot = p.hover === n;
          const side = mixed && !p.counted.has(e.id);
          return (
            <g key={e.id} className={`pv-mark${hot ? " hot" : ""}${side ? " side" : ""}`} onMouseEnter={() => p.onHover(n)} onMouseLeave={() => p.onHover(null)}>
              <title>{`${n}: ${e.kind}${e.label ? ` "${e.label}"` : ""}${side ? " (other check)" : ""}`}</title>
              <circle className="pv-ring" cx={ccx} cy={ccy} r={r} strokeWidth={(hot ? 3 : 2) * u} strokeDasharray={side ? `${4 * u} ${3 * u}` : undefined} />
              <circle className="pv-tag" cx={tx} cy={ty} r={8 * u} />
              <text className="pv-num" x={tx} y={ty} fontSize={10 * u} dy={3.5 * u} textAnchor="middle">{n}</text>
              {e.kind === "label" && e.label && (
                <text className="pv-lbl" x={tx + 10 * u} y={ty} dy={4 * u} fontSize={11 * u} strokeWidth={3 * u}>{e.label}</text>
              )}
            </g>
          );
        })}
      </svg>
      <figcaption className="muted sm">
        {p.compact ? (
          <>Circled: {ev.length} element{ev.length === 1 ? "" : "s"} the answer rests on{mixed ? " (dashed: another check's)" : ""}.</>
        ) : mixed ? (
          <>
            <span className="pv-key solid" /> counted by the check the answer follows · <span className="pv-key dash" /> found by another check
          </>
        ) : (
          <>Circled: the {ev.length} element{ev.length === 1 ? "" : "s"} behind this answer, numbered as in the list.</>
        )}
        {p.proof.provenance.credit && <span className="pv-credit">{p.proof.provenance.credit}</span>}
      </figcaption>
    </figure>
  );
}

function sentence(p: ProofObject, vt: Voter, byId: Map<string, Element>): string {
  const w = who(vt.name);
  if (!has(vt)) return `${w} gave no number.`;
  const labels = vt.element_ids.map((id) => byId.get(id)).filter((e): e is Element => !!e && e.kind === "label" && !!e.label).map((e) => e.label as string);
  if (labels.length) return `${w} read ${labels.join(", ")} → ${amount(p, vt.value)}.`;
  return `${w} found ${amount(p, vt.value)}.`;
}

/** The verdict as plain text: did the checks agree, which one the answer follows, and the tier word. */
export function verdictLine(p: ProofObject): { text: string; word: string; rel: string | null } {
  const { valued, dec } = deciders(p);
  const v = verdict(p);
  const rel = p.reliability_note ? `Answers like this: ${p.reliability_note}.` : v.rel !== null ? `Measured reliability ${Math.round(v.rel * 100)}%.` : null;
  if (p.tier === "grey") return { text: `No answer: ${p.refusal ?? "no reason given"}`, word: v.word, rel: null };
  if (!valued.length) return { text: "No check produced a number", word: v.word, rel };
  if (valued.length === 1) return { text: `Only one check (${lc(who(valued[0].name))}) ran, nothing cross-checks it`, word: v.word, rel };
  const distinct = [...new Set(valued.map((x) => fmtNum(x.value)))];
  if (distinct.length === 1) return { text: `All ${valued.length} checks agree on ${amount(p, valued[0].value)}`, word: v.word, rel };
  const nums = valued.every((x) => typeof x.value === "number") ? valued.map((x) => x.value as number) : null;
  const how = nums && valued.length === 2 ? `Checks disagree by ${fmtNum(Math.max(...nums) - Math.min(...nums))}` : `Checks disagree (${distinct.join(" vs ")})`;
  if (!dec.length) return { text: `${how}; the answer ${fmtNum(p.value)} is not any single check's value`, word: v.word, rel };
  const decides = p.notes.some((n) => n.includes("decides this answer")) && dec.some((d) => d.name === "label_reader");
  return { text: `${how}; the answer follows the ${dec.map((d) => lc(who(d.name))).join(" and ")}${decides ? ", which the engine marks as deciding" : ""}`, word: v.word, rel };
}
const lc = (s: string) => s.replace(/^./, (c) => c.toLowerCase());

function Verdict({ p }: { p: ProofObject }) {
  const l = verdictLine(p);
  return (
    <>
      <p className="pv-verdict">{l.text} → <b>{l.word}</b>.</p>
      {l.rel && <p className="muted">{l.rel}</p>}
    </>
  );
}

/** Whether the evidence can be drawn on the image (raster pixel coordinates). */
function drawable(pr: ProofObject, coords?: string | null) {
  const file = pr.provenance.file ?? "";
  const pixels = coords ? coords === "pixels" : RASTER.test(file) && !pr.provenance.resolved_from;
  return pixels && pr.evidence.length > 0 && pr.evidence.every((e) => e.polygon && e.polygon.length > 0);
}

/** The drawing cropped to the evidence with numbered circles (null when the coords are not image pixels). */
export function ProofCrop(p: { proof: ProofObject; src: string; coords?: string | null; hover: number | null; onHover: (i: number | null) => void; compact?: boolean }) {
  if (!drawable(p.proof, p.coords)) return null;
  return <Picture proof={p.proof} src={p.src} counted={deciders(p.proof).counted} hover={p.hover} onHover={p.onHover} compact={p.compact} />;
}

/** Small action chip that opens the full reasoning. */
export function SeeProof({ onClick, label = "See proof" }: { onClick: () => void; label?: string }) {
  return (
    <button type="button" className="pv-see" onClick={onClick}>
      <ScanSearch size={13} strokeWidth={1.75} aria-hidden="true" />
      {label}
    </button>
  );
}

/** Inline proof under a selected finding: crop, up to 3 "who said what" lines, the verdict, a link to the full sheet. */
export function ProofCard(p: { proof: ProofObject; src: string; coords?: string | null; hover: number | null; onHover: (i: number | null) => void; onFull: () => void }) {
  const pr = p.proof;
  const { valued, dec } = deciders(pr);
  const byId = new Map(pr.evidence.map((e) => [e.id, e]));
  const l = verdictLine(pr);
  const shown = pr.voters.slice(0, 3);
  return (
    <div className="pv-card">
      <ProofCrop proof={pr} src={p.src} coords={p.coords} hover={p.hover} onHover={p.onHover} compact />
      {shown.length > 0 && (
        <ul className="pv-mini">
          {shown.map((vt) => (
            <li key={vt.name} className={dec.includes(vt) && valued.length > 1 ? "dec" : ""}>{sentence(pr, vt, byId)}</li>
          ))}
          {pr.voters.length > shown.length && <li className="muted">+{pr.voters.length - shown.length} more</li>}
        </ul>
      )}
      <p className="pv-verdict">{l.text} → <b>{l.word}</b>.</p>
      <SeeProof onClick={p.onFull} label="Full reasoning" />
    </div>
  );
}

export default function ProofView(p: {
  proof: ProofObject;
  /** image URL of the drawing (imageUrl(path)) */
  src: string;
  /** geometry coords of the drawing ("pixels" for raster); undefined when unknown */
  coords?: string | null;
  hover: number | null;
  onHover: (i: number | null) => void;
  /** optional chip row renderer for a voter's element ids (keeps hover in sync with the rest of the sheet) */
  chips?: (ids: string[]) => ReactNode;
}) {
  const pr = p.proof;
  const { valued, dec } = deciders(pr);
  const byId = new Map(pr.evidence.map((e) => [e.id, e]));

  return (
    <div className="pv">
      <ProofCrop proof={pr} src={p.src} coords={p.coords} hover={p.hover} onHover={p.onHover} />
      <b>Who said what</b>
      {pr.voters.length === 0 ? (
        <p className="muted">No separate checks were recorded for this answer.</p>
      ) : (
        <ul className="pv-voters">
          {pr.voters.map((vt) => {
            const isDec = dec.includes(vt) && valued.length > 1;
            const runs = vt.runs.length > 1 ? (vt.runs.every((r) => r === vt.runs[0]) ? `same in all ${vt.runs.length} runs` : `runs: ${vt.runs.join(", ")}`) : null;
            return (
              <li key={vt.name} className={isDec ? "dec" : ""}>
                <p>
                  {sentence(pr, vt, byId)} {isDec && <span className="pv-badge">answer follows</span>}
                  {runs && <span className="muted"> ({runs})</span>}
                </p>
                {vt.note && <p className="muted sm">{vt.note}</p>}
                {p.chips?.(vt.element_ids)}
              </li>
            );
          })}
        </ul>
      )}
      <Verdict p={pr} />
    </div>
  );
}
