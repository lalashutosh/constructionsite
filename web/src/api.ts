/** Live engine client (FastAPI on :8000). The UI renders only contract JSON from here. */
import type { Element, ProofObject } from "./types";

export const BASE = (import.meta.env.VITE_ENGINE as string | undefined) ?? "http://localhost:8000/api";
const q1 = (path: string) => encodeURIComponent(path);

export const imageUrl = (path: string) => `${BASE}/image?path=${q1(path)}`;

export async function ask(path: string, question: string): Promise<ProofObject> {
  const res = await fetch(`${BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, question, benchmark: false }),
  });
  if (!res.ok) throw new Error(`engine answered ${res.status}`);
  return (await res.json()) as ProofObject;
}

export async function upload(file: File): Promise<string> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`upload failed (${res.status})`);
  return ((await res.json()) as { path: string }).path;
}

export type Ring = [number, number][];
export interface Geometry {
  width: number;
  height: number;
  coords: string;
  walls: { outer: Ring; holes: Ring[] }[];
  rooms: Element[];
  doors: Element[];
  windows: Element[];
  fixtures: Element[];
  elements_aligned: boolean;
  credit?: string | null;
  wall_note?: string | null;
  check?: ScanCheck | null;
  px_per_m?: number | null;        // the sheet's own scale when printed evidence solved it (sizes shown without asking)
  scale_note?: string | null;
  cost?: { ms: number; cpu_s?: number; llm_calls: number; usd: number; note?: string | null } | null;
}
export interface ScanView {
  n: number;
  box: [number, number, number, number];
  type: string;
  type_source?: string | null;
  reader?: string | null;
  agreement?: number | null;
  why?: string | null;
  flags?: string[];
}
export interface ScanCheck {
  views: ScanView[];
  warnings: string[];
  floors?: SheetFloor[];
  reviewer?: { used?: boolean; models?: string[]; cost_usd?: number; notes?: string | null } | null;
}

export async function geometry(path: string): Promise<Geometry> {
  const res = await fetch(`${BASE}/geometry?path=${q1(path)}`);
  if (!res.ok) throw new Error(`geometry ${res.status}`);
  return (await res.json()) as Geometry;
}

export interface Sample {
  id: string;
  path: string;
  label: string;
  kind: "plan" | "not_plan";
  credit: string;
  thumb: string;
  questions: { label: string; text: string }[];
}

export async function fetchSamples(): Promise<Sample[]> {
  try {
    const res = await fetch("/samples/samples.json");
    return res.ok ? ((await res.json()) as { samples: Sample[] }).samples : [];
  } catch {
    return [];
  }
}

/* ---------- build plan ---------- */
export type PhaseName = "site" | "foundation" | "floor" | "walls" | "openings" | "services" | "finishes" | "roof";
export interface PlanBasis { value: string | number; unit?: string | null; tag: string; source?: string | null }
export interface PlanItem { id: string; group: string; item: string; qty: number | string | null; unit: string; tag: string; basis: string; step?: string; per?: string }
export interface PlanStep { n: number; id: string; title: string; why: string; needs: string[]; phase: PhaseName }
export interface BuildPlan {
  building: { type: string; label: string; confidence: string; evidence: string[] };
  vibe: string;
  vibes: { id: string; label: string; blurb: string }[];
  basis: Record<string, PlanBasis>;
  checklist: PlanItem[];
  steps: PlanStep[];
  open_inputs?: unknown[];
  /** true when the engine endpoint was unreachable and the local sample shape is shown */
  mock?: boolean;
}

export async function fetchPlan(path: string, vibe: string, extra: Record<string, number | string> = {}): Promise<BuildPlan> {
  try {
    const more = Object.entries(extra).map(([k, v]) => `&${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join("");
    const res = await fetch(`${BASE}/plan?path=${q1(path)}&vibe=${encodeURIComponent(vibe)}${more}`);
    if (res.ok) return (await res.json()) as BuildPlan;
  } catch {
    /* fall through to the local sample */
  }
  const m = (await import("./mockPlan.json")).default as unknown as BuildPlan;
  return { ...m, vibe, mock: true };
}

/** User-measured scale: two image-pixel points and the real length between them. Returns the recomputed answers. */
export async function setScale(path: string, pxLength: number, lengthM: number, questions: string[]): Promise<ProofObject[]> {
  const res = await fetch(`${BASE}/scale`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, anchors: [{ kind: "user", px_length: pxLength, length_m: lengthM }], questions }),
  });
  if (res.status === 422) {
    const j = (await res.json().catch(() => ({}))) as { detail?: ScaleIssue };
    throw new ScaleError(j.detail ?? { message: "That measurement does not look right." });
  }
  if (!res.ok) throw new Error(`scale failed (${res.status})`);
  return (await res.json()) as ProofObject[];
}

export interface ScaleIssue {
  message: string;
  median_room_m2?: number;
  suggestion?: string | { label?: string; length_m?: number; unit?: string; value?: number } | null;
}
/** HTTP 422 from /api/scale: the measurement is implausible; nothing was applied. */
export class ScaleError extends Error {
  issue: ScaleIssue;
  constructor(issue: ScaleIssue) {
    super(issue.message);
    this.issue = issue;
  }
}

/* ---------- project (folder) ---------- */
export interface BuildingFloor { path: string; name: string; doc_type: string; sheet?: string | null; title?: string | null; level?: number | null; level_label?: string | null; level_source?: string | null; why?: string | null; stack_index: number; display_label?: string | null }
export interface BuildingOther { path: string; name: string; doc_type: string; discipline?: string | null; sheet?: string | null; title?: string | null; why?: string | null; scan_check?: unknown; display_label?: string | null }
export interface BuildingAlt extends BuildingOther { alternative_of?: string | null; level_label?: string | null; stack_index?: number }
export interface BuildingResult { building: string; method: string; floors: BuildingFloor[]; alternatives: BuildingAlt[]; other: BuildingOther[]; groups: Record<string, string[]>; notes: string[] }

export async function buildProject(files: { path: string; name: string }[]): Promise<BuildingResult> {
  const res = await fetch(`${BASE}/building`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ files }) });
  if (!res.ok) throw new Error(`could not sort the folder (${res.status})`);
  const j = (await res.json()) as BuildingResult;
  return { ...j, floors: j.floors ?? [], alternatives: j.alternatives ?? [], other: j.other ?? [], groups: j.groups ?? {}, notes: j.notes ?? [] };
}

/** One floor plan on a sheet that holds several (from the scan check, engine/scancheck.py). */
export interface SheetFloor {
  view: number;
  box: [number, number, number, number];
  level?: number | null;
  level_label?: string;
  label: string;
  wall_indices: number[];
  level_source?: string;
}

/* ---------- checks: confidence meter + yes/no questions (docs/decisions/checks-api.md) ---------- */
export type CheckKind = "scale" | "sheet_type" | "plan_view" | "units";
export type CheckStatus = "open" | "confirmed" | "rejected" | "auto";
export interface Check {
  id: string;
  kind: CheckKind;
  status: CheckStatus;
  /** 0..1, what the meter shows */
  confidence: number;
  summary: string;
  question: string | null;
  /** image-pixel boxes, same space as /api/image */
  evidence: { box: [number, number, number, number]; label: string }[];
  impact: string | null;
  value: Record<string, unknown>;
}
export interface ChecksResponse { path: string; items: Check[] }

/** VITE_API=mock serves a local, stateful sample so the UI can be built and screenshotted without the endpoints. */
export const MOCK_CHECKS = import.meta.env.VITE_API === "mock";
const mockState = new Map<string, Check[]>();
function mockFor(path: string, w: number, h: number): Check[] {
  const hit = mockState.get(path);
  if (hit) return hit;
  const b = (x0: number, y0: number, x1: number, y1: number): [number, number, number, number] => [x0 * w, y0 * h, x1 * w, y1 * h];
  const items: Check[] = [
    { id: "scale:note:1in=40ft", kind: "scale", status: "open", confidence: 0.62, summary: "Scale looks like 1\" = 40'-0\" (title block note; the scale bar disagrees by 9%)", question: "Is the overall width 323'-4\" (98.6 m)?", evidence: [{ box: b(0.08, 0.86, 0.34, 0.93), label: "title block scale note" }, { box: b(0.36, 0.9, 0.6, 0.94), label: "scale bar" }], impact: "All areas and lengths depend on this.", value: { px_per_m: 1.853, source: "printed_ratio", tag: "specified" } },
    { id: "plan_view:view2", kind: "plan_view", status: "open", confidence: 0.71, summary: "The large drawing on the left is the floor plan; the small one is a section.", question: "Is the large drawing on the left the floor plan to count from?", evidence: [{ box: b(0.05, 0.1, 0.62, 0.8), label: "view read as the plan" }], impact: "Counts come from this view only.", value: {} },
    { id: "units:ft", kind: "units", status: "open", confidence: 0.46, summary: "Dimensions read as feet and inches; no unit is printed next to them.", question: "Are the dimension strings in feet and inches?", evidence: [{ box: b(0.12, 0.05, 0.4, 0.09), label: "dimension string" }], impact: "A wrong unit changes every size by 3.28x.", value: {} },
    { id: "sheet_type:plan", kind: "sheet_type", status: "auto", confidence: 0.96, summary: "This sheet is a floor plan (walls, doors and room labels found).", question: null, evidence: [], impact: null, value: {} },
  ];
  mockState.set(path, items);
  return items;
}
export async function fetchChecks(path: string, dims?: { w: number; h: number }): Promise<Check[]> {
  if (MOCK_CHECKS) return structuredClone(mockFor(path, dims?.w ?? 1000, dims?.h ?? 700));
  const res = await fetch(`${BASE}/checks?path=${q1(path)}`);
  if (!res.ok) throw new Error(`checks ${res.status}`);
  return ((await res.json()) as ChecksResponse).items ?? [];
}
export async function answerCheck(path: string, id: string, answer: "yes" | "no", value: number | null = null): Promise<Check[]> {
  if (MOCK_CHECKS) {
    const items = mockState.get(path) ?? [];
    const c = items.find((x) => x.id === id);
    if (c) {
      c.status = answer === "yes" ? "confirmed" : "rejected";
      c.confidence = answer === "yes" ? 0.97 : 0;
      c.question = null;
      if (answer === "yes") c.summary = c.summary.replace(/ \(.*$/, "") + " (you confirmed)";
      const next = items.find((x) => x.status === "open" && x.kind === c.kind && x !== c);
      if (answer === "no" && !next && c.kind === "scale") items.push({ id: "scale:bar:alt", kind: "scale", status: "open", confidence: 0.55, summary: "The scale bar suggests a different scale: 1\" = 50'-0\".", question: "Does 1\" = 50'-0\" look right?", evidence: [{ box: [100, 300, 260, 330], label: "scale bar" }], impact: "All areas and lengths depend on this.", value: {} });
    }
    await new Promise((r) => setTimeout(r, 450));
    return structuredClone(items);
  }
  const res = await fetch(`${BASE}/checks/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, id, answer, value }),
  });
  if (!res.ok) throw new Error(`answer failed (${res.status})`);
  return ((await res.json()) as ChecksResponse).items ?? [];
}

// ---- element inspector (every drawn element is selectable and can be retyped) ----
export interface PlanElement {
  id: string;
  kind: string;
  subtype: string | null;
  label: string | null;
  conf: number;
  polygon: [number, number][];
  size_m: { w: number; h: number; area?: number; area_m2?: number } | null;
  tag: "drawn" | "specified" | "chosen";
  feeds: string[];
  explanation: string;
  /** set by the engine when the user changed it (optional: also derived client-side) */
  user_changed?: boolean;
  removed?: boolean;
}
export class ElementsUnavailable extends Error {}
export async function fetchElements(path: string): Promise<PlanElement[]> {
  const res = await fetch(`${BASE}/elements?path=${q1(path)}`);
  if (res.status === 404 || res.status === 405 || res.status === 501) throw new ElementsUnavailable(`elements ${res.status}`);
  if (!res.ok) throw new Error(`elements ${res.status}`);
  const j = (await res.json()) as PlanElement[] | { items?: PlanElement[]; elements?: PlanElement[] };
  return Array.isArray(j) ? j : (j.elements ?? j.items ?? []);
}
export interface OverrideBody { element_id: string; action: "retype" | "remove" | "restore"; kind?: string; subtype?: string }
export async function overrideElement(path: string, b: OverrideBody): Promise<{ element: PlanElement | null; affected: string[] }> {
  const res = await fetch(`${BASE}/elements/override`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path, ...b }) });
  if (!res.ok) throw new Error(`could not save the change (${res.status})`);
  const j = (await res.json()) as { element?: PlanElement | null; affected?: string[] };
  return { element: j.element ?? null, affected: j.affected ?? [] };
}
export async function undoElement(path: string): Promise<boolean> {
  const res = await fetch(`${BASE}/elements/undo`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path }) });
  if (!res.ok) throw new Error(`undo failed (${res.status})`);
  const j = (await res.json().catch(() => ({ ok: true }))) as { ok?: boolean };
  return j.ok !== false;
}
