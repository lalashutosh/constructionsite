/** Live engine client (FastAPI on :8000). The UI renders only contract JSON from here. */
import type { Element, ProofObject } from "./types";

export const BASE = "http://localhost:8000/api";
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
  if (!res.ok) throw new Error(`scale failed (${res.status})`);
  return (await res.json()) as ProofObject[];
}
