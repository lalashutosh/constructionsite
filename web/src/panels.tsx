import { useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight, CircleCheck, CircleMinus, FolderUp, BookOpen, LayoutGrid, Moon, Play, Ruler, Square, Sun, TriangleAlert, Upload, X } from "lucide-react";
import { imageUrl, type BuildPlan, type Geometry, type Sample, type ScanCheck } from "./api";
import { fmtCost, fmtNum, reliabilityWord, sentenceOf, tierSentence, verdict, voterWord, type FindingSpec } from "./logic";
import type { ProofObject } from "./types";
import { PlumbViewer, THEMES, type Phase } from "./viewer3d";

export type ThemeName = "dark" | "light";

export interface Floor {
  key: string;
  path: string;
  name: string;
  credit: string | null;
  geo: Geometry | null;
  geoErr: string | null;
}
export interface FindingState {
  loading?: boolean;
  proof?: ProofObject;
  err?: string;
}
export interface Upload {
  path: string;
  name: string;
}

/* ---------- icons ---------- */
const ic = { size: 16, strokeWidth: 1.5, "aria-hidden": true } as const;
export const TierIcon = ({ tier }: { tier: "green" | "amber" | "grey" }) =>
  tier === "green" ? <CircleCheck {...ic} /> : tier === "amber" ? <TriangleAlert {...ic} /> : <CircleMinus {...ic} />;

/* ---------- left rail ---------- */
export function Rail(p: { onImage: () => void; onFolder: () => void; onDrawings: () => void; drawerOpen: boolean; theme: ThemeName; onTheme: () => void; howOn: boolean; onHow: () => void }) {
  return (
    <nav className="rail" aria-label="Tools">
      <div className="mark" title="Plumb">P</div>
      <button className="rbtn" data-tip="Upload image or plan (png, jpg, pdf, dxf, ifc, svg)" aria-label="Upload image" onClick={p.onImage}><Upload {...ic} /></button>
      <button className="rbtn" data-tip="Upload folder: files become stacked floors" aria-label="Upload folder" onClick={p.onFolder}><FolderUp {...ic} /></button>
      <button className={`rbtn ${p.drawerOpen ? "on" : ""}`} data-tip="Drawings: samples and your uploads" aria-label="Drawings" onClick={p.onDrawings}><LayoutGrid {...ic} /></button>
      <button className={`rbtn ${p.howOn ? "on" : ""}`} data-tip="How it works" aria-label="How it works" onClick={p.onHow}><BookOpen {...ic} /></button>
      <div className="grow" />
      <button className="rbtn" data-tip={p.theme === "dark" ? "Switch to light theme" : "Switch to dark theme"} aria-label="Toggle theme" onClick={p.onTheme}>
        {p.theme === "dark" ? <Sun {...ic} /> : <Moon {...ic} />}
      </button>
    </nav>
  );
}

/* ---------- drawings drawer ---------- */
export function Drawer(p: { samples: Sample[]; uploads: Upload[]; onPick: (path: string, name: string, credit?: string) => void; onClose: () => void }) {
  return (
    <aside className="drawer" aria-label="Drawings">
      <header>
        <h2>Drawings</h2>
        <button className="x" onClick={p.onClose} aria-label="Close drawings"><X {...ic} /></button>
      </header>
      <div className="dscroll">
        {p.uploads.length > 0 && <h3>Your uploads</h3>}
        {p.uploads.map((u) => (
          <button key={u.path} className="drow" onClick={() => p.onPick(u.path, u.name)}>
            <Thumb src={imageUrl(u.path)} />
            <span><b>{u.name}</b><small>uploaded</small></span>
          </button>
        ))}
        <h3>Samples</h3>
        {p.samples.map((s) => (
          <button key={s.id} className="drow" onClick={() => p.onPick(s.path, s.label, s.credit)}>
            <Thumb src={s.thumb || imageUrl(s.path)} />
            <span><b>{s.label}</b><small>{s.path.split("/").slice(1, 2)[0]}{s.kind === "not_plan" ? " · not a plan" : ""}</small></span>
          </button>
        ))}
      </div>
    </aside>
  );
}
function Thumb({ src }: { src: string }) {
  const [bad, setBad] = useState(false);
  return bad ? <i className="thumb ph" /> : <img className="thumb" src={src} alt="" loading="lazy" onError={() => setBad(true)} />;
}

/* ---------- shared bits ---------- */
/** A sentence with its numbers in bold. */
export function Sentence({ text }: { text: string }) {
  return <>{text.split(/(\d+(?:[.,]\d+)?)/).map((t, i) => (i % 2 ? <b key={i}>{t}</b> : <span key={i}>{t}</span>))}</>;
}
export interface BannerItem { label: string; value: number; unit: string }
function CountUp({ to, delay }: { to: number; delay: number }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { setV(to); return; }
    let raf = 0;
    const t0 = performance.now() + delay;
    const tick = () => {
      const u = Math.min(1, Math.max(0, (performance.now() - t0) / 900));
      setV(to * (1 - Math.pow(1 - u, 3)));
      if (u < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, delay]);
  return <span className="mono">{v.toFixed(to >= 100 ? 0 : 1)}</span>;
}

/* ---------- 3D viewer ---------- */
export type ScaleState = "off" | "pick" | "enter" | "payoff";
export function ViewerPane(p: {
  floors: Floor[];
  active: Floor | null;
  selected: { path: string; proof: ProofObject } | null;
  selFloor: Floor | undefined;
  showPins: boolean;
  hoverIdx: number | null;
  onHover: (i: number | null) => void;
  busy: string | null;
  onPickFloor: (k: string) => void;
  onOpenDrawings: () => void;
  stage: Phase[] | null;
  stageLabel: string | null;
  drawingOn: boolean;
  setDrawingOn: (b: boolean) => void;
  theme: ThemeName;
  scale: ScaleState;
  scaleKind: "defaulted" | "specified" | "chosen";
  scaleSrc: string | null;
  scaleIssue: { message: string; label: string | null; lengthM: number | null } | null;
  ppm: number | null;
  banner: BannerItem[] | null;
  applying: boolean;
  onScaleStart: () => void;
  onScaleCancel: () => void;
  onMeasured: (px: [number, number][]) => void;
  onApplyLength: (m: number, typed?: { v: number; unit: string }) => void;
  onWhyRead: () => void;
}) {
  const [len, setLen] = useState("");
  const [unit, setUnit] = useState<"m" | "cm" | "mm">("m");
  const [narr, setNarr] = useState<"reading" | "found" | "built">("reading");
  const host = useRef<HTMLDivElement>(null);
  const viewer = useRef<PlumbViewer | null>(null);
  const hoverCb = useRef(p.onHover);
  hoverCb.current = p.onHover;
  const measCb = useRef(p.onMeasured);
  measCb.current = p.onMeasured;

  useEffect(() => {
    const v = new PlumbViewer(host.current!, { onHoverPin: (i) => hoverCb.current(i) }, THEMES[p.theme]);
    viewer.current = v;
    return () => {
      v.dispose();
      viewer.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => viewer.current?.setTheme(THEMES[p.theme]), [p.theme]);
  const ready = p.floors.filter((f) => f.geo);
  const sig = ready.map((f) => f.key).join("|");
  useEffect(() => {
    void viewer.current?.setFloors(ready.map((f) => ({ key: f.key, label: f.name, geo: f.geo!, imgUrl: imageUrl(f.path) })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig, p.theme]);

  // story line: reading -> found -> built
  const a = p.active;
  const hasGeo = !!a?.geo;
  useEffect(() => {
    if (!hasGeo) { setNarr("reading"); return; }
    setNarr("found");
    const t = window.setTimeout(() => setNarr("built"), 2700);
    return () => window.clearTimeout(t);
  }, [hasGeo, a?.key]);

  const sf = p.selFloor;
  const mapped = !!(sf?.geo && sf.geo.coords === "pixels" && p.selected && p.selected.path === sf.key);
  const proof = p.selected?.proof;
  useEffect(() => {
    const pins = mapped && p.showPins && proof ? proof.evidence.map((e, i) => ({ idx: i + 1, polygon: e.polygon as [number, number][] })) : [];
    viewer.current?.setPins(mapped && p.showPins && sf ? sf.key : null, pins);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig, p.theme, mapped, p.showPins, proof?.id]);
  useEffect(() => viewer.current?.setHighlight(p.hoverIdx), [p.hoverIdx]);
  useEffect(() => viewer.current?.setDrawing(p.drawingOn), [p.drawingOn, sig, p.theme]);
  useEffect(() => viewer.current?.setStage(p.stage), [p.stage, sig, p.theme]);

  const measuring = p.scale === "pick" || p.scale === "enter";
  const mFloor = a?.key ?? null;
  useEffect(() => {
    viewer.current?.setMeasure(measuring ? mFloor : null, (px) => measCb.current(px));
  }, [measuring, mFloor]);
  useEffect(() => {
    if (p.scale === "pick") setLen("");
  }, [p.scale]);
  const topDown = p.scale !== "off";
  useEffect(() => viewer.current?.setTopDown(topDown), [topDown]);
  useEffect(() => viewer.current?.setDimensions(p.ppm ? mFloor : null, p.ppm), [p.ppm, mFloor, sig, p.theme]);

  const loading = a && !a.geo && !a.geoErr;
  const credit = a?.geo?.credit || p.selected?.proof.provenance.credit || a?.credit || (a ? "Uploaded by you; no licence text supplied." : "");
  const notMapped = !!(proof && sf?.geo && sf.geo.coords !== "pixels");
  const ck = a?.geo?.check;
  const plans = ck ? ck.views.filter((v) => v.type === "floor_plan").length : 0;
  const readers = ck && ck.views.some((v) => v.agreement != null) ? 2 : 1;
  const reviewers = ck?.reviewer?.used ? (ck.reviewer.models?.length ?? 0) : 0;
  const found = ck
    ? `Found ${plans} floor plan${plans === 1 ? "" : "s"}${reviewers ? ` · checked by ${readers} readers + ${reviewers} AI reviewers` : ""}`
    : "Found the drawing";
  const narrText = !a ? "" : narr === "reading" ? (a.geoErr ? "Could not read this drawing" : "Reading the drawing…") : narr === "found" ? found : "Built in 3D";

  return (
    <div className="viewer panel">
      <div ref={host} className="canvas" />
      <div className="vtitle">
        <span className="vname">{a ? a.name : "No drawing open"}</span>
        {p.floors.length > 1 && <span className="pill">{p.floors.length} floors</span>}
      </div>
      {a && (
        <div className="narr" role="status">
          <span key={narrText}>{narrText}</span>
          {narr === "built" && ck && <button className="linkbtn" onClick={p.onWhyRead}>Why?</button>}
          {narr === "built" && ck && ck.warnings.length > 0 && <span className="warnline"><TierIcon tier="amber" />Needs a look · {ck.warnings[0]}</span>}
        </div>
      )}
      {p.floors.length > 1 && (
        <div className="floorpills">
          {[...p.floors].reverse().map((f) => (
            <button key={f.key} className={`fpill ${f.key === a?.key ? "on" : ""}`} onClick={() => p.onPickFloor(f.key)}>{f.name}</button>
          ))}
        </div>
      )}
      {a && p.scale === "off" && (
        <div className="scalecta">
          <button className="ctabtn" onClick={p.onScaleStart}><Ruler {...ic} size={18} />{p.scaleKind === "specified" ? "Check real size" : p.scaleKind === "chosen" ? "Change real size" : "Set real size"}</button>
          {p.scaleKind === "defaulted" ? <span>One real measurement unlocks every size.</span> : <span title={p.scaleSrc ?? undefined}>{p.scaleKind === "specified" ? "Sizes from measurements printed on the drawing" : "Sizes from your measurement"}</span>}
        </div>
      )}
      {measuring && (
        <div className="measure">
          {p.scale === "pick" ? (
            <p>Click both ends of a wall or door you know</p>
          ) : (
            <div className="mform">
              <form onSubmit={(e) => { e.preventDefault(); const n = Number(len); if (n > 0) p.onApplyLength(n / (unit === "cm" ? 100 : unit === "mm" ? 1000 : 1), { v: n, unit }); }}>
                <label>How long is this? <input type="number" step="any" min="0" autoFocus value={len} onChange={(e) => setLen(e.target.value)} aria-label="Real length" />
                  <select value={unit} onChange={(e) => setUnit(e.target.value as "m" | "cm" | "mm")} aria-label="Unit"><option value="m">m</option><option value="cm">cm</option><option value="mm">mm</option></select></label>
                <button className="primary" type="submit" disabled={!(Number(len) > 0) || p.applying}>{p.applying ? "Working…" : "Set size"}</button>
              </form>
              {p.scaleIssue && (
                <p className="issue" role="alert"><TierIcon tier="amber" /><span>Needs a look · {p.scaleIssue.message}{" "}
                  {p.scaleIssue.label && p.scaleIssue.lengthM !== null && <button className="linkbtn" onClick={() => p.onApplyLength(p.scaleIssue!.lengthM!, { v: Number(len), unit: "cm" })}>{p.scaleIssue.label}</button>}</span></p>
              )}
            </div>
          )}
          <button className="linkbtn" onClick={p.onScaleCancel}>Cancel</button>
        </div>
      )}
      {p.banner && (
        <div className="banner" role="status">
          <span className="lbl">Unlocked by one measurement</span>
          <div className="bitems">
            {p.banner.map((b, i) => (
              <div key={b.label} className="bitem"><CountUp to={b.value} delay={i * 160} /><small>{b.unit} {b.label}</small></div>
            ))}
          </div>
        </div>
      )}
      {a && p.scale === "off" && (
        <label className="dtoggle" title="Show or hide the drawing under the model">
          <span>Drawing</span>
          <span className="seg2">
            <button type="button" className={p.drawingOn ? "on" : ""} onClick={() => p.setDrawingOn(true)}>on</button>
            <button type="button" className={!p.drawingOn ? "on" : ""} onClick={() => p.setDrawingOn(false)}>off</button>
          </span>
        </label>
      )}
      {p.stageLabel && <div className="stagecap">{p.stageLabel}</div>}
      {!a && (
        <div className="empty">
          <h1>Open a drawing</h1>
          <p>Upload a plan or pick a sample. Plumb builds it in 3D and answers with receipts.</p>
          <button className="primary" onClick={p.onOpenDrawings}>Browse samples</button>
        </div>
      )}
      {(loading || p.busy) && !p.busy && null}
      {p.busy && (
        <div className="loading" role="status"><span className="spin" /><div><b>{p.busy}</b></div></div>
      )}
      {a?.geoErr && <div className="loading err" role="alert"><div><b>Could not build the 3D view</b><small>{a.geoErr}</small></div></div>}
      {a?.geo && a.geo.walls.length === 0 && <div className="note-tl">No walls could be read from this file.</div>}
      {notMapped && <div className="note-tr">exact file read: pins not mapped to this view</div>}
      {a?.geo?.cost && <div className="readcost mono">Read once in {(a.geo.cost.ms / 1000).toFixed(1)} s{a.geo.cost.llm_calls > 0 ? ` · ${a.geo.cost.llm_calls} LLM review${a.geo.cost.llm_calls > 1 ? "s" : ""}` : ""} · ${a.geo.cost.usd.toFixed(4)}</div>}
      <div className="credit" title={credit}>{a ? credit : ""}</div>
    </div>
  );
}

/* ---------- ask bar ---------- */
export function Ask(p: { active: Floor | null; chips: string[]; selected: ProofObject | null; asking: boolean; err: string | null; onAsk: (q: string) => void; onWhy: () => void }) {
  const [q, setQ] = useState("");
  const send = (t: string) => {
    setQ(t);
    p.onAsk(t);
  };
  const pr = p.selected;
  const v = pr ? verdict(pr) : null;
  return (
    <div className="ask">
      <form className="askform" onSubmit={(e) => { e.preventDefault(); p.onAsk(q); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask anything about this drawing" aria-label="Question" disabled={!p.active} />
        <button type="submit" className="primary" disabled={!p.active || p.asking || !q.trim()}>{p.asking ? "Asking…" : "Ask"}</button>
      </form>
      <div className="chips">
        {p.chips.slice(0, 5).map((c) => (
          <button key={c} className="chip" disabled={!p.active || p.asking} onClick={() => send(c)}>{c}</button>
        ))}
      </div>
      {p.err && <div className="errline" role="alert">Engine problem: {p.err}</div>}
      {pr && v ? (
        <div className={`answer ${v.tier} ${p.asking ? "stale" : ""}`}>
          <p className="asent"><Sentence text={sentenceOf(pr)} /></p>
          <p className="ameta">
            <span className={`status ${v.tier}`}><TierIcon tier={v.tier} />{reliabilityWord(pr)}</span>
            <span className="cost mono">{fmtCost(pr)}</span>
            <button className="linkbtn" onClick={p.onWhy}>Why?</button>
          </p>
        </div>
      ) : (
        <div className="answer empty-a">{p.active ? "Pick a finding, or ask a question." : "Open a drawing to start."}</div>
      )}
    </div>
  );
}

/* ---------- findings ---------- */
const viewLabel = (t: string) => { const w = t.replace(/_/g, " "); return w.charAt(0).toUpperCase() + w.slice(1); };
export function Findings(p: {
  active: Floor | null;
  specs: FindingSpec[];
  states: Record<string, FindingState>;
  floors: Floor[];
  activeKey: string | null;
  onPickFloor: (k: string) => void;
  selectedId: string | null;
  onSelect: (p: ProofObject) => void;
  onWhy: (p: ProofObject) => void;
  seg: ReactNode;
}) {
  return (
    <div className="findings panel">
      {p.seg}
      <div className="phead"><h2 className="ttl">{p.active ? p.active.name : "Findings"}</h2></div>
      {p.floors.length > 1 && (
        <div className="fchips">
          {p.floors.map((f) => (
            <button key={f.key} className={`chip sm ${f.key === p.activeKey ? "on" : ""}`} onClick={() => p.onPickFloor(f.key)}>{f.name}</button>
          ))}
        </div>
      )}
      <ul className="flist">
        {!p.active && <li className="muted pad">Findings appear here once a drawing is open.</li>}
        {p.specs.map((s) => {
          const st = p.states[s.key];
          if (!st) return null;
          if (st.loading) return <li key={s.key} className="frow wait"><span className="ficon"><span className="spin sm" /></span><span className="ftext"><span className="fsent muted">Counting {s.noun}…</span></span></li>;
          if (st.err || !st.proof) return <li key={s.key} className="frow grey"><span className="ficon"><TierIcon tier="grey" /></span><span className="ftext"><span className="fsent">{s.noun}: can't answer.</span><small>{st.err}</small></span></li>;
          const pr = st.proof;
          const v = verdict(pr);
          return (
            <li key={s.key} className={`frow ${v.tier} ${pr.id === p.selectedId ? "sel" : ""}`}>
              <button className="fmain" onClick={() => p.onSelect(pr)}>
                <span className={`ficon ${v.tier}`}><TierIcon tier={v.tier} /></span>
                <span className="ftext">
                  <span className="fsent"><Sentence text={sentenceOf(pr)} /></span>
                  <small>{reliabilityWord(pr)}</small>
                </span>
              </button>
              <button className="linkbtn why" onClick={() => p.onWhy(pr)}>Why?</button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Chips({ ids, proof, hover, onHover }: { ids: string[]; proof: ProofObject; hover: number | null; onHover: (i: number | null) => void }) {
  const idxs = ids.map((id) => proof.evidence.findIndex((e) => e.id === id) + 1).filter((n) => n > 0);
  if (!idxs.length) return null;
  const shown = idxs.slice(0, 20);
  return (
    <span className="echips">
      {shown.map((n) => (
        <span key={n} className={`echip mono ${hover === n ? "hot" : ""}`} onMouseEnter={() => onHover(n)} onMouseLeave={() => onHover(null)}>{n}</span>
      ))}
      {idxs.length > shown.length && <span className="muted">+{idxs.length - shown.length}</span>}
    </span>
  );
}

export function Know(p: {
  proof: ProofObject | null;
  floor: Floor | null;
  hoverIdx: number | null;
  onHover: (i: number | null) => void;
  showPins: boolean;
  setShowPins: (b: boolean) => void;
  imgUrl: string;
  check: ScanCheck | null;
  onClose: () => void;
}) {
  const pr = p.proof;
  const close = <button className="x" onClick={p.onClose} aria-label="Close"><X {...ic} /></button>;
  if (!pr) {
    return (
      <aside className="sheet" aria-label="Why">
        <div className="phead"><h2 className="ttl">How the drawing was read</h2>{close}</div>
        <div className="kscroll">
          {p.check && p.check.views.length > 0 ? (
            <>
              <p className="muted pad0">Views found on this sheet</p>
              <ol className="steps">
                {p.check.views.map((v) => (
                  <li key={v.n}>
                    <span className="sn mono">{v.n}</span>
                    <div>
                      <b>{viewLabel(v.type)}</b>
                      {v.type_source && <p>{v.type_source}</p>}
                      <p className="muted">{[v.reader ? `Walls read by ${v.reader}` : "No walls read", v.agreement != null ? `agreement ${Math.round(v.agreement * 100)}%` : null].filter(Boolean).join(" · ")}</p>
                      {v.why && <p className="muted">{v.why}</p>}
                      {v.flags?.map((f) => <p key={f} className="muted">{f}</p>)}
                    </div>
                  </li>
                ))}
              </ol>
            </>
          ) : (
            <div className="muted pad0">Select a finding or ask a question to see the steps behind the number.</div>
          )}
        </div>
      </aside>
    );
  }
  const v = verdict(pr);
  const prov = pr.provenance;
  const tierS = tierSentence(pr);
  const extra = pr.notes.filter((n) => !n.startsWith("tier:") && !n.startsWith("triage:"));
  const canPins = !!(p.floor?.geo && p.floor.geo.coords === "pixels");
  const kinds = new Map<string, number>();
  pr.evidence.forEach((e) => kinds.set(e.kind, (kinds.get(e.kind) ?? 0) + 1));
  let n = 0;
  const step = () => ++n;
  return (
    <aside className="sheet" aria-label="Why">
      <div className="phead"><h2 className="ttl">Why this answer</h2>{close}</div>
      <p className="sheetq"><Sentence text={sentenceOf(pr)} /> <span className={`status sm ${v.tier}`}><TierIcon tier={v.tier} />{v.word}</span></p>
      <div className="kscroll">
        <ol className="steps">
          <li>
            <span className="sn mono">{step()}</span>
            <div>
              <b>Which file was read</b>
              <p className="mono sm">{prov.file}</p>
              {prov.resolved_from ? <p>Read from the exact .{prov.resolved_from} version of this drawing.</p> : prov.fmt ? <p>Read as a .{prov.fmt} file.</p> : null}
            </div>
          </li>
          {pr.voters.length > 0 ? (
            <li>
              <span className="sn mono">{step()}</span>
              <div>
                <b>{pr.voters.length === 1 ? "The check that was run" : `${pr.voters.length} independent checks`}</b>
                {pr.voters.map((vt) => (
                  <div key={vt.name} className="vrow">
                    <p>
                      <span className="cap">{voterWord(vt.name)}</span> found <span className="mono val">{fmtNum(vt.value)}</span>
                      {vt.runs.length > 1 && <span className="muted"> (runs: {vt.runs.join(", ")})</span>}
                    </p>
                    {vt.note && <p className="muted">{vt.note}</p>}
                    <Chips ids={vt.element_ids} proof={pr} hover={p.hoverIdx} onHover={p.onHover} />
                  </div>
                ))}
              </div>
            </li>
          ) : (
            <li>
              <span className="sn mono">{step()}</span>
              <div><b>Checks</b><p className="muted">No separate checks were recorded for this answer.</p></div>
            </li>
          )}
          <li>
            <span className="sn mono">{step()}</span>
            <div>
              <b>Assumptions</b>
              {pr.assumptions.length ? (
                pr.assumptions.map((a) => (
                  <p key={a.key}>
                    <span className="mono">{a.key} = {fmtNum(a.value)}{a.unit ? ` ${a.unit}` : ""}</span> <span className={`tag ${a.tag}`}>{a.tag}</span> <span className="muted">from {a.source}</span>
                  </p>
                ))
              ) : (
                <p className="muted">None recorded.</p>
              )}
            </div>
          </li>
          <li>
            <span className="sn mono">{step()}</span>
            <div>
              <b>How the final number was chosen</b>
              <p>{tierS ?? v.pill + "."}</p>
              {extra.map((e) => <p key={e} className="muted">{e}</p>)}
              {pr.refusal && <p>Refusal reason: {pr.refusal}</p>}
            </div>
          </li>
        </ol>
        <div className="sources">
          <h3>Sources</h3>
          <p><span className="muted">File</span> <span className="mono sm">{prov.file.split("/").pop()}</span></p>
          {prov.credit && <p className="muted sm">{prov.credit}</p>}
          <p>
            <span className="muted">Elements</span> <span className="mono">{pr.evidence.length}</span>
            {pr.evidence.length > 0 && <span className="muted"> ({[...kinds].map(([k, c]) => `${c} ${k}`).join(", ")})</span>}
          </p>
          {pr.evidence.length > 0 && (
            <label className={`toggle ${canPins ? "" : "off"}`}>
              <input type="checkbox" checked={p.showPins && canPins} disabled={!canPins} onChange={(e) => p.setShowPins(e.target.checked)} />
              <span>show on model</span>
              {!canPins && <small className="muted">exact file read: pins not mapped to this view</small>}
            </label>
          )}
        </div>
      </div>
    </aside>
  );
}

/* ---------- right column mode switch ---------- */
export function Seg({ mode, onMode }: { mode: "findings" | "plan"; onMode: (m: "findings" | "plan") => void }) {
  return (
    <div className="seg" role="tablist" aria-label="Right column view">
      <button role="tab" aria-selected={mode === "findings"} className={mode === "findings" ? "on" : ""} onClick={() => onMode("findings")}>Findings</button>
      <button role="tab" aria-selected={mode === "plan"} className={mode === "plan" ? "on" : ""} onClick={() => onMode("plan")}>Build plan</button>
    </div>
  );
}

/* ---------- build plan ---------- */
const GROUP_ORDER = ["Structure", "Openings", "Electrical", "Plumbing", "Finishes", "Fit-out"];
export function BuildPanel(p: {
  plan: BuildPlan | null;
  vibe: string;
  onVibe: (v: string) => void;
  stepIdx: number | null;
  onStep: (i: number) => void;
  playing: boolean;
  onPlay: () => void;
  seg: ReactNode;
  hasDrawing: boolean;
  onSetSize: () => void;
  onInput: (key: string, value: number) => void;
  scaleKind: "defaulted" | "specified" | "chosen";
  scaleSrc: string | null;
  flash: string[];
}) {
  const [view, setView] = useState<"steps" | "list">("list");
  const [open, setOpen] = useState<string | null>(null);
  const [evOpen, setEvOpen] = useState(false);
  const [it, setIt] = useState("");
  const pl = p.plan;
  const groups = new Map<string, BuildPlan["checklist"]>();
  pl?.checklist.forEach((c) => groups.set(c.group, [...(groups.get(c.group) ?? []), c]));
  const ordered = [...groups].sort((a, b) => {
    const ia = GROUP_ORDER.indexOf(a[0]);
    const ib = GROUP_ORDER.indexOf(b[0]);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
  return (
    <div className="findings panel">
      {p.seg}
      {!p.hasDrawing ? (
        <div className="muted pad">Open a drawing to get a build plan.</div>
      ) : !pl ? (
        <div className="muted pad row"><span className="spin" /> Working out the build plan…</div>
      ) : (
        <>
          <div className="bhead">
            <button className="bld" onClick={() => setEvOpen((o) => !o)} aria-expanded={evOpen} title="Show why">
              <span>Building: <b>{pl.building.label}</b> · {pl.building.confidence} confidence</span>
              <span className="muted">{evOpen ? <ChevronDown {...ic} /> : <ChevronRight {...ic} />}</span>
            </button>
            {evOpen && <ul className="evl">{pl.building.evidence.map((e) => <li key={e}>{e}</li>)}</ul>}
            {p.scaleKind === "defaulted" && <p className="estnote">Sizes are estimated from a typical 0.9 m door. <button className="linkbtn" onClick={p.onSetSize}>Set real size</button> for exact quantities.</p>}
            {p.scaleKind === "specified" && <p className="estnote" title={p.scaleSrc ?? undefined}>Sizes from measurements printed on the drawing. <button className="linkbtn" onClick={p.onSetSize}>Check real size</button></p>}
            {p.scaleKind === "chosen" && <p className="estnote">Sizes from your measurement.</p>}
            {pl.mock && <div className="mocknote">Sample plan shape: the engine's plan endpoint did not answer.</div>}
            <div className="vibes">
              {pl.vibes.map((v) => (
                <button key={v.id} className={`chip sm ${p.vibe === v.id ? "on" : ""}`} title={v.blurb} onClick={() => p.onVibe(v.id)}>{v.label}</button>
              ))}
            </div>
            <div className="subseg">
              <button className={view === "list" ? "on" : ""} onClick={() => setView("list")}>Materials</button>
              <button className={view === "steps" ? "on" : ""} onClick={() => setView("steps")}>Build steps</button>
              <button className="play" onClick={() => { setView("steps"); p.onPlay(); }}>{p.playing ? <><Square {...ic} size={12} /> Stop</> : <><Play {...ic} size={12} /> Play</>}</button>
            </div>
          </div>
          {view === "steps" ? (
            <ol className="stepper">
              {pl.steps.map((st, i) => (
                <li key={st.id}>
                  <button className={`stp ${p.stepIdx === i ? "sel" : ""} ${p.stepIdx !== null && i < p.stepIdx ? "past" : ""}`} onClick={() => p.onStep(i)}>
                    <span className="sn mono">{st.n}</span>
                    <span><b>{st.title}</b><small>{st.why}</small></span>
                  </button>
                </li>
              ))}
            </ol>
          ) : (
            <div className="flist">
              {ordered.map(([g, items]) => (
                <div key={g} className="cgroup">
                  <h3>{g}</h3>
                  {items.map((c) => {
                    const needsIt = c.qty === null && (c.per === "it_load_kw" || /it.?load/i.test(c.basis));
                    const src = c.per ? pl.basis[c.per]?.source : null;
                    return (
                      <div key={c.id}>
                        <div className={`crow ${p.flash.includes(c.id) ? "flash" : ""}`}>
                          <button className="cit" onClick={() => setOpen(open === c.id ? null : c.id)} aria-expanded={open === c.id}>{c.item}</button>
                          {c.qty === null ? (
                            needsIt ? (
                              <form className="itin" onSubmit={(e) => { e.preventDefault(); const n = Number(it); if (n > 0) p.onInput("it_load_kw", n); }}>
                                <span className="muted sm">needs your input</span>
                                <input type="number" step="any" min="0" value={it} onChange={(e) => setIt(e.target.value)} aria-label="IT load in kW" className="mono" /> <span className="muted sm">kW</span>
                                <button className="linkbtn" type="submit">Apply</button>
                              </form>
                            ) : (
                              <span className="sm">needs real size · <button className="linkbtn" onClick={p.onSetSize}>Set real size</button></span>
                            )
                          ) : (
                            <>
                              <span className="mono cq">{typeof c.qty === "number" ? fmtNum(c.qty) : c.qty} <small>{c.unit}</small></span>
                              <span className={`tag ${c.tag}`}>{c.tag}</span>
                            </>
                          )}
                        </div>
                        {open === c.id && <p className="cbasis muted">{c.basis}{src ? <><br />source: {src}</> : null}</p>}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
