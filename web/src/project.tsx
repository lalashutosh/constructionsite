import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Folder, X } from "lucide-react";
import type { BuildingResult } from "./api";

const ic = { size: 16, strokeWidth: 1.5, "aria-hidden": true } as const;

/** Plain word for a document type from the engine. */
export function typeWord(t: string): string {
  const k = t.toLowerCase();
  if (/floor/.test(k)) return "Floor plan";
  if (/site/.test(k)) return "Site plan";
  if (/section/.test(k)) return "Section";
  if (/elev/.test(k)) return "Elevation";
  if (/detail/.test(k)) return "Detail";
  if (/sched/.test(k)) return "Schedule";
  if (/render|3d|view/.test(k)) return "3D render";
  if (/bim|ifc|model/.test(k)) return "BIM model";
  if (/cad|dwg|dxf/.test(k)) return "CAD drawing";
  if (/photo/.test(k)) return "Photo";
  const w = k.replace(/_/g, " ");
  return w.charAt(0).toUpperCase() + w.slice(1);
}
const plural = (w: string, n: number) => (n === 1 ? w : /plan$/.test(w) ? `${w}s` : `${w}s`);

export interface ProjFile {
  path: string;
  name: string;
  docType: string;
  sheet: string | null;
  title: string | null;
  why: string | null;
  isFloor: boolean;
  levelLabel: string | null;
  altOf?: string | null; // path of the plan this is another version of
  label?: string | null;
}

export function flattenProject(r: BuildingResult): ProjFile[] {
  const out: ProjFile[] = [];
  const pathOf = new Map(r.floors.map((f) => [f.name, f.path]));
  for (const f of r.floors)
    out.push({ path: f.path, name: f.name, docType: f.doc_type || "floor_plan", sheet: f.sheet ?? null, title: f.title ?? null, why: f.why ?? null, isFloor: true, levelLabel: f.level_label ?? null, label: f.display_label ?? null });
  for (const f of r.alternatives)
    out.push({ path: f.path, name: f.name, docType: f.doc_type || "floor_plan", sheet: f.sheet ?? null, title: f.title ?? null, why: f.why ?? null, isFloor: true, levelLabel: f.level_label ?? null, altOf: (f.alternative_of && pathOf.get(f.alternative_of)) || "", label: f.display_label ?? null });
  for (const f of r.other)
    out.push({ path: f.path, name: f.name, docType: f.doc_type, sheet: f.sheet ?? null, title: f.title ?? null, why: f.why ?? null, isFloor: false, levelLabel: null, label: f.display_label ?? null });
  return out;
}

/** Sentence for the viewer when the folder has no floor plans, e.g. "3 sections, 2 elevations". */
export function noFloorsNote(files: ProjFile[]): string {
  const c = new Map<string, number>();
  for (const f of files) if (!f.isFloor) c.set(typeWord(f.docType), (c.get(typeWord(f.docType)) ?? 0) + 1);
  const parts = [...c].map(([w, n]) => `${n} ${plural(w.toLowerCase(), n)}`);
  return `No floor plans in this folder${parts.length ? ` — ${parts.join(", ")}` : ""} (click a file to view it)`;
}

interface Node {
  name: string;
  children: Map<string, Node>;
  file?: ProjFile;
}

export type FileStatus = "queued" | "reading" | "done" | "not a plan";
export function ProjectDrawer(p: {
  result: BuildingResult | null;
  pending: string[];
  statusOf: (f: ProjFile) => FileStatus;
  files: ProjFile[];
  activePath: string | null;
  flatPath: string | null;
  onOpen: (f: ProjFile) => void;
  onClose: () => void;
  skipped: string;
}) {
  const [filter, setFilter] = useState<string | null>(null);
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const counts = useMemo(() => {
    const c = new Map<string, number>();
    for (const f of p.files) c.set(f.docType, (c.get(f.docType) ?? 0) + 1);
    return [...c];
  }, [p.files]);
  const root = useMemo(() => {
    const r: Node = { name: "", children: new Map() };
    for (const f of p.files) {
      if (filter && f.docType !== filter) continue;
      const parts = f.name.split("/");
      let n = r;
      parts.forEach((seg, i) => {
        if (!n.children.has(seg)) n.children.set(seg, { name: seg, children: new Map() });
        n = n.children.get(seg)!;
        if (i === parts.length - 1) n.file = f;
      });
    }
    return r;
  }, [p.files, filter]);

  const row = (n: Node, depth: number, id: string): React.ReactNode => {
    if (n.file) {
      const f = n.file;
      const sel = f.path === (p.flatPath ?? p.activePath);
      return (
        <li key={id}>
          <button className={`prow ${sel ? "sel" : ""}`} style={{ paddingLeft: 21 + depth * 13 }} onClick={() => p.onOpen(f)} title={f.why ?? undefined}>
            <span className="ptitle">
              <span className="pname">{f.sheet ? <b className="mono">{f.sheet}</b> : null}{f.sheet ? " " : ""}{f.label || f.title || n.name}</span>
              {sel && f.why && <small className="muted">{f.why}</small>}
            </span>
            <span className={`ptype ${f.isFloor ? "plan" : ""}`}>{f.altOf !== undefined && <em className="pst version">version</em>}{f.docType === "pending" ? "" : typeWord(f.docType)}<em className={`pst ${p.statusOf(f).replace(" ", "-")}`}>{p.statusOf(f)}</em></span>
          </button>
        </li>
      );
    }
    const open = !closed.has(id);
    return (
      <li key={id}>
        <button className="prow folder" style={{ paddingLeft: 13 + depth * 13 }} onClick={() => setClosed((s) => { const x = new Set(s); if (x.has(id)) x.delete(id); else x.add(id); return x; })} aria-expanded={open}>
          {open ? <ChevronDown {...ic} size={14} /> : <ChevronRight {...ic} size={14} />}<Folder {...ic} size={14} /><span className="pname">{n.name}</span>
        </button>
        {open && <ul className="ptree">{[...n.children.values()].map((c) => row(c, depth + 1, `${id}/${c.name}`))}</ul>}
      </li>
    );
  };

  return (
    <aside className="drawer projdrawer" aria-label="Project">
      <header>
        <h2>Project</h2>
        <button className="x" onClick={p.onClose} aria-label="Close project"><X {...ic} /></button>
      </header>
      <div className="phd">
        <p>{p.result?.building || "Sorting the folder…"}</p>
        {p.result && <small className="muted mono">{p.result.method}</small>}
        {p.skipped && <small className="muted">{p.skipped}</small>}
        {(p.result?.notes ?? []).map((n) => <small key={n} className="muted">{n}</small>)}
      </div>
      <div className="pchips">
        <button className={`chip sm ${filter === null ? "on" : ""}`} onClick={() => setFilter(null)}>All {p.files.length}</button>
        {counts.map(([t, n]) => (
          <button key={t} className={`chip sm ${filter === t ? "on" : ""}`} onClick={() => setFilter(filter === t ? null : t)}>{typeWord(t)} {n}</button>
        ))}
      </div>
      <div className="dscroll"><ul className="ptree">{[...root.children.values()].map((c) => row(c, 0, c.name))}</ul></div>
    </aside>
  );
}
