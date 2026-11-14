/** Imperative three.js scene: drawing floats as a glowing slab, walls extruded from /api/geometry, evidence pins above. */
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import type { Geometry, Ring } from "./api";
import { buildObjects, obb } from "./objects3d";

const viewName = (t: string) => { const w = t.replace(/_/g, " "); return w.charAt(0).toUpperCase() + w.slice(1); };

export interface FloorInput {
  key: string;
  label: string;
  geo: Geometry;
  imgUrl: string;
  /** part of the image this floor shows (one of several plans on one sheet), in drawing pixels */
  crop?: [number, number, number, number];
}
export interface PinInput {
  idx: number;
  polygon: Ring;
  /** floor the pin sits on when it differs from setPins' floorKey (several plans on one sheet) */
  floor?: string;
}
interface Callbacks {
  onHoverPin: (idx: number | null) => void;
  onDimInfo?: (tip: { text: string; x: number; y: number } | null) => void;
  /** pointer over/click on a floor plane: floor key + floor-local drawing pixels (null = nothing) */
  onElementPoint?: (kind: "hover" | "click", hit: { floor: string; x: number; y: number } | null) => void;
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
  layer: number;
  delayUntil: number;
  rate: number;
}
/** vertical rank used by the idle layer separation */
const LAYER: Record<string, number> = { foundation: -1, floor: 1, finishes: 1, fixtures: 1.5, walls: 2, services: 2.5, openings: 3, roof: 4, views: 0 };
const INTRO_DELAY: Record<string, number> = { foundation: 1100, floor: 1300, finishes: 1300, walls: 1500, fixtures: 2100, openings: 2100 };

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
  glass: number;
  body: number;
  bodyOp: number;
  wet: number;
  warm: number;
}
export const THEMES: Record<"dark" | "light", Theme> = {
  dark: {
    name: "dark", bg: 0x0a1828, accent: 0x178582, edge: 0x1fa8a3, pin: 0xbfa181, pinCss: "#bfa181", pinHot: "#e8d3b4", pinInk: "#0a1828",
    slab: 0x1b3550, tile: 0x2a4766, tileLine: 0x3a5a7c, door: 0xe6e2d8, win: 0x8a97a6, fix: 0x3a5a7c, planeBase: 0x12263d,
    imgColor: 0xd7dde6, imgOpacity: 0.35, grid: 0x2a4766, gridOp: 0.5, tintA: 0x178582, tintB: 0xbfa181,
    labelBg: "rgba(15,32,52,0.95)", labelText: "#e6e2d8", glass: 0x8fb8d8, body: 0xe6e2d8, bodyOp: 0.5, wet: 0x1f6e8c, warm: 0xbfa181,
  },
  light: {
    name: "light", bg: 0xffffff, accent: 0x970747, edge: 0x970747, pin: 0x970747, pinCss: "#970747", pinHot: "#d0306f", pinInk: "#ffffff",
    slab: 0xd9d3d6, tile: 0xe9e4e6, tileLine: 0xb8aeb3, door: 0x1a1012, win: 0x6b5a60, fix: 0xb8aeb3, planeBase: 0xf1edef,
    imgColor: 0xffffff, imgOpacity: 0.35, grid: 0xb8aeb3, gridOp: 0.45, tintA: 0x970747, tintB: 0x6b5a60,
    labelBg: "rgba(255,255,255,0.95)", labelText: "#1a1012", glass: 0x5a8fb8, body: 0x6b5a60, bodyOp: 0.5, wet: 0x5b86a8, warm: 0xb08968,
  },
};

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

interface DimHover {
  kind: "room" | "wall";
  poly: Ring;
  floorKey: string;
  ppm: number;
  src: string;
  area?: number;
}

/** Minimum-area bounding rectangle of a polygon (brute force over edge directions). L >= B. */
function minRect(poly: Ring) {
  let best = { area: Infinity, ang: 0, u0: 0, u1: 0, v0: 0, v1: 0 };
  for (let i = 0; i < poly.length; i++) {
    const [x1, y1] = poly[i];
    const [x2, y2] = poly[(i + 1) % poly.length];
    const ang = Math.atan2(y2 - y1, x2 - x1);
    const c = Math.cos(ang), s = Math.sin(ang);
    let u0 = Infinity, u1 = -Infinity, v0 = Infinity, v1 = -Infinity;
    for (const [x, y] of poly) {
      const u = x * c + y * s;
      const v = -x * s + y * c;
      u0 = Math.min(u0, u); u1 = Math.max(u1, u); v0 = Math.min(v0, v); v1 = Math.max(v1, v);
    }
    const area = (u1 - u0) * (v1 - v0);
    if (area < best.area) best = { area, ang, u0, u1, v0, v1 };
  }
  const { ang, u0, u1, v0, v1 } = best;
  const c = Math.cos(ang), s = Math.sin(ang);
  const pt = (u: number, v: number): [number, number] => [u * c - v * s, u * s + v * c];
  const corners = [pt(u0, v0), pt(u1, v0), pt(u1, v1), pt(u0, v1)];
  return { corners, L: Math.max(u1 - u0, v1 - v0), B: Math.min(u1 - u0, v1 - v0), lenFirst: u1 - u0 >= v1 - v0 };
}
const shoelace = (r: Ring) => {
  let a = 0;
  for (let i = 0; i < r.length; i++) { const [x1, y1] = r[i]; const [x2, y2] = r[(i + 1) % r.length]; a += x1 * y2 - x2 * y1; }
  return Math.abs(a / 2);
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
  private lastInteract = performance.now();
  private k = 0;
  private reduce = typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  private resumeTimer = 0;
  private mousePx = { x: -99, y: -99 };
  private frame = 0;
  private measureKey: string | null = null;
  private measureCb: ((px: [number, number][]) => void) | null = null;
  private measurePts: [number, number][] = [];
  private measureGroup = new THREE.Group();
  private downAt = { x: 0, y: 0, t: 0 };
  private geos = new Map<string, Geometry>();
  private tween: { p0: THREE.Vector3; t0: THREE.Vector3; p1: THREE.Vector3; t1: THREE.Vector3; start: number; dur: number; done?: () => void } | null = null;
  private home = { pos: new THREE.Vector3(), target: new THREE.Vector3() };
  private beforeScale: { pos: THREE.Vector3; target: THREE.Vector3 } | null = null;
  private scans: { mesh: THREE.Mesh; start: number; h: number; fl: { group: THREE.Group } }[] = [];
  private introUntil = 0;
  private dimGroup = new THREE.Group();
  private dims: { sprite: THREE.Sprite; born: number; hover?: DimHover; wpx: number; hpx: number }[] = [];
  private hlGroup = new THREE.Group();
  private elGroup = new THREE.Group();
  private elPicking = false;
  private lastElHover = 0;
  private hoverDim = -1;
  private measureHover: { a: THREE.Vector3; b: THREE.Vector3; px: number } | null = null;
  private measureTyped: string | null = null;
  private stage: Phase[] | null = null;
  private drawing = true;
  private pinGroup = new THREE.Group();
  private pins: { dot: THREE.Sprite; label: THREE.Sprite; idx: number; base: THREE.Vector3; top: THREE.Vector3; lw: number; lh: number; show: boolean }[] = [];
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
    this.controls.dampingFactor = 0.07;
    this.controls.zoomToCursor = true;          // wheel zooms towards the point under the cursor
    this.controls.zoomSpeed = 1.1;
    this.controls.screenSpacePanning = true;
    this.controls.autoRotate = false;          // idle drift only after a long pause (see IDLE_MS), and slowly
    this.controls.autoRotateSpeed = 0.25;      // one turn per 4 min
    this.controls.maxPolarAngle = Math.PI * 0.49;
    this.controls.addEventListener("start", () => {
      this.controls.autoRotate = false;
      window.clearTimeout(this.resumeTimer);
      this.lastInteract = performance.now();
    });
    this.controls.addEventListener("end", () => {
      this.lastInteract = performance.now();
      window.clearTimeout(this.resumeTimer);
      this.resumeTimer = window.setTimeout(() => (this.controls.autoRotate = !this.reduce), 45000);
    });
    this.scene.add(this.measureGroup);
    this.scene.add(this.dimGroup);
    this.scene.add(this.hlGroup);
    this.scene.add(this.elGroup);
    this.camera.position.set(95, 100, 125);
    const dom = this.renderer.domElement;
    dom.addEventListener("pointermove", (e) => {
      const r = dom.getBoundingClientRect();
      this.mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      this.mousePx = { x: e.clientX - r.left, y: e.clientY - r.top };
      const now = performance.now();
      if (this.elPicking && !this.measureKey && now - this.lastElHover > 60 && e.buttons === 0) {
        this.lastElHover = now;
        this.cb.onElementPoint?.("hover", this.floorPoint());
      }
    });
    dom.addEventListener("pointerleave", () => {
      this.mouse.set(9, 9);
      this.mousePx = { x: -99, y: -99 };
    });
    dom.addEventListener("wheel", () => (this.lastInteract = performance.now()), { passive: true });
    dom.addEventListener("pointerdown", (e) => {
      this.downAt = { x: e.clientX, y: e.clientY, t: performance.now() };
      this.skipIntro();
    });
    dom.addEventListener("pointerup", (e) => {
      if (!this.measureKey) {
        if (!this.elPicking || Math.hypot(e.clientX - this.downAt.x, e.clientY - this.downAt.y) > 5 || performance.now() - this.downAt.t > 500) return;
        const r = dom.getBoundingClientRect();
        this.mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
        this.cb.onElementPoint?.("click", this.floorPoint());
        return;
      }
      if (Math.hypot(e.clientX - this.downAt.x, e.clientY - this.downAt.y) > 5 || performance.now() - this.downAt.t > 500) return;
      // aim from THIS click, not the last pointermove (taps and clicks without a prior move missed the drawing)
      const r = dom.getBoundingClientRect();
      this.mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      this.measureClick();
    });
    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(el);
    this.resize();
    const loop = () => {
      if (this.disposed) return;
      this.raf = requestAnimationFrame(loop);
      this.controls.update();
      this.pick();
      this.stepTween();
      this.stepScans();
      this.stepDims();
      if ((this.frame++ & 3) === 0) this.declutter();
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

  private spritePx(px: number) {
    return (px * 2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2))) / Math.max(1, this.el.clientHeight);
  }

  private pick() {
    this.pickDim();
    if (!this.pins.length) return;
    let hit: number | null = null;
    let best = 11;
    const w = this.el.clientWidth;
    const h = this.el.clientHeight;
    const v = new THREE.Vector3();
    for (const p of this.pins) {
      v.copy(p.base).project(this.camera);
      const d = Math.hypot((v.x * 0.5 + 0.5) * w - this.mousePx.x, (-v.y * 0.5 + 0.5) * h - this.mousePx.y);
      if (d < best) {
        best = d;
        hit = p.idx;
      }
    }
    if (hit !== this.hover) {
      this.hover = hit;
      this.renderer.domElement.style.cursor = this.measureKey ? "crosshair" : hit === null ? "grab" : "pointer";
      this.cb.onHoverPin(hit);
      this.applyHot();
    }
  }

  private toScreen(v: THREE.Vector3) {
    const p = v.clone().project(this.camera);
    return { x: (p.x * 0.5 + 0.5) * this.el.clientWidth, y: (-p.y * 0.5 + 0.5) * this.el.clientHeight };
  }

  private pickDim() {
    let hit = -1;
    let hitMeasure = false;
    const m = this.mousePx;
    if (m.x > -50 && !this.tween) {
      this.dims.forEach((d, i) => {
        if (!d.hover || hit >= 0) return;
        const sc = this.toScreen(d.sprite.position);
        if (Math.abs(sc.x - m.x) <= d.wpx / 2 + 3 && Math.abs(sc.y - m.y) <= d.hpx / 2 + 3) hit = i;
      });
      if (hit < 0 && this.measureHover) {
        const a = this.toScreen(this.measureHover.a), b = this.toScreen(this.measureHover.b);
        const dx = b.x - a.x, dy = b.y - a.y;
        const t = Math.max(0, Math.min(1, ((m.x - a.x) * dx + (m.y - a.y) * dy) / (dx * dx + dy * dy || 1)));
        if (Math.hypot(a.x + t * dx - m.x, a.y + t * dy - m.y) < 8) hitMeasure = true;
      }
    }
    const id = hitMeasure ? -2 : hit;
    if (id === this.hoverDim) return;
    this.hoverDim = id;
    this.clearHover();
    if (id === -1) { this.cb.onDimInfo?.(null); return; }
    if (id === -2 && this.measureHover) {
      this.cb.onDimInfo?.({ text: `${Math.round(this.measureHover.px)} px on the drawing${this.measureTyped ? ` = ${this.measureTyped} (what you typed)` : ""}`, x: m.x, y: m.y });
      return;
    }
    const d = this.dims[id];
    if (d?.hover) this.showHover(d.hover, m);
  }

  private clearHover() {
    this.clear(this.hlGroup);
  }

  /** Show how a size label was measured: outline, bounding box with two dimension lines, or the centre line. */
  private showHover(hv: DimHover, m: { x: number; y: number }) {
    const fl = this.floorGroups.get(hv.floorKey);
    if (!fl) return;
    const { group, w, h, s, H } = fl;
    const y = group.position.y + 0.6;
    const W3 = (p: [number, number]) => new THREE.Vector3((p[0] - w / 2) * s, y, (p[1] - h / 2) * s);
    const line = (pts: THREE.Vector3[], op = 1, loop = false) => {
      const g = new THREE.BufferGeometry().setFromPoints(pts);
      const mat = new THREE.LineBasicMaterial({ color: this.T.pin, transparent: true, opacity: op, depthTest: false });
      const l = loop ? new THREE.LineLoop(g, mat) : new THREE.Line(g, mat);
      l.renderOrder = 14;
      this.hlGroup.add(l);
    };
    const tag = (text: string, at: THREE.Vector3) => {
      const { t, wpx, hpx } = this.tagTex(text);
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthTest: false, fog: false, sizeAttenuation: false }));
      sp.scale.set(this.spritePx(wpx), this.spritePx(hpx), 1);
      sp.position.copy(at);
      sp.renderOrder = 15;
      this.hlGroup.add(sp);
    };
    const mm = (px: number) => (px / hv.ppm).toFixed(1);
    let text = "";
    if (hv.kind === "room") {
      line(hv.poly.map(W3), 1, true);
      const r = minRect(hv.poly);
      const c = r.corners;
      line(c.map(W3), 0.6, true);
      // two dimension lines, offset outward from the box, one per side length
      const off = Math.max(w, h) * 0.025;
      const cx = (c[0][0] + c[1][0] + c[2][0] + c[3][0]) / 4, cy = (c[0][1] + c[1][1] + c[2][1] + c[3][1]) / 4;
      const dim = (p: [number, number], q: [number, number], label: string) => {
        const mx = (p[0] + q[0]) / 2, my = (p[1] + q[1]) / 2;
        let nx = my - cy, ny = -(mx - cx);
        const nl = Math.hypot(nx, ny) || 1;
        nx /= nl; ny /= nl;
        // outward normal of this edge: perpendicular to the edge, away from the centre
        const ex = q[0] - p[0], ey = q[1] - p[1];
        const el = Math.hypot(ex, ey) || 1;
        let px = -ey / el, py = ex / el;
        if (px * (mx - cx) + py * (my - cy) < 0) { px = -px; py = -py; }
        const P: [number, number] = [p[0] + px * off, p[1] + py * off];
        const Q: [number, number] = [q[0] + px * off, q[1] + py * off];
        line([W3(p), W3(P), W3(Q), W3(q)], 1);
        tag(label, W3([(P[0] + Q[0]) / 2 + px * off * 0.6, (P[1] + Q[1]) / 2 + py * off * 0.6]));
        void nx; void ny;
      };
      const len01 = Math.hypot(c[1][0] - c[0][0], c[1][1] - c[0][1]);
      const len12 = Math.hypot(c[2][0] - c[1][0], c[2][1] - c[1][1]);
      dim(c[0], c[1], `${mm(len01)} m`);
      dim(c[1], c[2], `${mm(len12)} m`);
      const L = r.L / hv.ppm, B = r.B / hv.ppm;
      const area = hv.area ?? shoelace(hv.poly) / (hv.ppm * hv.ppm);
      const corners = hv.poly.length;
      const isRect = Math.abs(area - L * B) / Math.max(area, 0.01) < 0.03;
      text = `Length ${L.toFixed(1)} m × breadth ${B.toFixed(1)} m (outer box) · area ${area.toFixed(1)} m² from the room outline ` + (isRect ? "(= L × B)" : `(not L × B: the outline has ${corners} corners)`);
    } else {
      const ob = obb(hv.poly as [number, number][]);
      line(hv.poly.map(W3), 1, true);
      const c = Math.cos(ob.th), sn = Math.sin(ob.th);
      const a: [number, number] = [ob.cx - (c * ob.L) / 2, ob.cy - (sn * ob.L) / 2];
      const b2: [number, number] = [ob.cx + (c * ob.L) / 2, ob.cy + (sn * ob.L) / 2];
      line([W3(a), W3(b2)], 1);
      tag(`${mm(ob.L)} m`, W3([ob.cx, ob.cy]).setY(y + H * s * 0.3));
      let per = 0;
      for (let i = 0; i < hv.poly.length; i++) { const [x1, y1] = hv.poly[i]; const [x2, y2] = hv.poly[(i + 1) % hv.poly.length]; per += Math.hypot(x2 - x1, y2 - y1); }
      const thick = per > 0 ? Math.min(ob.W, (2 * shoelace(hv.poly)) / per) : ob.W;
      text = `Centre-line length ${mm(ob.L)} m · thickness ≈ ${mm(thick)} m`;
    }
    this.cb.onDimInfo?.({ text: `${text} · scale: ${hv.src}`, x: m.x, y: m.y });
  }

  /** What to say about the Set-real-size line when hovered: the metres that were typed. */
  setMeasureInfo(typed: string | null) {
    this.measureTyped = typed;
  }

  private dotTex(): THREE.CanvasTexture {
    const k = `dot:${this.T.name}`;
    let t = this.texCache.get(k);
    if (!t) {
      const c = document.createElement("canvas");
      c.width = c.height = 32;
      const g = c.getContext("2d")!;
      g.beginPath();
      g.arc(16, 16, 13, 0, Math.PI * 2);
      g.fillStyle = this.T.pinCss;
      g.fill();
      t = new THREE.CanvasTexture(c);
      t.colorSpace = THREE.SRGBColorSpace;
      this.texCache.set(k, t);
    }
    return t;
  }

  private labelTex(n: number, hot: boolean) {
    const k = `lbl:${n}:${hot}:${this.T.name}`;
    let t = this.texCache.get(k);
    const wpx = 12 + String(n).length * 7;
    if (!t) {
      const c = document.createElement("canvas");
      c.width = wpx * 2;
      c.height = 28;
      const g = c.getContext("2d")!;
      g.fillStyle = hot ? this.T.pinCss : this.T.labelBg;
      g.strokeStyle = this.T.pinCss;
      g.lineWidth = 2;
      g.beginPath();
      g.roundRect(1, 1, c.width - 2, c.height - 2, 4);
      g.fill();
      g.stroke();
      g.fillStyle = hot ? this.T.pinInk : this.T.pinCss;
      g.font = "400 22px 'IBM Plex Mono', monospace";
      g.textAlign = "center";
      g.textBaseline = "middle";
      g.fillText(String(n), c.width / 2, c.height / 2 + 1);
      t = new THREE.CanvasTexture(c);
      t.colorSpace = THREE.SRGBColorSpace;
      this.texCache.set(k, t);
    }
    return { t, wpx, hpx: 14 };
  }

  private applyHot() {
    const hot = this.ext ?? this.hover;
    for (const p of this.pins) {
      const on = p.idx === hot;
      const { t, wpx, hpx } = this.labelTex(p.idx, on);
      const m = p.label.material as THREE.SpriteMaterial;
      m.map = t;
      m.needsUpdate = true;
      p.lw = wpx;
      p.lh = hpx;
      p.label.scale.set(this.spritePx(wpx), this.spritePx(hpx), 1);
      p.dot.scale.setScalar(this.spritePx(on ? 8 : 5));
      if (on) p.show = true;
      p.label.visible = p.show;
    }
  }

  /** Hide labels that would overlap an earlier one; the dot stays and the number appears on hover. */
  private declutter() {
    const hot = this.ext ?? this.hover;
    const w = this.el.clientWidth;
    const h = this.el.clientHeight;
    const rects: [number, number, number, number][] = [];
    const v = new THREE.Vector3();
    const order = [...this.pins].sort((a, b) => (a.idx === hot ? -1 : b.idx === hot ? 1 : a.idx - b.idx));
    for (const p of order) {
      v.copy(p.top).project(this.camera);
      const x = (v.x * 0.5 + 0.5) * w;
      const y = (-v.y * 0.5 + 0.5) * h;
      const r: [number, number, number, number] = [x - p.lw / 2 - 2, y - p.lh - 2, x + p.lw / 2 + 2, y + 2];
      const clash = rects.some((q) => r[0] < q[2] && r[2] > q[0] && r[1] < q[3] && r[3] > q[1]);
      p.show = p.idx === hot || !clash;
      if (p.show) rects.push(r);
      p.label.visible = p.show;
    }
  }

  private animateParts() {
    const now = performance.now();
    const idle = (now - this.lastInteract) / 1000;
    if (this.reduce) this.k = 0;
    else if (idle > 6) {
      const tc = (idle - 6) % 12;
      this.k = tc < 6 ? 0.5 - 0.5 * Math.cos((2 * Math.PI * tc) / 6) : 0;
    } else this.k += (0 - this.k) * 0.12;
    for (const fl of this.floorGroups.values()) {
      const gap = fl.H * 1.1;
      for (const p of fl.parts) {
        if (now < p.delayUntil) continue;
        const d = p.target - p.cur;
        if (Math.abs(d) > 0.002) p.cur += d * p.rate;
        else p.cur = p.target;
        p.obj.visible = p.cur > 0.01;
        if (p.scaleY) p.obj.scale.y = Math.max(0.001, p.cur);
        else for (const x of p.mats) x.m.opacity = x.base * p.cur;
        p.obj.position.y = p.layer * gap * this.k;
      }
    }
  }

  // ---- camera tween, intro, scale mode, dimension labels
  private flyTo(pos: THREE.Vector3, target: THREE.Vector3, dur: number, done?: () => void) {
    if (this.reduce) {
      this.camera.position.copy(pos);
      this.controls.target.copy(target);
      this.controls.update();
      done?.();
      return;
    }
    this.controls.autoRotate = false;
    this.tween = { p0: this.camera.position.clone(), t0: this.controls.target.clone(), p1: pos.clone(), t1: target.clone(), start: performance.now(), dur, done };
  }

  private stepTween() {
    const tw = this.tween;
    if (!tw) return;
    const u = Math.min(1, (performance.now() - tw.start) / tw.dur);
    const e = u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;   // easeInOutCubic: soft start and landing
    this.camera.position.lerpVectors(tw.p0, tw.p1, e);
    this.controls.target.lerpVectors(tw.t0, tw.t1, e);
    if (u >= 1) {
      this.tween = null;
      if (!this.measureKey) this.armIdle();
      tw.done?.();
    }
  }

  private stepScans() {
    if (!this.scans.length) return;
    const now = performance.now();
    for (const sc of this.scans) {
      const u = Math.min(1, Math.max(0, (now - sc.start) / 1100));
      sc.mesh.position.set(0, 0.8, -sc.h / 2 + sc.h * (1 - Math.pow(1 - u, 2)));
      sc.mesh.visible = now >= sc.start;
    }
    if (now > this.scans[0].start + 1200) this.clearScans();
  }

  private clearScans() {
    for (const sc of this.scans) {
      sc.fl.group.remove(sc.mesh);
      sc.mesh.geometry.dispose();
      (sc.mesh.material as THREE.Material).dispose();
    }
    this.scans = [];
  }

  /** A click during the intro jumps straight to the finished model. */
  private skipIntro() {
    if (performance.now() > this.introUntil) return;
    this.introUntil = 0;
    this.clearScans();
    for (const fl of this.floorGroups.values()) for (const p of fl.parts) { p.delayUntil = 0; p.cur = p.target; p.rate = 0.1; }
    if (this.tween) {
      const tw = this.tween;
      this.tween = null;
      this.camera.position.copy(tw.p1);
      this.controls.target.copy(tw.t1);
    }
  }

  /** Scale mode: straight top-down view, the drawing at near full opacity. Off eases back to where the camera was. */
  private topDown = false;
  setTopDown(on: boolean) {
    this.topDown = on;
    const planes = [...this.floorGroups.values()].map((f) => f.plane.material as THREE.MeshBasicMaterial);
    if (on) {
      this.beforeScale = { pos: this.camera.position.clone(), target: this.controls.target.clone() };
      const t = this.controls.target.clone();
      const d = this.camera.position.distanceTo(t);
      this.flyTo(t.clone().add(new THREE.Vector3(0, d * 1.02, 0.001)), t, 1100);
      for (const m of planes) if (m.map) m.opacity = 0.95;
    } else {
      for (const m of planes) if (m.map) m.opacity = this.T.imgOpacity;
      const b = this.beforeScale ?? this.home;
      this.flyTo(b.pos, b.target, 1400);
      this.beforeScale = null;
    }
  }

  private tagTex(text: string): { t: THREE.CanvasTexture; wpx: number; hpx: number } {
    const k = `tag:${text}:${this.T.name}`;
    const wpx = Math.round(text.length * 7 + 14);
    let t = this.texCache.get(k);
    if (!t) {
      const c = document.createElement("canvas");
      c.width = wpx * 2;
      c.height = 32;
      const g = c.getContext("2d")!;
      g.fillStyle = this.T.labelBg;
      g.strokeStyle = "#" + this.T.accent.toString(16).padStart(6, "0");
      g.lineWidth = 2;
      g.beginPath();
      g.roundRect(1, 1, c.width - 2, c.height - 2, 4);
      g.fill();
      g.stroke();
      g.fillStyle = this.T.labelText;
      g.font = "400 22px 'IBM Plex Mono', monospace";
      g.textAlign = "center";
      g.textBaseline = "middle";
      g.fillText(text, c.width / 2, c.height / 2 + 1);
      t = new THREE.CanvasTexture(c);
      t.colorSpace = THREE.SRGBColorSpace;
      this.texCache.set(k, t);
    }
    return { t, wpx, hpx: 16 };
  }

  /** Room names on every floor; once a scale is known also wall lengths and room areas on that floor. */
  setDimensions(floorKey: string | null, ppm: number | null, src = "typical door size") {
    this.clear(this.dimGroup);
    this.dims = [];
    this.clearHover();
    const t0 = performance.now();
    let n = 0;
    for (const [key, fl] of this.floorGroups) {
      const geo = this.geos.get(key);
      if (!geo) continue;
      const { group, w, h, H, s } = fl;
      const scaled = !!ppm && key === floorKey;
      const items: { x: number; y: number; text: string; hover?: DimHover }[] = [];
      if (scaled && ppm) {
        const walls = geo.walls
          .filter((wl) => wl.outer.length >= 3)
          .map((wl) => {
            const ob = obb(wl.outer as [number, number][]);
            return { len: ob.L, cx: ob.cx, cy: ob.cy, poly: wl.outer as Ring };
          })
          .filter((x) => x.len / ppm >= 1.5)
          .sort((a, b) => b.len - a.len)
          .slice(0, 8);
        for (const wl of walls) items.push({ x: wl.cx, y: wl.cy, text: `${(wl.len / ppm).toFixed(1)} m`, hover: { kind: "wall", poly: wl.poly, floorKey: key, ppm, src } });
      }
      const long = Math.max(w, h);
      const rooms = geo.rooms
        .filter((r) => r.polygon.length >= 3)
        .map((r) => {
          let a2 = 0, cx = 0, cy = 0, x0 = Infinity, x1 = -Infinity;
          for (let i = 0; i < r.polygon.length; i++) {
            const [xa, ya] = r.polygon[i];
            const [xb, yb] = r.polygon[(i + 1) % r.polygon.length];
            a2 += xa * yb - xb * ya;
            cx += xa;
            cy += ya;
            x0 = Math.min(x0, xa);
            x1 = Math.max(x1, xa);
          }
          const nm = r.label ?? (r.subtype && r.subtype !== "room" ? r.subtype : null);
          return { px: Math.abs(a2 / 2), cx: cx / r.polygon.length, cy: cy / r.polygon.length, bw: x1 - x0, nm, poly: r.polygon as Ring };
        })
        .filter((r) => r.bw >= long * 0.05 && (scaled || r.nm))
        .filter((r) => !r.nm || !/^(space|zone|region)$/i.test(r.nm))
        .sort((a, b) => b.px - a.px)
        .slice(0, 12);
      for (const r of rooms) {
        const area = scaled && ppm ? r.px / (ppm * ppm) : null;
        if (area !== null && area < 2 && !r.nm) continue;
        const text = [r.nm, area !== null ? `${area.toFixed(1)} m²` : null].filter(Boolean).join(" · ");
        if (text) items.push({ x: r.cx, y: r.cy, text, hover: scaled && ppm ? { kind: "room", poly: r.poly, floorKey: key, ppm, src, area: area ?? undefined } : undefined });
      }
      for (const it of items) {
        const { t, wpx, hpx } = this.tagTex(it.text);
        const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, opacity: 0, depthTest: false, fog: false, sizeAttenuation: false }));
        sp.scale.set(this.spritePx(wpx), this.spritePx(hpx), 1);
        sp.position.set((it.x - w / 2) * s, group.position.y + H * s * 0.6, (it.y - h / 2) * s);
        sp.renderOrder = 13;
        this.dimGroup.add(sp);
        this.dims.push({ sprite: sp, born: t0 + (scaled ? n * 90 : 2600 + n * 40), hover: it.hover, wpx, hpx });
        n++;
      }
    }
  }

  private stepDims() {
    if (!this.dims.length) return;
    const now = performance.now();
    for (const d of this.dims) (d.sprite.material as THREE.SpriteMaterial).opacity = Math.min(1, Math.max(0, (now - d.born) / 300));
  }

  // ---- measure tool
  /** Turn on two-click measuring on one floor; cb gets the two image-pixel points. */
  setMeasure(floorKey: string | null, cb: ((px: [number, number][]) => void) | null, keep = false) {
    this.measureKey = floorKey;
    this.measureCb = cb;
    if (!keep) {
      this.measurePts = [];
      this.clear(this.measureGroup);
      this.measureHover = null;
    }
    this.renderer.domElement.style.cursor = floorKey ? "crosshair" : "grab";
    // hold the model still while measuring (two exact clicks on a rotating model is impossible)
    window.clearTimeout(this.resumeTimer);
    this.controls.autoRotate = floorKey ? false : !this.reduce;
    this.controls.enableRotate = !floorKey;
  }

  /** Nearest floor plane under the pointer, as floor-local drawing pixels. Planes are raycast even when the drawing is hidden. */
  private floorPoint(): { floor: string; x: number; y: number } | null {
    this.ray.setFromCamera(this.mouse, this.camera);
    let best: { floor: string; x: number; y: number; d: number } | null = null;
    for (const [key, fl] of this.floorGroups) {
      const hit = this.ray.intersectObject(fl.plane, false)[0];
      if (!hit || (best && hit.distance >= best.d)) continue;
      const l = fl.group.worldToLocal(hit.point.clone());
      best = { floor: key, x: l.x + fl.w / 2, y: l.z + fl.h / 2, d: hit.distance };
    }
    return best ? { floor: best.floor, x: best.x, y: best.y } : null;
  }

  /** Turn element picking (hover + click on the model) on or off. */
  setElementPicking(on: boolean) {
    this.elPicking = on;
    if (!on) this.clear(this.elGroup);
  }

  /** Outline one element on its floor (floor-local drawing pixels); null clears. `hot` = selected, else hover. */
  setElementOutline(floorKey: string | null, polygon: [number, number][] | null, hot: boolean) {
    this.clear(this.elGroup);
    const fl = floorKey ? this.floorGroups.get(floorKey) : undefined;
    if (!fl || !polygon || polygon.length < 2) return;
    const y = fl.H * 0.55;
    const pts = polygon.map(([x, z]) => fl.group.localToWorld(new THREE.Vector3(x - fl.w / 2, y, z - fl.h / 2)));
    const mat = new THREE.LineBasicMaterial({ color: hot ? this.T.pin : this.T.accent, depthTest: false, transparent: true, opacity: hot ? 1 : 0.8 });
    const line = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts), mat);
    line.renderOrder = 11;
    this.elGroup.add(line);
  }

  /** slow idle drift, only after 45 s without any interaction */
  private armIdle() {
    window.clearTimeout(this.resumeTimer);
    this.controls.autoRotate = false;
    this.resumeTimer = window.setTimeout(() => (this.controls.autoRotate = !this.reduce && !this.measureKey), 45000);
  }

  // ---- view cube: preset views, orbit by drag, re-centre (eased, damped)
  private viewMode: "3d" | "top" | "front" | "side" = "3d";
  get view() { return this.viewMode; }
  private bounds(): { c: THREE.Vector3; r: number } {
    const box = new THREE.Box3();
    for (const fl of this.floorGroups.values()) box.expandByObject(fl.plane);
    if (box.isEmpty()) return { c: new THREE.Vector3(), r: 100 };
    const sph = box.getBoundingSphere(new THREE.Sphere());
    return { c: sph.center, r: Math.max(10, sph.radius) };
  }
  setView(mode: "3d" | "top" | "front" | "side", dur = 650) {
    this.viewMode = mode;
    const { c, r } = this.bounds();
    const d = r * 2.1;
    const dir = mode === "top" ? new THREE.Vector3(0, 1, 0.0001)
      : mode === "front" ? new THREE.Vector3(0, 0.18, 1)
      : mode === "side" ? new THREE.Vector3(1, 0.18, 0)
      : new THREE.Vector3(0.62, 0.72, 0.85);
    this.controls.maxPolarAngle = mode === "top" ? 0.0001 : Math.PI * 0.49;
    this.controls.enableRotate = mode !== "top";
    this.controls.autoRotate = false;
    this.flyTo(c.clone().add(dir.normalize().multiplyScalar(d)), c.clone(), dur);
  }
  recenter(dur = 600) { this.setView(this.viewMode, dur); }
  /** drag on the view cube: orbit around the target */
  orbitBy(dxPx: number, dyPx: number) {
    if (this.viewMode === "top") { this.setView("3d", 450); return; }
    const off = this.camera.position.clone().sub(this.controls.target);
    const sph = new THREE.Spherical().setFromVector3(off);
    sph.theta -= dxPx * 0.008;
    sph.phi = Math.min(Math.PI * 0.49, Math.max(0.05, sph.phi - dyPx * 0.008));
    off.setFromSpherical(sph);
    this.camera.position.copy(this.controls.target.clone().add(off));
    this.controls.autoRotate = false;
    this.controls.update();
  }
  /** camera azimuth in radians (the view cube rotates with it) */
  azimuth(): number {
    const off = this.camera.position.clone().sub(this.controls.target);
    return Math.atan2(off.x, off.z);
  }

  // ---- layers (envelope / walls / furniture / piping / electrical) and multi-highlight
  private layerObjs: Record<string, THREE.Object3D> = {};
  setLayers(floorKey: string | null, layers: { envelope?: [number, number][][]; rooms?: [number, number][][]; furniture?: { polygon: [number, number][] }[];
    piping?: [number, number][][]; electrical?: [number, number][][] } | null, colours: Record<string, number>) {
    for (const o of Object.values(this.layerObjs)) o.parent?.remove(o);
    this.layerObjs = {};
    const fl = floorKey ? this.floorGroups.get(floorKey) : undefined;
    if (!fl || !layers) return;
    // children of the floor group: the same local drawing-pixel frame as the walls (x - w/2, height, z - h/2)
    const L = (x: number, z: number, y: number) => new THREE.Vector3(x - fl.w / 2, y, z - fl.h / 2);
    const mk = (name: string, rings: [number, number][][], y: number, closed: boolean) => {
      const g = new THREE.Group();
      const mat = new THREE.LineBasicMaterial({ color: colours[name] ?? 0xffffff, transparent: true, opacity: 0.95, depthTest: false });
      for (const r of rings) {
        if (r.length < 2) continue;
        const geo = new THREE.BufferGeometry().setFromPoints(r.map(([x, z]) => L(x, z, y)));
        const ln = closed ? new THREE.LineLoop(geo, mat) : new THREE.Line(geo, mat);
        ln.renderOrder = 9;
        g.add(ln);
      }
      this.layerObjs[name] = g;
      fl.group.add(g);
    };
    if (layers.envelope?.length) mk("envelope", layers.envelope, fl.H * 0.03, true);
    if (layers.rooms?.length) mk("rooms", layers.rooms, fl.H * 0.04, true);       // room boundaries as thin lines
    if (layers.furniture?.length) {          // furniture: low translucent blocks, about knee height
      const g = new THREE.Group();
      const mat = new THREE.MeshBasicMaterial({ color: colours.furniture ?? 0x2dd4bf, transparent: true, opacity: 0.38, depthWrite: false });
      const hgt = fl.H * 0.08;                  // low blocks: the building reads first, furniture second
      for (const f of layers.furniture) {
        const xs = f.polygon.map((q) => q[0]), zs = f.polygon.map((q) => q[1]);
        const x0 = Math.min(...xs), x1 = Math.max(...xs), z0 = Math.min(...zs), z1 = Math.max(...zs);
        const m = new THREE.Mesh(new THREE.BoxGeometry(Math.max(1, x1 - x0), hgt, Math.max(1, z1 - z0)), mat);
        m.position.copy(L((x0 + x1) / 2, (z0 + z1) / 2, hgt / 2));
        g.add(m);
      }
      this.layerObjs.furniture = g;
      fl.group.add(g);
    }
    if (layers.piping?.length) mk("piping", layers.piping, fl.H * 0.35, false);
    if (layers.electrical?.length) mk("electrical", layers.electrical, fl.H * 0.5, false);
  }
  setLayerVisible(name: string, on: boolean) {
    const o = this.layerObjs[name];
    if (o) o.visible = on;
    if (name === "walls") for (const fl of this.floorGroups.values()) for (const pt of fl.parts) if ((pt as { kind?: string }).kind === "wall") pt.obj.visible = on;
  }
  private multiGroup = new THREE.Group();
  /** highlight many polygons at once (a checklist row: every bed) and fly to them */
  setMulti(floorKey: string | null, polys: [number, number][][], fly = true) {
    this.clear(this.multiGroup);
    if (!this.multiGroup.parent) this.scene.add(this.multiGroup);
    const fl = floorKey ? this.floorGroups.get(floorKey) : undefined;
    if (!fl || !polys.length) return;
    const y = fl.H * 0.6;
    const mat = new THREE.LineBasicMaterial({ color: this.T.pin, depthTest: false, transparent: true, opacity: 0.95 });
    const box = new THREE.Box3();
    for (const poly of polys) {
      const pts = poly.map(([x, z]) => fl.group.localToWorld(new THREE.Vector3(x - fl.w / 2, y, z - fl.h / 2)));
      pts.forEach((q) => box.expandByPoint(q));
      const ln = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts), mat);
      ln.renderOrder = 12;
      this.multiGroup.add(ln);
    }
    if (fly && !box.isEmpty()) {
      const sph = box.getBoundingSphere(new THREE.Sphere());
      const off = this.camera.position.clone().sub(this.controls.target).normalize();
      this.flyTo(sph.center.clone().add(off.multiplyScalar(Math.max(18, sph.radius * 2.4))), sph.center.clone(), 650);
    }
  }

  private measureClick() {
    const fl = this.measureKey ? this.floorGroups.get(this.measureKey) : undefined;
    if (!fl) return;
    this.ray.setFromCamera(this.mouse, this.camera);
    const hit = this.ray.intersectObject(fl.plane, false)[0];
    if (!hit) return;
    const l = fl.group.worldToLocal(hit.point.clone());
    if (this.measurePts.length >= 2) {
      this.measurePts = [];
      this.measureHover = null;
      this.clear(this.measureGroup);
    }
    this.measurePts.push([l.x + fl.w / 2, l.z + fl.h / 2]);
    const dot = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.dotTex(), transparent: true, depthTest: false, fog: false, sizeAttenuation: false }));
    dot.scale.setScalar(this.spritePx(7));
    dot.position.copy(hit.point).setY(fl.group.position.y + 0.5);
    dot.renderOrder = 12;
    this.measureGroup.add(dot);
    if (this.measurePts.length === 2) {
      const a = this.measureGroup.children[0].position;
      const b = this.measureGroup.children[1].position;
      this.measureGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]), new THREE.LineBasicMaterial({ color: this.T.pin, depthTest: false })));
      this.measureHover = { a: a.clone(), b: b.clone(), px: Math.hypot(this.measurePts[1][0] - this.measurePts[0][0], this.measurePts[1][1] - this.measurePts[0][1]) };
      this.measureCb?.([...this.measurePts]);
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
        if (performance.now() > this.introUntil) p.rate = 0.1;
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
    this.geos = new Map(floors.map((f) => [f.key, f.geo]));
    this.clearScans();
    const my = ++this.token;
    this.clear(this.root);
    this.floorGroups.clear();
    this.clearPins();
    this.clear(this.dimGroup);
    this.dims = [];
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
    this.linkStairs(floors, gap);
    this.applyStage();
    if (!this.reduce) {
      const t0 = performance.now();
      this.introUntil = t0 + 2700;
      for (const fl of this.floorGroups.values()) {
        for (const p of fl.parts) if (p.target > 0) {
          p.cur = 0;
          p.delayUntil = t0 + (INTRO_DELAY[p.name] ?? 0);
          if (p.name === "walls") p.rate = 0.04;
        }
        // a thin scan line sweeps the flat drawing before anything rises
        const w = fl.w;
        const h = fl.h;
        const bar = new THREE.Mesh(new THREE.PlaneGeometry(w, Math.max(w, h) * 0.008), new THREE.MeshBasicMaterial({ color: this.T.accent, transparent: true, opacity: 0.95, depthWrite: false, depthTest: false }));
        bar.rotation.x = -Math.PI / 2;
        bar.renderOrder = 8;
        fl.group.add(bar);
        this.scans.push({ mesh: bar, start: t0 + 100, h, fl });
      }
    }
    this.lastInteract = performance.now();
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
    const homePos = new THREE.Vector3(fx + dist * 0.55, mid + dist * 0.5, fz + dist * 0.7);
    const homeTarget = new THREE.Vector3(fx, mid, fz);
    this.home = { pos: homePos.clone(), target: homeTarget.clone() };
    this.beforeScale = null;
    if (this.reduce) this.camera.position.copy(homePos);
    else {
      const from = homeTarget.clone().add(homePos.clone().sub(homeTarget).multiplyScalar(1.45)).add(new THREE.Vector3(0, dist * 0.45, 0));
      this.camera.position.copy(from);
      this.flyTo(homePos, homeTarget, 2600);
    }
    this.armIdle();
    if (this.topDown) {                       // floors rebuilt while measuring: stay looking straight down
      this.controls.autoRotate = false;
      this.beforeScale = { pos: homePos.clone(), target: homeTarget.clone() };
      this.flyTo(homeTarget.clone().add(new THREE.Vector3(0, homePos.distanceTo(homeTarget) * 1.02, 0.001)), homeTarget, 900);
    }
    this.controls.update();
  }

  /** Stacked floors: a dashed line joins each staircase to the nearest staircase on the floor above. */
  private linkStairs(floors: FloorInput[], gap: number) {
    if (floors.length < 2) return;
    const at = (f: FloorInput, i: number) => {
      const s = 100 / Math.max(f.geo.width, f.geo.height);
      return f.geo.fixtures.filter((e) => /stair/i.test(e.kind) && e.polygon.length).map((e) => {
        const cx = e.polygon.reduce((a, p) => a + p[0], 0) / e.polygon.length;
        const cy = e.polygon.reduce((a, p) => a + p[1], 0) / e.polygon.length;
        return new THREE.Vector3((cx - f.geo.width / 2) * s, i * gap, (cy - f.geo.height / 2) * s);
      });
    };
    const mat = new THREE.LineDashedMaterial({ color: this.T.accent, dashSize: 1.2, gapSize: 0.8, transparent: true, opacity: 0.9 });
    const stepMat = new THREE.MeshBasicMaterial({ color: this.T.accent, transparent: true, opacity: 0.6, depthWrite: false });
    const edgeMat = new THREE.LineBasicMaterial({ color: this.T.accent, transparent: true, opacity: 0.85 });
    for (let i = 0; i + 1 < floors.length; i++) {
      const lo = at(floors[i], i), hi = at(floors[i + 1], i + 1);
      for (const a of lo) {
        if (!hi.length) break;
        const b = hi.reduce((best, p) => (Math.hypot(p.x - a.x, p.z - a.z) < Math.hypot(best.x - a.x, best.z - a.z) ? p : best), hi[0]);
        const from = a.clone().setY(a.y + 3.6);
        const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([from, b]), mat);
        line.computeLineDistances();
        line.userData.stairLink = true;
        this.root.add(line);
        // a see-through flight of steps climbing from this staircase to the one on the floor above
        const n = Math.max(8, Math.round((b.y - from.y) / 1.6));
        const dir = new THREE.Vector3(b.x - from.x, 0, b.z - from.z);
        const yaw = Math.atan2(dir.x, dir.z);
        for (let k = 0; k < n; k++) {
          const t = (k + 0.5) / n;
          const g = new THREE.BoxGeometry(4.2, (b.y - from.y) / n, Math.max(0.8, dir.length() / n + 0.4));
          const step = new THREE.Mesh(g, stepMat);
          step.position.set(from.x + dir.x * t, from.y + (b.y - from.y) * t, from.z + dir.z * t);
          step.rotation.y = yaw;
          step.userData.stairLink = true;
          const ed = new THREE.LineSegments(new THREE.EdgesGeometry(g), edgeMat);
          ed.position.copy(step.position);
          ed.rotation.copy(step.rotation);
          this.root.add(step, ed);
        }
      }
    }
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
      const p: Part = { name, obj, mats, target: 1, cur: 1, scaleY: onY, layer: LAYER[name] ?? 0, delayUntil: 0, rate: 0.1 };
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
        const rt = `${r.subtype ?? ""} ${r.label ?? ""}`.toLowerCase();
        const c = new THREE.Color(/bath|toilet|wc|sauna|shower|laundry|wet|kph|\bph\b|\bwc\b/.test(rt) ? T.wet : /living|kitchen|dining|lounge|oh\b|\bkk\b/.test(rt) ? T.warm : T.tileLine);
        void i;
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

    const objs = buildObjects(geo.doors, geo.windows, geo.fixtures, w, h, H, T);
    mk("fixtures", objs.fixtures);
    mk("openings", objs.openings);

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
        if (v.type === "other" || views.length === 1) continue;     // no tag for generic regions (clutter, no information)
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

    void tintPart;
    return { group, s, w, h, H, plane, rim, content, parts };
  }

  private async loadTexture(f: FloorInput, plane: THREE.Mesh, token: number) {
    try {
      const res = await fetch(f.imgUrl);
      if (!res.ok) return;
      const blob = await res.blob();
      const long = Math.max(f.geo.width, f.geo.height);
      const scale = Math.min(1, 2048 / long);
      const opts: ImageBitmapOptions = { resizeWidth: Math.round(f.geo.width * scale), resizeHeight: Math.round(f.geo.height * scale), resizeQuality: "high", imageOrientation: "flipY" };
      const c = f.crop;
      const bmp = c ? await createImageBitmap(blob, c[0], c[1], c[2] - c[0], c[3] - c[1], opts) : await createImageBitmap(blob, { resizeWidth: Math.round(f.geo.width * scale), resizeHeight: Math.round(f.geo.height * scale), resizeQuality: "high", imageOrientation: "flipY" });
      if (token !== this.token || this.disposed) return;
      const t = new THREE.Texture(bmp);
      t.colorSpace = THREE.SRGBColorSpace;
      t.flipY = false; // already flipped when the bitmap was made
      t.anisotropy = 4;
      t.needsUpdate = true;
      const m = plane.material as THREE.MeshBasicMaterial;
      m.map = t;
      m.color.set(this.T.imgColor);
      m.opacity = this.topDown ? 0.95 : this.T.imgOpacity;
      m.needsUpdate = true;
    } catch {
      /* image stays a plain slab */
    }
  }

  private clearPins() {
    this.clear(this.pinGroup);
    this.pins = [];
  }

  /** Pins for the selected answer: a 5 px dot on the element, a 1 px leader up, a compact number tag. */
  setPins(floorKey: string | null, pins: PinInput[]) {
    this.clearPins();
    this.lastInteract = performance.now();
    const fl0 = floorKey ? this.floorGroups.get(floorKey) : undefined;
    if (!pins.length) return;
    const lineMat = new THREE.LineBasicMaterial({ color: this.T.pin, transparent: true, opacity: 0.85 });
    for (const p of pins) {
      const fl = p.floor ? this.floorGroups.get(p.floor) : fl0;
      if (!fl) continue;
      const { group, w, h, H, s } = fl;
      const lift = H * 2.0 * s;
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
      const wy = group.position.y + H * 0.4 * s;
      const base = new THREE.Vector3(wx, wy, wz);
      const top = new THREE.Vector3(wx, wy + lift, wz);
      const dot = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.dotTex(), transparent: true, depthTest: false, fog: false, sizeAttenuation: false }));
      dot.position.copy(base);
      dot.renderOrder = 10;
      const label = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.labelTex(p.idx, false).t, transparent: true, depthTest: false, fog: false, sizeAttenuation: false }));
      label.center.set(0.5, 0);
      label.position.copy(top);
      label.renderOrder = 11;
      this.pinGroup.add(dot, label);
      this.pinGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([base, top]), lineMat));
      const pts = poly.map(([x, y]) => new THREE.Vector3((x - w / 2) * s, group.position.y + 0.4, (y - h / 2) * s));
      if (pts.length > 1) this.pinGroup.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: this.T.pin, transparent: true, opacity: 0.6 })));
      this.pins.push({ dot, label, idx: p.idx, base, top, lw: 20, lh: 14, show: true });
    }
    this.applyHot();
    this.declutter();
  }

  private clear(g: THREE.Object3D) {
    for (const c of [...g.children]) {
      g.remove(c);
      c.traverse((o) => {
        const m = o as THREE.Mesh;
        m.geometry?.dispose?.();
        const mat = m.material as THREE.Material & { map?: THREE.Texture | null };
        if (mat?.map && !(o instanceof THREE.Sprite && (g === this.pinGroup || g === this.measureGroup))) mat.map.dispose();
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
