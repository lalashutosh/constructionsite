import { useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Element as PlumbElement, ProofObject, Tier } from "../types";
import { refusalWords } from "../derive";
import { bboxOf, centroid, polygonToPoints } from "../geometry";

export interface ScanImage {
  url: string;
  /** "pixels": same coordinate space as the evidence polygons. Anything else is shown for reference only. */
  coords: "pixels" | "pdf-render" | "svg" | "none";
}

export interface DuelReader {
  name: string;
  ids: string[];
}

export type ViewMode = "scan" | "reading" | "overlay";

export interface StackProps {
  proof: ProofObject;
  /** Context + evidence elements (facts merged with proof.evidence). */
  elements: PlumbElement[];
  size: { w: number; h: number } | null;
  answerIds: string[];
  disputedIds: string[];
  anchorIds: string[];
  tier: Tier;
  mode: ViewMode;
  explode: number;
  wipe: number;
  highlightIds: string[];
  pinnedId: string | null;
  lens: boolean;
  /** Show only the first N numbered chips (hook animation). */
  chipLimit?: number;
  trace?: boolean;
  /** 0..1 scan-line position, or null. */
  sweep?: number | null;
  showCredit?: boolean;
  /** The real scan (GET /api/image). Without it the Scan layer is a synthetic render of the facts. */
  scan?: ScanImage | null;
  /** Hook only: draw the plane at the scan's true pixel size, then ease to fit. */
  trueSize?: boolean;
  /** The two independent readers as two overlays (ring vs diamond). */
  readers?: DuelReader[];
  onHover: (ids: string[]) => void;
  onPin: (id: string | null) => void;
}

const GAP = 58;
const LABELS: Record<string, string> = {
  scan: "Scan",
  walls: "Walls",
  rooms: "Rooms",
  windows: "Windows",
  doors: "Doors",
  scale: "Scale anchors",
};
const KIND_LAYER: Record<string, string> = { wall: "walls", room: "rooms", window: "windows", door: "doors" };

export function isSynthetic(proof: ProofObject): boolean {
  const t = `${proof.provenance.credit ?? ""} ${proof.provenance.license ?? ""}`.toLowerCase();
  return t.includes("synthetic");
}

export function EvidenceStack(p: StackProps) {
  const els = p.elements as PlumbElement[];
  const sceneRef = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<{ w: number; h: number } | null>(null);
  useLayoutEffect(() => {
    const el = sceneRef.current;
    if (!el) return;
    const read = () => setBox({ w: el.clientWidth, h: el.clientHeight });
    read();
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const view = useMemo(() => {
    if (p.size) return { x: 0, y: 0, w: p.size.w, h: p.size.h };
    const b = bboxOf(els);
    return { x: b.minX, y: b.minY, w: b.width, h: b.height };
  }, [p.size, els]);

  const layers = useMemo(() => {
    const out: { key: string; els: PlumbElement[] }[] = [];
    for (const key of ["walls", "rooms", "windows", "doors"]) {
      const list = els.filter((e) => KIND_LAYER[e.kind] === key);
      if (list.length) out.push({ key, els: list });
    }
    const anchors = els.filter((e) => p.anchorIds.includes(e.id));
    if (anchors.length) out.push({ key: "scale", els: anchors });
    return out;
  }, [els, p.anchorIds]);

  const u = Math.max(view.w, view.h) / 62; // chip radius in drawing units: about 10 px on screen at any scale
  const synthetic = isSynthetic(p.proof);
  const words = refusalWords(p.proof);
  if (p.proof.tier === "grey") {
    return (
      <div className="stage">
        {p.scan && <img className="refusal-scan" src={p.scan.url} alt="the drawing that was refused" />}
        <div className="refusal" role="status">
          <div className="big" aria-hidden="true">∅</div>
          <h3>cannot answer</h3>
          <p>{words.reason}</p>
          <p className="fix-line">{words.fix}</p>
        </div>
        {synthetic && <div className="ribbon">SYNTHETIC DEMO</div>}
        <Credit proof={p.proof} />
      </div>
    );
  }

  const flat = p.mode !== "reading";
  const e = flat ? 0 : p.explode;
  let trueK = 1;
  if (p.trueSize && p.size && box) {
    const fit = Math.min((box.h * 0.84) / p.size.h, (box.w * 0.8) / p.size.w);
    trueK = fit > 0 ? 1 / fit : 1;
  }
  const planeT = `${trueK !== 1 ? `scale(${trueK}) ` : ""}rotateX(${58 * e}deg) rotateZ(${-30 * e}deg) scale(${1 - 0.1 * e}) translateY(${-2 * e}%)`;
  const tagStyle = { transform: `rotateZ(${30 * e}deg) rotateX(${-58 * e}deg) scale(${1 / (1 - 0.1 * e)})`, transformOrigin: "0 0", fontSize: 13 } as const;
  const isLit = (id: string) => p.highlightIds.includes(id) || p.pinnedId === id;
  const anyLit = p.highlightIds.length > 0 || p.pinnedId !== null;
  const chipOf = (id: string) => p.answerIds.indexOf(id);

  function shapes(list: PlumbElement[], key: string) {
    return list.map((el) => {
      const lit = isLit(el.id);
      const dis = p.disputedIds.includes(el.id);
      if (key === "scale") {
        const [cx, cy] = centroid(el.polygon);
        const b = bboxOf([el], 6);
        return <rect key={el.id} className="anchor-ring" x={b.minX - 4} y={b.minY - 4} width={b.width + 8} height={b.height + 8} data-cx={cx} data-cy={cy} />;
      }
      return (
        <g key={el.id}>
          <polygon
            points={polygonToPoints(el.polygon)}
            className={`shape shape--${el.kind} ${lit ? "shape--lit" : ""} ${dis ? "shape--disputed" : ""}`}
          />
          {el.kind === "room" && el.label && (
            <text className="room-label" x={centroid(el.polygon)[0]} y={bboxOf([el], 0).minY + 34} textAnchor="middle">
              {el.label}
            </text>
          )}
        </g>
      );
    });
  }

  function chips(list: PlumbElement[]) {
    return list.map((el) => {
      const idx = chipOf(el.id);
      if (idx < 0 || idx >= (p.chipLimit ?? 999)) return null;
      const [cx, cy] = centroid(el.polygon);
      const b = bboxOf([el], 0);
      // chips for doors/windows sit just above the element so they never hide it
      const small = b.height < u * 2.7;
      const y = small ? b.minY - u * 1.5 : cy;
      const dis = p.disputedIds.includes(el.id);
      const pinned = p.pinnedId === el.id;
      const toggle = () => p.onPin(pinned ? null : el.id);
      return (
        <g
          key={el.id}
          className={`chip chip--${p.tier} ${isLit(el.id) ? "chip--lit" : ""} ${pinned ? "chip--pinned" : ""} ${dis ? "chip--disputed" : ""} ${p.chipLimit !== undefined ? "chip--pop" : ""}`}
          tabIndex={0}
          role="button"
          aria-label={`${el.kind} ${idx + 1}${dis ? ", disputed" : ""}`}
          onMouseEnter={() => p.onHover([el.id])}
          onMouseLeave={() => p.onHover([])}
          onFocus={() => p.onHover([el.id])}
          onBlur={() => p.onHover([])}
          onClick={toggle}
          onKeyDown={(ev) => {
            if (ev.key === "Enter") toggle();
          }}
        >
          <circle cx={cx} cy={y} r={u} style={{ strokeWidth: u / 5.5 }} />
          <text x={cx} y={y + u * 0.36} textAnchor="middle" style={{ fontSize: u }}>
            {idx + 1}
          </text>
        </g>
      );
    });
  }

  const byId = new Map(els.map((x) => [x.id, x]));
  const readerLayer =
    p.readers && p.readers.length >= 2 ? (
      <div className="layer layer--readers" style={{ transform: `translateZ(${(layers.length + 1) * GAP * e}px)` }} aria-hidden="true">
        <svg viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`} preserveAspectRatio="xMidYMid meet">
          {p.readers.slice(0, 2).flatMap((rd, k) =>
            rd.ids.map((id) => {
              const el = byId.get(id);
              if (!el) return null;
              const [cx] = centroid(el.polygon);
              const b = bboxOf([el], 0);
              const off = u * 0.9;
              const x = k === 0 ? Math.min(b.minX, cx) - off * 0.2 : Math.max(b.maxX, cx) + off * 0.2;
              const y = k === 0 ? b.minY - off * 0.2 : b.maxY + off * 0.2;
              const dis = p.disputedIds.includes(id);
              const r = u * 0.62;
              return k === 0 ? (
                <circle key={`${rd.name}-${id}`} className={`reader reader--a ${dis ? "reader--dis" : ""}`} cx={x} cy={y} r={r} />
              ) : (
                <polygon key={`${rd.name}-${id}`} className={`reader reader--b ${dis ? "reader--dis" : ""}`} points={`${x},${y - r * 1.25} ${x + r * 1.25},${y} ${x},${y + r * 1.25} ${x - r * 1.25},${y}`} />
              );
            }),
          )}
        </svg>
        {e > 0.3 && <span className="layer-tag" style={tagStyle}>Two readers</span>}
      </div>
    ) : null;
  const vb = `${view.x} ${view.y} ${view.w} ${view.h}`;
  const reading = (
    <div
      className="reading-wrap"
      style={{
        position: "absolute",
        inset: 0,
        transformStyle: "preserve-3d",
        clipPath: p.mode === "overlay" ? `inset(0 ${100 - p.wipe}% 0 0)` : undefined,
        display: p.mode === "scan" ? "none" : undefined,
      }}
    >
      {layers.map((l, i) => {
        const lit = l.els.some((x) => isLit(x.id));
        const dim = p.lens && anyLit && !lit;
        return (
          <div
            key={l.key}
            className={`layer ${lit ? "layer--lit" : ""} ${dim ? "layer--dim" : ""}`}
            style={{ transform: `translateZ(${(i + 1) * GAP * e}px)` }}
          >
            {e > 0.05 && <div className="layer-glow" />}
            <svg viewBox={vb} preserveAspectRatio="xMidYMid meet" aria-label={LABELS[l.key]}>
              {shapes(l.els, l.key)}
              {l.key !== "scale" && chips(l.els)}
            </svg>
            {e > 0.3 && <span className="layer-tag" style={tagStyle}>{LABELS[l.key]} · {l.els.length}</span>}
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="stage">
      <div className="scene" ref={sceneRef}>
        <div
          className={`plane ${p.trace ? "trace" : ""}`}
          style={{ aspectRatio: `${view.w} / ${view.h}`, transform: planeT }}
        >
          <div className="layer" style={{ transform: "translateZ(0)" }}>
            <svg viewBox={vb} preserveAspectRatio="xMidYMid meet" aria-label="Scan">
              <defs>
                <filter id="grain">
                  <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="n" />
                  <feColorMatrix type="matrix" values="0 0 0 0 .5  0 0 0 0 .55  0 0 0 0 .6  0 0 0 .22 0" in="n" result="g" />
                  <feComposite in="g" in2="SourceGraphic" operator="in" result="gg" />
                  <feMerge>
                    <feMergeNode in="SourceGraphic" />
                    <feMergeNode in="gg" />
                  </feMerge>
                </filter>
              </defs>
              <g className="scan-wrap">
                <rect className="paper" x={view.x} y={view.y} width={view.w} height={view.h} />
                {p.scan ? (
                  <image className="scan-img" href={p.scan.url} x={view.x} y={view.y} width={view.w} height={view.h} preserveAspectRatio="xMidYMid meet" />
                ) : (
                  els
                    .filter((x) => x.kind !== "scale_anchor")
                    .map((x) => <polygon key={x.id} className="scan-ink" points={polygonToPoints(x.polygon)} />)
                )}
              </g>
            </svg>
            {e > 0.3 && <span className="layer-tag" style={tagStyle}>{p.scan ? (p.scan.coords === "pixels" ? "Scan" : "Scan (reference)") : "Scan (synthetic)"}</span>}
          </div>
          {reading}
          {p.mode !== "scan" && readerLayer}
          {p.mode === "overlay" && <div className="wipe-line" style={{ left: `${p.wipe}%` }} />}
          {p.sweep != null && <div className="sweep" style={{ top: `${p.sweep * 100}%` }} />}
        </div>
      </div>
      {synthetic && <div className="ribbon">SYNTHETIC DEMO</div>}
      {p.showCredit !== false && <Credit proof={p.proof} />}
    </div>
  );
}

export function Credit({ proof }: { proof: ProofObject }) {
  return (
    <p className="credit-line">
      <b>{proof.provenance.file.split("/").pop()}</b> · {proof.provenance.credit ?? proof.provenance.license ?? "no credit on file"}
    </p>
  );
}
