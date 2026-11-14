/**
 * Two data modes, selected by VITE_API:
 *  - "fixtures" (default): fetch static JSON from /fixtures/*.json, copied
 *    from contracts/fixtures/ by scripts/copy-fixtures.mjs (predev/prebuild).
 *  - "live": fetch from the FastAPI engine at :8000.
 *
 * The UI never invents a number: every ProofObject comes from one of these
 * two places, or is read verbatim from claims.json.
 */
import type { ProofObject } from "./types";

export type Mode = "fixtures" | "live";

export function getMode(): Mode {
  return import.meta.env.VITE_API === "live" ? "live" : "fixtures";
}

const LIVE_BASE = "http://localhost:8000/api";

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
