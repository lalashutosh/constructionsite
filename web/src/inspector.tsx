/** Element inspector: every drawn element is selectable (2D map here, 3D in the viewer); the user can change what it is. */
import { useMemo, useState } from "react";
import { Pencil, RotateCcw, Trash2, Undo2 } from "lucide-react";
import type { PlanElement } from "./api";
import { Meter } from "./checks";

export type Pt = [number, number];
export const KIND_WORD: Record<string, string> = { door: "door", window: "window", opening: "wall opening", fixture: "fixture", wall: "wall", room: "room", stair: "stair", label: "label" };
export const kindName = (k: string) => KIND_WORD[k] ?? k.replace(/_/g, " ");
const TAG_WORD: Record<string, string> = { drawn: "Drawn: read from the drawing", specified: "Specified: printed on the drawing", chosen: "Chosen: you decided this" };
export const ROOM_TYPES = ["bedroom", "kitchen", "living", "bathroom", "wc", "sauna", "storage", "hall", "balcony", "other"];
/** What the type picker offers. `kind` + optional subtype is what the engine receives. */
const PICK: { id: string; label: string; kind?: string }[] = [
  { id: "door", label: "Door", kind: "door" },
  { id: "window", label: "Window", kind: "window" },
  { id: "opening", label: "Wall opening", kind: "opening" },
  { id: "fixture", label: "Fixture", kind: "fixture" },
  { id: "wall", label: "Wall", kind: "wall" },
  { id: "room", label: "Room", kind: "room" },
  { id: "stair", label: "Stair", kind: "stair" },
  { id: "none", label: "Not an element (remove)" },
];

export const isChanged = (e: PlanElement, local?: Set<string>) => !!(e.user_changed || e.tag === "chosen" || local?.has(e.id));

function inside(p: Pt, poly: Pt[]) {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if (yi > p[1] !== yj > p[1] && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) c = !c;
  }
  return c;
}
const areaPx = (poly: Pt[]) => {
  let a = 0;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) a += poly[j][0] * poly[i][1] - poly[i][0] * poly[j][1];
  return Math.abs(a) / 2;
};
/** Element under a drawing point: the smallest outline wins, so a door beats the room around it. Thin ones get a small tolerance. */
export function pickAt(els: PlanElement[], x: number, y: number, tol = 4): PlanElement | null {
  let best: PlanElement | null = null;
  let bestA = Infinity;
  for (const e of els) {
    if (e.polygon.length < 3) continue;
    let hit = inside([x, y], e.polygon);
    if (!hit && e.kind !== "room") {
      const xs = e.polygon.map((p) => p[0]), ys = e.polygon.map((p) => p[1]);
      hit = x >= Math.min(...xs) - tol && x <= Math.max(...xs) + tol && y >= Math.min(...ys) - tol && y <= Math.max(...ys) + tol;
    }
    if (!hit) continue;
    const a = areaPx(e.polygon);
    if (a < bestA) { best = e; bestA = a; }
  }
  return best;
}

const pts = (poly: Pt[]) => poly.map((p) => p.join(",")).join(" ");

function ElementMap(p: { src: string; w: number; h: number; els: PlanElement[]; selId: string | null; hoverId: string | null; local: Set<string>; onSelect: (id: string | null) => void; onHover: (id: string | null) => void; credit: string; synthetic: boolean }) {
  const u = Math.max(p.w, p.h) / 400;
  const sel = p.els.find((e) => e.id === p.selId);
  return (
    <figure className="elmap">
      <svg viewBox={`0 0 ${p.w} ${p.h}`} preserveAspectRatio="xMidYMid meet" role="group" aria-label="Drawing with selectable elements"
        onClick={(ev) => {
          const r = (ev.currentTarget as SVGSVGElement).getBoundingClientRect();
          const s = Math.min(r.width / p.w, r.height / p.h);
          const x = (ev.clientX - r.left - (r.width - p.w * s) / 2) / s, y = (ev.clientY - r.top - (r.height - p.h * s) / 2) / s;
          p.onSelect(pickAt(p.els, x, y, 3 * u)?.id ?? null);
        }}
        onMouseMove={(ev) => {
          const r = (ev.currentTarget as SVGSVGElement).getBoundingClientRect();
          const s = Math.min(r.width / p.w, r.height / p.h);
          const x = (ev.clientX - r.left - (r.width - p.w * s) / 2) / s, y = (ev.clientY - r.top - (r.height - p.h * s) / 2) / s;
          const id = pickAt(p.els, x, y, 3 * u)?.id ?? null;
          if (id !== p.hoverId) p.onHover(id);
        }}
        onMouseLeave={() => p.onHover(null)}>
        <image href={p.src} x={0} y={0} width={p.w} height={p.h} />
        {p.els.map((e) => {
          const cls = ["elpoly", e.kind, e.removed ? "removed" : "", e.id === p.selId ? "sel" : "", e.id === p.hoverId ? "hov" : "", isChanged(e, p.local) ? "chg" : ""].join(" ");
          return <polygon key={e.id} className={cls} points={pts(e.polygon)} strokeWidth={(e.id === p.selId ? 3 : 1.5) * u} />;
        })}
        {sel && sel.polygon.length > 0 && <polygon className="elpoly selring" points={pts(sel.polygon)} strokeWidth={4 * u} pointerEvents="none" />}
      </svg>
      {p.synthetic && <span className="elribbon">SYNTHETIC DEMO</span>}
      <figcaption className="muted sm">{p.els.length} elements. Click one to see what it is{p.credit ? "." : ""} {p.credit && <span className="pv-credit">{p.credit}</span>}</figcaption>
    </figure>
  );
}

export interface InspectorProps {
  path: string;
  els: PlanElement[] | null;
  /** engine has no /api/elements yet */
  unavailable: boolean;
  selId: string | null;
  hoverId: string | null;
  local: Set<string>;
  busy: boolean;
  note: string | null;
  err: string | null;
  canUndo: boolean;
  imgSrc: string;
  dims: { w: number; h: number } | null;
  credit: string;
  synthetic: boolean;
  onSelect: (id: string | null) => void;
  onHover: (id: string | null) => void;
  onRetype: (e: PlanElement, kind: string, subtype?: string) => void;
  onRemove: (e: PlanElement) => void;
  onRestore: (e: PlanElement) => void;
  onUndo: () => void;
}

export function Inspector(p: InspectorProps) {
  const [open, setOpen] = useState(false);
  const sel = useMemo(() => p.els?.find((e) => e.id === p.selId) ?? null, [p.els, p.selId]);
  if (p.unavailable) return <section className="inspector" aria-label="Element inspector"><div className="chead"><span className="lbl">Elements</span></div><p className="muted sm elna">Inspector not available: this engine does not serve element data yet.</p></section>;
  if (!p.els || !p.els.length) return null;
  const counts = new Map<string, number>();
  for (const e of p.els) if (!e.removed) counts.set(e.kind, (counts.get(e.kind) ?? 0) + 1);
  const summary = [...counts.entries()].map(([k, n]) => `${n} ${kindName(k)}${n === 1 ? "" : "s"}`).join(" · ");
  return (
    <section className="inspector" aria-label="Element inspector">
      <div className="chead">
        <span className="lbl">Elements</span>
        <span className="muted sm">{summary}</span>
        <button className="linkbtn" onClick={() => setOpen((o) => !o)} aria-expanded={open}>{open ? "Hide map" : "Show map"}</button>
      </div>
      {open && p.dims && <ElementMap src={p.imgSrc} w={p.dims.w} h={p.dims.h} els={p.els} selId={p.selId} hoverId={p.hoverId} local={p.local} onSelect={p.onSelect} onHover={p.onHover} credit={p.credit} synthetic={p.synthetic} />}
      <div className="cnote" role="status" aria-live="polite">{p.note}</div>
      {p.err && <div className="errline" role="alert">{p.err}</div>}
      {sel ? <Detail key={sel.id} {...p} el={sel} /> : <p className="muted sm elhint">Click an element on the map or in the 3D view to see what it is and change it.</p>}
      {p.canUndo && <button className="linkbtn elundo" disabled={p.busy} onClick={p.onUndo}><Undo2 size={13} aria-hidden /> Undo last change</button>}
    </section>
  );
}

function pickIdOf(e: PlanElement) {
  if (e.removed) return "none";
  return PICK.find((x) => x.kind === e.kind)?.id ?? "fixture";
}

function Detail(p: InspectorProps & { el: PlanElement }) {
  const e = p.el;
  const changed = isChanged(e, p.local);
  const [pick, setPick] = useState(pickIdOf(e));
  const [room, setRoom] = useState(e.kind === "room" && e.subtype && ROOM_TYPES.includes(e.subtype) ? e.subtype : "");
  const word = kindName(e.kind);
  const what = e.removed ? "Removed by you" : `${word.charAt(0).toUpperCase() + word.slice(1)}${e.subtype && e.kind !== "room" ? ` · ${e.subtype}` : ""}`;
  const sm = (e.size_m ?? null) as { w?: number; h?: number; area?: number; area_m2?: number } | null;
  const area = sm ? (sm.area_m2 ?? sm.area) : undefined;             // the API sends area_m2
  const size = !sm ? null : typeof area === "number" ? `${area.toFixed(1)} m²` + (typeof sm.w === "number" && typeof sm.h === "number" ? ` (${sm.w.toFixed(2)} × ${sm.h.toFixed(2)} m)` : "")
    : typeof sm.w === "number" && typeof sm.h === "number" ? `${sm.w.toFixed(2)} × ${sm.h.toFixed(2)} m` : null;
  const apply = () => {
    if (pick === "none") return p.onRemove(e);
    const k = PICK.find((x) => x.id === pick)?.kind;
    if (k) p.onRetype(e, k, k === "room" && room ? room : undefined);
  };
  const dirty = pick !== pickIdOf(e) || (pick === "room" && !!room && room !== e.subtype);
  return (
    <div className={`eldetail ${e.removed ? "gone" : ""}`}>
      <div className="eltop">
        <b className="elwhat">{what}</b>
        {e.label && <span className="mono elabel">“{e.label}”</span>}
        {changed && <span className="elbadge"><Pencil size={11} aria-hidden /> you changed this</span>}
      </div>
      <dl className="elfacts">
        <div><dt>Size</dt><dd>{size ?? "not known: scale not solved"}</dd></div>
        <div><dt>Source</dt><dd>{TAG_WORD[e.tag] ?? e.tag}</dd></div>
        <div><dt>Confidence</dt><dd>{changed && e.tag === "chosen" ? "You decided this" : <Meter value={typeof e.conf === "number" ? e.conf : 0.5} label={word} />}</dd></div>
        <div><dt>Feeds</dt><dd>{e.feeds?.length ? e.feeds.join(", ") : "no answer"}</dd></div>
      </dl>
      <p className="elexp">{e.explanation || `This is a ${word}${e.label ? ` labelled “${e.label}”` : ""}.`}</p>
      {e.removed ? (
        <div className="cact"><button className="cbtn" disabled={p.busy} onClick={() => p.onRestore(e)}><RotateCcw size={13} aria-hidden /> Restore it</button></div>
      ) : (
        <>
          <div className="elpick">
            <label>Wrong? It is a{" "}
              <select value={pick} onChange={(ev) => setPick(ev.target.value)} aria-label="What is this element">
                {PICK.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
              </select>
            </label>
            {pick === "room" && (
              <label>Room type{" "}
                <select value={room} onChange={(ev) => setRoom(ev.target.value)} aria-label="Room type">
                  <option value="">choose…</option>
                  {ROOM_TYPES.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </label>
            )}
            <button className="cbtn yes" disabled={p.busy || !dirty || (pick === "room" && !room)} onClick={apply}>{p.busy ? "Saving…" : "Change"}</button>
          </div>
          <div className="cact"><button className="cbtn" disabled={p.busy} onClick={() => p.onRemove(e)}><Trash2 size={13} aria-hidden /> Not a {word}, remove</button></div>
        </>
      )}
    </div>
  );
}
