import type { Element, Point } from "./types";

export interface BBox {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
  width: number;
  height: number;
}

const FALLBACK: BBox = { minX: 0, minY: 0, maxX: 480, maxY: 620, width: 480, height: 620 };

/** Bounding box of all element polygons, padded, or a fixed fallback box when there is no evidence. */
export function bboxOf(elements: Element[], pad = 24): BBox {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const el of elements) {
    for (const [x, y] of el.polygon) {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  }
  if (!Number.isFinite(minX)) return FALLBACK;
  minX -= pad;
  minY -= pad;
  maxX += pad;
  maxY += pad;
  return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
}

export function centroid(polygon: Point[]): Point {
  if (polygon.length === 0) return [0, 0];
  let sx = 0;
  let sy = 0;
  for (const [x, y] of polygon) {
    sx += x;
    sy += y;
  }
  return [sx / polygon.length, sy / polygon.length];
}

export function polygonToPoints(polygon: Point[]): string {
  return polygon.map(([x, y]) => `${x},${y}`).join(" ");
}

/** Layer an element kind sorts into for the evidence stack. */
export type LayerKind = "scan" | "walls" | "rooms" | "doors" | "windows" | "other";

export function layerOf(kind: string): LayerKind {
  switch (kind) {
    case "wall":
      return "walls";
    case "room":
      return "rooms";
    case "door":
      return "doors";
    case "window":
      return "windows";
    default:
      return "other";
  }
}

/** Extraction layers only — the scan itself is rendered separately as the base plane. */
export const LAYER_ORDER: LayerKind[] = ["walls", "rooms", "windows", "doors"];

export const LAYER_LABEL: Record<LayerKind, string> = {
  scan: "Scan",
  walls: "Walls",
  rooms: "Rooms",
  doors: "Doors",
  windows: "Windows",
  other: "Other",
};
