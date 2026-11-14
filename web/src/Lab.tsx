import { useEffect, useState } from "react";
import { loadAll, mergeElements, sizeOf, type Loaded } from "./App";
import { effective, findings, receipt } from "./derive";
import { EvidenceStack } from "./components/EvidenceStack";
import { AnswerCard } from "./components/AnswerCard";
import { ReceiptPanel } from "./components/ReceiptPanel";
import { DecisionCards } from "./components/DecisionCards";
import { FindingsList } from "./components/FindingsList";
import { ScaleAsk } from "./components/ScaleAsk";
import { CostMeter } from "./components/CostMeter";
import { TrustLens } from "./components/TrustLens";
import { Hook } from "./components/Hook";
import type { Scalar } from "./types";

const NAMES = ["stack", "answer", "receipt", "decide", "scale", "findings", "cost", "lens", "hook"];

/** Fixture-driven story page for one component: /#/lab/<name>. */
export function Lab({ name }: { name: string }) {
  const [d, setD] = useState<Loaded | null>(null);
  const [lens, setLens] = useState(false);
  const [chosen, setChosen] = useState<Record<string, Scalar>>({});
  const [vibe, setVibe] = useState<string | null>(null);
  const [hl, setHl] = useState<string[]>([]);
  const [pin, setPin] = useState<string | null>(null);
  useEffect(() => {
    void loadAll().then(setD);
  }, []);
  const nav = (
    <nav>
      {NAMES.map((n) => (
        <a key={n} href={`#/lab/${n}`}>
          {n}
        </a>
      ))}
      <a href="#/">app</a>
    </nav>
  );
  if (!d || !d.proofs.doors) return <div className="lab">{nav}Loading…</div>;
  const doors = d.proofs.doors;
  const area = d.proofs.area_before ?? doors;
  const doorEls = mergeElements(doors, d.facts.doors);
  const noop = () => {};
  return (
    <div className="lab">
      {nav}
      <h2 style={{ color: "#f1f5f9" }}>{name}</h2>
      {name === "stack" && (
        <div className="bigstage">
          <EvidenceStack proof={doors} elements={doorEls} size={sizeOf(d.facts.doors)} answerIds={doors.evidence.map((e) => e.id)} disputedIds={["d3"]} anchorIds={[]} tier="amber" mode="reading" explode={1} wipe={50} highlightIds={hl} pinnedId={pin} lens={lens} onHover={setHl} onPin={setPin} />
        </div>
      )}
      {name === "answer" && (
        <div className="box">
          <AnswerCard proof={doors} eff={effective(doors, null)} ruling={null} axis={null} canAsk={false} onRule={noop} onHover={noop} onPin={noop} onAsk={noop} />
        </div>
      )}
      {name === "receipt" && (
        <div className="box">
          <ReceiptPanel lines={receipt(area, chosen, vibe)} onHover={noop} onPin={noop} />
        </div>
      )}
      {name === "decide" && (
        <div className="box">
          <DecisionCards proof={area} chosen={chosen} vibe={vibe} axis={area.interval ?? null} onChoose={(k, v) => setChosen((c) => ({ ...c, [k]: v }))} onVibe={setVibe} />
        </div>
      )}
      {name === "scale" && area.interval && <ScaleAsk proof={area} doors={doorEls.filter((e) => e.kind === "door")} axis={area.interval} onAnswer={noop} onClose={noop} />}
      {name === "findings" && (
        <div className="box">
          <FindingsList items={findings(doors, null, {})} onHover={noop} onPin={noop} />
        </div>
      )}
      {name === "cost" && (
        <div className="box">
          <CostMeter cost={doors.cost} claims={null} />
        </div>
      )}
      {name === "lens" && <TrustLens on={lens} onToggle={() => setLens((v) => !v)} />}
      {name === "hook" && <Hook proof={doors} elements={doorEls} size={sizeOf(d.facts.doors)} answerIds={doors.evidence.map((e) => e.id)} onDone={noop} />}
    </div>
  );
}
