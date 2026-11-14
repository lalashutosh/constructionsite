/**
 * Two data modes, selected by VITE_API:
 *  - "fixtures" (default): fetch static JSON from /fixtures/*.json, copied
 *    from contracts/fixtures/ by scripts/copy-fixtures.mjs (predev/prebuild).
 *  - "live": fetch from the FastAPI engine at :8000.
 *
 * The UI never invents a number: every ProofObject comes from one of these
 * two places, or is read verbatim from claims.json.
 */
import type { Element, ProofObject, SheetFacts } from "./types";

export type Mode = "fixtures" | "live";

let resolved: Mode | null = null;

/**
 * Mode resolution, once at startup: ?api=live|fixtures wins, then VITE_API, then a 900 ms probe of the
 * engine's /health. Live when the engine answers, fixtures otherwise (so the UI is never blocked).
 */
export async function initMode(): Promise<Mode> {
  const q = new URLSearchParams(window.location.search).get("api");
  const env = import.meta.env.VITE_API as string | undefined;
  if (q === "live" || q === "fixtures") resolved = q;
  else if (env === "live" || env === "fixtures") resolved = env;
  else {
    try {
      const ctl = new AbortController();
      const t = setTimeout(() => ctl.abort(), 900);
      const r = await fetch("http://localhost:8000/health", { signal: ctl.signal });
      clearTimeout(t);
      resolved = r.ok ? "live" : "fixtures";
    } catch {
      resolved = "fixtures";
    }
  }
  return resolved;
}

export function getMode(): Mode {
  return resolved ?? (import.meta.env.VITE_API === "live" ? "live" : "fixtures");
}

const LIVE_BASE = "http://localhost:8000/api";
const q1 = (path: string) => encodeURIComponent(path);

/** One row of the demo fixture switcher: id, human label, tier hint, file. */
export interface FixtureEntry {
  id: string;
  label: string;
  file: string;
}

export const DEMO_FIXTURES: FixtureEntry[] = [
  { id: "doors", label: "Doors · 7 vs 6 (amber)", file: "sample_proof_doors.json" },
  { id: "area_before", label: "Area · before scale (amber)", file: "sample_proof_area.json" },
  { id: "area_after", label: "Area · after scale (green)", file: "demo_takeoff_area.json" },
  { id: "refusal", label: "Elevation · refused (grey)", file: "sample_proof_refusal.json" },
];

export async function fetchProof(entry: FixtureEntry): Promise<ProofObject> {
  if (getMode() === "live") {
    const res = await fetch(`${LIVE_BASE}/analyze?id=${encodeURIComponent(entry.id)}`);
    if (!res.ok) throw new Error(`live API ${res.status} for ${entry.id}`);
    return (await res.json()) as ProofObject;
  }
  const res = await fetch(`/fixtures/${entry.file}`);
  if (!res.ok) throw new Error(`fixture ${entry.file} not found (${res.status})`);
  return (await res.json()) as ProofObject;
}

/** SheetFacts for context geometry (walls/rooms/windows around the answer). Null if unavailable. */
export async function fetchFacts(proof: ProofObject): Promise<SheetFacts | null> {
  try {
    const url = getMode() === "live" ? `${LIVE_BASE}/facts?path=${q1(proof.provenance.file)}` : "/fixtures/sample_facts.json";
    const res = await fetch(url);
    if (!res.ok) return null;
    const f = (await res.json()) as SheetFacts;
    return f.provenance.file === proof.provenance.file ? f : null;
  } catch {
    return null;
  }
}

async function post<T>(method: "POST" | "DELETE", path: string, body: unknown): Promise<T> {
  const res = await fetch(`${LIVE_BASE}/${path}`, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`live API ${res.status} for ${path}`);
  return (await res.json()) as T;
}

/** POST /api/ask: the real ProofObject for one drawing and one question. */
export const liveAsk = (path: string, question: string) => post<ProofObject>("POST", "ask", { path, question });

/** POST /api/override: one user verdict on one element; returns the recomputed ProofObject. */
export const liveOverride = (path: string, question: string, e: Element, keep: boolean) =>
  post<ProofObject>("POST", "override", { path, question, element_id: e.id, polygon: e.polygon, keep });

export const liveClearOverrides = (path: string) => post<{ cleared: boolean }>("DELETE", "override", { path });

/** POST /api/scale: a user anchor ({px_length, length_m} or {px_per_m}), recomputes the given questions. */
export const liveScale = (path: string, anchors: Record<string, unknown>[], questions: string[]) =>
  post<ProofObject[]>("POST", "scale", { path, anchors, questions });

/** A drawing the user dropped in: stored by the engine, returns the dataset-relative path. */
export async function liveUpload(file: File): Promise<string> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${LIVE_BASE}/upload`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`live API ${res.status} for upload`);
  return ((await res.json()) as { path: string }).path;
}

export interface ImageInfo {
  url: string;
  /** "pixels" is the only value whose size shares the evidence polygon coordinate space. */
  coords: "pixels" | "pdf-render" | "svg" | "none";
  w: number;
  h: number;
}

/** Real scan from GET /api/image. Resolves with natural size; null if the engine cannot render it. */
export function loadImage(path: string): Promise<ImageInfo | null> {
  return new Promise((resolve) => {
    const url = `${LIVE_BASE}/image?path=${q1(path)}`;
    void fetch(url)
      .then(async (r) => {
        if (!r.ok) return resolve(null);
        // custom headers are only readable cross-origin when the engine exposes them: fall back to the extension
        const ext = path.toLowerCase().split(".").pop() ?? "";
        const guess: ImageInfo["coords"] = ["png", "jpg", "jpeg", "webp"].includes(ext) ? "pixels" : ext === "pdf" ? "pdf-render" : ext === "svg" ? "svg" : "none";
        const coords = (r.headers.get("X-Plumb-Coords") ?? guess) as ImageInfo["coords"];
        const blob = await r.blob();
        const obj = URL.createObjectURL(blob);
        const im = new Image();
        im.onload = () => resolve({ url: obj, coords, w: im.naturalWidth, h: im.naturalHeight });
        im.onerror = () => resolve(null);
        im.src = obj;
      })
      .catch(() => resolve(null));
  });
}

export interface Sample {
  id: string;
  path: string;
  label: string;
  tags: string[];
  kind: "plan" | "not_plan";
  credit: string;
  thumb: string;
  questions: { label: string; text: string }[];
  /** Fixture used to stand in when the engine is not reachable. */
  fixture?: string;
}

export async function fetchSamples(): Promise<Sample[]> {
  try {
    const res = await fetch("/samples/samples.json");
    if (!res.ok) return [];
    return ((await res.json()) as { samples: Sample[] }).samples;
  } catch {
    return [];
  }
}

/** claims.json: numbers measured by evalkit. Optional; never required. */
export async function fetchClaims(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch("/claims.json");
    if (!res.ok) return null;
    return (await res.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}
