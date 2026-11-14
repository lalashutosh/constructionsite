/**
 * Everything here is a pure function of a ProofObject (plus the user's own
 * clicks). No number is produced that is not already in the proof.
 */
import type { Decision, Element, ProofObject, Scalar, Tag, Tier } from "./types";

export type Ruling = "yes" | "no" | null;

/** Elements claimed by exactly one voter: the thing to look at first. */
export function disputedIds(p: ProofObject): string[] {
  if (p.kind !== "count" || p.voters.length < 2) return [];
  const sets = p.voters.map((v) => new Set(v.element_ids));
  const all = new Set(p.voters.flatMap((v) => v.element_ids));
  return [...all].filter((id) => sets.some((s) => !s.has(id)));
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
    const vs = p.voters.map((v) => `${v.name.replace(/_/g, " ")} ${v.value}`).join(" vs ");
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
