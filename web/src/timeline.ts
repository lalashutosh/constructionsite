/**
 * The 10-second hook, tuned from this one file. Times are seconds from the start; they follow the table
 * "First 10 seconds" in docs/DEMO_SCRIPT.md. Nothing else in the app knows these numbers.
 */
export const TIMING = {
  scanAppears: 0.0,
  sweepStart: 1.0,
  sweepEnd: 1.1, // the CSS transition on .sweep carries the line down (see index.css)
  explode: 2.5,
  chipsStart: 4.5,
  chipsSpan: 2.0,
  fold: 6.5,
  title: 8.0,
  end: 10.0,
};

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

export const INIT: HookState = { scanVisible: false, sweep: null, trace: false, explode: 0, chips: 0, flat: true, caption: "", big: false, title: false };

export interface HookStep {
  t: number; // seconds from start
  action: (s: HookState, ctx: { w: number; caption0: string }) => HookState;
}

export function buildTimeline(chipCount: number): HookStep[] {
  const steps: HookStep[] = [
    { t: TIMING.scanAppears, action: (s, c) => ({ ...s, scanVisible: true, caption: c.caption0.replace("{w}", String(c.w)) }) },
    { t: TIMING.sweepStart, action: (s) => ({ ...s, sweep: 0, trace: true, caption: "" }) },
    { t: TIMING.sweepEnd, action: (s) => ({ ...s, sweep: 1 }) },
    { t: TIMING.explode, action: (s) => ({ ...s, sweep: null, flat: false, explode: 1, caption: "Every number gets a receipt." }) },
    { t: TIMING.fold, action: (s) => ({ ...s, explode: 0, flat: true, caption: "", big: true }) },
    { t: TIMING.title, action: (s) => ({ ...s, big: false, title: true }) },
  ];
  for (let i = 1; i <= chipCount; i++) {
    steps.push({ t: TIMING.chipsStart + (i - 1) * (TIMING.chipsSpan / Math.max(chipCount, 1)), action: (s) => ({ ...s, chips: i }) });
  }
  return steps.sort((a, b) => a.t - b.t);
}
