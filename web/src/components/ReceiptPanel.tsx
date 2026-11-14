import type { ReceiptLine } from "../derive";
import type { Tag } from "../types";

const ROWS: { tag: Tag; label: string; icon: string }[] = [
  { tag: "drawn", label: "Drawn", icon: "✎" },
  { tag: "specified", label: "Specified", icon: "§" },
  { tag: "chosen", label: "Chosen", icon: "✓" },
  { tag: "defaulted", label: "Defaulted", icon: "≈" },
  { tag: "open", label: "Open", icon: "?" },
];

export function ReceiptPanel({ lines, onHover, onPin }: { lines: Record<Tag, ReceiptLine[]>; onHover: (ids: string[]) => void; onPin: (id: string | null) => void }) {
  return (
    <>
      {ROWS.map((r) => (
        <section key={r.tag} className={`rrow r--${r.tag}`} data-testid={`receipt-${r.tag}`}>
          <h4>
            <span aria-hidden="true">{r.icon}</span> {r.label} <span style={{ opacity: 0.7 }}>{lines[r.tag].length}</span>
          </h4>
          {lines[r.tag].length === 0 ? (
            <p className="empty">nothing here</p>
          ) : (
            <ul>
              {lines[r.tag].map((l, i) => (
                <li key={i}>
                  <button
                    onMouseEnter={() => onHover(l.ids)}
                    onMouseLeave={() => onHover([])}
                    onFocus={() => onHover(l.ids)}
                    onBlur={() => onHover([])}
                    onClick={() => onPin(l.ids[0] ?? null)}
                  >
                    {l.text}
                    <span className="src">{l.source}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </>
  );
}
