import { useRef, useState } from "react";
import type { Sample } from "../api";

export interface SampleStripProps {
  samples: Sample[];
  sampleId: string;
  question: string;
  busy: boolean;
  onPick: (s: Sample) => void;
  onAsk: (q: string) => void;
  onUpload: (f: File) => void;
}

/** Live-mode header row: choose a drawing, choose or type a question. Every drawing carries its credit. */
export function SampleStrip({ samples, sampleId, question, busy, onPick, onAsk, onUpload }: SampleStripProps) {
  const cur = samples.find((s) => s.id === sampleId);
  const [typed, setTyped] = useState("");
  const file = useRef<HTMLInputElement>(null);
  return (
    <div className="strip" role="group" aria-label="choose a drawing and a question">
      <div className="thumbs" role="listbox" aria-label="sample drawings">
        {samples.map((s) => (
          <button key={s.id} role="option" aria-selected={s.id === sampleId} className={`thumb ${s.id === sampleId ? "thumb--on" : ""}`} title={`${s.label} · ${s.tags.join(", ")}`} onClick={() => onPick(s)}>
            {s.thumb ? <img src={s.thumb} alt="" loading="lazy" /> : <span className="thumb-vec" aria-hidden="true">vector</span>}
            <span className="thumb-l">{s.label}</span>
          </button>
        ))}
        <button className="thumb thumb--add" onClick={() => file.current?.click()} title="Use your own drawing">
          <span aria-hidden="true">+</span>
          <span className="thumb-l">Your drawing</span>
        </button>
        <input ref={file} type="file" accept=".png,.jpg,.jpeg,.pdf,.svg,.dxf" hidden onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])} />
      </div>
      <div className="askbar">
        <div className="qchips">
          {cur?.questions.map((q) => (
            <button key={q.label} className="qchip" aria-pressed={q.text === question} disabled={busy} onClick={() => onAsk(q.text)}>
              {q.label}
            </button>
          ))}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (typed.trim()) onAsk(typed.trim());
          }}
        >
          <input aria-label="ask a question about this drawing" placeholder="Ask anything about this drawing…" value={typed} onChange={(e) => setTyped(e.target.value)} />
          <button className="btn btn--primary" disabled={busy || !typed.trim()}>
            Ask
          </button>
        </form>
      </div>
    </div>
  );
}
