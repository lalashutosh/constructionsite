import { useEffect, useState } from "react";

type Cell = { pct: number; n: number };
interface Claims {
  with_siblings?: { dev_pct: number; ci: [number, number]; n: number; by_source: Record<string, Record<string, Cell>> };
  no_siblings?: { dev_pct: number; ci: [number, number]; n: number; by_source: Record<string, Record<string, Cell>> };
  router_leave_one_language_out?: number;
  calibrator_trained_on?: number;
  llm_ledger?: { calls: number; usd: number };
  // flat schema (single run)
  headline_ci?: [number, number];
  green_acc?: number;
  green_coverage?: number;
  router_lolo?: number;
  llm_calls?: number;
  usd_total?: number;
  n_questions?: number;
  n_drawings?: number;
}

const st = { fill: "none", stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round", strokeLinejoin: "round" } as const;
const txt = { fill: "currentColor", fontFamily: "var(--sans)", fontSize: 11 } as const;

function Arrow({ x1, x2, y }: { x1: number; x2: number; y: number }) {
  return <path d={`M${x1} ${y}H${x2}M${x2 - 5} ${y - 4}L${x2} ${y}L${x2 - 5} ${y + 4}`} {...st} />;
}

function ReadFig() {
  return (
    <svg viewBox="0 0 420 110" role="img" aria-label="A file is parsed into walls, rooms and openings">
      <rect x="8" y="22" width="64" height="70" {...st} />
      <text x="40" y="62" textAnchor="middle" {...txt}>.dxf .ifc</text>
      <text x="40" y="76" textAnchor="middle" {...txt}>.pdf .svg</text>
      <Arrow x1={76} x2={118} y={57} />
      <text x="97" y="46" textAnchor="middle" {...txt}>parse</text>
      <rect x="122" y="22" width="64" height="70" {...st} strokeDasharray="3 3" />
      <text x="154" y="62" textAnchor="middle" {...txt}>.png scan</text>
      <Arrow x1={190} x2={232} y={57} />
      <text x="211" y="46" textAnchor="middle" {...txt}>neural net + OCR</text>
      <path d="M244 28H340V90H244ZM244 56H296M296 28V90M296 66H340" {...st} />
      <text x="292" y="106" textAnchor="middle" {...txt}>walls · rooms · openings</text>
    </svg>
  );
}
function CheckFig() {
  return (
    <svg viewBox="0 0 420 110" role="img" aria-label="Two wall readers and two AI reviewers must agree">
      <rect x="8" y="14" width="88" height="30" {...st} />
      <text x="52" y="33" textAnchor="middle" {...txt}>wall reader A</text>
      <rect x="8" y="62" width="88" height="30" {...st} />
      <text x="52" y="81" textAnchor="middle" {...txt}>wall reader B</text>
      <Arrow x1={100} x2={150} y={29} />
      <Arrow x1={100} x2={150} y={77} />
      <circle cx="170" cy="53" r="20" {...st} />
      <text x="170" y="50" textAnchor="middle" {...txt}>2 AI</text>
      <text x="170" y="63" textAnchor="middle" {...txt}>reviews</text>
      <Arrow x1={194} x2={236} y={53} />
      <path d="M244 40L254 52L274 28" {...st} />
      <text x="252" y="74" textAnchor="middle" {...txt}>agree: verified</text>
      <path d="M342 30L358 46M358 30L342 46" {...st} />
      <text x="352" y="74" textAnchor="middle" {...txt}>differ: flagged</text>
    </svg>
  );
}
function AnswerFig() {
  return (
    <svg viewBox="0 0 420 110" role="img" aria-label="Known questions use fixed readers; new questions get a query that code runs">
      <text x="8" y="22" {...txt}>common question</text>
      <rect x="8" y="30" width="96" height="26" {...st} />
      <text x="56" y="47" textAnchor="middle" {...txt}>fixed readers</text>
      <Arrow x1={108} x2={170} y={43} />
      <text x="8" y="76" {...txt}>new question</text>
      <rect x="8" y="84" width="60" height="22" {...st} />
      <text x="38" y="99" textAnchor="middle" {...txt}>AI query</text>
      <Arrow x1={72} x2={110} y={95} />
      <rect x="114" y="84" width="60" height="22" {...st} />
      <text x="144" y="99" textAnchor="middle" {...txt}>code runs it</text>
      <path d="M178 95H190V43" {...st} />
      <rect x="194" y="28" width="90" height="30" {...st} />
      <text x="239" y="47" textAnchor="middle" {...txt}>number + receipt</text>
      <text x="290" y="82" {...txt}>the AI never</text>
      <text x="290" y="95" {...txt}>produces the number</text>
    </svg>
  );
}
function PlanFig() {
  return (
    <svg viewBox="0 0 420 110" role="img" aria-label="Building type, then materials, then build order">
      <rect x="8" y="30" width="80" height="50" {...st} />
      <text x="48" y="59" textAnchor="middle" {...txt}>building type</text>
      <Arrow x1={92} x2={134} y={55} />
      <path d="M140 30H220V80H140ZM150 44H162M168 44H210M150 56H162M168 56H210M150 68H162M168 68H200" {...st} />
      <text x="180" y="98" textAnchor="middle" {...txt}>materials list</text>
      <Arrow x1={224} x2={262} y={55} />
      <path d="M270 80H290V64H310V48H330V32" {...st} />
      <text x="300" y="98" textAnchor="middle" {...txt}>build order</text>
    </svg>
  );
}

const STEPS = [
  { t: "Read", d: "Exact files (CAD, IFC, vector PDF) are parsed directly. Scans go through a CubiCasa neural net and text recognition.", f: <ReadFig /> },
  { t: "Check", d: "Two wall readers and two AI reviewers must agree. Disagreements are shown, not hidden.", f: <CheckFig /> },
  { t: "Answer", d: "Common questions use fixed readers. For a new question an AI writes a query and code computes the number. The AI never produces the number.", f: <AnswerFig /> },
  { t: "Plan", d: "Building type, then a materials checklist, then a build order you can play on the model.", f: <PlanFig /> },
];

const pct = (c?: Cell) => (c ? `${c.pct.toFixed(1)}%` : "–");
const nOf = (c?: Cell) => (c ? `n=${c.n}` : "");

export function HowPage() {
  const [c, setC] = useState<Claims | null>(null);
  useEffect(() => {
    void fetch("/claims.json").then((r) => (r.ok ? r.json() : null)).then(setC).catch(() => setC(null));
  }, []);
  const w = c?.with_siblings;
  const n = c?.no_siblings;
  const cells: { label: string; value: string; sub: string }[] = [];
  if (w) cells.push({ label: "DEV accuracy, with sibling files", value: `${w.dev_pct.toFixed(1)}%`, sub: `n=${w.n} · 95% CI ${w.ci[0]}–${w.ci[1]}` });
  if (n) cells.push({ label: "DEV accuracy, given file only", value: `${n.dev_pct.toFixed(1)}%`, sub: `n=${n.n} · 95% CI ${n.ci[0]}–${n.ci[1]}` });
  const sw = w?.by_source?.swiss_dwellings;
  const ifc = w?.by_source?.ifc_models;
  const cub = w?.by_source?.cubicasa5k;
  if (sw?.count) cells.push({ label: "Swiss dwellings, counts", value: pct(sw.count), sub: nOf(sw.count) });
  if (sw?.area) cells.push({ label: "Swiss dwellings, areas", value: pct(sw.area), sub: nOf(sw.area) });
  if (ifc?.area) cells.push({ label: "IFC models, areas", value: pct(ifc.area), sub: nOf(ifc.area) });
  if (cub?.count) cells.push({ label: "CubiCasa scans, counts", value: pct(cub.count), sub: nOf(cub.count) });
  if (!w && !n && c?.headline_ci) cells.push({ label: "DEV accuracy, 95% interval", value: `${(c.headline_ci[0] * 100).toFixed(1)}–${(c.headline_ci[1] * 100).toFixed(1)}%`, sub: c.n_questions ? `n=${c.n_questions} questions · ${c.n_drawings ?? "?"} drawings` : "" });
  if (typeof c?.green_acc === "number") cells.push({ label: "Accuracy when verified", value: `${(c.green_acc * 100).toFixed(1)}%`, sub: typeof c.green_coverage === "number" ? `${(c.green_coverage * 100).toFixed(1)}% of answers` : "" });
  if (typeof c?.router_lolo === "number") cells.push({ label: "Question router, new language held out", value: `${(c.router_lolo * 100).toFixed(1)}%`, sub: "leave-one-language-out" });
  if (!c?.llm_ledger && typeof c?.llm_calls === "number") cells.push({ label: "LLM calls in this run", value: String(c.llm_calls), sub: `$${(c.usd_total ?? 0).toFixed(4)} in total` });
  if (typeof c?.router_leave_one_language_out === "number") cells.push({ label: "Question router, new language held out", value: `${(c.router_leave_one_language_out * 100).toFixed(1)}%`, sub: "leave-one-language-out" });
  if (c?.llm_ledger) cells.push({ label: "LLM calls so far", value: String(c.llm_ledger.calls), sub: `$${c.llm_ledger.usd.toFixed(4)} in total` });
  return (
    <div className="how">
      <div className="howin">
        <h1>How Plumb works</h1>
        <p className="muted lead">A drawing in, numbers out, each with a receipt.</p>
        <ol className="hsteps">
          {STEPS.map((s, i) => (
            <li key={s.t}>
              <div className="hn mono">{i + 1}</div>
              <div className="hbody">
                <h2>{s.t}</h2>
                <p>{s.d}</p>
              </div>
              <div className="hfig">{s.f}</div>
            </li>
          ))}
        </ol>
        <h3 className="lbl">Measured on the development split</h3>
        {cells.length === 0 ? (
          <p className="muted">Numbers are read from claims.json and none are available right now.</p>
        ) : (
          <div className="nums">
            {cells.map((x) => (
              <div key={x.label} className="num">
                <span className="mono nv">{x.value}</span>
                <span>{x.label}</span>
                <small className="muted mono">{x.sub}</small>
              </div>
            ))}
          </div>
        )}
        <p className="muted sm">Source: evaluation reports, development split only; the hold-out set was never used for tuning.</p>
      </div>
    </div>
  );
}
