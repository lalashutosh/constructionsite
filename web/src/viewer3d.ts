/** Imperative three.js scene: drawing floats as a glowing slab, walls extruded from /api/geometry, evidence pins above. */
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import type { Geometry, Ring } from "./api";

const viewName = (t: string) => { const w = t.replace(/_/g, " "); return w.charAt(0).toUpperCase() + w.slice(1); };

export interface FloorInput {
  key: string;
  label: string;
  geo: Geometry;
  imgUrl: string;
}
export interface PinInput {
  idx: number;
  polygon: Ring;
}
interface Callbacks {
  onHoverPin: (idx: number | null) => void;
}

export type Phase = "site" | "foundation" | "floor" | "walls" | "openings" | "services" | "finishes" | "roof";
/** which build phase shows each part of the model */
const PART_PHASE: Record<string, string> = { fixtures: "openings" };
interface Part {
  name: string;
  obj: THREE.Object3D;
  mats: { m: THREE.Material; base: number }[];
  target: number;
  cur: number;
  scaleY: boolean;
}

export interface Theme {
  name: "dark" | "light";
  bg: number;
  accent: number;
  edge: number;
  pin: number;
  pinCss: string;
  pinHot: string;
  pinInk: string;
  slab: number;
  tile: number;
  tileLine: number;
  door: number;
  win: number;
  fix: number;
  planeBase: number;
  imgColor: number;
  imgOpacity: number;
  grid: number;
  gridOp: number;
  tintA: number;
  tintB: number;
  labelBg: string;
  labelText: string;
}
export const THEMES: Record<"dark" | "light", Theme> = {
  dark: {
    name: "dark", bg: 0x0a1828, accent: 0x178582, edge: 0x1fa8a3, pin: 0xbfa181, pinCss: "#bfa181", pinHot: "#e8d3b4", pinInk: "#0a1828",
    slab: 0x1b3550, tile: 0x2a4766, tileLine: 0x3a5a7c, door: 0xe6e2d8, win: 0x8a97a6, fix: 0x3a5a7c, planeBase: 0x12263d,
    imgColor: 0xd7dde6, imgOpacity: 0.35, grid: 0x2a4766, gridOp: 0.5, tintA: 0x178582, tintB: 0xbfa181,
    labelBg: "rgba(15,32,52,0.95)", labelText: "#e6e2d8",
  },
  light: {
    name: "light", bg: 0xffffff, accent: 0x970747, edge: 0x970747, pin: 0x970747, pinCss: "#970747", pinHot: "#d0306f", pinInk: "#ffffff",
    slab: 0xd9d3d6, tile: 0xe9e4e6, tileLine: 0xb8aeb3, door: 0x1a1012, win: 0x6b5a60, fix: 0xb8aeb3, planeBase: 0xf1edef,
    imgColor: 0xffffff, imgOpacity: 0.35, grid: 0xb8aeb3, gridOp: 0.45, tintA: 0x970747, tintB: 0x6b5a60,
    labelBg: "rgba(255,255,255,0.95)", labelText: "#1a1012",
  },
};

function pinTexture(n: number, hot: boolean, T: Theme): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d")!;
  g.beginPath();
  g.arc(64, 64, 52, 0, Math.PI * 2);
  g.fillStyle = hot ? T.pinHot : T.pinCss;
  g.fill();
  g.lineWidth = 5;
  g.strokeStyle = T.pinInk;
  g.stroke();
  g.fillStyle = T.pinInk;
  g.font = "500 60px 'IBM Plex Mono', monospace";
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.fillText(String(n), 64, 68);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function labelTexture(text: string, on: boolean, T: Theme): { tex: THREE.CanvasTexture; aspect: number } {
  const c = document.createElement("canvas");
  c.width = 384;
  c.height = 72;
  const g = c.getContext("2d")!;
  g.font = "400 30px 'IBM Plex Sans', sans-serif";
  const w = Math.min(366, g.measureText(text).width + 36);
  g.fillStyle = T.labelBg;
  g.strokeStyle = on ? "#" + T.accent.toString(16).padStart(6, "0") : "#8a97a6";
  g.lineWidth = 2;
  g.beginPath();
  g.roundRect(4, 8, w, 56, 4);
  g.fill();
  g.stroke();
  g.fillStyle = T.labelText;
  g.textBaseline = "middle";
  g.fillText(text, 22, 38);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return { tex: t, aspect: 384 / 72 };
}

const area = (r: Ring) => {
  let a = 0;
  for (let i = 0; i < r.length; i++) {
    const [x1, y1] = r[i];
    const [x2, y2] = r[(i + 1) % r.length];
    a += x1 * y2 - x2 * y1;
  }
  return a / 2;
};

export class PlumbViewer {
  private el: HTMLElement;
  private cb: Callbacks;
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(32, 1, 1, 2000);
  private controls: OrbitControls;
  private root = new THREE.Group();
  private raf = 0;
  private ro: ResizeObserver;
  private floorGroups = new Map<string, { group: THREE.Group; s: number; w: number; h: number; H: number; plane: THREE.Mesh; rim: THREE.Object3D; parts: Part[] }>();
  private stage: Phase[] | null = null;
  private drawing = true;
  private pinGroup = new THREE.Group();
  private pins: { sprite: THREE.Sprite; idx: number; base: number }[] = [];
  private hover: number | null = null;
  private ext: number | null = null;
  private ray = new THREE.Raycaster();
  private mouse = new THREE.Vector2(9, 9);
  private disposed = false;
  private token = 0;
  private texCache = new Map<string, THREE.CanvasTexture>();
  private signature = "";
  private T: Theme = THEMES.dark;
  private grid: THREE.GridHelper | null = null;

  constructor(el: HTMLElement, cb: Callbacks, theme: Theme = THEMES.dark) {
    this.T = theme;
    this.el = el;
    this.cb = cb;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio));
    this.renderer.setClearColor(theme.bg, 1);
    el.appendChild(this.renderer.domElement);
    this.scene.fog = new THREE.Fog(theme.bg, 170, 520);
    this.makeGrid();
    this.scene.add(this.root);
    this.scene.add(this.pinGroup);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.autoRotate = true;
    this.controls.autoRotateSpeed = 0.5;
    this.controls.maxPolarAngle = Math.PI * 0.49;
    this.controls.addEventListener("start", () => (this.controls.autoRotate = false));
    this.camera.position.set(95, 100, 125);
    const dom = this.renderer.domElement;
    dom.addEventListener("pointermove", (e) => {
      const r = dom.getBoundingClientRect();
      this.mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    });
    dom.addEventListener("pointerleave", () => this.mouse.set(9, 9));
    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(el);
    this.resize();
    const loop = () => {
      if (this.disposed) return;
      this.raf = requestAnimationFrame(loop);
      this.controls.update();
      this.pick();
      this.animatePins();
      this.animateParts();
      this.renderer.render(this.scene, this.camera);
    };
    loop();
  }

  private makeGrid() {
    if (this.grid) {
      this.scene.remove(this.grid);
      this.grid.geometry.dispose();
    }
    const g = new THREE.GridHelper(420, 42, this.T.grid, this.T.grid);
    const m = g.material as THREE.Material;
    m.transparent = true;
    m.opacity = this.T.gridOp * 0.5;
    g.position.y = -2;
    this.grid = g;
    this.scene.add(g);
  }

  /** Switch colours; floors rebuild on the next setFloors call. */
  setTheme(t: Theme) {
    this.T = t;
    this.signature = "";
    this.texCache.clear();
    this.renderer.setClearColor(t.bg, 1);
    (this.scene.fog as THREE.Fog).color.setHex(t.bg);
    this.makeGrid();
  }

  private resize() {
    const w = this.el.clientWidth || 1;
    const h = this.el.clientHeight || 1;
    this.renderer.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  private pick() {
    if (!this.pins.length) return;
    let hit: number | null = null;
    if (Math.abs(this.mouse.x) <= 1) {
      this.ray.setFromCamera(this.mouse, this.camera);
      const objs = this.pins.map((p) => p.sprite);
      const h = this.ray.intersectObjects(objs, false)[0];
      if (h) hit = this.pins.find((p) => p.sprite === h.object)!.idx;
    }
    if (hit !== this.hover) {
      this.hover = hit;
      this.renderer.domElement.style.cursor = hit === null ? "grab" : "pointer";
      this.cb.onHoverPin(hit);
      this.applyHot();
    }
  }

  private tex(n: number, hot: boolean) {
    const k = `${n}:${hot}:${this.T.name}`;
    let t = this.texCache.get(k);
    if (!t) {
      t = pinTexture(n, hot, this.T);
      this.texCache.set(k, t);
    }
    return t;
  }

  private applyHot() {
    const hot = this.ext ?? this.hover;
    for (const p of this.pins) {
      const on = p.idx === hot;
      (p.sprite.material as THREE.SpriteMaterial).map = this.tex(p.idx, on);
      (p.sprite.material as THREE.SpriteMaterial).needsUpdate = true;
      p.sprite.scale.setScalar(p.base * (on ? 1.5 : 1));
    }
  }

  private animatePins() {
    const t = performance.now() / 700;
    void t;
  }

  private animateParts() {
    for (const { parts } of this.floorGroups.values()) {
      for (const p of parts) {
        const d = p.target - p.cur;
        if (Math.abs(d) > 0.002) p.cur += d * 0.1;
        else p.cur = p.target;
        p.obj.visible = p.cur > 0.01;
        if (p.scaleY) p.obj.scale.y = Math.max(0.001, p.cur);
        else for (const x of p.mats) x.m.opacity = x.base * p.cur;
      }
    }
  }

  /** Build-plan stage: null shows the finished model without roof or services. */
  setStage(st: Phase[] | null) {
    this.stage = st;
    this.applyStage();
  }

  /** Show or hide the drawing image under the model. */
  setDrawing(on: boolean) {
    this.drawing = on;
    for (const f of this.floorGroups.values()) f.plane.visible = on;
  }

  private applyStage() {
    const done = this.stage ? new Set<string>(this.stage) : null;
    for (const { parts } of this.floorGroups.values()) {
      for (const p of parts) {
        const phase = PART_PHASE[p.name] ?? p.name;
        p.target = p.name === "views" ? 1 : done ? (done.has(phase) ? 1 : 0) : ["services", "roof"].includes(p.name) ? 0 : 1;
      }
    }
  }

  setHighlight(idx: number | null) {
    this.ext = idx;
    this.applyHot();
  }

  /** Replace the displayed floors. Returns after textures are loaded (or failed quietly). */
  async setFloors(floors: FloorInput[]) {
    const sig = floors.map((f) => f.key).join("|");
    if (sig === this.signature) return;
    this.signature = sig;
    const my = ++this.token;
    this.clear(this.root);
    this.floorGroups.clear();
    this.clearPins();
    const n = floors.length;
    const big = Math.max(...floors.map((f) => Math.max(f.geo.width, f.geo.height)), 1);
    const gap = n > 1 ? 30 : 0;
    for (let i = 0; i < n; i++) {
      const f = floors[i];
      const built = this.buildFloor(f, 100 / Math.max(f.geo.width, f.geo.height));
      built.group.position.y = i * gap;
      this.root.add(built.group);
      this.floorGroups.set(f.key, built);
      built.plane.visible = this.drawing;
      void this.loadTexture(f, built.plane, my);
      if (n > 1) {
      const { tex, aspect } = labelTexture(f.label.length > 22 ? f.label.slice(0, 21) + "…" : f.label, i === n - 1, this.T);
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, fog: false }));
      sp.scale.set(14 * aspect * 0.55, 14 * 0.55, 1);
      const half = (100 * f.geo.width) / Math.max(f.geo.width, f.geo.height) / 2;
      sp.position.set(-half + 8, i * gap + 4, (100 * f.geo.height) / Math.max(f.geo.width, f.geo.height) / 2 + 4);
      this.root.add(sp);
      }
    }
    void big;
    this.applyStage();
    // camera framing: aim at the walls' bounding box so small plans on big sheets still fill the view
    const mid = ((n - 1) * gap) / 2;
    let fx = 0;
    let fz = 0;
    let frac = 1;
    const f0 = floors[0];
    {
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (const wl of f0.geo.walls) for (const [x, y] of wl.outer) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
      if (x1 > x0) {
        const long = Math.max(f0.geo.width, f0.geo.height);
        const s0 = 100 / long;
        fx = ((x0 + x1) / 2 - f0.geo.width / 2) * s0;
        fz = ((y0 + y1) / 2 - f0.geo.height / 2) * s0;
        frac = Math.min(1, Math.max(0.5, Math.max(x1 - x0, y1 - y0) / long + 0.08));
      }
    }
    const dist = (170 * frac + 40) + (n - 1) * 26;
    this.controls.target.set(fx, mid, fz);
    this.camera.position.set(fx + dist * 0.55, mid + dist * 0.5, fz + dist * 0.7);
    this.controls.autoRotate = true;
    this.controls.update();
  }

  private buildFloor(f: FloorInput, s: number) {
    const { geo } = f;
    const w = geo.width;
    const h = geo.height;
    const long = Math.max(w, h);
    const H = long * 0.04;
    const group = new THREE.Group();
    group.scale.setScalar(s);
    const content = new THREE.Group();
    group.add(content);
    const T = this.T;
    const parts: Part[] = [];
    const mk = (name: string, obj: THREE.Object3D, onY = false): Part => {
      const mats: { m: THREE.Material; base: number }[] = [];
      obj.traverse((o) => {
        const m = (o as THREE.Mesh).material as THREE.Material | undefined;
        if (m) mats.push({ m, base: m.opacity });
      });
      const p: Part = { name, obj, mats, target: 1, cur: 1, scaleY: onY };
      content.add(obj);
      parts.push(p);
      return p;
    };

    const plane = new THREE.Mesh(
      new THREE.PlaneGeometry(w, h),
      new THREE.MeshBasicMaterial({ color: T.planeBase, transparent: true, opacity: 0.6, depthWrite: false, side: THREE.DoubleSide }),
    );
    plane.rotation.x = -Math.PI / 2;
    content.add(plane);
    const rim = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.PlaneGeometry(w, h)),
      new THREE.LineBasicMaterial({ color: T.accent, transparent: true, opacity: 0.5 }),
    );
    rim.rotation.x = -Math.PI / 2;
    content.add(rim);

    // image row 0 is the top of the drawing: pixel (x, y) -> world (x - w/2, 0, y - h/2); the camera looks toward -z, so it reads upright
    const P = (p: [number, number]) => new THREE.Vector2(p[0] - w / 2, -(p[1] - h / 2));
    const toShape = (outer: Ring, holes: Ring[] = []) => {
      const sh = new THREE.Shape(outer.map(P));
      for (const hole of holes) if (hole.length >= 3) sh.holes.push(new THREE.Path(hole.map(P)));
      return sh;
    };
    const extrude = (shape: THREE.Shape, depth: number, y0 = 0) => {
      const g = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: false, steps: 1 });
      g.rotateX(-Math.PI / 2);
      if (y0) g.translate(0, y0, 0);
      return g;
    };
    const nonIdx = (g: THREE.BufferGeometry) => (g.index ? g.toNonIndexed() : g);

    // footprint = bounding box of the walls (falls back to the whole sheet)
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const wl of geo.walls) for (const [x, y] of wl.outer) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
    if (!(x1 > x0)) { x0 = 0; y0 = 0; x1 = w; y1 = h; }
    const inset = Math.min(x1 - x0, y1 - y0) * 0.015;
    const fx0 = x0 + inset, fx1 = x1 - inset, fy0 = y0 + inset, fy1 = y1 - inset;

    // foundation slab
    const slabT = H * 0.14;
    const slabG = new THREE.BoxGeometry(fx1 - fx0, slabT, fy1 - fy0);
    slabG.translate((fx0 + fx1) / 2 - w / 2, -slabT / 2, (fy0 + fy1) / 2 - h / 2);
    const slab = new THREE.Group();
    slab.add(new THREE.Mesh(slabG, new THREE.MeshBasicMaterial({ color: T.slab, transparent: true, opacity: 0.7, depthWrite: false })));
    slab.add(new THREE.LineSegments(new THREE.EdgesGeometry(slabG), new THREE.LineBasicMaterial({ color: T.tileLine, transparent: true, opacity: 0.9 })));
    mk("foundation", slab);

    // walls (grow from the floor)
    const wallParts: THREE.BufferGeometry[] = [];
    for (const wl of geo.walls) {
      if (wl.outer.length < 3 || Math.abs(area(wl.outer)) < 0.5) continue;
      try { wallParts.push(nonIdx(extrude(toShape(wl.outer, wl.holes), H))); } catch { /* skip a degenerate piece */ }
    }
    const merged = wallParts.length ? mergeGeometries(wallParts, false) : null;
    const wallGrp = new THREE.Group();
    if (merged) {
      wallGrp.add(new THREE.Mesh(merged, new THREE.MeshBasicMaterial({ color: T.accent, transparent: true, opacity: 0.24, depthWrite: false, side: THREE.DoubleSide })));
      wallGrp.add(new THREE.LineSegments(new THREE.EdgesGeometry(merged, 25), new THREE.LineBasicMaterial({ color: T.edge, transparent: true, opacity: 1 })));
    }
    mk("walls", wallGrp, true);

    // floor tiles (one per room) and room tint (finishes)
    const tileParts: THREE.BufferGeometry[] = [];
    const tintParts: THREE.BufferGeometry[] = [];
    geo.rooms.forEach((r, i) => {
      if (r.polygon.length < 3) return;
      try {
        const g = nonIdx(new THREE.ShapeGeometry(toShape(r.polygon as Ring)));
        g.rotateX(-Math.PI / 2);
        const t = g.clone();
        g.translate(0, 0.25, 0);
        t.translate(0, 0.5, 0);
        const c = new THREE.Color(i % 2 ? T.tintA : T.tintB);
        const n = t.attributes.position.count;
        const col = new Float32Array(n * 3);
        for (let k = 0; k < n; k++) col.set([c.r, c.g, c.b], k * 3);
        t.setAttribute("color", new THREE.BufferAttribute(col, 3));
        tileParts.push(g);
        tintParts.push(t);
      } catch { /* skip */ }
    });
    const tilesM = tileParts.length ? mergeGeometries(tileParts, false) : null;
    const tiles = new THREE.Group();
    if (tilesM) {
      tiles.add(new THREE.Mesh(tilesM, new THREE.MeshBasicMaterial({ color: T.tile, transparent: true, opacity: 0.55, depthWrite: false, side: THREE.DoubleSide })));
      tiles.add(new THREE.LineSegments(new THREE.EdgesGeometry(tilesM, 10), new THREE.LineBasicMaterial({ color: T.tileLine, transparent: true, opacity: 0.6 })));
    }
    mk("floor", tiles);
    const tintM = tintParts.length ? mergeGeometries(tintParts, false) : null;
    const tint = new THREE.Group();
    if (tintM) tint.add(new THREE.Mesh(tintM, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.3, depthWrite: false, side: THREE.DoubleSide })));
    const tintPart = mk("finishes", tint);

    const markers = (name: string, els: { polygon: [number, number][] }[], color: number, depth: number, yy: number, op: number) => {
      const ps: THREE.BufferGeometry[] = [];
      for (const e of els) {
        if (e.polygon.length < 3 || Math.abs(area(e.polygon as Ring)) < 0.2) continue;
        try { ps.push(nonIdx(extrude(toShape(e.polygon as Ring), depth, yy))); } catch { /* skip */ }
      }
      const m = ps.length ? mergeGeometries(ps, false) : null;
      const g = new THREE.Group();
      if (m) g.add(new THREE.Mesh(m, new THREE.MeshBasicMaterial({ color, transparent: true, opacity: op, depthWrite: false })));
      return mk(name, g);
    };
    const fix = markers("fixtures", geo.fixtures, T.fix, H * 0.22, 0, 0.35);
    const win = markers("openings", geo.windows, T.win, H * 0.6, H * 0.25, 0.75);
    const door = markers("openings", geo.doors, T.door, H * 0.75, 0, 0.7);

    // services: glowing lines running along the walls
    const sv: THREE.Vector3[] = [];
    for (const wl of geo.walls) {
      const o = wl.outer;
      if (o.length < 3 || Math.abs(area(o)) < 3) continue;
      for (let i = 0; i < o.length; i++) {
        const a = o[i];
        const b = o[(i + 1) % o.length];
        sv.push(new THREE.Vector3(a[0] - w / 2, H * 0.35, a[1] - h / 2), new THREE.Vector3(b[0] - w / 2, H * 0.35, b[1] - h / 2));
      }
    }
    const svc = new THREE.Group();
    if (sv.length) svc.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(sv), new THREE.LineBasicMaterial({ color: T.pin, transparent: true, opacity: 0.9 })));
    mk("services", svc);

    // one tag per detected view of the sheet; views that are not floor plans are dimmed
    const views = geo.check?.views ?? [];
    if (views.length) {
      const vg = new THREE.Group();
      for (const v of views) {
        const [bx0, by0, bx1, by1] = v.box;
        const plan = v.type === "floor_plan";
        const pts = [[bx0, by0], [bx1, by0], [bx1, by1], [bx0, by1]].map(([x, y]) => new THREE.Vector3(x - w / 2, 0.4, y - h / 2));
        vg.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: plan ? T.accent : T.tileLine, transparent: true, opacity: plan ? 0.9 : 0.5 })));
        const { tex, aspect } = labelTexture(viewName(v.type), plan, T);
        const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, opacity: plan ? 1 : 0.55, depthTest: false, fog: false }));
        const sh = long * 0.05;
        sp.scale.set(sh * aspect, sh, 1);
        sp.renderOrder = 9;
        sp.position.set(bx0 - w / 2 + (sh * aspect) / 2 * 0.9, H * 1.2, by0 - h / 2 - sh * 0.4);
        vg.add(sp);
      }
      mk("views", vg);
    }

    // roof: flat translucent lid over the footprint
    const roofG = new THREE.BoxGeometry(fx1 - fx0 + inset, H * 0.08, fy1 - fy0 + inset);
    roofG.translate((fx0 + fx1) / 2 - w / 2, H * 1.04, (fy0 + fy1) / 2 - h / 2);
    const roof = new THREE.Group();
    roof.add(new THREE.Mesh(roofG, new THREE.MeshBasicMaterial({ color: T.accent, transparent: true, opacity: 0.3, depthWrite: false })));
    roof.add(new THREE.LineSegments(new THREE.EdgesGeometry(roofG), new THREE.LineBasicMaterial({ color: T.edge, transparent: true, opacity: 1 })));
    mk("roof", roof);

    void fix; void win; void door; void tintPart;
    return { group, s, w, h, H, plane, rim, content, parts };
  }

  private async loadTexture(f: FloorInput, plane: THREE.Mesh, token: number) {
    try {
      const res = await fetch(f.imgUrl);
      if (!res.ok) return;
      const blob = await res.blob();
      const long = Math.max(f.geo.width, f.geo.height);
      const scale = Math.min(1, 2048 / long);
      const bmp = await createImageBitmap(blob, { resizeWidth: Math.round(f.geo.width * scale), resizeHeight: Math.round(f.geo.height * scale), resizeQuality: "high", imageOrientation: "flipY" });
      if (token !== this.token || this.disposed) return;
      const t = new THREE.Texture(bmp);
      t.colorSpace = THREE.SRGBColorSpace;
      t.flipY = false; // already flipped when the bitmap was made
      t.anisotropy = 4;
      t.needsUpdate = true;
      const m = plane.material as THREE.MeshBasicMaterial;
      m.map = t;
      m.color.set(this.T.imgColor);
      m.opacity = this.T.imgOpacity;
      m.needsUpdate = true;
    } catch {
      /* image stays a plain slab */
    }
  }

  private clearPins() {
    this.clear(this.pinGroup);
    this.pins = [];
  }

  /** Numbered pins for the selected answer. floorKey null removes them. */
  setPins(floorKey: string | null, pins: PinInput[]) {
    this.clearPins();
    const fl = floorKey ? this.floorGroups.get(floorKey) : undefined;
    if (!fl || !pins.length) return;
    const { group, w, h, H, s } = fl;
    const y0 = H * 2.0 * s;
    const size = 6.5;
    const lineMat = new THREE.LineBasicMaterial({ color: this.T.pin, transparent: true, opacity: 0.8 });
    for (const p of pins) {
      const poly = p.polygon;
      if (!poly.length) continue;
      let cx = 0;
      let cy = 0;
      for (const [x, y] of poly) {
        cx += x;
        cy += y;
      }
      cx /= poly.length;
      cy /= poly.length;
      const wx = (cx - w / 2) * s;
      const wz = (cy - h / 2) * s;
      const wy = group.position.y;
      const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.tex(p.idx, false), transparent: true, depthTest: false, fog: false }));
      sprite.scale.setScalar(size);
      sprite.renderOrder = 10;
      sprite.position.set(wx, wy + y0, wz);
      sprite.userData = { y0: wy + y0, amp: 0.6 };
      this.pinGroup.add(sprite);
      const stem = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(wx, wy + 0.2, wz), new THREE.Vector3(wx, wy + y0 - size * 0.5, wz)]);
      this.pinGroup.add(new THREE.Line(stem, lineMat));
      // footprint outline on the plan
      const pts = poly.map(([x, y]) => new THREE.Vector3((x - w / 2) * s, wy + 0.4, (y - h / 2) * s));
      if (pts.length > 1) this.pinGroup.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: this.T.pin })));
      this.pins.push({ sprite, idx: p.idx, base: size });
    }
    this.applyHot();
  }

  private clear(g: THREE.Object3D) {
    for (const c of [...g.children]) {
      g.remove(c);
      c.traverse((o) => {
        const m = o as THREE.Mesh;
        m.geometry?.dispose?.();
        const mat = m.material as THREE.Material & { map?: THREE.Texture | null };
        if (mat?.map && !(o instanceof THREE.Sprite && g === this.pinGroup)) mat.map.dispose();
        mat?.dispose?.();
      });
    }
  }

  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.raf);
    this.ro.disconnect();
    this.controls.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
