/**
 * Hand-written mirror of contracts/proof.py. Keep in sync by hand — the
 * generated json-schema-to-typescript output loses the Point tuple shape
 * (collapses to `[unknown, unknown]`), which this file needs for SVG coords.
 *
 * Source of truth: contracts/proof.py (FROZEN after Wave 0).
 */

export type Point = [number, number];
export type Scalar = number | string;

export type Tier = "green" | "amber" | "grey";

export type Tag = "drawn" | "specified" | "chosen" | "defaulted" | "open";

export interface Element {
  id: string;
  kind: string; // door|window|room|fixture|wall|symbol|label|scale_anchor|...
  subtype?: string | null;
  polygon: Point[];
  label?: string | null;
  conf: number;
  attrs: Record<string, unknown>;
}

export interface Voter {
  name: string;
  value?: Scalar | null;
  element_ids: string[];
  runs: number[];
  note?: string | null;
}

export type ScaleAnchorKind =
  | "scale_bar"
  | "dimension"
  | "printed_ratio"
  | "printed_area"
  | "door_prior"
  | "user";

export interface ScaleAnchor {
  kind: ScaleAnchorKind;
  px_per_m: number;
  rel_sigma: number;
  tag: Tag;
  note?: string | null;
  element_ids: string[];
}

export interface ScaleInfo {
  px_per_m?: number | null;
  rel_sigma?: number | null;
  anchors: ScaleAnchor[];
  widths_relative: boolean;
  needs_user: boolean;
}

export interface Assumption {
  key: string;
  value: Scalar;
  unit?: string | null;
  tag: Tag;
  source: string;
  depends_on: string[];
}

export interface Option {
  value: Scalar;
  label: string;
  total_delta?: number | null;
  fits: boolean;
  note?: string | null;
}

export interface Decision {
  key: string;
  question: string;
  options: Option[];
  default: Scalar;
  tag: Tag;
  impact: number;
  decide_by?: string | null;
  affects: string[];
}

export interface Interval {
  lo: number;
  hi: number;
}

export interface Provenance {
  file: string;
  sha256?: string | null;
  page?: number | null;
  revision?: string | null;
  resolved_from?: string | null;
  fmt?: string | null;
  license?: string | null;
  credit?: string | null;
}

export interface Cost {
  ms: number;
  tokens_in: number;
  tokens_out: number;
  usd: number;
  llm_calls: number;
  planner_calls: number;
}

export type ProofKind = "count" | "area" | "length" | "volume" | "text" | "other";

export interface ProofObject {
  id: string;
  question: string;
  intent?: string | null;
  kind: ProofKind;
  value?: Scalar | null;
  unit?: string | null;
  interval?: Interval | null;
  tier: Tier;
  evidence: Element[];
  voters: Voter[];
  scale?: ScaleInfo | null;
  assumptions: Assumption[];
  decisions_open: Decision[];
  provenance: Provenance;
  cost: Cost;
  notes: string[];
  query_spec?: Record<string, unknown> | null;
  refusal?: string | null;
}

export type SheetType =
  | "floor_plan"
  | "elevation"
  | "section"
  | "site_plan"
  | "detail"
  | "multi_view"
  | "schedule"
  | "not_a_plan"
  | "unknown";

export interface PrintedArea {
  text?: string;
  value_m2?: number;
  polygon?: Point[];
}

export interface SheetFacts {
  provenance: Provenance;
  sheet_type: SheetType;
  legible: boolean;
  legibility_note?: string | null;
  width_px?: number | null;
  height_px?: number | null;
  language?: string | null;
  elements: Element[];
  scale?: ScaleInfo | null;
  printed_areas: PrintedArea[];
  extras: Record<string, unknown>;
}

/** Shape of claims.json, when present: free-form key -> number|string. */
export type Claims = Record<string, Scalar>;
