import type { Finding } from "../derive";

const IC = { ok: "✓", warn: "▲", info: "i" } as const;

export function FindingsList({ items, onHover, onPin }: { items: Finding[]; onHover: (ids: string[]) => void; onPin: (id: string | null) => void }) {
  return (
    <>
      {items.map((f, i) => (
        <button
          key={i}
          className={`find find--${f.sev}`}
          onMouseEnter={() => onHover(f.ids)}
          onMouseLeave={() => onHover([])}
          onFocus={() => onHover(f.ids)}
          onBlur={() => onHover([])}
          onClick={() => onPin(f.ids[0] ?? null)}
        >
          <span className="ic" aria-hidden="true">
            {IC[f.sev]}
          </span>
          <span>
            {f.text}
            {f.detail && <small>{f.detail}</small>}
          </span>
        </button>
      ))}
    </>
  );
}
