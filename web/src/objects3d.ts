/** Low-poly parametric objects for the 3D model: doors with a swing arc, glazed windows, bathroom and kitchen fixtures,
 *  stairs. Each is sized from the element polygon's oriented bounding box, everything is merged per material so the
 *  scene stays at a handful of draw calls. */
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import type { Element } from "./types";
import type { Theme } from "./viewer3d";

interface Obb {
  cx: number;
  cy: number;
  th: number;
  L: number;
  W: number;
}

/** Oriented bounding box along the polygon's long axis (image-pixel space). */
export function obb(poly: [number, number][]): Obb {
  const n = poly.length;
  let mx = 0, my = 0;
  for (const [x, y] of poly) { mx += x; my += y; }
  mx /= n; my /= n;
  let sxx = 0, syy = 0, sxy = 0;
  for (const [x, y] of poly) { sxx += (x - mx) ** 2; syy += (y - my) ** 2; sxy += (x - mx) * (y - my); }
  const th = 0.5 * Math.atan2(2 * sxy, sxx - syy);
  const c = Math.cos(th), s = Math.sin(th);
  let a0 = Infinity, a1 = -Infinity, b0 = Infinity, b1 = -Infinity;
  for (const [x, y] of poly) {
    const a = (x - mx) * c + (y - my) * s;
    const b = -(x - mx) * s + (y - my) * c;
    a0 = Math.min(a0, a); a1 = Math.max(a1, a); b0 = Math.min(b0, b); b1 = Math.max(b1, b);
  }
  const am = (a0 + a1) / 2, bm = (b0 + b1) / 2;
  return { cx: mx + am * c - bm * s, cy: my + am * s + bm * c, th, L: Math.max(a1 - a0, 0.5), W: Math.max(b1 - b0, 0.5) };
}

type Bag = { geos: THREE.BufferGeometry[]; lines: THREE.Vector3[] };
const bag = (): Bag => ({ geos: [], lines: [] });
const ni = (g: THREE.BufferGeometry) => (g.index ? g.toNonIndexed() : g);

export interface Objects {
  openings: THREE.Group;
  fixtures: THREE.Group;
}

export function buildObjects(doors: Element[], windows: Element[], fixtures: Element[], w: number, h: number, H: number, T: Theme): Objects {
  const leaf = bag(), glass = bag(), sill = bag(), body = bag(), dark = bag(), tall = bag();
  const arcs: THREE.Vector3[] = [];
  const m = H / 2.7; // one metre in drawing units, as a typical room height reads

  const frame = (o: Obb) => new THREE.Matrix4().makeTranslation(o.cx - w / 2, 0, o.cy - h / 2).multiply(new THREE.Matrix4().makeRotationY(-o.th));
  const box = (b: Bag, M: THREE.Matrix4, l: number, hh: number, wd: number, x: number, y: number, z: number) => {
    const g = new THREE.BoxGeometry(l, hh, wd);
    g.translate(x, y + hh / 2, z);
    g.applyMatrix4(M);
    b.geos.push(ni(g));
  };
  const cyl = (b: Bag, M: THREE.Matrix4, rx: number, rz: number, hh: number, x: number, y: number, z: number, seg = 18) => {
    const g = new THREE.CylinderGeometry(1, 1, hh, seg);
    g.scale(rx, 1, rz);
    g.translate(x, y + hh / 2, z);
    g.applyMatrix4(M);
    b.geos.push(ni(g));
  };

  for (const e of doors) {
    if (e.polygon.length < 3) continue;
    const o = obb(e.polygon as [number, number][]);
    const M = frame(o);
    const len = o.L;
    // leaf hinged at one end, opened about 30 degrees
    const g = new THREE.BoxGeometry(len, H * 0.78, Math.max(o.W * 0.5, 0.3));
    g.translate(len / 2, H * 0.39, 0);
    g.rotateY(THREE.MathUtils.degToRad(-30));
    g.translate(-len / 2, 0, 0);
    g.applyMatrix4(M);
    leaf.geos.push(ni(g));
    // quarter-circle swing arc on the floor
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i <= 10; i++) {
      const a = (i / 10) * (Math.PI / 2);
      pts.push(new THREE.Vector3(-len / 2 + Math.cos(a) * len, 0.5, Math.sin(a) * len).applyMatrix4(M));
    }
    for (let i = 0; i < pts.length - 1; i++) arcs.push(pts[i], pts[i + 1]);
    arcs.push(new THREE.Vector3(-len / 2, 0.5, 0).applyMatrix4(M), new THREE.Vector3(-len / 2 + len, 0.5, 0).applyMatrix4(M));
  }

  for (const e of windows) {
    if (e.polygon.length < 3) continue;
    const o = obb(e.polygon as [number, number][]);
    const M = frame(o);
    const t = Math.max(o.W * 0.35, 0.3);
    box(glass, M, o.L, H * 0.45, t, 0, H * 0.3, 0);
    box(sill, M, o.L * 1.04, H * 0.04, o.W * 0.9, 0, H * 0.26, 0);
  }

  for (const e of fixtures) {
    if (e.polygon.length < 3) continue;
    const o = obb(e.polygon as [number, number][]);
    const M = frame(o);
    const { L, W } = o;
    const k = `${e.kind} ${e.subtype ?? ""}`.toLowerCase();
    if (/toilet|wc/.test(k)) {
      box(body, M, L * 0.3, H * 0.3, W * 0.85, -L * 0.33, 0, 0); // tank
      cyl(body, M, L * 0.3, W * 0.4, H * 0.17, L * 0.15, 0, 0); // bowl
      cyl(body, M, L * 0.18, W * 0.25, H * 0.1, L * 0.15, 0, 0, 14); // pedestal
    } else if (/sink|basin|wash/.test(k)) {
      box(body, M, L, H * 0.32, W, 0, 0, 0);
      cyl(dark, M, L * 0.34, W * 0.34, H * 0.012, 0, H * 0.325, 0);
      cyl(body, M, L * 0.03, L * 0.03, H * 0.08, 0, H * 0.32, -W * 0.38, 8);
    } else if (/bath|tub/.test(k)) {
      box(body, M, L, H * 0.22, W, 0, 0, 0);
      box(dark, M, L * 0.86, H * 0.012, W * 0.78, 0, H * 0.22, 0);
    } else if (/shower/.test(k)) {
      box(body, M, L, H * 0.04, W, 0, 0, 0);
      box(glass, M, L, H * 0.7, Math.max(W * 0.04, 0.3), 0, H * 0.04, W / 2);
    } else if (/sauna|bench/.test(k)) {
      box(body, M, L, H * 0.14, W * 0.5, 0, 0, -W * 0.25);
      box(body, M, L, H * 0.28, W * 0.5, 0, 0, W * 0.25);
    } else if (/stair/.test(k)) {
      const n = Math.max(4, Math.min(16, Math.round(L / (0.28 * m))));
      for (let i = 0; i < n; i++) {
        const sh = ((i + 1) / n) * H * 0.9;
        box(body, M, L / n, sh, W, -L / 2 + (i + 0.5) * (L / n), 0, 0);
      }
    } else if (/appliance|stove|oven|fridge|counter|kitchen|cook/.test(k)) {
      box(body, M, L, H * 0.3, W, 0, 0, 0);
      box(dark, M, L, H * 0.02, W, 0, H * 0.3, 0);
    } else if (/closet|wardrobe|cupboard/.test(k)) {
      box(tall, M, L, H * 0.7, W, 0, 0, 0);
    } else {
      box(body, M, L, H * 0.22, W, 0, 0, 0);
    }
  }

  const mat = (c: number, op: number, extra: Partial<THREE.MeshBasicMaterialParameters> = {}) =>
    new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: op, depthWrite: false, ...extra });
  const addMesh = (grp: THREE.Group, b: Bag, c: number, op: number, edge: number | null, edgeOp = 0.85) => {
    if (!b.geos.length) return;
    const mg = mergeGeometries(b.geos, false);
    if (!mg) return;
    grp.add(new THREE.Mesh(mg, mat(c, op)));
    if (edge !== null) grp.add(new THREE.LineSegments(new THREE.EdgesGeometry(mg, 30), new THREE.LineBasicMaterial({ color: edge, transparent: true, opacity: edgeOp })));
  };

  const openings = new THREE.Group();
  addMesh(openings, glass, T.glass, 0.35, T.glass, 0.9);
  addMesh(openings, sill, T.body, 0.7, T.body, 0.7);
  addMesh(openings, leaf, T.body, 0.8, T.body, 0.95);
  if (arcs.length) openings.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(arcs), new THREE.LineBasicMaterial({ color: T.edge, transparent: true, opacity: 0.75 })));

  const fixturesG = new THREE.Group();
  addMesh(fixturesG, body, T.body, T.bodyOp, T.edge, 0.7);
  addMesh(fixturesG, dark, T.bg, 0.9, null);
  addMesh(fixturesG, tall, T.fix, 0.35, T.edge, 0.6);
  return { openings, fixtures: fixturesG };
}
