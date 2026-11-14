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
  return `${(c.ms / 1000).toFixed(1)} s · ${c.tokens_in + c.tokens_out} tokens · $${c.usd.toFixed(2)}`;
}

const valued = (vs: Voter[]) => vs.filter((v) => v.value !== null && v.value !== undefined);

export interface Verdict {
  tier: "green" | "amber" | "grey";
  word: string;
  /** short detail after the word, for list rows */
  detail: string;
  /** full pill sentence */
  pill: string;
}

export function verdict(p: ProofObject): Verdict {
  if (p.tier === "grey") {
    const why = p.refusal ?? "no reason given";
    return { tier: "grey", word: "Can't answer", detail: why, pill: `Can't answer: ${why}` };
  }
  const vs = valued(p.voters);
  if (p.tier === "green") {
    const agree = vs.filter((v) => String(v.value) === String(p.value)).length || vs.length;
    const detail = `${agree} ${agree === 1 ? "check agrees" : "checks agree"}`;
    return { tier: "green", word: "Verified", detail, pill: `Verified — ${agree} independent ${agree === 1 ? "check agrees" : "checks agree"}` };
  }
  const distinct = new Set(vs.map((v) => String(v.value)));
  if (vs.length >= 2 && distinct.size > 1) {
    const list = vs.map((v) => `${voterWord(v.name)} ${fmtNum(v.value)}`).join(", ");
    const ab = vs.slice(0, 2).map((v) => fmtNum(v.value)).join(" vs ");
    return { tier: "amber", word: "Needs a look", detail: list, pill: `Needs a look — checks disagree (${ab})` };
  }
  return { tier: "amber", word: "Needs a look", detail: "single check", pill: "Needs a look — single check" };
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
  const cap = spec.noun.charAt(0).toUpperCase() + spec.noun.slice(1);
  if (!p || p.tier === "grey" || p.value === null || p.value === undefined) return cap;
  if (p.kind === "area" || spec.key === "area") return `${fmtNum(p.value)} ${p.unit && p.unit !== "count" ? p.unit : "m²"} ${spec.noun}`;
  return `${fmtNum(p.value)} ${spec.noun}`;
}

/** The engine's "tier:" note as a sentence, saying "checks" for "voters". */
export function tierSentence(p: ProofObject): string | null {
  const n = p.notes.find((x) => x.startsWith("tier:"));
  if (!n) return null;
  return `Final rating: ${n.replace(/^tier:\s*/, "").replace(/voters/g, "checks")}.`;
}
