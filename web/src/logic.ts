/** Plain-language helpers. Everything here is derived from ProofObject fields; nothing is invented. */
import type { ProofObject, Scalar, Voter } from "./types";

const VOTER_WORDS: Record<string, string> = {
  detector: "symbol detector",
  doors_arc: "door-arc line check",
  arc_geometry: "door-arc line check",
  ocr_labels: "printed-label reader",
  dxf_exact: "exact CAD read",
  ifc_exact: "exact IFC read",
  printed_area: "printed room areas",
  polygon_shoelace: "room-outline area",
  planner_query: "planned query",
};
export const voterWord = (name: string) => VOTER_WORDS[name] ?? name.replace(/_/g, " ");

export function fmtNum(v: Scalar | null | undefined): string {
  if (v === null || v === undefined || v === "") return "–";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : String(Math.round(v * 100) / 100);
  return String(v);
}

export function fmtCost(p: ProofObject): string {
  const c = p.cost;
  const llm = c.llm_calls > 0 ? ` · ${c.llm_calls} LLM call${c.llm_calls > 1 ? "s" : ""}` : "";
  return `${(c.ms / 1000).toFixed(1)} s · ${c.tokens_in + c.tokens_out} tokens · $${c.usd.toFixed(4)}${llm}`;
}

const UNITS: Record<string, string> = { m2: "m²", m3: "m³", m: "m" };
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export interface Display {
  /** the headline value, null when there is nothing to show */
  big: string | null;
  unit: string;
  /** compared parts for yes/no style answers */
  parts: string | null;
  small: boolean;
}

/** The headline of an answer, by kind: integer, one decimal with unit, or the word itself. */
export function answerDisplay(p: ProofObject): Display {
  const none: Display = { big: null, unit: "", parts: null, small: false };
  if (p.tier === "grey" || p.value === null || p.value === undefined || p.value === "") return none;
  const v = p.value;
  if (p.kind === "count") return { ...none, big: String(Math.round(Number(v))) };
  if (p.kind === "area" || p.kind === "length" || p.kind === "volume") {
    const n = Number(v);
    return { ...none, big: Number.isFinite(n) ? n.toFixed(1) : String(v), unit: UNITS[p.unit ?? ""] ?? (p.unit && p.unit !== "count" ? p.unit : "") };
  }
  if (p.kind === "text") {
    const note = p.notes.find((n) => n.startsWith("query parts:"));
    let parts: string | null = null;
    if (note) {
      const vals = [...note.matchAll(/part\d+=(-?[\d.]+)/g)].map((m) => m[1]);
      const sel = ((p.query_spec as { parts?: { select?: string }[] } | null)?.parts ?? []).map((x) => x.select ?? "");
      parts = vals.map((x, k) => (sel[k] ? `${x} ${sel[k]}${Number(x) === 1 ? "" : "s"}` : x)).join(" vs ");
    }
    return { big: cap(String(v)), unit: "", parts, small: true };
  }
  return { ...none, big: String(v), small: String(v).length > 6 };
}

const valued = (vs: Voter[]) => vs.filter((v) => v.value !== null && v.value !== undefined);

export interface Verdict {
  tier: "green" | "amber" | "grey";
  word: string;
  /** short detail after the word, for list rows */
  detail: string;
  /** full pill sentence */
  pill: string;
  /** reliability 0..1 when the engine measured one */
  rel: number | null;
}

export function verdict(p: ProofObject): Verdict {
  const rel = typeof p.reliability === "number" ? p.reliability : null;
  if (p.tier === "grey") {
    const why = p.refusal ?? "no reason given";
    return { tier: "grey", word: "Can't answer", detail: why, pill: `Can't answer: ${why}`, rel };
  }
  const vs = valued(p.voters);
  if (p.tier === "green") {
    const agree = vs.filter((v) => String(v.value) === String(p.value)).length || vs.length;
    const detail = `${agree} ${agree === 1 ? "check agrees" : "checks agree"}`;
    return { tier: "green", word: "Verified", detail, pill: `Verified — ${agree} independent ${agree === 1 ? "check agrees" : "checks agree"}`, rel };
  }
  const pct = rel === null ? null : `${Math.round(rel * 100)}% reliable`;
  const distinct = new Set(vs.map((v) => String(v.value)));
  if (vs.length >= 2 && distinct.size > 1) {
    const ab = vs.slice(0, 2).map((v) => fmtNum(v.value)).join(" vs ");
    const list = vs.map((v) => `${voterWord(v.name)} ${fmtNum(v.value)}`).join(", ");
    return { tier: "amber", word: "Needs a look", detail: pct ?? list, pill: `Needs a look — checks disagree (${ab})`, rel };
  }
  if (pct) return { tier: "amber", word: "Needs a look", detail: pct, pill: `Needs a look — ${pct}`, rel };
  if (p.query_spec) return { tier: "amber", word: "Needs a look", detail: "Computed from a query · check the parts", pill: "Needs a look — computed from a query, check the parts", rel };
  return { tier: "amber", word: "Needs a look", detail: "check the highlighted elements", pill: "Needs a look", rel };
}

export interface FindingSpec {
  key: string;
  noun: string;
  q: string;
}

const CUBI: FindingSpec[] = [
  { key: "doors", noun: "doors", q: "How many doors are shown on this floor plan? Count doorways fitted with a door; open doorways without a door leaf do not count." },
  { key: "windows", noun: "windows", q: "How many windows are shown on this floor plan?" },
  { key: "bedrooms", noun: "bedrooms", q: "How many bedrooms are there?" },
  { key: "toilets", noun: "toilets", q: "How many toilets are there?" },
  { key: "sinks", noun: "sinks", q: "How many sinks are there?" },
  { key: "kitchens", noun: "kitchens", q: "How many kitchens are there?" },
];
const SWISS: FindingSpec[] = [
  { key: "doors", noun: "doors", q: "How many doors (interior doors and entrance doors together) are drawn on this floor plan?" },
  { key: "windows", noun: "windows", q: "How many windows are drawn on this floor plan?" },
  { key: "toilets", noun: "toilets", q: "How many toilets are drawn on this floor plan?" },
  { key: "washbasins", noun: "washbasins", q: "How many washbasins are drawn on this floor plan?" },
  { key: "apartments", noun: "apartments", q: "How many apartments are on this floor?" },
  {
    key: "area",
    noun: "net floor area",
    q: "What is the total net floor area in m² of all numbered indoor rooms on this floor (excluding balconies, loggias, terraces and other outdoor spaces, shafts and voids)?",
  },
];
const IFC: FindingSpec[] = [
  { key: "doors", noun: "doors", q: "How many doors are in the model?" },
  { key: "windows", noun: "windows", q: "How many windows are in the model?" },
  { key: "rooms", noun: "rooms", q: "How many rooms are in the model?" },
];

type SampleLike = { path: string; questions: { label: string; text: string }[] };

export function findingSpecs(path: string, samples: SampleLike[]): FindingSpec[] {
  const p = path.toLowerCase();
  const ext = p.split(".").pop() ?? "";
  let base = CUBI;
  if (ext === "ifc" || p.includes("ifc_")) base = IFC;
  else if (p.includes("swiss_dwellings") || ext === "pdf" || ext === "dxf") base = SWISS;
  const s = samples.find((x) => x.path === path);
  if (!s) return base;
  const pick = (re: RegExp) => s.questions.find((q) => re.test(q.label) && !/\(fi\)/i.test(q.label))?.text;
  return base.map((b) => {
    const t = b.key === "doors" ? pick(/door/i) : b.key === "windows" ? pick(/window/i) : b.key === "area" ? pick(/area/i) : undefined;
    return t ? { ...b, q: t } : b;
  });
}

export function chipsFor(path: string): string[] {
  const p = path.toLowerCase();
  const ext = p.split(".").pop() ?? "";
  if (ext === "ifc") return ["How many doors?", "How many windows?", "How many rooms are there?", "Are there more windows than doors?", "How many storeys?"];
  if (p.includes("swiss_dwellings") || ext === "pdf" || ext === "dxf") {
    return ["How many doors?", "How many windows?", "Which room is the largest?", "Total floor area of all bathrooms?", "Are there more windows than doors?", "How many apartments are there?"];
  }
  return ["How many doors?", "How many windows?", "Which room is the largest?", "How many bedrooms are there?", "Total floor area of all bathrooms?", "Are there more windows than doors?"];
}

/** Title for a finding row: bold "5 doors", or the bare noun for a refusal. */
export function findingTitle(spec: FindingSpec, p: ProofObject | null): string {
  const c = spec.noun.charAt(0).toUpperCase() + spec.noun.slice(1);
  if (!p) return c;
  const d = answerDisplay(p);
  if (d.big === null) return c;
  return `${d.big}${d.unit ? ` ${d.unit}` : ""} ${spec.noun}`;
}

/** The engine's "tier:" note as a sentence, saying "checks" for "voters". */
export function tierSentence(p: ProofObject): string | null {
  const n = p.notes.find((x) => x.startsWith("tier:"));
  if (!n) return null;
  return `Final rating: ${n.replace(/^tier:\s*/, "").replace(/voters/g, "checks")}.`;
}
