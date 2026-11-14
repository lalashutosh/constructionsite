import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ask, fetchPlan, fetchSamples, setScale, geometry, imageUrl, upload, type Geometry, type Sample, type BuildPlan } from "./api";
import { chipsFor, findingSpecs } from "./logic";
import type { ProofObject } from "./types";
import { HowPage } from "./how";
import { Ask, BuildPanel, Findings, Know, Rail, Drawer, Seg, ViewerPane, type BannerItem, type ScaleState, type ThemeName, type Floor, type FindingState, type Upload } from "./panels";

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
  const [busy, setBusy] = useState<string | null>(null);
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
  const [page, setPage] = useState<"work" | "how">("work");
  const [measuredPx, setMeasuredPx] = useState<number | null>(null);
  const [planExtra, setPlanExtra] = useState<Record<string, number>>({});
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

  // geometry for every floor, one at a time (first call per file can take a while)
  const geoBusy = useRef(false);
  useEffect(() => {
    if (geoBusy.current) return;
    const next = [...floors].sort((a, b) => (a.key === activeKey ? -1 : b.key === activeKey ? 1 : 0)).find((f) => !f.geo && !f.geoErr);
    if (!next) return;
    geoBusy.current = true;
    geometry(next.path)
      .then((g: Geometry) => setFloors((fs) => fs.map((f) => (f.key === next.key ? { ...f, geo: g } : f))))
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

  const submit = async (q: string) => {
    if (!active || !q.trim()) return;
    setAsking(true);
    setAskErr(null);
    try {
      const p = await ask(active.path, q.trim());
      setSelected({ path: active.path, proof: p });
    } catch (e) {
      setAskErr((e as Error).message);
    } finally {
      setAsking(false);
    }
  };

  const doUpload = async (files: File[], folder: boolean) => {
    const ok = files.filter((f) => EXTS.includes(extOf(f.name))).slice(0, 12);
    if (!ok.length) return;
    ok.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
    setBusy(`Uploading ${ok.length} file${ok.length > 1 ? "s" : ""}…`);
    try {
      const done: Upload[] = [];
      for (const f of ok) done.push({ path: await upload(f), name: f.name });
      setUploads((u) => [...done, ...u]);
      open(done.map((d) => ({ ...d, credit: undefined })));
      void folder;
    } catch (e) {
      setAskErr((e as Error).message);
    } finally {
      setBusy(null);
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
    setScaleState("pick");
  };
  const cancelScale = () => setScaleState("off");
  const applyLength = async (m: number) => {
    if (!active || measuredPx === null) return;
    const q = selected?.proof.question ?? specs[0]?.q;
    if (!q) return;
    const path = active.path;
    setAsking(true);
    try {
      const before = plans[planKey] ?? (await fetchPlan(path, vibe, planExtra));
      const [pr] = await setScale(path, measuredPx, m, [q]);
      if (pr) setSelected({ path, proof: pr });
      const after = await fetchPlan(path, vibe, planExtra);
      setPlans({ [planKey]: after });
      setPpmByPath((x) => ({ ...x, [path]: measuredPx / m }));
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
      setAskErr((e as Error).message);
      setScaleState("off");
    } finally {
      setAsking(false);
    }
  };
  const seg = <Seg mode={mode} onMode={setMode} />;

  const selFloor = selected ? floors.find((f) => f.key === selected.path) : undefined;

  return (
    <div className="app">
      <Rail
        onImage={() => fileRef.current?.click()}
        onFolder={() => dirRef.current?.click()}
        onDrawings={() => setDrawer((d) => !d)}
        drawerOpen={drawer}
        theme={theme}
        onTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
        howOn={page === "how"}
        onHow={() => setPage((p) => (p === "how" ? "work" : "how"))}
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
      {page === "how" ? (
        <HowPage />
      ) : (
      <main className="grid">
        <section className="col left">
          <ViewerPane
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
            scaled={!!(active && ppmByPath[active.path])}
            ppm={active ? (ppmByPath[active.path] ?? null) : null}
            banner={banner}
            applying={asking}
            onScaleStart={startScale}
            onScaleCancel={cancelScale}
            onMeasured={(px) => {
              setMeasuredPx(Math.hypot(px[1][0] - px[0][0], px[1][1] - px[0][1]));
              setScaleState("enter");
            }}
            onApplyLength={(m) => void applyLength(m)}
            onWhyRead={() => {
              setSelected(null);
              setWhy(true);
            }}
          />
          <Ask
            active={active}
            chips={active ? chipsFor(active.path) : []}
            selected={selected && active && selected.path === active.path ? selected.proof : null}
            asking={asking}
            err={askErr}
            onAsk={(q) => void submit(q)}
            onWhy={() => setWhy(true)}
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
              scaled={!!(active && ppmByPath[active.path])}
              flash={flash}
            />
          ) : (
            <Findings
              seg={seg}
              active={active}
              specs={specs}
              states={active ? (findings[active.path] ?? {}) : {}}
              floors={floors}
              activeKey={activeKey}
              onPickFloor={setActiveKey}
              selectedId={selected?.proof.id ?? null}
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
