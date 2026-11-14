/**
 * Everything here is a pure function of a ProofObject (plus the user's own
 * clicks). No number is produced that is not already in the proof.
 */
import type { Decision, Element, ProofObject, Scalar, Tag, Tier } from "./types";

export type Ruling = "yes" | "no" | null;

function bb(poly: [number, number][]) {
  const xs = poly.map((q) => q[0]);
  const ys = poly.map((q) => q[1]);
  return { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
}

/** Intersection over union of the two bounding boxes (enough to tell "same element" from "different"). */
export function iou(a: Element, b: Element): number {
  if (!a.polygon.length || !b.polygon.length) return 0;
  const p = bb(a.polygon);
  const q = bb(b.polygon);
  const w = Math.min(p.x1, q.x1) - Math.max(p.x0, q.x0);
  const h = Math.min(p.y1, q.y1) - Math.max(p.y0, q.y0);
  // degenerate (thin) boxes: pad by one unit so a line-like door still overlaps itself
  const inter = Math.max(0, w + 1) * Math.max(0, h + 1);
  const ua = (p.x1 - p.x0 + 1) * (p.y1 - p.y0 + 1) + (q.x1 - q.x0 + 1) * (q.y1 - q.y0 + 1) - inter;
  return ua > 0 ? inter / ua : 0;
}

export const IOU_MATCH = 0.3;

/** True when the two readers' elements live in one coordinate space (their overall boxes overlap). */
export function readersShareSpace(p: ProofObject): boolean {
  const r = duelReaders(p);
  if (r.length < 2) return false;
  const byId = new Map(p.evidence.map((e) => [e.id, e]));
  const box = (ids: string[]) => {
    const pts = ids.flatMap((id) => byId.get(id)?.polygon ?? []);
    return pts.length ? bb(pts as [number, number][]) : null;
  };
  const a = box(r[0].ids);
  const b = box(r[1].ids);
  if (!a || !b) return true; // nothing to compare geometrically: trust the ids
  const w = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0);
  const h = Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0);
  if (w <= 0 || h <= 0) return false;
  const inter = w * h;
  const un = (a.x1 - a.x0) * (a.y1 - a.y0) + (b.x1 - b.x0) * (b.y1 - b.y0) - inter;
  return un > 0 && inter / un >= IOU_MATCH;
}

/** The first two voters that point at elements: the two independent readers shown in the Skeptic Duel. */
export function duelReaders(p: ProofObject): { name: string; value: Scalar | null | undefined; ids: string[] }[] {
  return p.voters.filter((v) => v.element_ids.length > 0).slice(0, 2).map((v) => ({ name: v.name, value: v.value, ids: v.element_ids }));
}

/**
 * Elements to look at first: claimed by only one reader, where "the same element" means a shared id or an
 * overlap (IoU >= 0.3) with something the other reader found. If the two readers share no coordinates at
 * all (for example a vector file and its PDF render) they cannot be compared element by element: none.
 */
export function disputedIds(p: ProofObject): string[] {
  if (p.kind !== "count") return [];
  const r = duelReaders(p);
  if (r.length < 2) return [];
  const byId = new Map(p.evidence.map((e) => [e.id, e]));
  if (!readersShareSpace(p)) return [];
  const [A, B] = r;
  const setA = new Set(A.ids);
  const setB = new Set(B.ids);
  const side = (mine: string[], other: string[], otherSet: Set<string>) =>
    mine.filter((id) => {
      if (otherSet.has(id)) return false;
      const e = byId.get(id);
      if (!e) return true;
      return !other.some((o) => {
        const f = byId.get(o);
        return f ? iou(e, f) >= IOU_MATCH : false;
      });
    });
  const onlyA = side(A.ids, B.ids, setB);
  const onlyB = side(B.ids, A.ids, setA);
  return [...onlyA, ...onlyB];
}

export interface Effective {
  value: Scalar | null | undefined;
  tier: Tier;
  why: string;
  duel: boolean;
}

export function chipNumber(p: ProofObject, id: string): number {
  return p.evidence.findIndex((e) => e.id === id) + 1;
}

export function effective(p: ProofObject, ruling: Ruling): Effective {
  const dis = disputedIds(p);
  if (p.tier === "grey") {
    return { value: null, tier: "grey", why: p.refusal ?? "No answer available.", duel: false };
  }
  if (dis.length > 0 && ruling) {
    const idx = ruling === "yes" ? 0 : 1;
    const v = p.voters[idx] ?? p.voters[0];
    return {
      value: v.value,
      tier: "green",
      why: `You ruled on ${p.kind === "count" ? "item" : "element"} ${dis.map((d) => chipNumber(p, d)).join(", ")}; both readers now agree on ${v.value}.`,
      duel: false,
    };
  }
  if (dis.length > 0) {
    const vs = duelReaders(p).map((v) => `${v.name.replace(/_/g, " ")} ${v.value}`).join(" vs ");
    return {
      value: p.value,
      tier: "amber",
      why: `Readers disagree (${vs}). Look at item ${dis.map((d) => chipNumber(p, d)).join(", ")} first.`,
      duel: true,
    };
  }
  if (p.tier === "amber" && p.interval) {
    return {
      value: p.value,
      tier: "amber",
      why: `Could be ${fmt(p.interval.lo)} to ${fmt(p.interval.hi)} ${unitLabel(p.unit)} until the scale is pinned down.`,
      duel: false,
    };
  }
  if (p.tier === "green") {
    const n = p.voters.length;
    return {
      value: p.value,
      tier: "green",
      why: n > 1 ? `${n} independent readers agree${p.interval ? `, within ${fmt(p.interval.lo)} to ${fmt(p.interval.hi)} ${unitLabel(p.unit)}` : ""}.` : "Verified.",
      duel: false,
    };
  }
  return { value: p.value, tier: p.tier, why: p.notes[0] ?? "", duel: false };
}

export function fmt(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

export function unitLabel(u?: string | null): string {
  if (!u) return "";
  return u === "m2" ? "m²" : u === "m3" ? "m³" : u;
}

export const TIER_WORD: Record<Tier, string> = {
  green: "voters agree",
  amber: "look here first",
  grey: "cannot answer",
};
export const TIER_ICON: Record<Tier, string> = { green: "✓", amber: "▲", grey: "∅" };

export interface Finding {
  sev: "ok" | "warn" | "info";
  text: string;
  detail?: string;
  ids: string[];
}

export function findings(p: ProofObject, ruling: Ruling, chosen: Record<string, Scalar>): Finding[] {
  const out: Finding[] = [];
  const eff = effective(p, ruling);
  if (p.tier === "grey") {
    out.push({ sev: "info", text: p.refusal ?? "Cannot answer from this sheet.", ids: [] });
    return out;
  }
  const kinds = new Map<string, Element[]>();
  p.evidence.forEach((e) => kinds.set(e.kind, [...(kinds.get(e.kind) ?? []), e]));
  for (const [k, list] of kinds) {
    out.push({
      sev: "ok",
      text: `${list.length} ${k}${list.length === 1 ? "" : "s"} drawn`,
      detail: "Counted from the drawing itself.",
      ids: list.map((e) => e.id),
    });
  }
  const dis = disputedIds(p);
  if (dis.length) {
    out.push({
      sev: ruling ? "ok" : "warn",
      text: ruling
        ? `Item ${dis.map((d) => chipNumber(p, d)).join(", ")} settled by you: ${ruling === "yes" ? "counted" : "not counted"}`
        : `Readers disagree on item ${dis.map((d) => chipNumber(p, d)).join(", ")}: look here first`,
      detail: p.notes[0] ?? undefined,
      ids: dis,
    });
  }
  if (p.interval && eff.tier === "amber") {
    out.push({
      sev: "warn",
      text: `${p.kind} could be ${fmt(p.interval.lo)} to ${fmt(p.interval.hi)} ${unitLabel(p.unit)} until one dimension is known`,
      detail: "One tap on a door narrows it.",
      ids: p.scale?.anchors.flatMap((a) => a.element_ids) ?? [],
    });
  }
  if (p.scale?.widths_relative) {
    out.push({ sev: "warn", text: "Widths are relative: scale came only from a door prior", ids: [] });
  }
  const open = p.decisions_open.filter((d) => !(d.key in chosen));
  if (open.length) {
    out.push({
      sev: "info",
      text: `${open.length} decision${open.length === 1 ? "" : "s"} open before ordering`,
      detail: open.map((d) => d.question).join(" · "),
      ids: [],
    });
  }
  for (const n of p.notes) out.push({ sev: "info", text: n, ids: [] });
  return out;
}

export interface ReceiptLine {
  text: string;
  source: string;
  ids: string[];
}

export function receipt(p: ProofObject, chosen: Record<string, Scalar>, vibe: string | null): Record<Tag, ReceiptLine[]> {
  const r: Record<Tag, ReceiptLine[]> = { drawn: [], specified: [], chosen: [], defaulted: [], open: [] };
  const kinds = new Map<string, Element[]>();
  p.evidence.forEach((e) => kinds.set(e.kind, [...(kinds.get(e.kind) ?? []), e]));
  for (const [k, list] of kinds) {
    r.drawn.push({ text: `${list.length} ${k}${list.length === 1 ? "" : "s"} on the sheet`, source: "extracted geometry", ids: list.map((e) => e.id) });
  }
  for (const a of p.assumptions) {
    r[a.tag].push({
      text: `${a.key} = ${a.value}${a.unit ? " " + a.unit : ""}`,
      source: `${a.source}${a.depends_on.length ? " · depends on " + a.depends_on.join(", ") : ""}`,
      ids: p.scale?.anchors.flatMap((x) => x.element_ids) ?? [],
    });
  }
  for (const a of p.scale?.anchors ?? []) {
    r[a.tag].push({
      text: `scale anchor: ${a.kind.replace(/_/g, " ")} → ${a.px_per_m.toFixed(0)} px/m (±${(a.rel_sigma * 100).toFixed(0)}%)`,
      source: a.note ?? "no note",
      ids: a.element_ids,
    });
  }
  for (const d of p.decisions_open) {
    if (d.key in chosen) {
      r.chosen.push({ text: `${d.question} ${chosen[d.key]}`, source: "your choice", ids: [] });
    } else {
      r.open.push({ text: d.question, source: `default ${d.default} until decided`, ids: [] });
    }
  }
  if (vibe) r.chosen.push({ text: `vibe preset: ${vibe}`, source: "your choice", ids: [] });
  return r;
}

export function topDecisions(p: ProofObject): Decision[] {
  return [...p.decisions_open].sort((a, b) => b.impact - a.impact).slice(0, 3);
}

/** Readable one-liner for a planner query_spec (best effort over free-form JSON). */
export function querySentence(spec: Record<string, unknown>): string {
  const bits: string[] = [];
  for (const [k, v] of Object.entries(spec)) {
    if (v == null) continue;
    bits.push(`${k.replace(/_/g, " ")} = ${typeof v === "object" ? JSON.stringify(v) : String(v)}`);
  }
  return bits.join(", ");
}

/** Plain-language reason + what would make the question answerable (grey tier). No numbers invented. */
export function refusalWords(p: ProofObject, sheetType?: string | null): { reason: string; fix: string } {
  const raw = (p.refusal ?? "").trim();
  const low = raw.toLowerCase();
  if (low.includes("tesseract") || low.includes("extraction failed")) {
    return {
      reason: "The reader could not run on this machine, so nothing was measured and nothing is guessed.",
      fix: "Install the missing text reader on the server (tesseract) and ask again, or open a vector drawing.",
    };
  }
  if (low.includes("elevation") || low.includes("section") || sheetType === "elevation" || sheetType === "section") {
    return { reason: raw || "This is an elevation or section; floor-plan questions do not apply.", fix: "Upload the top-down floor plan of the same building." };
  }
  if (low.includes("tiny") || low.includes("thumbnail") || low.includes("too small") || low.includes("resolution")) {
    return { reason: raw, fix: "Upload a larger scan of the same plan, so the linework is readable." };
  }
  if (low.includes("not a plan") || low.includes("not a floor") || sheetType === "not_a_plan") {
    return { reason: raw || "This does not look like a floor plan.", fix: "Upload a floor plan: a top-down drawing with walls, doors and room labels." };
  }
  return { reason: raw || "No answer is available for this drawing.", fix: "Upload a clear, top-down floor plan, or rephrase the question." };
}

/** Calibration sentence from claims.json; null when the claims file has no number for this tier. */
export function calibrationSentence(tier: Tier, claims: Record<string, unknown> | null): string | null {
  if (!claims) return null;
  const num = (k: string) => (typeof claims[k] === "number" ? (claims[k] as number) : null);
  const acc = tier === "green" ? num("green_acc") : tier === "amber" ? num("amber_acc") : null;
  if (acc == null) return null;
  const holdout = num("headline_acc_holdout") != null;
  const n = num("n_questions");
  const d = num("n_drawings");
  const where = holdout ? "held-out" : "development";
  const sample = n != null ? ` (${n.toLocaleString("en")} questions${d != null ? `, ${d} drawings` : ""})` : "";
  const word = tier === "green" ? "when the readers agree like this" : "when the readers disagree like this";
  return `${word}, we were right ${(acc * 100).toFixed(1)}% of the time on ${where} drawings${sample}.`;
}

/** Weight of one scale anchor in the combined estimate: 1 / sigma^2 (same rule as engine/scale/anchors.py). */
export function anchorWeight(relSigma: number): number {
  return relSigma > 0 ? 1 / (relSigma * relSigma) : 0;
}

export function shortList(ids: string[], n = 3): string {
  return ids.slice(0, n).join(", ") + (ids.length > n ? ` +${ids.length - n}` : "");
}

export function estimateSeconds(cpuPerDrawing: number, drawings: number): number {
  return cpuPerDrawing * drawings;
}

export function humanDuration(sec: number): string {
  if (sec < 90) return `${sec.toFixed(0)} s`;
  if (sec < 5400) return `${(sec / 60).toFixed(0)} min`;
  return `${(sec / 3600).toFixed(1)} h`;
}

/** The challenge corpus size used for the CPU-time estimate (from the brief, not measured here). */
export const CORPUS_DRAWINGS = 14000;
