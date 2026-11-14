import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { answerCheck, fetchChecks, MOCK_CHECKS, ask, buildProject, fetchPlan, fetchSamples, setScale, ScaleError, geometry, imageUrl, upload, type Geometry, type Sample, type BuildPlan, type BuildingResult, type Check, type PlanElement, fetchElements, overrideElement, undoElement, ElementsUnavailable } from "./api";
import { ChecksBlock, kindWord, scaleBrief, pct as pctNum } from "./checks";
import { Inspector, kindName } from "./inspector";
import { chipsFor, findingSpecs } from "./logic";
import type { ProofObject } from "./types";
import { HowPage } from "./how";
import { ChecklistPanel, Tour, LAYER_COLOURS } from "./deepui";
import type { PlumbViewer } from "./viewer3d";
import { ProjectDrawer, flattenProject, noFloorsNote, typeWord, type FileStatus, type ProjFile } from "./project";
import { Ask, BuildPanel, Findings, Know, Rail, Drawer, Seg, ViewerPane, type BannerItem, type ProgressInfo, type ScaleState, type ThemeName, type Floor, type FindingState, type Upload } from "./panels";

interface ProjectState {
  names: string[];
  result: BuildingResult | null;
  stage: "upload" | "title" | "sort" | "build" | "done";
  upI: number;
  upN: number;
  since: number;
  error: string | null;
  skipped: string;
}
const FOLDER_STAGES = ["Uploading", "Reading title blocks", "AI sorting the sheets", "Building floors"];
const SINGLE_STAGES = ["Uploading", "Reading the drawing", "Checking with 2 AI reviewers", "Building in 3D", "Counting"];
const EXTS = ["png", "jpg", "jpeg", "pdf", "dxf", "ifc", "svg"];
const extOf = (n: string) => n.toLowerCase().split(".").pop() ?? "";

export default function App() {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [floors, setFloors] = useState<Floor[]>([]);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [findings, setFindings] = useState<Record<string, Record<string, FindingState>>>({});
  const [selected, setSelected] = useState<{ path: string; proof: ProofObject } | null>(null);
  const [asking, setAsking] = useState(false);
  const [askErr, setAskErr] = useState<string | null>(null);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [showPins, setShowPins] = useState(true);
  const [drawer, setDrawer] = useState(false);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [busy] = useState<string | null>(null);
  const [mode, setMode] = useState<"findings" | "plan">("findings");
  const [vibe, setVibe] = useState("standard");
  const [plans, setPlans] = useState<Record<string, BuildPlan>>({});
  const [stepIdx, setStepIdx] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [drawingOn, setDrawingOn] = useState(true);
  const [theme, setTheme] = useState<ThemeName>(() => {
    const saved = localStorage.getItem("plumb-theme");
    return saved === "light" || saved === "dark" ? saved : window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("plumb-theme", theme);
  }, [theme]);
  const [scale, setScaleState] = useState<ScaleState>("off");
  const [ppmByPath, setPpmByPath] = useState<Record<string, number>>({});
  const [banner, setBanner] = useState<BannerItem[] | null>(null);
  const [flash, setFlash] = useState<string[]>([]);
  const [why, setWhy] = useState(false);
  const [proj, setProj] = useState<ProjectState | null>(null);
  const [projDrawer, setProjDrawer] = useState(false);
  const [flat, setFlat] = useState<{ path: string; typeWord: string; title: string; why: string | null; sheet: string | null; isSchedule: boolean } | null>(null);
  const [upl, setUpl] = useState<{ since: number } | null>(null);
  const [, setTick] = useState(0);
  const retryRef = useRef<(() => void) | null>(null);
  const doneAt = useRef<Record<string, number>>({});
  const needTick = useRef(false);
  const [scaleIssue, setScaleIssue] = useState<{ message: string; label: string | null; lengthM: number | null } | null>(null);
  const [page, setPage] = useState<"work" | "how">("work");
  const [measureTyped, setMeasureTyped] = useState<string | null>(null);
  const [measuredPx, setMeasuredPx] = useState<number | null>(null);
  const [planExtra, setPlanExtra] = useState<Record<string, number>>({});
  const [checks, setChecks] = useState<Record<string, Check[]>>({});
  const [hoverCheck, setHoverCheck] = useState<Check | null>(null);
  const [checkBusy, setCheckBusy] = useState<string | null>(null);
  const [checkNote, setCheckNote] = useState<string | null>(null);
  const [checkErr, setCheckErr] = useState<string | null>(null);
  // element inspector
  const [elems, setElems] = useState<Record<string, PlanElement[] | "na">>({});
  const [elSel, setElSel] = useState<string | null>(null);
  const vref = useRef<PlumbViewer | null>(null);
  const [ckN, setCkN] = useState<Record<string, number>>({});
  const [elHover, setElHover] = useState<string | null>(null);
  const [elLocal, setElLocal] = useState<Record<string, Set<string>>>({});
  const [elUndo, setElUndo] = useState<Record<string, number>>({});
  const [elBusy, setElBusy] = useState(false);
  const [elNote, setElNote] = useState<string | null>(null);
  const [elErr, setElErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const dirRef = useRef<HTMLInputElement>(null);
  const runId = useRef(0);
  const [epoch, setEpoch] = useState(0);

  useEffect(() => {
    void fetchSamples().then(setSamples);
  }, []);

  const active = floors.find((f) => f.key === activeKey) ?? null;

  const open = useCallback((list: { path: string; name: string; credit?: string }[]) => {
    setEpoch((e) => e + 1);
    setSelected(null);
    setAskErr(null);
    setHoverIdx(null);
    setFloors(list.map((l) => ({ key: l.path, path: l.path, name: l.name, credit: l.credit ?? null, geo: null, geoErr: null })));
    setActiveKey(list[list.length - 1]?.path ?? null);
    setDrawer(false);
  }, []);

  // deep link: ?open=<dataset-relative or upload path>&name=<shown name> (demo + tests)
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const path = q.get("open");
    if (path) open([{ path, name: q.get("name") ?? path.split("/").pop() ?? path }]);
  }, [open]);

  // geometry for every floor, one at a time (first call per file can take a while)
  const geoBusy = useRef(false);
  useEffect(() => {
    if (geoBusy.current) return;
    const next = [...floors].sort((a, b) => (a.key === activeKey ? -1 : b.key === activeKey ? 1 : 0)).find((f) => !f.geo && !f.geoErr);
    if (!next) return;
    geoBusy.current = true;
    setFloors((fs) => fs.map((f) => (f.key === next.key ? { ...f, geoStart: Date.now() } : f)));
    geometry(next.path)
      .then((g: Geometry) => setFloors((fs) => fs.map((f) => (f.key === next.key ? { ...f, geo: g, geoDone: Date.now() } : f))))
      .catch((e: Error) => setFloors((fs) => fs.map((f) => (f.key === next.key ? { ...f, geoErr: e.message } : f))))
      .finally(() => {
        geoBusy.current = false;
        setFloors((fs) => [...fs]);
      });
  }, [floors, activeKey]);

  // findings for the active drawing, asked in sequence
  const specs = useMemo(() => (active ? findingSpecs(active.path, samples) : []), [active, samples]);
  useEffect(() => {
    if (!active || !specs.length) return;
    const path = active.path;
    const my = ++runId.current;
    const have = findings[path] ?? {};
    void (async () => {
      for (const s of specs) {
        if (have[s.key]?.proof || have[s.key]?.err) continue;
        if (runId.current !== my) return;
        setFindings((f) => ({ ...f, [path]: { ...(f[path] ?? {}), [s.key]: { loading: true } } }));
        let st: FindingState;
        try {
          st = { proof: await ask(path, s.q) };
        } catch (e) {
          st = { err: (e as Error).message };
        }
        setFindings((f) => ({ ...f, [path]: { ...(f[path] ?? {}), [s.key]: st } }));
        if (st.proof) setSelected((cur) => (cur && cur.path === path ? cur : { path, proof: st.proof! }));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active?.path, specs.length, epoch]);

  // checks (scale, sheet type, plan view, units): fetched once the drawing is read
  const geoReady = !!active?.geo;
  useEffect(() => {
    if (!active || !active.geo || checks[active.path]) return;
    const path = active.path;
    const dims = { w: active.geo.width, h: active.geo.height };
    setCheckNote(null);
    setCheckErr(null);
    fetchChecks(path, dims).then((it) => setChecks((c) => ({ ...c, [path]: it }))).catch(() => { /* endpoint missing: no Checks block, nothing invented */ });
  }, [active?.path, geoReady]); // eslint-disable-line react-hooks/exhaustive-deps

  // elements (rooms, walls, doors, windows, fixtures, stairs, labels): fetched once the drawing is read
  useEffect(() => {
    if (!active || !active.geo || elems[active.path]) return;
    const path = active.path;
    setElSel(null);
    setElHover(null);
    fetchElements(path).then((it) => setElems((m) => ({ ...m, [path]: it }))).catch((e) => { if (e instanceof ElementsUnavailable) setElems((m) => ({ ...m, [path]: "na" })); });
  }, [active?.path, geoReady]); // eslint-disable-line react-hooks/exhaustive-deps

  const askPath = flat?.path ?? active?.path ?? null;
  const submit = async (q: string) => {
    if (!askPath || !q.trim()) return;
    setAsking(true);
    setAskErr(null);
    try {
      const p = await ask(askPath, q.trim(), elSel);
      setSelected({ path: askPath, proof: p });
    } catch (e) {
      setAskErr((e as Error).message);
    } finally {
      setAsking(false);
    }
  };

  // re-ask every standard question (and the selected one) without blanking the rows: sizes update in place
  const reask = async (path: string) => {
    const qs = new Map<string, string>(specs.map((s) => [s.key, s.q]));
    const selQ = selected && selected.path === path ? selected.proof.question : null;
    await Promise.all([...qs.entries()].map(async ([k, q]) => {
      try {
        const proof = await ask(path, q);
        setFindings((f) => ({ ...f, [path]: { ...(f[path] ?? {}), [k]: { proof } } }));
      } catch { /* keep the previous answer */ }
    }));
    if (selQ) {
      try {
        const proof = await ask(path, selQ);
        setSelected((cur) => (cur && cur.path === path ? { path, proof } : cur));
      } catch { /* keep */ }
    } else {
      setSelected((cur) => {
        if (!cur || cur.path !== path) return cur;
        const hit = specs.map((s) => findingsRef.current[path]?.[s.key]?.proof).find((x) => x && x.question === cur.proof.question);
        return hit ? { path, proof: hit } : cur;
      });
    }
  };
  const findingsRef = useRef(findings);
  findingsRef.current = findings;
  const onCheckAnswer = async (c: Check, a: "yes" | "no") => {
    if (!active) return;
    const path = active.path;
    setCheckBusy(c.id);
    setCheckErr(null);
    setCheckNote(null);
    try {
      let items = await answerCheck(path, c.id, a);
      if (!MOCK_CHECKS) items = await fetchChecks(path).catch(() => items);
      setChecks((m) => ({ ...m, [path]: items }));
      setHoverCheck(null);
      if (c.kind === "scale" || c.kind === "units") {
        const g = await geometry(path).catch(() => null);
        if (g) setFloors((fs) => fs.map((f) => (f.path === path ? { ...f, geo: g } : f)));
      }
      await reask(path);
      setCheckNote(a === "yes" ? `${kindWord(c.kind)} confirmed: ${c.kind === "scale" || c.kind === "units" ? "areas and lengths updated" : "numbers updated"}` : `${kindWord(c.kind)}: noted, that one is ruled out`);
      window.setTimeout(() => setCheckNote(null), 6000);
    } catch (e) {
      setCheckErr((e as Error).message);
    } finally {
      setCheckBusy(null);
    }
  };
  /** after any element change: re-read elements, the 3D geometry, the checks, and every answer, in place */
  const refreshAfterElement = async (path: string) => {
    const [it, g, ck] = await Promise.all([fetchElements(path).catch(() => null), geometry(path).catch(() => null), fetchChecks(path).catch(() => null)]);
    if (it) setElems((m) => ({ ...m, [path]: it }));
    if (g) setFloors((fs) => fs.map((f) => (f.path === path ? { ...f, geo: g } : f)));
    if (ck) setChecks((m) => ({ ...m, [path]: ck }));
    await reask(path);
  };
  const runElement = async (what: string, fn: (path: string) => Promise<{ affected?: string[]; id?: string } | void>, undo = 0) => {
    if (!active) return;
    const path = active.path;
    setElBusy(true);
    setElErr(null);
    try {
      const r = await fn(path);
      if (r && r.id) setElLocal((m) => ({ ...m, [path]: new Set([...(m[path] ?? []), r.id!]) }));
      setElUndo((m) => ({ ...m, [path]: Math.max(0, (m[path] ?? 0) + undo) }));
      await refreshAfterElement(path);
      const aff = r && r.affected && r.affected.length ? ` Updated: ${r.affected.join(", ")}.` : "";
      setElNote(`${what}.${aff}`);
      window.setTimeout(() => setElNote(null), 6000);
    } catch (e) {
      setElErr((e as Error).message);
    } finally {
      setElBusy(false);
    }
  };
  const elList = active && Array.isArray(elems[active.path]) ? (elems[active.path] as PlanElement[]) : null;
  const inspector = active ? (
    <Inspector
      path={active.path}
      els={elList}
      unavailable={elems[active.path] === "na"}
      selId={elSel}
      hoverId={elHover}
      local={elLocal[active.path] ?? new Set()}
      busy={elBusy}
      note={elNote}
      err={elErr}
      canUndo={(elUndo[active.path] ?? 0) > 0 || !!elList?.some((e) => e.user_changed)}
      imgSrc={imageUrl(active.path)}
      dims={active.geo ? { w: active.geo.width, h: active.geo.height } : null}
      credit={active.geo?.credit || active.credit || ""}
      synthetic={/synthetic/i.test(active.geo?.credit || active.credit || "")}
      onSelect={setElSel}
      onHover={setElHover}
      onRetype={(e, kind, subtype) => void runElement(`Changed to ${subtype ?? kindName(kind)}`, async (path) => { const r = await overrideElement(path, { element_id: e.id, action: "retype", kind, subtype }); return { affected: r.affected, id: e.id }; }, 1)}
      onRemove={(e) => void runElement(`Removed (not a ${kindName(e.kind)})`, async (path) => { const r = await overrideElement(path, { element_id: e.id, action: "remove" }); return { affected: r.affected, id: e.id }; }, 1)}
      onRestore={(e) => void runElement("Restored", async (path) => { const r = await overrideElement(path, { element_id: e.id, action: "restore" }); return { affected: r.affected, id: e.id }; }, 1)}
      onUndo={() => void runElement("Undone", async (path) => { await undoElement(path); }, -1)}
    />
  ) : null;
  const activeChecks = active ? (checks[active.path] ?? null) : null;
  const scaleLine = scaleBrief(activeChecks ?? undefined);

  const flatName = (f: File) => (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name;
  const levelName = (f: { level?: number | null; level_label?: string | null; sheet?: string | null; display_label?: string | null }) =>
    f.display_label || f.level_label || (f.level != null ? `Level ${f.level}` : (f.sheet ?? "Plan"));

  const runBuild = async (done: { path: string; name: string }[], skipped: string) => {
    setProj((p) => (p ? { ...p, stage: "title", since: Date.now(), error: null } : p));
    const timer = window.setTimeout(() => setProj((p) => (p && p.stage === "title" ? { ...p, stage: "sort", since: Date.now() } : p)), 6000);
    try {
      const result = await buildProject(done);
      window.clearTimeout(timer);
      const floorsSorted = [...result.floors].sort((x, y) => x.stack_index - y.stack_index);
      open(floorsSorted.map((f) => ({ path: f.path, name: levelName(f) })));
      setFlat(null);
      setProj((p) => (p ? { ...p, result, stage: floorsSorted.length ? "build" : "done", since: Date.now(), skipped } : p));
      setProjDrawer(true);
    } catch (e) {
      window.clearTimeout(timer);
      retryRef.current = () => void runBuild(done, skipped);
      setProj((p) => (p ? { ...p, error: (e as Error).message } : p));
    }
  };

  const doUpload = async (files: File[], folder: boolean) => {
    const visible = files.filter((f) => !flatName(f).split("/").some((s) => s.startsWith(".")));
    if (folder && visible.length > 1) {
      const ok = visible.slice(0, 80).sort((x, y) => flatName(x).localeCompare(flatName(y), undefined, { numeric: true }));
      setPage("work");
      setDrawer(false);
      setProjDrawer(true);
      setProj({ names: ok.map(flatName), result: null, stage: "upload", upI: 0, upN: ok.length, since: Date.now(), error: null, skipped: "" });
      const done: { path: string; name: string }[] = [];
      const skipExt: Record<string, number> = {};
      for (let k = 0; k < ok.length; k++) {
        try {
          done.push({ path: await upload(ok[k]), name: flatName(ok[k]) });
        } catch {
          const e = `.${extOf(ok[k].name)}`;
          skipExt[e] = (skipExt[e] ?? 0) + 1;
        }
        setProj((p) => (p ? { ...p, upI: k + 1 } : p));
      }
      if (!done.length) {
        retryRef.current = () => void doUpload(files, folder);
        setProj((p) => (p ? { ...p, error: "None of the files could be uploaded" } : p));
        return;
      }
      const nSkip = Object.values(skipExt).reduce((s, n) => s + n, 0);
      await runBuild(done, nSkip ? `${nSkip} file${nSkip > 1 ? "s" : ""} not uploaded (type not supported): ${Object.entries(skipExt).map(([e, n]) => `${n} ${e}`).join(", ")}` : "");
      return;
    }
    const ok = visible.filter((f) => EXTS.includes(extOf(f.name))).slice(0, 12);
    if (!ok.length) return;
    ok.sort((x, y) => x.name.localeCompare(y.name, undefined, { numeric: true }));
    setProj(null);
    setUpl({ since: Date.now() });
    try {
      const done: Upload[] = [];
      for (const f of ok) done.push({ path: await upload(f), name: f.name });
      setUploads((u) => [...done, ...u]);
      open(done.map((d) => ({ ...d, credit: undefined })));
      setFlat(null);
    } catch (e) {
      setAskErr((e as Error).message);
    } finally {
      setUpl(null);
    }
  };

  const planKey = active ? `${active.path}|${vibe}|${JSON.stringify(planExtra)}` : "";
  const plan = plans[planKey] ?? null;
  useEffect(() => {
    if (mode !== "plan" || !active || (plans[planKey] && !plans[planKey].mock)) return;
    let live = true;
    void fetchPlan(active.path, vibe, planExtra).then((p) => live && setPlans((m) => ({ ...m, [planKey]: p })));
    return () => {
      live = false;
    };
  }, [mode, planKey]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    setStepIdx(null);
    setPlaying(false);
  }, [active?.path, mode]);
  useEffect(() => {
    if (!playing || !plan) return;
    const t = setInterval(() => {
      setStepIdx((i) => {
        const n = i === null ? 0 : i + 1;
        if (n >= plan.steps.length) {
          setPlaying(false);
          return plan.steps.length - 1;
        }
        return n;
      });
    }, 2200);
    return () => clearInterval(t);
  }, [playing, plan]);
  const curStep = mode === "plan" && plan && stepIdx !== null ? plan.steps[stepIdx] : null;
  const startScale = () => {
    setPage("work");
    setBanner(null);
    setMeasuredPx(null);
    setScaleIssue(null);
    setScaleState("pick");
  };
  const cancelScale = () => setScaleState("off");
  const applyLength = async (m: number, typed?: { v: number; unit: string }, force = false) => {
    if (!active || measuredPx === null) return;
    const q = selected?.proof.question ?? specs[0]?.q;
    if (!q) return;
    const path = active.path;
    setAsking(true);
    setScaleIssue(null);
    try {
      const before = plans[planKey] ?? (await fetchPlan(path, vibe, planExtra));
      const [pr] = await setScale(path, measuredPx, m, [q], force);
      if (pr) setSelected({ path, proof: pr });
      const after = await fetchPlan(path, vibe, planExtra);
      setPlans({ [planKey]: after });
      setPpmByPath((x) => ({ ...x, [path]: measuredPx / m }));
      setMeasureTyped(`${typed ? `${typed.v} ${typed.unit}` : `${m} m`}`);
      const want: [string, string][] = [["floor_area_m2", "floor area"], ["wall_length_m", "wall length"], ["paint_l", "paint"], ["dry_area_m2", "flooring"], ["wet_tiles", "wet-floor tiles"]];
      const items: BannerItem[] = [];
      for (const [k, label] of want) {
        const b = after.basis[k];
        if (b && typeof b.value === "number" && b.value > 0) items.push({ label, value: b.value, unit: k === "wet_tiles" ? "pcs" : (b.unit ?? "").replace("m2", "m²") });
      }
      setBanner(items);
      const old = new Map(before.checklist.map((c) => [c.id, c.qty]));
      setFlash(after.checklist.filter((c) => c.qty !== null && old.get(c.id) !== c.qty).map((c) => c.id));
      setScaleState("payoff");
      window.setTimeout(() => setScaleState("off"), 5200);
      window.setTimeout(() => setBanner(null), 9000);
    } catch (e) {
      if (e instanceof ScaleError) {
        // implausible measurement: nothing was applied, keep the form open and offer the fix
        const s = e.issue.suggestion;
        let label: string | null = null;
        let lengthM: number | null = null;
        if (s && typeof s === "object") {
          lengthM = typeof s.length_m === "number" ? s.length_m : null;
          label = s.label ?? (typed ? `Use ${typed.v} ${s.unit ?? "cm"}` : null);
        } else if (typeof s === "string") {
          label = s;
        }
        if (lengthM === null && typed && typed.unit === "m" && typed.v >= 50) {
          lengthM = typed.v / 100;
          label = label ?? `Use ${typed.v} cm`;
        }
        setScaleIssue({ message: e.issue.message, label, lengthM });
      } else {
        setAskErr((e as Error).message);
        setScaleState("off");
      }
    } finally {
      setAsking(false);
    }
  };
  // how the current sizes were obtained: defaulted (typical door), specified (printed on the drawing), chosen (you measured)
  const scaleAsm = selected?.proof.assumptions.find((x) => x.key === "scale_px_per_m");
  const planBasis = plan?.basis?.scale_px_per_m;
  const scaleTag = active && ppmByPath[active.path] ? "chosen" : (scaleAsm?.tag ?? planBasis?.tag ?? "defaulted");
  const scaleSrc = scaleAsm?.source ?? planBasis?.source ?? null;
  const scaleKind: "defaulted" | "specified" | "chosen" = scaleTag === "specified" ? "specified" : scaleTag === "chosen" ? "chosen" : "defaulted";
  const settled = (path: string) => specs.filter((s) => findings[path]?.[s.key]?.proof || findings[path]?.[s.key]?.err).length;
  const nowMs = Date.now();
  let progress: ProgressInfo | null = null;
  if (proj && proj.error) {
    progress = { stages: FOLDER_STAGES, idx: proj.stage === "upload" ? 0 : 2, frac: null, since: proj.since, label: "", error: proj.error, onRetry: () => retryRef.current?.() };
  } else if (proj && proj.stage !== "done") {
    if (proj.stage === "upload") progress = { stages: FOLDER_STAGES, idx: 0, frac: proj.upI / Math.max(1, proj.upN), since: proj.since, label: `Uploading ${proj.upI}/${proj.upN} files` };
    else if (proj.stage === "title") progress = { stages: FOLDER_STAGES, idx: 1, frac: null, since: proj.since, label: "Reading title blocks" };
    else if (proj.stage === "sort") progress = { stages: FOLDER_STAGES, idx: 2, frac: null, since: proj.since, label: "AI sorting the sheets" };
    else {
      const K = floors.length;
      const k = floors.filter((f) => f.geo || f.geoErr).length;
      progress = { stages: FOLDER_STAGES, idx: 3, frac: K ? k / K : 1, since: proj.since, label: `Building floor ${Math.min(k + 1, K)}/${K}` };
    }
  } else if (upl) {
    progress = { stages: SINGLE_STAGES, idx: 0, frac: null, since: upl.since, label: "Uploading" };
  } else if (active && active.geoErr) {
    progress = { stages: SINGLE_STAGES, idx: 1, frac: null, since: active.geoStart ?? nowMs, label: "", error: active.geoErr, onRetry: () => setFloors((fs) => fs.map((f) => (f.key === active.key ? { ...f, geoErr: null } : f))) };
  } else if (active && !active.geo) {
    const since = active.geoStart ?? nowMs;
    const el = (nowMs - since) / 1000;
    progress = { stages: SINGLE_STAGES, idx: el > 6 ? 2 : 1, frac: null, since, label: el > 6 ? "Checking with 2 AI reviewers" : "Reading the drawing" };
  } else if (active && active.geo && nowMs - (active.geoDone ?? 0) < 2700) {
    const ck = active.geo.check;
    const plans = ck ? ck.views.filter((v) => v.type === "floor_plan").length : 0;
    progress = { stages: SINGLE_STAGES, idx: 3, frac: Math.min(1, (nowMs - (active.geoDone ?? nowMs)) / 2700), since: active.geoDone ?? nowMs, label: `Building in 3D${plans ? ` · found ${plans} floor plan${plans === 1 ? "" : "s"}` : ""}` };
  } else if (active && specs.length && settled(active.path) < specs.length) {
    progress = { stages: SINGLE_STAGES, idx: 4, frac: settled(active.path) / specs.length, since: active.geoDone ?? nowMs, label: `Counting · ${settled(active.path)}/${specs.length} questions` };
  } else if (active && active.geo) {
    const t = (doneAt.current[active.key] ??= nowMs);
    if (nowMs - t < 1500) progress = { stages: SINGLE_STAGES, idx: 5, frac: 1, since: t, label: "Done" };
  }
  needTick.current = progress !== null;
  useEffect(() => {
    const t = window.setInterval(() => needTick.current && setTick((x) => x + 1), 500);
    return () => window.clearInterval(t);
  }, []);
  useEffect(() => {
    if (proj && proj.stage === "build" && floors.length && floors.every((f) => f.geo || f.geoErr)) setProj((p) => (p ? { ...p, stage: "done" } : p));
  }, [floors, proj]);

  const projFiles: ProjFile[] = proj?.result
    ? flattenProject(proj.result)
    : (proj?.names ?? []).map((n) => ({ path: "", name: n, docType: "pending", sheet: null, title: null, why: null, isFloor: false, levelLabel: null }));
  const statusOf = (f: ProjFile): FileStatus => {
    if (!proj?.result) return proj && proj.names.indexOf(f.name) < proj.upI ? "reading" : "queued";
    if (!f.isFloor) return "not a plan";
    if (f.altOf !== undefined) return "queued";
    const fl = floors.find((x) => x.path === f.path);
    if (fl?.geo || fl?.geoErr) return "done";
    const firstPending = floors.find((x) => !x.geo && !x.geoErr);
    return firstPending?.path === f.path ? "reading" : "queued";
  };
  const openProjFile = (f: ProjFile) => {
    if (!f.path) return;
    if (f.isFloor && f.altOf === undefined) {
      setFlat(null);
      setActiveKey(f.path);
    } else if (f.isFloor && f.altOf !== undefined) {
      // another version of a storey: swap it into the stack in place of the shown plan, never stack both
      const of = f.altOf;
      setFlat(null);
      setFloors((fs) => {
        if (fs.some((x) => x.path === f.path)) return fs;
        const base = fs.find((x) => x.path === of) ?? fs[fs.length - 1];
        return fs.map((x) => (x === base ? { key: f.path, path: f.path, name: `${f.label || base.name} (version)`, credit: null, geo: null, geoErr: null } : x));
      });
      setActiveKey(f.path);
    } else {
      setFlat({ path: f.path, typeWord: typeWord(f.docType), title: f.label || [f.sheet, f.title].filter(Boolean).join(" · ") || f.name.split("/").pop() || f.name, why: f.why, sheet: f.sheet, isSchedule: /sched/i.test(f.docType) });
    }
  };
  const projectNote = proj?.result && proj.result.floors.length === 0 && proj.stage === "done" ? noFloorsNote(projFiles) : null;
  const seg = <Seg mode={mode} onMode={setMode} />;

  const selFloor = selected ? floors.find((f) => f.key === selected.path) : undefined;

  return (
    <div className={`app ${projDrawer && proj ? "pd" : ""}`}>
      <Rail
        onImage={() => fileRef.current?.click()}
        onFolder={() => dirRef.current?.click()}
        onDrawings={() => { setProjDrawer(false); setDrawer((d) => !d); }}
        drawerOpen={drawer}
        theme={theme}
        onTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
        howOn={page === "how"}
        onHow={() => setPage((p) => (p === "how" ? "work" : "how"))}
        hasProject={!!proj}
        onProject={() => { setDrawer(false); setProjDrawer((d) => !d); }}
      />
      <input
        ref={fileRef}
        type="file"
        hidden
        accept=".png,.jpg,.jpeg,.pdf,.dxf,.ifc,.svg"
        onChange={(e) => {
          void doUpload([...(e.target.files ?? [])], false);
          e.target.value = "";
        }}
      />
      <input
        ref={dirRef}
        type="file"
        hidden
        // @ts-expect-error non-standard but widely supported directory picker
        webkitdirectory=""
        multiple
        onChange={(e) => {
          void doUpload([...(e.target.files ?? [])], true);
          e.target.value = "";
        }}
      />
      {drawer && (
        <Drawer
          samples={samples}
          uploads={uploads}
          onPick={(p, n, c) => open([{ path: p, name: n, credit: c }])}
          onClose={() => setDrawer(false)}
        />
      )}
      {projDrawer && proj && (
        <ProjectDrawer
          result={proj.result}
          pending={proj.names}
          statusOf={statusOf}
          files={projFiles}
          activePath={activeKey}
          flatPath={flat?.path ?? null}
          onOpen={openProjFile}
          onClose={() => setProjDrawer(false)}
          skipped={proj.skipped}
        />
      )}
      {page === "how" ? (
        <HowPage />
      ) : (
      <main className="grid">
        <section className="col left">
          {active?.geo && (
            <Tour k={active.path} steps={[
              { title: "We read the scale from the sheet itself",
                body: scaleLine ? `${scaleLine.text} The pins on the drawing show exactly where: the printed scale note, the graphic bar and the dimension strings we measured.` : "No printed scale was found; one real length you measure unlocks every size.",
                act: () => { const sc = activeChecks?.find((c) => c.kind === "scale"); setHoverCheck(sc ?? null); vref.current?.setView("top"); } },
              { title: "Every number says where it came from",
                body: "Drawn = measured on the drawing, specified = printed on it, chosen = you decided, defaulted = an assumption we had to make. Open 'See proof' on any answer for the receipt.",
                act: () => setHoverCheck(null) },
              { title: "What's on this sheet",
                body: active.geo.deep?.on ? `This sheet is very detailed: the deep read counts every bed, door, chair and fixture and names every room. It takes about ${Math.max(1, Math.round((active.geo.deep.eta_s || 60) / 60))} min and we tell you before it starts.` : "The checklist on the right counts every element and names every room. Click a row to light up all of them.",
                act: () => document.querySelector(".cklist")?.scrollIntoView({ behavior: "smooth", block: "center" }) },
              { title: "Look around, click anything, ask",
                body: "The octagon top-right switches 2D / 3D (tap) and rotates (drag); the wheel zooms where your cursor is. Click a room, then ask 'what is the size of this room?'.",
                act: () => vref.current?.setView("3d") },
            ]} />
          )}
          <ViewerPane
            vref={vref}
            layerExtra={active ? { furniture: ckN[active.path] ?? 0 } : undefined}
            scaleText={scaleLine ? `${scaleLine.text.split(":")[0]} · ${pctNum(scaleLine.conf)}% sure` : null}
            onScaleWhere={() => { const sc = activeChecks?.find((c) => c.kind === "scale"); setHoverCheck(sc ?? null); vref.current?.setView("top"); }}
            floors={floors}
            active={active}
            selected={selected}
            selFloor={selFloor}
            showPins={showPins}
            hoverIdx={hoverIdx}
            onHover={setHoverIdx}
            busy={busy}
            onPickFloor={setActiveKey}
            onOpenDrawings={() => setDrawer(true)}
            stage={curStep && plan && stepIdx !== null ? plan.steps.slice(0, stepIdx + 1).map((x) => x.phase) : null}
            stageLabel={curStep ? `Step ${curStep.n} · ${curStep.title}` : null}
            drawingOn={drawingOn}
            setDrawingOn={setDrawingOn}
            theme={theme}
            scale={scale}
            scaleKind={scaleKind}
            scaleSrc={scaleSrc}
            scaleIssue={scaleIssue}
            ppm={active ? (ppmByPath[active.path] ?? active.geo?.px_per_m ?? null) : null}
            banner={banner}
            applying={asking}
            onScaleStart={startScale}
            onScaleCancel={cancelScale}
            onMeasured={(px) => {
              setMeasuredPx(Math.hypot(px[1][0] - px[0][0], px[1][1] - px[0][1]));
              setScaleState("enter");
            }}
            onApplyLength={(m, typed, force) => void applyLength(m, typed, force)}
            progress={progress}
            measureTyped={measureTyped}
            flat={flat}
            onCloseFlat={() => setFlat(null)}
            projectNote={projectNote}
            onRetryGeo={() => setFloors((fs) => fs.map((f) => (f.key === activeKey ? { ...f, geoErr: null } : f)))}
            checkEv={hoverCheck?.evidence ?? null}
            elements={elList}
            elSelId={elSel}
            elHoverId={elHover}
            onElPick={(id, how) => (how === "click" ? setElSel(id) : setElHover(id))}
            onWhyRead={() => {
              setSelected(null);
              setWhy(true);
            }}
          />
          <Ask
            active={askPath}
            chips={askPath ? (flat ? chipsFor(flat.path).slice(0, 2) : chipsFor(askPath)) : []}
            selected={selected && askPath && selected.path === askPath ? selected.proof : null}
            asking={asking}
            err={askErr}
            onAsk={(q) => void submit(q)}
            selName={elSel ? (() => { const e = elList?.find((x) => x.id === elSel); return e ? (e.label || kindName(e.kind)) : elSel; })() : null}
            onClearSel={() => { setElSel(null); vref.current?.setMulti(null, []); }}
            onWhy={() => setWhy(true)}
            scaleLine={scaleLine}
          />
        </section>
        <section className="col right">
          {mode === "plan" ? (
            <BuildPanel
              plan={plan}
              vibe={vibe}
              onVibe={setVibe}
              stepIdx={stepIdx}
              onStep={(i) => {
                setPlaying(false);
                setStepIdx(i);
              }}
              playing={playing}
              onPlay={() => {
                if (playing) setPlaying(false);
                else {
                  setStepIdx(null);
                  setPlaying(true);
                }
              }}
              seg={seg}
              hasDrawing={!!active}
              onSetSize={startScale}
              onInput={(k, v) => setPlanExtra((x) => ({ ...x, [k]: v }))}
              scaleKind={scaleKind}
              scaleSrc={scaleSrc}
              flash={flash}
            />
          ) : (
            <Findings
              seg={seg}
              flat={flat}
              onAskSchedule={() => document.querySelector<HTMLInputElement>(".askform input")?.focus()}
              active={active}
              specs={specs}
              states={active ? (findings[active.path] ?? {}) : {}}
              floors={floors}
              activeKey={activeKey}
              onPickFloor={setActiveKey}
              selectedId={selected?.proof.id ?? null}
              hoverIdx={hoverIdx}
              onHover={setHoverIdx}
              imgUrl={active ? imageUrl(active.path) : ""}
              scaleLine={scaleLine}
              checks={<>{active && <ChecklistPanel path={active.path} deepHint={active.geo?.deep ?? null}
                services={active.geo?.layers?.quantities ?? null}
                onShow={(polys) => vref.current?.setMulti(active.key, polys)}
                onRoom={(id, poly) => { setElSel(id); vref.current?.setMulti(active.key, [poly]); }}
                onLoaded={(c) => { setCkN((m) => ({ ...m, [active.path]: c.elements.length }));
                  vref.current?.setLayers(active.key, { ...(active.geo?.layers ?? {}), furniture: c.elements } as never, LAYER_COLOURS); }} />}
                <ChecksBlock items={activeChecks} busyId={checkBusy} note={checkNote} err={checkErr} onAnswer={(c, ans) => void onCheckAnswer(c, ans)} onType={startScale} onHover={setHoverCheck} />{inspector}</>}
              onSelect={(p) => active && setSelected({ path: active.path, proof: p })}
              onWhy={(p) => {
                if (active) setSelected({ path: active.path, proof: p });
                setWhy(true);
              }}
            />
          )}
          {why && (
            <Know
              proof={selected && active && selected.path === active.path ? selected.proof : null}
              floor={selFloor ?? null}
              hoverIdx={hoverIdx}
              onHover={setHoverIdx}
              showPins={showPins}
              setShowPins={setShowPins}
              imgUrl={active ? imageUrl(active.path) : ""}
              check={active?.geo?.check ?? null}
              onClose={() => setWhy(false)}
            />
          )}
        </section>
      </main>
      )}
    </div>
  );
}
