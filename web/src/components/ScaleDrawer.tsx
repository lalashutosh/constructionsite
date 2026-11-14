import type { ReactNode } from "react";

const n = (c: Record<string, unknown> | null, k: string): number | null => (c && typeof c[k] === "number" ? (c[k] as number) : null);

/** "How we scale": design facts and ONLY numbers read from claims.json. */
export function ScaleDrawer({ claims, onClose }: { claims: Record<string, unknown> | null; onClose: () => void }) {
  const cpu = n(claims, "cpu_per_drawing_s");
  const ms = n(claims, "mean_ms");
  const usd = n(claims, "usd_total");
  const llm = n(claims, "llm_calls");
  const nq = n(claims, "n_questions");
  const rows: { h: string; p: ReactNode }[] = [
    { h: "Extract once per file hash", p: `A drawing is read once and cached under its sha256. Asking again, or asking something else, never re-reads it.${cpu != null ? ` Measured: ${cpu.toFixed(2)} s of CPU per drawing (estimate for a fresh read).` : ""}` },
    { h: "Questions are lookups", p: `After extraction a question is a query over stored facts.${ms != null ? ` Mean ${ms.toFixed(0)} ms per question${nq != null ? ` over ${nq.toLocaleString("en")} questions` : ""}.` : ""}` },
    { h: "Cascade, cheapest exact reader first", p: "Vector files answer exactly; raster needs two independent readers; only unresolved cases would ever reach a model." },
    { h: "Routing by title block only", p: "Deciding which reader a sheet needs looks at the title block, not at every pixel." },
    { h: "Model use", p: `${llm != null ? `${llm} model calls` : "No model calls"} in the measured run${usd != null ? `, $${usd.toFixed(2)} in total` : ""}. The model never produces the number.` },
  ];
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal drawer" role="dialog" aria-modal="true" aria-label="How we scale" onClick={(e) => e.stopPropagation()} data-testid="scale-drawer">
        <h3>How we scale</h3>
        <ul>
          {rows.map((r) => (
            <li key={r.h}>
              <b>{r.h}</b>
              <p>{r.p}</p>
            </li>
          ))}
        </ul>
        <div className="btnrow">
          <button className="btn" onClick={onClose} autoFocus>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
