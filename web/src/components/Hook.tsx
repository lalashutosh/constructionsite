import { useEffect, useState } from "react";
import type { Element, ProofObject } from "../types";
import { EvidenceStack } from "./EvidenceStack";
import { CostMeter } from "./CostMeter";
import { TIER_ICON, TIER_WORD } from "../derive";

/** Everything the hook screen can show; the timeline flips these fields. */
export interface HookState {
  scanVisible: boolean;
  sweep: number | null;
  trace: boolean;
  explode: number;
  chips: number;
  flat: boolean;
  caption: string;
  big: boolean;
  title: boolean;
}

const INIT: HookState = { scanVisible: false, sweep: null, trace: false, explode: 0, chips: 0, flat: true, caption: "", big: false, title: false };

export interface HookStep {
  t: number; // seconds from start
  action: (s: HookState, ctx: { w: number }) => HookState;
}

/** Timing table from docs/DEMO_SCRIPT.md "First 10 seconds". Tune here only. */
export function buildTimeline(chipCount: number): HookStep[] {
  const steps: HookStep[] = [
    { t: 0.0, action: (s, c) => ({ ...s, scanVisible: true, caption: `A ${c.w} px scan. Finnish labels. No scale.` }) },
    { t: 1.0, action: (s) => ({ ...s, sweep: 0, trace: true, caption: "" }) },
    { t: 1.1, action: (s) => ({ ...s, sweep: 1 }) },
    { t: 2.5, action: (s) => ({ ...s, sweep: null, flat: false, explode: 1, caption: "Every number gets a receipt." }) },
    { t: 6.5, action: (s) => ({ ...s, explode: 0, flat: true, caption: "", big: true }) },
    { t: 8.0, action: (s) => ({ ...s, big: false, title: true }) },
  ];
  for (let i = 1; i <= chipCount; i++) {
    steps.push({ t: 4.5 + (i - 1) * (2.0 / Math.max(chipCount, 1)), action: (s) => ({ ...s, chips: i }) });
  }
  return steps.sort((a, b) => a.t - b.t);
}

export interface HookProps {
  proof: ProofObject;
  elements: Element[];
  size: { w: number; h: number } | null;
  answerIds: string[];
  onDone: () => void;
  /** Test hook: start the clock at this offset in seconds. */
  startAt?: number;
}

export function Hook({ proof, elements, size, answerIds, onDone, startAt = 0 }: HookProps) {
  const [s, setS] = useState<HookState>(INIT);
  useEffect(() => {
    const steps = buildTimeline(answerIds.length);
    const t0 = performance.now() - startAt * 1000;
    let i = 0;
    let st = INIT;
    let raf = 0;
    const loop = () => {
      const now = (performance.now() - t0) / 1000;
      let changed = false;
      while (i < steps.length && steps[i].t <= now) {
        st = steps[i].action(st, { w: size?.w ?? 0 });
        i++;
        changed = true;
      }
      if (changed) setS(st);
      if (now >= 10) onDone();
      else raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    const key = () => onDone();
    window.addEventListener("keydown", key);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("keydown", key);
    };
  }, [answerIds.length, size, onDone, startAt]);

  const cost = { ...proof.cost, tokens_in: 0, tokens_out: 0, usd: 0 };
  const value = proof.voters[0]?.value ?? proof.value;
  return (
    <div className="hook" role="presentation" data-testid="hook">
      <span className="hook-skip">press any key to skip</span>
      {s.scanVisible && (
        <div style={{ display: "contents", opacity: 1 }}>
          <EvidenceStack
            proof={proof}
            elements={elements}
            size={size}
            answerIds={answerIds}
            disputedIds={[]}
            anchorIds={[]}
            tier={proof.tier}
            mode={s.trace ? "reading" : "scan"}
            explode={s.explode}
            wipe={100}
            highlightIds={[]}
            pinnedId={null}
            lens={false}
            chipLimit={s.chips}
            trace={s.trace}
            sweep={s.sweep}
            showCredit
            onHover={() => {}}
            onPin={() => {}}
          />
        </div>
      )}
      {s.chips > 0 && (
        <div className="tally" aria-hidden="true">
          <i style={{ width: `${(s.chips / Math.max(answerIds.length, 1)) * 100}%` }} />
        </div>
      )}
      <p className="hook-cap" style={{ opacity: s.caption ? 1 : 0 }}>{s.caption}</p>
      {s.chips > 0 && (
        <div className="hook-meter">
          <CostMeter cost={cost} claims={null} />
        </div>
      )}
      {s.big && (
        <div className="hook-big">
          <div className="n">{String(value)}</div>
          <span className={`tier tier--${proof.tier}`}>
            {TIER_ICON[proof.tier]} {proof.voters.length > 1 && proof.tier === "green" ? `${proof.voters.length} independent readers agree` : proof.voters.map((v) => `${v.name.replace(/_/g, " ")} ${v.value}`).join(" · ") + " · " + TIER_WORD[proof.tier]}
          </span>
        </div>
      )}
      {s.title && (
        <div className="hook-title">
          <h1>Plumb</h1>
          <p>Blueprints that show their work.</p>
        </div>
      )}
    </div>
  );
}
