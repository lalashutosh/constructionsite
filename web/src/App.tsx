import { useCallback, useEffect, useMemo, useState } from "react";
import { DEMO_FIXTURES, fetchClaims, fetchFacts, fetchProof, getMode } from "./api";
import type { Element, Interval, ProofObject, Scalar, SheetFacts } from "./types";
import { effective, findings, receipt, type Ruling } from "./derive";
import { disputedIds } from "./derive";
import { EvidenceStack, type ViewMode } from "./components/EvidenceStack";
import { AnswerCard } from "./components/AnswerCard";
import { ReceiptPanel } from "./components/ReceiptPanel";
import { DecisionCards } from "./components/DecisionCards";
import { FindingsList } from "./components/FindingsList";
import { ScaleAsk } from "./components/ScaleAsk";
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
  const ids = new Set(proof.evidence.map((e) => e.id));
  return [...(facts?.elements ?? []).filter((e) => !ids.has(e.id)), ...proof.evidence];
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

function Main() {
  const q = useQuery();
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
  const hookAt = Number(q.get("hookAt") ?? 0);

  useEffect(() => {
    void loadAll().then(setLoaded);
    void fetchClaims().then(setClaims);
  }, []);

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setPinned(null);
        setHover([]);
        setAsking(false);
      }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);

  const proof = loaded?.proofs[fx] ?? null;
  const facts = loaded?.facts[fx] ?? null;
  const elements = useMemo(() => (proof ? mergeElements(proof, facts) : []), [proof, facts]);
  const eff = useMemo(() => (proof ? effective(proof, ruling) : null), [proof, ruling]);
  const dis = useMemo(() => (proof ? disputedIds(proof) : []), [proof]);
  const anchorIds = useMemo(() => proof?.scale?.anchors.flatMap((a) => a.element_ids) ?? [], [proof]);
  const doorsCtx = useMemo(() => elements.filter((e) => e.kind === "door"), [elements]);

  // the widest interval among fixtures for the same question: the "before" band the collapse is measured against
  const axis = useMemo<Interval | null>(() => {
    if (!proof?.interval || !loaded) return null;
    const same = Object.values(loaded.proofs).filter((p) => p.question === proof.question && p.interval);
    const lo = Math.min(...same.map((p) => p.interval!.lo));
    const hi = Math.max(...same.map((p) => p.interval!.hi));
    const pad = (hi - lo) * 0.08;
    return { lo: Math.max(0, lo - pad), hi: hi + pad };
  }, [proof, loaded]);

  const pick = useCallback((id: string) => {
    setFx(id);
    setRuling(null);
    setPinned(null);
    setHover([]);
    setChosen({});
    setVibe(null);
    setTab("answer");
  }, []);

  const endHook = useCallback(() => setHook(false), []);

  if (!loaded || !proof || !eff) {
    return <div className="lab">Loading proof…</div>;
  }
  const highlight = hover.length ? hover : pinned ? [pinned] : [];
  const canAsk = proof.kind === "area" && proof.tier === "amber" && Boolean(loaded.proofs["area_after"]) && fx === "area_before";
  const fin = findings(proof, ruling, chosen);
  const lines = receipt(proof, chosen, vibe);
  const showAsk = asking || (proof.scale?.needs_user === true && proof.kind === "area" && !askDismissed.includes(fx) && !hook);

  return (
    <div className="app">
      {hook && fx === "doors" && (
        <Hook proof={proof} elements={elements} size={sizeOf(facts)} answerIds={proof.evidence.filter((e) => e.kind === "door").map((e) => e.id)} onDone={endHook} startAt={hookAt} />
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
        <span className="pill">{facts?.sheet_type?.replace(/_/g, " ") ?? (proof.tier === "grey" ? "not a plan" : "sheet")}</span>
        <select aria-label="demo question" value={fx} onChange={(e) => pick(e.target.value)}>
          {DEMO_FIXTURES.filter((f) => loaded.proofs[f.id]).map((f) => (
            <option key={f.id} value={f.id}>
              {f.label}
            </option>
          ))}
        </select>
        <span className="spacer" />
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
                size={sizeOf(facts)}
                answerIds={proof.evidence.map((e) => e.id)}
                disputedIds={ruling ? [] : dis}
                anchorIds={anchorIds}
                tier={eff.tier}
                mode={mode}
                explode={explode}
                wipe={wipe}
                highlightIds={highlight}
                pinnedId={pinned}
                lens={lens}
                onHover={setHover}
                onPin={setPinned}
              />
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
          <div className="tabpanel" role="tabpanel">
            {tab === "answer" && <AnswerCard proof={proof} eff={eff} ruling={ruling} axis={axis} canAsk={canAsk} onRule={setRuling} onHover={setHover} onPin={setPinned} onAsk={() => setAsking(true)} />}
            {tab === "receipt" && <ReceiptPanel lines={lines} onHover={setHover} onPin={setPinned} />}
            {tab === "decide" && <DecisionCards proof={proof} chosen={chosen} vibe={vibe} axis={axis} onChoose={(k, v) => setChosen((c) => ({ ...c, [k]: v }))} onVibe={setVibe} />}
            {tab === "findings" && <FindingsList items={fin} onHover={setHover} onPin={setPinned} />}
          </div>
        </aside>
      </div>

      <footer className="foot">
        <CostMeter cost={proof.cost} claims={claims} />
        <span className="spacer" />
        <span className="credit">
          {getMode() === "live" ? "live" : "fixtures"} · {proof.provenance.credit ?? proof.provenance.license ?? "no credit on file"}
          {proof.provenance.resolved_from ? ` · resolved from ${proof.provenance.resolved_from}` : ""}
        </span>
      </footer>

      {showAsk && axis && (
        <ScaleAsk
          proof={proof}
          doors={doorsCtx}
          axis={axis}
          onClose={() => {
            setAsking(false);
            setAskDismissed((d) => [...d, fx]);
          }}
          onAnswer={() => {
            setAsking(false);
            // fixtures mode: the post-answer proof is the real takeoff output
            pick("area_after");
          }}
        />
      )}
    </div>
  );
}
