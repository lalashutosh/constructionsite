/** Deep-read UI: view cube (2D/3D, orbit, re-centre), layer toggles, "What's on this sheet" checklist, first-time tour. */
import { useEffect, useRef, useState } from "react";
import { Crosshair, Layers as LayersIcon, ChevronUp, ChevronDown, Pencil } from "lucide-react";
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
        <button title="Re-centre" aria-label="Re-centre the view" onClick={() => viewer()?.recenter()}><Crosshair size={13} aria-hidden="true" /></button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- layers
export const LAYER_COLOURS: Record<string, number> = { equipment: 0xf472b6, rooms: 0x94a3b8, envelope: 0xe7c98a, walls: 0xcbd5e1, furniture: 0x2dd4bf, piping: 0x3b82f6, electrical: 0xf59e0b };
const LAYER_NAMES: [string, string][] = [["envelope", "Envelope"], ["walls", "Walls"], ["furniture", "Furniture"], ["equipment", "Equipment tags"], ["piping", "Piping"], ["electrical", "Electrical"]];
export type Layers = { envelope?: [number, number][][]; walls?: [number, number][][]; furniture?: { id: string; kind: string; polygon: [number, number][] }[];
  equipment?: { label?: string | null; polygon: [number, number][] }[];
  piping?: [number, number][][]; electrical?: [number, number][][]; notes?: Record<string, string>; estimated?: boolean;
  quantities?: Record<string, { value: number; unit: string; tag: string; basis: string }> };
export function LayerToggles({ viewer, layers, extra }: { viewer: () => PlumbViewer | null; layers: Layers | null | undefined; extra?: Record<string, number> }) {
  const [on, setOn] = useState<Record<string, boolean>>({ envelope: true, walls: true, furniture: true, piping: true, electrical: true });
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { if (!msg) return; const t = setTimeout(() => setMsg(null), 3500); return () => clearTimeout(t); }, [msg]);
  const [open, setOpen] = useState(true);              // open and inviting by default
  if (!layers) return null;
  return (
    <div className={`layers ${open ? "open" : ""}`}>
      <button className="layers-btn" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <LayersIcon size={14} aria-hidden="true" /> Layers {open ? <ChevronDown size={13} aria-hidden="true" /> : <ChevronUp size={13} aria-hidden="true" />}</button>
      {open && <div className="layers-list">
      {LAYER_NAMES.filter(([k]) => k === "walls" || ((layers as Record<string, unknown[] | undefined>)[k]?.length ?? 0) > 0 || (extra?.[k] ?? 0) > 0).map(([k, label]) => {
        const has = true;
        const why = layers.notes?.[k];
        return (
          <button key={k} title={has ? `${label}: show / hide` : why || "not on this sheet"}
            className={`layer ${on[k] && has ? "on" : ""} ${has ? "" : "empty"}`}
            onClick={() => {
              if (!has) { setMsg(`${label}: ${why || "not on this sheet"}`); return; }
              const nv = !on[k]; setOn({ ...on, [k]: nv }); viewer()?.setLayerVisible(k, nv);
            }}>
            <i style={{ background: `#${LAYER_COLOURS[k].toString(16).padStart(6, "0")}` }} />{label}
            {layers.estimated && (k === "piping" || k === "electrical") && has ? <small className="est"> estimated</small> : null}
          </button>
        );
      })}
      {msg && <div className="layer-msg">{msg}</div>}
      {LAYER_NAMES.filter(([k]) => k !== "walls" && !((layers as Record<string, unknown[] | undefined>)[k]?.length) && !(extra?.[k])).length > 0 && (
        <p className="layer-none">Not on this sheet: {LAYER_NAMES.filter(([k]) => k !== "walls" && !((layers as Record<string, unknown[] | undefined>)[k]?.length) && !(extra?.[k])).map(([, l]) => l.toLowerCase()).join(", ")}</p>
      )}
      </div>}
    </div>
  );
}

// ---------------------------------------------------------------- checklist
export type Checklist = {
  deep: { on: boolean; reason: string; eta_s: number };
  rooms: { id: string; name: string; kind: string; area_m2: number | null; polygon: [number, number][]; counts: Record<string, number> }[];
  totals: { kind: string; label: string; count: number; ids: string[]; tier: "green" | "amber" | "grey"; note?: string; thumb?: string }[];
  elements: { id: string; kind: string; label: string; polygon: [number, number][]; room_id?: string | null }[];
  zones?: { name: string; polygon: [number, number][]; counts: Record<string, number> }[];
  summary?: string[];
  printed?: { title: string; text: string; kind: string }[];
  cost?: { usd: number; ms: number; names_cached?: boolean; first_usd?: number | null };
};
function costLine(c: NonNullable<Checklist["cost"]>) {
  const secs = `${(c.ms / 1000).toFixed(0)} s`;
  if (!c.names_cached) return <>{secs} · <b>${c.usd.toFixed(3)}</b> to read the whole sheet</>;
  if (c.first_usd != null) return <>{secs} · <b>${c.first_usd.toFixed(3)}</b> paid once, re-reads free</>;
  return <>{secs} · symbol names reused from an earlier read (its cost was not recorded)</>;
}

export function ChecklistPanel(p: { path: string | null; deepHint?: { on: boolean; eta_s: number; reason: string } | null;
  services?: Record<string, { value: number; unit: string; tag: string; basis: string }> | null;
  onShow: (polys: [number, number][][]) => void; onRoom: (id: string, poly: [number, number][]) => void;
  onLoaded?: (c: Checklist) => void }) {
  const [data, setData] = useState<Checklist | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [since, setSince] = useState(0);
  const [now, setNow] = useState(Date.now());
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { setData(null); setErr(null); if (p.path) void run(); }, [p.path]); // eslint-disable-line react-hooks/exhaustive-deps
  // the deep read is the normal read: it starts by itself when a drawing opens (cached per drawing after the first time)
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
  const rename = async (kind: string) => {
    const name = window.prompt("What is this symbol? (e.g. closet, TV, treadmill, sofa)", kind.startsWith("symbol type") ? "" : kind);
    if (!name || !p.path) return;
    const r = await fetch(`${BASE}/checklist/rename`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: p.path, kind, name }) });
    if (r.ok) { const c = (await r.json()) as Checklist; setData(c); p.onLoaded?.(c); }
  };
  if (!p.path) return null;
  const eta = data?.deep.eta_s ?? p.deepHint?.eta_s ?? 60;
  const byId = new Map((data?.elements ?? []).map((e) => [e.id, e]));
  return (
    <section className="cklist">
      <header><h3>What's on this sheet</h3>{data?.cost && <span className="ckcost">{costLine(data.cost)}</span>}</header>
      {(p.deepHint?.on || data?.deep.on) && !data && (
        <p className="deepnote">Deep read: this sheet is very detailed ({p.deepHint?.reason}). Counting every symbol takes about {Math.round(eta / 60) || 1} min.</p>
      )}
      {!data && !busy && err && <button className="btn" onClick={() => void run()}>Try again</button>}
      {busy && (() => {
        const el = (now - since) / 1000;
        const stages = ["Tracing the building and its rooms", "Finding every repeated symbol", "Naming each symbol type once",
          "Counting every copy (two ways)", "Doors, stairs, equipment tags", "Estimating pipework and electrical"];
        const k = Math.min(stages.length - 1, Math.floor((el / Math.max(eta, 1)) * stages.length));
        return (
          <div className="ckbusy live" role="status" aria-live="polite">
            <div className="ck-spin" aria-hidden="true" />
            <div className="ck-busytext">
              <b>Deep read in progress</b>
              <span>{stages[k]}…</span>
              <div className="bar"><i style={{ width: `${Math.min(96, (el / eta) * 100)}%` }} /></div>
              <small>{Math.round(el)} s of about {eta} s · keep exploring, results appear here when done</small>
            </div>
          </div>
        );
      })()}
      {err && <p className="err sm">{err}</p>}
      {data && (
        <>
          {!!data.summary?.length && (
            <div className="cksummary">
              <p className="lead">{data.summary[0]}</p>
              {data.summary.slice(1).map((t, i) => <p key={i}>{t}</p>)}
            </div>
          )}
          {!data.totals.length && <p className="muted sm">No repeated symbols or tagged equipment on this sheet.</p>}
          <ul className="cktotals">
            {data.totals.map((t) => (
              <li key={t.kind} onClick={() => p.onShow(t.ids.map((i) => byId.get(i)?.polygon).filter(Boolean) as [number, number][][])} title={t.note}>
                {t.thumb ? <img src={t.thumb} alt="" /> : <span className="ck-noimg" />}
                <span className="ck-name">{t.label.replace(/^Symbol Type (\d+)s$/, "Unnamed symbol $1")}
                  <small><i className={`dot ${t.tier}`} /> {t.tier === "green" ? "two checks agree" : "one check"}</small></span>
                <b>{t.count}</b>
                <button className="ck-rename" title="Wrong name? Rename this symbol (every copy follows)"
                  aria-label={`Rename ${t.label}`} onClick={(ev) => { ev.stopPropagation(); void rename(t.kind); }}><Pencil size={13} aria-hidden="true" /></button>
              </li>
            ))}
          </ul>
          {!!p.services && Object.keys(p.services).length > 0 && (
            <details className="ckrooms" open>
              <summary>Services, estimated (no MEP sheet in this set)</summary>
              <div className="svc-tiles">
                {Object.entries(p.services).map(([k, v]) => (
                  <div key={k} className={`svc-tile ${k}`} title={v.basis}>
                    <b>{v.value.toLocaleString()}{["m", "LU", "l/s"].includes(v.unit) ? <small> {v.unit}</small> : null}</b>
                    <span>{({ pipe_m: "Pipework", cable_m: "Cable", lights: "Light fittings (EN 12464-1)", sockets: "Sockets", wet_points: "Wet points",
                      loading_units: "Supply load (EN 806-3)", waste_flow_ls: "Waste flow (EN 12056-2)" } as Record<string, string>)[k] ?? k}</span>
                  </div>
                ))}
              </div>
              <p className="sm muted">How: {Object.values(p.services).map((v) => v.basis).filter((b, i, a) => a.indexOf(b) === i).slice(0, 2).join("; ")}.</p>
            </details>
          )}
          {!!data.zones?.length && (
            <details className="ckrooms" open>
              <summary>By wing / zone</summary>
              <ul>
                {data.zones.map((z) => (
                  <li key={z.name} onClick={() => p.onShow([z.polygon])}>
                    <span>{z.name}</span>
                    <div className="sm muted">{Object.entries(z.counts).sort((a, b) => b[1] - a[1]).map(([k, n]) => `${n} ${k}`).join(" · ")}</div>
                  </li>
                ))}
              </ul>
            </details>
          )}
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
  const key = `plumb-tour:${k}`;                         // a walk-through for every newly opened drawing
  const seenOf = () => { try { return localStorage.getItem(key) === "done"; } catch { return false; } };
  const [i, setI] = useState<number | null>(seenOf() ? null : 0);
  useEffect(() => { setI(seenOf() ? null : 0); }, [k]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (i !== null) steps[i]?.act?.(); }, [i, k]); // eslint-disable-line react-hooks/exhaustive-deps
  const done = () => { try { localStorage.setItem(key, "done"); } catch { /* private window */ } setI(null); };
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


// ---------------------------------------------------------------- service runs drawn over the building (build plan)
export function ServiceMap({ map, kind }: { map: { outline: [number, number][]; piping: [number, number][][]; electrical: [number, number][][];
  quantities: Record<string, { value: number; unit: string; basis: string }> }; kind: "piping" | "electrical" }) {
  const xs = map.outline.map((q) => q[0]), ys = map.outline.map((q) => q[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const pad = 0.04 * Math.max(x1 - x0, y1 - y0);
  const vb = `${x0 - pad} ${y0 - pad} ${x1 - x0 + 2 * pad} ${y1 - y0 + 2 * pad}`;
  const sw = Math.max(x1 - x0, y1 - y0) / 220;
  const lines = kind === "piping" ? map.piping : map.electrical;
  const col = kind === "piping" ? "#3b82f6" : "#f59e0b";
  const big = kind === "piping"
    ? [["pipe_m", "of pipework"], ["wet_points", "wet points"]]
    : [["cable_m", "of cable"], ["lights", "light fittings"], ["sockets", "sockets"]];
  return (
    <figure className="svcmap">
      <svg viewBox={vb} preserveAspectRatio="xMidYMid meet" role="img" aria-label={`${kind} runs over the building`}>
        <polygon points={map.outline.map((q) => q.join(",")).join(" ")} className="svc-outline" strokeWidth={sw * 1.5} />
        {lines.map((l, i) => <polyline key={i} points={l.map((q) => q.join(",")).join(" ")} fill="none" stroke={col} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" opacity={0.9} />)}
      </svg>
      <figcaption>
        <div className="svc-big">
          {big.filter(([k]) => map.quantities[k]).map(([k, w]) => (
            <span key={k}><b>{map.quantities[k].value.toLocaleString()}</b>{map.quantities[k].unit === "m" ? " m" : ""} <small>{w}</small></span>
          ))}
        </div>
        <small className="muted">Estimated: {map.quantities[kind === "piping" ? "pipe_m" : "cable_m"]?.basis}</small>
      </figcaption>
    </figure>
  );
}


// ---------------------------------------------------------------- build plan: headline numbers + finishes map
export function PlanHeadline({ basis, services }: { basis: Record<string, { value: number | null; unit: string; tag: string }>;
  services?: Record<string, { value: number; unit: string }> | null }) {
  const pick: [string, string, string][] = [["floor_area_m2", "floor area", "m²"], ["wall_area_m2", "wall area", "m²"],
    ["doors", "doors", ""], ["windows", "windows", ""]];
  const tiles = pick.filter(([k]) => basis[k]?.value != null && Number(basis[k].value) > 0)
    .map(([k, w, u]) => ({ k, v: Number(basis[k].value), w, u, est: basis[k].tag === "defaulted" }));
  for (const [k, w, u] of [["pipe_m", "pipework", "m"], ["cable_m", "cable", "m"]] as const)
    if (services?.[k]) tiles.push({ k, v: services[k].value, w, u, est: true });
  if (!tiles.length) return null;
  return (
    <div className="plan-head">
      {tiles.map((t) => (
        <div key={t.k} className={`ph-tile ${t.k}`}>
          <b>{Math.round(t.v).toLocaleString()}{t.u ? <small> {t.u}</small> : null}</b>
          <span>{t.w}{t.est ? " · est." : ""}</span>
        </div>
      ))}
    </div>
  );
}

export function FinishesMap({ map }: { map: NonNullable<import("./api").BuildPlan["finishes_map"]> }) {
  const xs = map.outline.map((q) => q[0]), ys = map.outline.map((q) => q[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const pad = 0.03 * Math.max(x1 - x0, y1 - y0);
  const [hot, setHot] = useState<string | null>(null);
  const tot = Object.entries(map.totals).sort((a, b) => b[1].m2 - a[1].m2);
  const sum = tot.reduce((a, [, v]) => a + v.m2, 0) || 1;
  return (
    <figure className="finmap">
      <figcaption><b>Floor finishes</b> <small className="muted">by room type · hover a finish</small></figcaption>
      <svg viewBox={`${x0 - pad} ${y0 - pad} ${x1 - x0 + 2 * pad} ${y1 - y0 + 2 * pad}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label="rooms coloured by floor finish">
        <polygon points={map.outline.map((q) => q.join(",")).join(" ")} className="svc-outline" />
        {map.rooms.map((r, i) => (
          <polygon key={i} points={r.polygon.map((q) => q.join(",")).join(" ")} fill={r.colour}
            opacity={hot && hot !== r.finish ? 0.18 : 0.85} className="fin-room"><title>{`${r.name}: ${r.finish}, ${r.area_m2} m²`}</title></polygon>
        ))}
      </svg>
      <div className="finbar" aria-hidden="true">{tot.map(([n, v]) => <i key={n} style={{ width: `${(v.m2 / sum) * 100}%`, background: v.colour }} />)}</div>
      <ul className="finlegend">
        {tot.map(([n, v]) => (
          <li key={n} onMouseEnter={() => setHot(n)} onMouseLeave={() => setHot(null)} onFocus={() => setHot(n)} onBlur={() => setHot(null)} tabIndex={0}>
            <i style={{ background: v.colour }} /><span>{n}</span><b>{v.m2.toFixed(1)} m²</b>
          </li>
        ))}
      </ul>
      <small className="muted">{map.note}</small>
    </figure>
  );
}
