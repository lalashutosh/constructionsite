import { useCallback, useEffect, useMemo, useState } from "react";
import { DEMO_FIXTURES, fetchClaims, fetchFacts, fetchProof, fetchSamples, initMode, liveAsk, liveClearOverrides, liveOverride, liveScale, liveUpload, loadImage, type ImageInfo, type Mode, type Sample } from "./api";
import type { Element, Interval, ProofObject, Scalar, SheetFacts } from "./types";
import { duelReaders, effective, findings, readersShareSpace, receipt, type Ruling } from "./derive";
import { disputedIds } from "./derive";
import { EvidenceStack, type ScanImage, type ViewMode } from "./components/EvidenceStack";
import { AnswerCard } from "./components/AnswerCard";
import { ReceiptPanel } from "./components/ReceiptPanel";
import { DecisionCards } from "./components/DecisionCards";
import { FindingsList } from "./components/FindingsList";
import { ScaleAsk, type ScaleAnswer } from "./components/ScaleAsk";
import { SampleStrip } from "./components/SampleStrip";
import { ScaleDrawer } from "./components/ScaleDrawer";
import { CostMeter } from "./components/CostMeter";
import { TrustLens } from "./components/TrustLens";
import { Hook } from "./components/Hook";
import { Lab } from "./Lab";

type Tab = "answer" | "receipt" | "decide" | "findings";
const TABS: { id: Tab; label: string }[] = [
  { id: "answer", label: "Answer" },
  { id: "receipt", label: "Receipt" },
  { id: "decide", label: "Decide" },
  { id: "findings", label: "Findings" },
];

export interface Loaded {
  proofs: Record<string, ProofObject>;
  facts: Record<string, SheetFacts | null>;
}

export async function loadAll(): Promise<Loaded> {
  const proofs: Record<string, ProofObject> = {};
  const facts: Record<string, SheetFacts | null> = {};
  await Promise.all(
    DEMO_FIXTURES.map(async (f) => {
      try {
        const p = await fetchProof(f);
        proofs[f.id] = p;
        facts[f.id] = await fetchFacts(p);
      } catch {
        /* fixture missing: simply not offered */
      }
    }),
  );
  return { proofs, facts };
}

export function mergeElements(proof: ProofObject, facts: SheetFacts | null): Element[] {
  // two readers in different coordinate spaces (a vector file and its PDF render) cannot share one canvas:
  // draw the first reader's elements and leave the other's out of the picture (still counted in the receipt)
  let evidence = proof.evidence;
  const r = duelReaders(proof);
  if (r.length >= 2 && !readersShareSpace(proof)) {
    const drop = new Set(r[1].ids.filter((id) => !r[0].ids.includes(id)));
    evidence = evidence.filter((e) => !drop.has(e.id));
  }
  const ids = new Set(evidence.map((e) => e.id));
  return [...(facts?.elements ?? []).filter((e) => !ids.has(e.id)), ...evidence];
}

export function sizeOf(facts: SheetFacts | null) {
  return facts?.width_px && facts.height_px ? { w: facts.width_px, h: facts.height_px } : null;
}

function useQuery() {
  return useMemo(() => new URLSearchParams(window.location.search), []);
}

export default function App() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const f = () => setHash(window.location.hash);
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  if (hash.startsWith("#/lab")) return <Lab name={hash.split("/")[2] ?? ""} />;
  return <Main />;
}

function withCredit(p: ProofObject, s: Sample | undefined): ProofObject {
  if (!s) return p;
  // the credit string from the dataset's LICENSE.md wins over the engine's short form
  return { ...p, provenance: { ...p.provenance, credit: s.credit } };
}

function Main() {
  const q = useQuery();
  const [apiMode, setApiMode] = useState<Mode | null>(null);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [claims, setClaims] = useState<Record<string, unknown> | null>(null);
  const [fx, setFx] = useState(q.get("fx") ?? "doors");
  const [tab, setTab] = useState<Tab>((q.get("tab") as Tab) ?? "answer");
  const [mode, setMode] = useState<ViewMode>((q.get("view") as ViewMode) ?? "reading");
  const [explode, setExplode] = useState(1);
  const [wipe, setWipe] = useState(50);
  const [lens, setLens] = useState(false);
  const [hover, setHover] = useState<string[]>([]);
  const [pinned, setPinned] = useState<string | null>(null);
  const [ruling, setRuling] = useState<Ruling>(q.get("rule") === "yes" ? "yes" : null);
  const [chosen, setChosen] = useState<Record<string, Scalar>>({});
  const [vibe, setVibe] = useState<string | null>(null);
  const [asking, setAsking] = useState(q.get("ask") === "1");
  const [askDismissed, setAskDismissed] = useState<string[]>([]);
  const [hook, setHook] = useState(q.get("hook") !== "0");
  const [hookRun, setHookRun] = useState(0);
  const hookAt = Number(q.get("hookAt") ?? 0);
  // live mode
  const [samples, setSamples] = useState<Sample[]>([]);
  const [sampleId, setSampleId] = useState<string>(q.get("sample") ?? "");
  const [question, setQuestion] = useState("");
  const [scan, setScan] = useState<ImageInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [overridden, setOverridden] = useState(false);
  const [seen, setSeen] = useState<Record<string, Interval>>({});
  const [scaleDrawer, setScaleDrawer] = useState(false);
  const live = apiMode === "live";
  const sample = samples.find((s) => s.id === sampleId);

  const runLive = useCallback(async (s: Sample, text: string, keepOverrides = false) => {
    setBusy(true);
    setErr(null);
    try {
      if (!keepOverrides) await liveClearOverrides(s.path).catch(() => undefined);
      const [pr, img] = await Promise.all([liveAsk(s.path, text), loadImage(s.path)]);
      const p = withCredit(pr, s);
      const f = await fetchFacts(p);
      setScan(img);
      setLoaded({ proofs: { live: p }, facts: { live: f } });
      setFx("live");
      setQuestion(text);
      setOverridden(false);
      setRuling(null);
      setPinned(null);
      setHover([]);
      setChosen({});
    } catch (e) {
      setErr(`The engine did not answer (${(e as Error).message}).`);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    let off = false;
    void fetchClaims().then(setClaims);
    void initMode().then(async (m) => {
      if (off) return;
      setApiMode(m);
      if (m === "fixtures") {
        setLoaded(await loadAll());
        return;
      }
      const list = await fetchSamples();
      setSamples(list);
      const first = list.find((s) => s.id === q.get("sample")) ?? list[0];
      if (first) {
        setSampleId(first.id);
        const text = q.get("q") ? first.questions[Number(q.get("q"))]?.text ?? first.questions[0].text : first.questions[0].text;
        await runLive(first, text);
      }
    });
    return () => {
      off = true;
    };
  }, [q, runLive]);

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setPinned(null);
        setHover([]);
        setAsking(false);
        setScaleDrawer(false);
      }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);

  const proof = loaded?.proofs[fx] ?? null;
  const facts = loaded?.facts[fx] ?? null;
  const elements = useMemo(() => (proof ? mergeElements(proof, facts) : []), [proof, facts]);
  const eff = useMemo(() => (proof ? effective(proof, live ? null : ruling) : null), [proof, ruling, live]);
  const dis = useMemo(() => (proof ? disputedIds(proof) : []), [proof]);
  const anchorIds = useMemo(() => proof?.scale?.anchors.flatMap((a) => a.element_ids) ?? [], [proof]);
  const doorsCtx = useMemo(() => elements.filter((e) => e.kind === "door"), [elements]);
  const readers = useMemo(() => (proof && proof.kind === "count" && readersShareSpace(proof) ? duelReaders(proof) : []), [proof]);

  // the widest interval seen for this drawing + question: the "before" band the collapse is measured against
  const bandKey = proof ? `${proof.provenance.file}|${proof.question}` : "";
  useEffect(() => {
    if (!proof?.interval || !live) return;
    setSeen((m) => {
      const old = m[bandKey];
      const lo = old ? Math.min(old.lo, proof.interval!.lo) : proof.interval!.lo;
      const hi = old ? Math.max(old.hi, proof.interval!.hi) : proof.interval!.hi;
      return old && old.lo === lo && old.hi === hi ? m : { ...m, [bandKey]: { lo, hi } };
    });
  }, [proof, live, bandKey]);

  const axis = useMemo<Interval | null>(() => {
    if (!proof?.interval) return null;
    let lo: number;
    let hi: number;
    if (live) {
      const w = seen[bandKey] ?? proof.interval;
      lo = Math.min(w.lo, proof.interval.lo);
      hi = Math.max(w.hi, proof.interval.hi);
    } else {
      if (!loaded) return null;
      const same = Object.values(loaded.proofs).filter((p) => p.question === proof.question && p.interval);
      lo = Math.min(...same.map((p) => p.interval!.lo));
      hi = Math.max(...same.map((p) => p.interval!.hi));
    }
    const pad = Math.max((hi - lo) * 0.08, 1e-6);
    return { lo: Math.max(0, lo - pad), hi: hi + pad };
  }, [proof, loaded, live, seen, bandKey]);

  const pick = useCallback((id: string) => {
    setFx(id);
    setRuling(null);
    setPinned(null);
    setHover([]);
    setChosen({});
    setVibe(null);
    setTab("answer");
  }, []);

  const pickSample = useCallback(
    (s: Sample) => {
      setSampleId(s.id);
      setTab("answer");
      void runLive(s, s.questions[0].text);
    },
    [runLive],
  );

  const upload = useCallback(
    async (f: File) => {
      setBusy(true);
      try {
        const path = await liveUpload(f);
        const s: Sample = {
          id: `upload-${Date.now()}`,
          path,
          label: f.name,
          tags: ["your drawing"],
          kind: "plan",
          credit: "Your own upload. Not shared.",
          thumb: "",
          questions: [
            { label: "Doors", text: "How many doors are shown on this floor plan?" },
            { label: "Floor area", text: "What is the total net floor area in m²?" },
          ],
        };
        setSamples((l) => [...l, s]);
        setSampleId(s.id);
        await runLive(s, s.questions[0].text);
      } catch (e) {
        setErr(`Upload failed (${(e as Error).message}).`);
      } finally {
        setBusy(false);
      }
    },
    [runLive],
  );

  const endHook = useCallback(() => setHook(false), []);

  if (!loaded || !proof || !eff) {
    return (
      <div className="lab" role="status">
        {err ?? (apiMode === null ? "Connecting…" : busy ? "Reading the drawing…" : "Loading proof…")}
      </div>
    );
  }

  const focusId = pinned && dis.includes(pinned) ? pinned : dis[0] ?? null;

  const onRule = async (r: Ruling) => {
    if (!live || !sample) {
      setRuling(r);
      return;
    }
    if (!r || !focusId) return;
    const el = elements.find((e) => e.id === focusId);
    if (!el) return;
    setBusy(true);
    setErr(null);
    try {
      const p = withCredit(await liveOverride(sample.path, question, el, r === "yes"), sample);
      setLoaded((l) => (l ? { ...l, proofs: { ...l.proofs, live: p } } : l));
      setOverridden(true);
      setPinned(null);
    } catch (e) {
      setErr(`Could not record your verdict (${(e as Error).message}).`);
    } finally {
      setBusy(false);
    }
  };
  const onUndo = async () => {
    if (!live || !sample) {
      setRuling(null);
      return;
    }
    await liveClearOverrides(sample.path).catch(() => undefined);
    await runLive(sample, question, true);
  };

  const onScale = async (a: ScaleAnswer) => {
    if (!live || !sample) {
      setAsking(false);
      pick("area_after");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const out = await liveScale(sample.path, [{ kind: "user", px_length: a.px_length, length_m: a.length_m, element_ids: [a.element_id], note: `you: this door is ${a.length_m} m wide` }], [question]);
      const p = withCredit(out[0], sample);
      setLoaded((l) => (l ? { ...l, proofs: { ...l.proofs, live: p } } : l));
      setAsking(false);
    } catch (e) {
      setErr(`Could not apply the scale (${(e as Error).message}).`);
    } finally {
      setBusy(false);
    }
  };

  const highlight = hover.length ? hover : pinned ? [pinned] : [];
  const userAnchored = proof.scale?.anchors.some((a) => a.kind === "user") ?? false;
  const canAsk = live
    ? proof.kind === "area" && Boolean(proof.interval) && proof.tier === "amber" && !userAnchored && doorsCtx.length > 0
    : proof.kind === "area" && proof.tier === "amber" && Boolean(loaded.proofs["area_after"]) && fx === "area_before";
  const fin = findings(proof, live ? null : ruling, chosen);
  const lines = receipt(proof, chosen, vibe);
  const showAsk = asking || (!live && proof.scale?.needs_user === true && proof.kind === "area" && !askDismissed.includes(fx) && !hook);
  const scanImg: ScanImage | null = scan ? { url: scan.url, coords: scan.coords } : null;
  const pixelScan = scan?.coords === "pixels" ? { w: scan.w, h: scan.h } : null;
  const size = pixelScan ?? sizeOf(facts);
  const answerIds = readers[0]?.ids ?? proof.evidence.map((e) => e.id);
  const hookCaption = sample ? `A {w} px scan.${sample.tags.includes("finnish") ? " Finnish labels." : ""}${sample.tags.includes("no scale") ? " No scale." : ""}` : undefined;
  const hookOn = hook && (live ? proof.tier !== "grey" && answerIds.length > 0 && Boolean(pixelScan) : fx === "doors");
  const twoVoters = proof.kind === "count" ? proof.voters.filter((v) => v.value != null).slice(0, 2) : [];
  const rA = twoVoters[0];
  const rB = twoVoters[1];

  return (
    <div className={`app ${live ? "app--live" : ""}`}>
      {hookOn && (
        <Hook key={hookRun} proof={proof} elements={elements} size={size} answerIds={answerIds} onDone={endHook} startAt={hookAt} scan={scanImg?.coords === "pixels" ? scanImg : null} caption0={hookCaption} />
      )}
      <header className="top">
        <span className="brand">
          <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
            <path d="M10 2v13M4 15h12M7 18h6" stroke="#7dd3fc" strokeWidth="1.8" fill="none" strokeLinecap="round" />
            <circle cx="10" cy="15" r="2.4" fill="#7dd3fc" />
          </svg>
          Plumb
        </span>
        <span className="file" title={proof.provenance.file}>{proof.provenance.file.split("/").pop()}</span>
        <span className="pill">{proof.tier === "grey" ? "refused" : facts?.sheet_type?.replace(/_/g, " ") ?? "sheet"}</span>
        {!live && (
          <select aria-label="demo question" value={fx} onChange={(e) => pick(e.target.value)}>
            {DEMO_FIXTURES.filter((f) => loaded.proofs[f.id]).map((f) => (
              <option key={f.id} value={f.id}>
                {f.label}
              </option>
            ))}
          </select>
        )}
        <span className="spacer" />
        {busy && <span className="pill pill--busy" role="status">working…</span>}
        <button className="toggle" onClick={() => { setHook(true); setHookRun((n) => n + 1); }} title="Replay the 10-second opening">
          Replay intro
        </button>
        <label className="asof" title="Needs a second revision of this drawing. None loaded yet.">
          as of revision
          <input type="range" min={0} max={1} defaultValue={0} disabled aria-label="as of revision" />
          <span>{proof.provenance.revision ?? "only one"}</span>
        </label>
        <TrustLens on={lens} onToggle={() => setLens((v) => !v)} />
        <div className="seg" role="group" aria-label="view">
          {([["scan", "Scan"], ["reading", "Our reading"], ["overlay", "Overlay"]] as [ViewMode, string][]).map(([m, l]) => (
            <button key={m} aria-pressed={mode === m} onClick={() => setMode(m)}>
              {l}
            </button>
          ))}
        </div>
      </header>

      {live && <SampleStrip samples={samples} sampleId={sampleId} question={question} busy={busy} onPick={pickSample} onAsk={(t) => sample && void runLive(sample, t)} onUpload={(f) => void upload(f)} />}

      <div className="main">
        <section className="left" aria-label="plan">
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column" }}>
            <div className="stage-tools" style={{ position: "relative" }}>
              <label>
                Layer gap
                <input type="range" min={0} max={1} step={0.01} value={explode} disabled={mode !== "reading"} onChange={(e) => setExplode(Number(e.target.value))} aria-label="layer gap" />
              </label>
              <label>
                Wipe
                <input type="range" min={0} max={100} value={wipe} disabled={mode !== "overlay"} onChange={(e) => setWipe(Number(e.target.value))} aria-label="wipe" />
              </label>
              <span>{mode === "reading" ? "Layers exploded: hover a number to light its layer" : mode === "overlay" ? "Drag to compare scan and reading" : "Raw scan, nothing added"}</span>
            </div>
            <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", position: "relative" }}>
              <EvidenceStack
                proof={proof}
                elements={elements}
                size={size}
                answerIds={answerIds}
                disputedIds={ruling ? [] : dis}
                anchorIds={anchorIds}
                tier={eff.tier}
                mode={mode}
                explode={explode}
                wipe={wipe}
                highlightIds={highlight}
                pinnedId={pinned}
                lens={lens}
                scan={scanImg}
                readers={readers}
                onHover={setHover}
                onPin={setPinned}
              />
              {rA && rB && proof.tier !== "grey" && (
                <div className={`duel-banner ${rA.value !== rB.value || dis.length > 0 ? "duel-banner--dis" : ""}`} role="status" data-testid="duel-banner">
                  <span className="rk rk--a" aria-hidden="true" />
                  <b>{String(rA.value ?? "–")}</b>
                  <span className="vs">{rA.value !== rB.value ? "vs" : "="}</span>
                  <b>{String(rB.value ?? "–")}</b>
                  <span className="rk rk--b" aria-hidden="true" />
                  <span className="dl">{dis.length > 0 ? `${dis.length} disputed · look here first` : rA.value === rB.value ? "readers agree" : "readers disagree"}</span>
                </div>
              )}
              {scanImg && scanImg.coords !== "pixels" && <span className="scan-note">scan shown for reference: this file is read from its vector geometry</span>}
            </div>
          </div>
        </section>

        <aside className="right">
          <div className="tabs" role="tablist">
            {TABS.map((t) => (
              <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>
                {t.label}
                {t.id === "findings" && <span className="badge">{fin.length}</span>}
                {t.id === "decide" && <span className="badge">{proof.decisions_open.filter((d) => !(d.key in chosen)).length}</span>}
              </button>
            ))}
          </div>
          <div className="tabpanel" role="tabpanel" key={`${String(eff.value)}-${eff.tier}`}>
            {err && <p className="err" role="alert">{err}</p>}
            {tab === "answer" && (
              <AnswerCard proof={proof} eff={eff} ruling={live ? null : ruling} axis={axis} canAsk={canAsk} onRule={(r) => void onRule(r)} onHover={setHover} onPin={setPinned} onAsk={() => setAsking(true)} claims={claims} focus={focusId} settled={overridden} busy={busy} sheetType={facts?.sheet_type} onUndo={() => void onUndo()} />
            )}
            {tab === "receipt" && <ReceiptPanel lines={lines} onHover={setHover} onPin={setPinned} />}
            {tab === "decide" && <DecisionCards proof={proof} chosen={chosen} vibe={vibe} axis={axis} onChoose={(k, v) => setChosen((c) => ({ ...c, [k]: v }))} onVibe={setVibe} />}
            {tab === "findings" && <FindingsList items={fin} onHover={setHover} onPin={setPinned} />}
          </div>
        </aside>
      </div>

      {/* a disputed element, pinned on the plan: the two-button card sits right on the stage */}
      {pinned && dis.includes(pinned) && !overridden && !ruling && (
        <div className="pin-card" role="dialog" aria-label="Is this a door?" tabIndex={-1} ref={(el) => el?.focus()}>
          <b>Is this a door?</b>
          <button className="btn btn--primary" disabled={busy} onClick={() => void onRule("yes")}>
            Yes
          </button>
          <button className="btn" disabled={busy} onClick={() => void onRule("no")}>
            No
          </button>
        </div>
      )}

      <footer className="foot">
        <CostMeter cost={proof.cost} claims={claims} extended onScale={() => setScaleDrawer(true)} />
        <span className="spacer" />
        <span className="credit">
          {live ? "live" : "fixtures"} · {proof.provenance.credit ?? proof.provenance.license ?? "no credit on file"}
          {proof.provenance.resolved_from ? ` · resolved from ${proof.provenance.resolved_from}` : ""}
        </span>
      </footer>

      {scaleDrawer && <ScaleDrawer claims={claims} onClose={() => setScaleDrawer(false)} />}

      {showAsk && axis && (
        <ScaleAsk
          proof={proof}
          doors={doorsCtx}
          axis={axis}
          busy={busy}
          onClose={() => {
            setAsking(false);
            setAskDismissed((d) => [...d, fx]);
          }}
          onAnswer={(a) => void onScale(a)}
        />
      )}
    </div>
  );
}
