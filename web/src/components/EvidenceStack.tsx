import { useMemo, useState } from "react";
import type { Element as PlumbElement, ProofObject } from "../types";
import { bboxOf, centroid, layerOf, polygonToPoints, LAYER_ORDER, LAYER_LABEL, type LayerKind } from "../geometry";
import "./EvidenceStack.css";

interface ChipElement {
  el: PlumbElement;
  chip: number;
}

type Grouped = Record<LayerKind, ChipElement[]>;

export type ViewMode = "scan" | "reading" | "overlay";

export interface EvidenceStackProps {
  proof: ProofObject | null;
  mode: ViewMode;
  highlightIds: string[];
  pinnedId: string | null;
  trustLens: boolean;
  onHoverIds: (ids: string[]) => void;
  onPin: (id: string | null) => void;
}

const GAP = 42; // px between layers at full explode
const TILT = 22; // deg rotateX at full explode

function isSynthetic(proof: ProofObject): boolean {
  const txt = `${proof.provenance.credit ?? ""} ${proof.provenance.license ?? ""}`.toLowerCase();
  return txt.includes("synthetic");
}

export function EvidenceStack({ proof, mode, highlightIds, pinnedId, trustLens, onHoverIds, onPin }: EvidenceStackProps) {
  const [explode, setExplode] = useState(1);
  const [wipe, setWipe] = useState(50);

  const grouped = useMemo<Grouped>(() => {
    const g: Grouped = {
      scan: [],
      walls: [],
      rooms: [],
      doors: [],
      windows: [],
      other: [],
    };
    if (!proof) return g;
    proof.evidence.forEach((el, i) => {
      g[layerOf(el.kind)].push({ el, chip: i + 1 });
    });
    return g;
  }, [proof]);

  if (!proof) {
    return (
      <div className="evidence-stack evidence-stack--empty">
        <p>Loading proof…</p>
      </div>
    );
  }

  const bbox = bboxOf(proof.evidence);
  const viewBox = `${bbox.minX} ${bbox.minY} ${bbox.width} ${bbox.height}`;
  const synthetic = isSynthetic(proof);
  const refused = proof.tier === "grey";

  const isLit = (id: string) => highlightIds.includes(id) || pinnedId === id;
  const layerLit = (kind: LayerKind) => grouped[kind].some((e) => isLit(e.el.id));
  const anyHighlighted = highlightIds.length > 0 || pinnedId !== null;

  const layers: LayerKind[] = grouped.other.length > 0 ? [...LAYER_ORDER, "other"] : LAYER_ORDER;
  const effectiveExplode = mode === "reading" ? explode : 0;

  function Chips({ kind }: { kind: LayerKind }) {
    return (
      <>
        {grouped[kind].map(({ el, chip }) => {
          const [cx, cy] = centroid(el.polygon);
          const lit = isLit(el.id);
          return (
            <g
              key={el.id}
              className={`chip ${lit ? "chip--lit" : ""} ${pinnedId === el.id ? "chip--pinned" : ""}`}
              tabIndex={0}
              role="button"
              aria-label={`${el.kind} ${chip}`}
              onMouseEnter={() => onHoverIds([el.id])}
              onMouseLeave={() => onHoverIds([])}
              onClick={() => onPin(pinnedId === el.id ? null : el.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter") onPin(pinnedId === el.id ? null : el.id);
              }}
            >
              <circle cx={cx} cy={cy} r={11} />
              <text x={cx} y={cy + 4} textAnchor="middle">
                {chip}
              </text>
            </g>
          );
        })}
      </>
    );
  }

  function LayerSvg({ kind, showChips }: { kind: LayerKind; showChips: boolean }) {
    return (
      <svg className="layer-svg" viewBox={viewBox} preserveAspectRatio="xMidYMid meet">
        {grouped[kind].map(({ el }) => (
          <polygon
            key={el.id}
            points={polygonToPoints(el.polygon)}
            className={`shape shape--${el.kind} ${isLit(el.id) ? "shape--lit" : ""}`}
          />
        ))}
        {showChips && <Chips kind={kind} />}
      </svg>
    );
  }

  function ScanLayer() {
    return (
      <svg className="layer-svg layer-svg--scan" viewBox={viewBox} preserveAspectRatio="xMidYMid meet">
        <rect x={bbox.minX} y={bbox.minY} width={bbox.width} height={bbox.height} className="scan-paper" />
      </svg>
    );
  }

  return (
    <div className="evidence-stack">
      <div className="evidence-stack__toolbar">
        <label className="slider-label">
          Explode
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={explode}
            disabled={mode !== "reading"}
            onChange={(e) => setExplode(Number(e.target.value))}
          />
        </label>
        <label className="slider-label">
          Wipe
          <input
            type="range"
            min={0}
            max={100}
            step={1}
            value={wipe}
            disabled={mode !== "overlay"}
            onChange={(e) => setWipe(Number(e.target.value))}
          />
        </label>
      </div>

      {synthetic && <div className="ribbon">SYNTHETIC DEMO</div>}

      {refused ? (
        <div className="refusal-panel">
          <div className="refusal-icon" aria-hidden="true">
            ∅
          </div>
          <p className="refusal-word">cannot answer</p>
          <p className="refusal-reason">{proof.refusal ?? "No evidence extracted from this sheet."}</p>
        </div>
      ) : mode === "scan" ? (
        <div className="stack-scene stack-scene--flat">
          <ScanLayer />
        </div>
      ) : mode === "overlay" ? (
        <div className="stack-scene stack-scene--flat">
          <div className="overlay-base">
            <ScanLayer />
          </div>
          <div className="overlay-reading" style={{ clipPath: `inset(0 ${100 - wipe}% 0 0)` }}>
            {layers.map((kind) => (
              <div key={kind} className={`overlay-layer ${layerLit(kind) ? "layer--lit" : ""}`}>
                <LayerSvg kind={kind} showChips={kind !== "walls" && kind !== "rooms"} />
              </div>
            ))}
          </div>
          <div className="wipe-line" style={{ left: `${wipe}%` }} />
        </div>
      ) : (
        <div className="stack-scene">
          <div className="stack-inner" style={{ transform: `rotateX(${TILT * effectiveExplode}deg)` }}>
            <div
              className="layer layer--scan"
              style={{ transform: `translateZ(${0}px)` }}
            >
              <ScanLayer />
              <span className="layer-tag">{LAYER_LABEL.scan}</span>
            </div>
            {layers.map((kind, i) => {
              const lit = layerLit(kind);
              const dim = trustLens && anyHighlighted && !lit;
              return (
                <div
                  key={kind}
                  className={`layer ${lit ? "layer--lit" : ""} ${dim ? "layer--dim" : ""}`}
                  style={{ transform: `translateZ(${(i + 1) * GAP * effectiveExplode}px)` }}
                >
                  <LayerSvg kind={kind} showChips />
                  <span className="layer-tag">{LAYER_LABEL[kind]}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <p className="credit-line">
        {proof.provenance.file} · {proof.provenance.credit ?? proof.provenance.license ?? "no credit on file"}
      </p>
    </div>
  );
}
