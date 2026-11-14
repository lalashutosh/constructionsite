/** Several floor plans on ONE sheet (e.g. "1. KERROS" and "2. KERROS" side by side) become separate floors:
 *  the scan check (engine/scancheck.py) found each plan's box and read its level; here each floor gets its own
 *  geometry (elements inside its box, shifted to the box origin) and its own crop of the drawing. */
import type { Geometry, Ring, SheetFloor } from "./api";
import type { Element } from "./types";

export interface SheetPart {
  key: string;            // `${path}#${view}`
  name: string;           // "1. KERROS" / "Floor 1"
  box: [number, number, number, number];
  geo: Geometry;
  source: string;         // where the level came from
}

const center = (poly: [number, number][] | Ring) => {
  let x = 0, y = 0;
  for (const [a, b] of poly) { x += a; y += b; }
  return [x / Math.max(poly.length, 1), y / Math.max(poly.length, 1)] as const;
};
const inside = (b: [number, number, number, number], p: readonly [number, number]) => p[0] >= b[0] && p[0] <= b[2] && p[1] >= b[1] && p[1] <= b[3];

export function sheetFloors(geo: Geometry | null): SheetFloor[] {
  const fl = geo?.check?.floors ?? [];
  return geo && geo.coords === "pixels" && fl.length > 1 ? [...fl].sort((a, b) => (a.level ?? 50) - (b.level ?? 50)) : [];
}

/** Which sheet floor holds a point (drawing pixels), or null. */
export function floorOf(floors: SheetFloor[], poly: [number, number][]): SheetFloor | null {
  const c = center(poly);
  return floors.find((f) => inside(f.box, c)) ?? null;
}

export function splitSheet(path: string, geo: Geometry): SheetPart[] {
  const floors = sheetFloors(geo);
  return floors.map((f, k) => {
    const [x0, y0, x1, y1] = f.box;
    const sh = (r: Ring): Ring => r.map(([x, y]) => [x - x0, y - y0]) as Ring;
    const pick = (els: Element[]) => els.filter((e) => e.polygon.length && inside(f.box, center(e.polygon as [number, number][])))
      .map((e) => ({ ...e, polygon: sh(e.polygon as Ring) }));
    const walls = geo.walls
      .filter((w, i) => f.wall_indices.includes(i) || inside(f.box, center(w.outer)))
      .map((w) => ({ outer: sh(w.outer), holes: w.holes.map(sh) }));
    const check = geo.check ? { ...geo.check, floors: [], views: geo.check.views.filter((v) => v.n === f.view).map((v) => ({ ...v, box: [0, 0, x1 - x0, y1 - y0] as [number, number, number, number] })) } : null;
    return {
      key: `${path}#${f.view}`,
      name: f.label || `Floor ${k + 1}`,
      box: f.box,
      source: f.level_source ?? "position on sheet",
      geo: { ...geo, width: x1 - x0, height: y1 - y0, walls, rooms: pick(geo.rooms), doors: pick(geo.doors), windows: pick(geo.windows), fixtures: pick(geo.fixtures), check },
    };
  });
}
