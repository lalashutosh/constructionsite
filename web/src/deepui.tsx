/** Deep-read UI: view cube (2D/3D, orbit, re-centre), layer toggles, "What's on this sheet" checklist, first-time tour. */
import { useEffect, useRef, useState } from "react";
import { BASE } from "./api";
import type { PlumbViewer } from "./viewer3d";

// ---------------------------------------------------------------- view cube
export function ViewCube({ viewer }: { viewer: () => PlumbViewer | null }) {
  const [az, setAz] = useState(0);
  const [mode, setMode] = useState<"3d" | "top" | "front" | "side">("3d");
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  useEffect(() => {
    let raf = 0, last = 0;
    const tick = (t: number) => {
      if (t - last > 60) { const v = viewer(); if (v) { setAz(v.azimuth()); setMode(v.view); } last = t; }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [viewer]);
  const go = (m: "3d" | "top" | "front" | "side") => { viewer()?.setView(m); setMode(m); };
  const onDown = (e: React.PointerEvent) => { (e.target as Element).setPointerCapture(e.pointerId); drag.current = { x: e.clientX, y: e.clientY, moved: false }; };
  const onMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.x, dy = e.clientY - d.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
    if (d.moved) { viewer()?.orbitBy(dx, dy); d.x = e.clientX; d.y = e.clientY; }
  };
  const onUp = () => { const d = drag.current; drag.current = null; if (d && !d.moved) go(mode === "top" ? "3d" : "top"); };
  const pts = Array.from({ length: 8 }, (_, i) => { const a = (i / 8) * Math.PI * 2 + Math.PI / 8; return `${50 + 40 * Math.cos(a)},${50 + 40 * Math.sin(a)}`; }).join(" ");
  return (
    <div className="vcube" title="Tap: 2D / 3D · drag: rotate">
      <svg viewBox="0 0 100 100" onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp}
        style={{ transform: `rotate(${(-az * 180) / Math.PI}deg)` }}>
        <polygon points={pts} className="vcube-oct" />
        <text x="50" y="18" className="vcube-n">N</text>
        <text x="50" y="57" className="vcube-mode" style={{ transform: `rotate(${(az * 180) / Math.PI}deg)`, transformOrigin: "50px 50px" }}>{mode === "top" ? "2D" : "3D"}</text>
      </svg>
      <div className="vcube-row">
        <button className={mode === "top" ? "on" : ""} onClick={() => go("top")}>Top</button>
        <button className={mode === "front" ? "on" : ""} onClick={() => go("front")}>Front</button>
        <button className={mode === "side" ? "on" : ""} onClick={() => go("side")}>Side</button>
        <button className={mode === "3d" ? "on" : ""} onClick={() => go("3d")}>3D</button>
        <button title="Re-centre" onClick={() => viewer()?.recenter()}>⌖</button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- layers
export const LAYER_COLOURS: Record<string, number> = { envelope: 0xe7c98a, walls: 0xcbd5e1, furniture: 0x2dd4bf, piping: 0x3b82f6, electrical: 0xf59e0b };
const LAYER_NAMES: [string, string][] = [["envelope", "Envelope"], ["walls", "Walls"], ["furniture", "Furniture"], ["piping", "Piping"], ["electrical", "Electrical"]];
export type Layers = { envelope?: [number, number][][]; walls?: [number, number][][]; furniture?: { id: string; kind: string; polygon: [number, number][] }[];
  piping?: [number, number][][]; electrical?: [number, number][][]; notes?: Record<string, string> };
export function LayerToggles({ viewer, layers }: { viewer: () => PlumbViewer | null; layers: Layers | null | undefined }) {
  const [on, setOn] = useState<Record<string, boolean>>({ envelope: true, walls: true, furniture: true, piping: true, electrical: true });
  if (!layers) return null;
  return (
    <div className="layers">
      {LAYER_NAMES.map(([k, label]) => {
        const has = k === "walls" || ((layers as Record<string, unknown[] | undefined>)[k]?.length ?? 0) > 0;
        const why = layers.notes?.[k];
        return (
          <button key={k} disabled={!has} title={has ? `${label}: show / hide` : why || "not on this sheet"}
            className={`layer ${on[k] && has ? "on" : ""}`}
            onClick={() => { const nv = !on[k]; setOn({ ...on, [k]: nv }); viewer()?.setLayerVisible(k, nv); }}>
            <i style={{ background: `#${LAYER_COLOURS[k].toString(16).padStart(6, "0")}` }} />{label}
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------- checklist
export type Checklist = {
  deep: { on: boolean; reason: string; eta_s: number };
  rooms: { id: string; name: string; kind: string; area_m2: number | null; polygon: [number, number][]; counts: Record<string, number> }[];
  totals: { kind: string; label: string; count: number; ids: string[]; tier: "green" | "amber" | "grey"; note?: string }[];
  elements: { id: string; kind: string; label: string; polygon: [number, number][]; room_id?: string | null }[];
  cost?: { usd: number; ms: number };
};
export function ChecklistPanel(p: { path: string | null; deepHint?: { on: boolean; eta_s: number; reason: string } | null;
  onShow: (polys: [number, number][][]) => void; onRoom: (id: string, poly: [number, number][]) => void;
  onLoaded?: (c: Checklist) => void }) {
  const [data, setData] = useState<Checklist | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [since, setSince] = useState(0);
  const [now, setNow] = useState(Date.now());
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { setData(null); setErr(null); }, [p.path]);
  useEffect(() => { if (!busy) return; const t = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(t); }, [busy]);
  const run = async () => {
    if (!p.path) return;
    setBusy(true); setErr(null); setSince(Date.now());
    try {
      const r = await fetch(`${BASE}/checklist?path=${encodeURIComponent(p.path)}`);
      if (r.status === 404) throw new Error("the engine does not have the deep read yet");
      if (!r.ok) throw new Error(`engine answered ${r.status}`);
      const c = (await r.json()) as Checklist;
      setData(c);
      p.onLoaded?.(c);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  if (!p.path) return null;
  const eta = data?.deep.eta_s ?? p.deepHint?.eta_s ?? 60;
  const byId = new Map((data?.elements ?? []).map((e) => [e.id, e]));
  return (
    <section className="cklist">
      <header><h3>What's on this sheet</h3>{data?.cost && <span className="muted sm">{(data.cost.ms / 1000).toFixed(0)} s · ${data.cost.usd.toFixed(3)}</span>}</header>
      {(p.deepHint?.on || data?.deep.on) && !data && (
        <p className="deepnote">Deep read: this sheet is very detailed ({p.deepHint?.reason}). Counting every symbol takes about {Math.round(eta / 60) || 1} min.</p>
      )}
      {!data && !busy && <button className="btn" onClick={() => void run()}>{p.deepHint?.on ? `Start the deep read (~${Math.round(eta / 60) || 1} min)` : "Count everything on this sheet"}</button>}
      {busy && (
        <div className="ckbusy"><div className="bar"><i style={{ width: `${Math.min(96, ((now - since) / 1000 / eta) * 100)}%` }} /></div>
          <span className="muted sm">Finding every symbol, naming each type once, counting ({Math.round((now - since) / 1000)} s of ~{eta} s)</span></div>
      )}
      {err && <p className="err sm">{err}</p>}
      {data && (
        <>
          <ul className="cktotals">
            {data.totals.map((t) => (
              <li key={t.kind} onClick={() => p.onShow(t.ids.map((i) => byId.get(i)?.polygon).filter(Boolean) as [number, number][][])} title={t.note}>
                <i className={`dot ${t.tier}`} /><span>{t.label}</span><b>{t.count}</b>
              </li>
            ))}
          </ul>
          <details className="ckrooms">
            <summary>{data.rooms.length} rooms</summary>
            <ul>
              {data.rooms.map((r) => (
                <li key={r.id} className={open === r.id ? "on" : ""} onClick={() => { setOpen(r.id); p.onRoom(r.id, r.polygon); }}>
                  <span>{r.name}</span><span className="muted sm">{r.area_m2 ? `${r.area_m2.toFixed(1)} m²` : ""}</span>
                  {open === r.id && Object.keys(r.counts).length > 0 && (
                    <div className="sm muted">{Object.entries(r.counts).map(([k, n]) => `${n} ${k}`).join(" · ")}</div>
                  )}
                </li>
              ))}
            </ul>
          </details>
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- first-time tour
export type TourStep = { title: string; body: string; act?: () => void };
export function Tour({ steps, k }: { steps: TourStep[]; k: string }) {
  const seen = typeof localStorage !== "undefined" && localStorage.getItem("plumb-tour") === "done";
  const [i, setI] = useState<number | null>(seen ? null : 0);
  useEffect(() => { if (i !== null) steps[i]?.act?.(); }, [i, k]); // eslint-disable-line react-hooks/exhaustive-deps
  const done = () => { localStorage.setItem("plumb-tour", "done"); setI(null); };
  if (i === null) return <button className="tourbtn" onClick={() => setI(0)} title="Show the tour again">Tour</button>;
  const s = steps[i];
  if (!s) return null;
  return (
    <div className="tour" role="dialog">
      <div className="tour-card">
        <div className="tour-step muted sm">{i + 1} / {steps.length}</div>
        <h3>{s.title}</h3>
        <p>{s.body}</p>
        <div className="tour-nav">
          <button className="ghost" onClick={done}>Skip</button>
          {i > 0 && <button className="ghost" onClick={() => setI(i - 1)}>Back</button>}
          {i < steps.length - 1 ? <button className="btn" onClick={() => setI(i + 1)}>Next</button> : <button className="btn" onClick={done}>Start</button>}
        </div>
      </div>
    </div>
  );
}
