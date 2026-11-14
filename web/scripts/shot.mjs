// Screenshots into docs/shots/ui/ (W1 fixtures) and docs/shots/wow/ (W3 beats). Builds are served by `vite preview` on :5173.
//
// Two kinds of live shots:
//   real-*  talk to the running engine on :8000 (nothing mocked)
//   mock-*  the engine's /api/{ask,override,scale,facts} are answered from the contract fixtures, scaled onto the
//           REAL scan from /api/image. They exist to exercise the live code paths (duel, scale band, hook) while
//           raster extraction is unavailable (no tesseract). Geometry in mock-* shots is NOT the engine's reading.
import { spawn } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, "..", "..", "docs", "shots", "ui");
const wow = join(here, "..", "..", "docs", "shots", "wow");
mkdirSync(out, { recursive: true });
mkdirSync(wow, { recursive: true });
const base = "http://localhost:5173/";
const fxDir = join(here, "..", "public", "fixtures");
const fix = (n) => JSON.parse(readFileSync(join(fxDir, n), "utf8"));

const srv = spawn("npx", ["vite", "preview", "--port", "5173", "--strictPort"], { cwd: join(here, ".."), stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
for (let i = 0; i < 40; i++) {
  try {
    if ((await fetch(base)).ok) break;
  } catch {
    /* not up yet */
  }
  await sleep(250);
}

let engineUp = false;
try {
  engineUp = (await fetch("http://localhost:8000/health")).ok;
} catch {
  engineUp = false;
}

// Playwright may want a newer browser build than the one cached on this machine: fall back to any cached one.
async function launch() {
  try {
    return await chromium.launch();
  } catch (e) {
    const { readdirSync, existsSync } = await import("node:fs");
    const cache = join(process.env.HOME ?? "", "Library", "Caches", "ms-playwright");
    const dirs = existsSync(cache) ? readdirSync(cache).filter((d) => d.startsWith("chromium_headless_shell-")).sort().reverse() : [];
    for (const d of dirs) {
      const sub = readdirSync(join(cache, d)).find((x) => x.startsWith("chrome-headless-shell"));
      const exe = sub && join(cache, d, sub, "chrome-headless-shell");
      if (exe && existsSync(exe)) return chromium.launch({ executablePath: exe });
    }
    throw e;
  }
}
const only = process.env.ONLY ?? ""; // ONLY=fx | real | mock runs just that section
const run = (k) => only === "" || only === k;
const browser = await launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
const shot = (dir, n) => page.screenshot({ path: join(dir, `${n}.png`) });

// ---------------------------------------------------------------- W1 fixture shots (api pinned to fixtures)
if (run("fx")) {
for (const [n, t] of [["hook-0s", 0.5], ["hook-3s", 3.4], ["hook-5s", 5.6], ["hook-7s", 7], ["hook-9s", 9]]) {
  await page.goto(`${base}?api=fixtures&hookAt=${t}`);
  await sleep(300);
  await shot(out, n);
}

}

async function app(query, name, act, dir = out) {
  await page.goto(`${base}?hook=0&${query}`);
  await page.waitForSelector(".stage");
  await sleep(900);
  if (act) await act();
  await sleep(900);
  await shot(dir, name);
}

if (run("fx")) {
await app("api=fixtures&fx=doors", "answer");
await app("api=fixtures&fx=doors", "answer-hover", async () => {
  await page.hover(".num");
});
await app("api=fixtures&fx=doors", "duel-resolved", async () => {
  await page.click("text=Yes, a door");
});
await app("api=fixtures&fx=area_before&tab=receipt", "receipt");
await app("api=fixtures&fx=area_before&tab=decide", "decide");
await app("api=fixtures&fx=area_before&tab=findings", "findings");
await app("api=fixtures&fx=area_before&ask=1", "scale-ask");
await app("api=fixtures&fx=area_before", "band-before");
await app("api=fixtures&fx=area_before&ask=1", "band-after", async () => {
  await page.click(".modal .hit");
  await page.click("text=Yes, 0.9 m");
});
await app("api=fixtures&fx=refusal", "grey");
await app("api=fixtures&fx=doors&view=overlay", "overlay");
await app("api=fixtures&fx=doors&view=scan", "scan");
await page.setViewportSize({ width: 1280, height: 720 });
await app("api=fixtures&fx=doors", "answer-1280");
await page.setViewportSize({ width: 1440, height: 900 });
}

// ---------------------------------------------------------------- W3 real-engine shots
if (engineUp && run("real")) {
  await app("api=live&sample=swiss-vector&q=0", "real-swiss-doors", null, wow);
  await app("api=live&sample=swiss-vector&q=0&tab=receipt", "real-swiss-receipt", null, wow);
  await app("api=live&sample=swiss-vector&q=2", "real-swiss-area", null, wow);
  await app("api=live&sample=elevation", "real-refusal-elevation", null, wow);
  await app("api=live&sample=thumbnail", "real-refusal-tiny", null, wow);
  await app("api=live&sample=tiny-scan", "real-raster-tiny", null, wow);
  await app("api=live&sample=rotated-text", "real-raster-rotated", null, wow);
  // beats 1+2: the hook over a real scan at its true pixel size, real engine, clock started at an offset
  for (const [n, t] of [["0s-true-size", 0.5], ["2s-sweep", 1.9], ["3s-explode", 3.4], ["5s-chips", 5.6], ["7s-big", 7.2], ["9s-title", 9]]) {
    for (let tries = 0; tries < 3; tries++) {
      await page.goto(`${base}?api=live&sample=clean-bw&hookAt=${t}`);
      try {
        await page.waitForSelector(".hook", { timeout: 20000 });
        break;
      } catch {
        /* the engine answered late and the short hook was already over: reload */
      }
    }
    await sleep(250);
    await shot(wow, `real-hook-${n}`);
  }
  await page.click("text=How we scale");
  await sleep(500);
  await shot(wow, "real-cost-scale-drawer");
  await page.setViewportSize({ width: 1920, height: 1080 });
  await app("api=live&sample=swiss-vector&q=0", "real-swiss-1920", null, wow);
  await page.setViewportSize({ width: 1440, height: 900 });
}

// ---------------------------------------------------------------- W3 mock-engine shots (see header)
const SAMPLE = "data/cubicasa5k/high_quality-11553.png"; // 366 x 525 px
const IMG = { w: 366, h: 525 };
// fixture geometry lives in a 480 x 620 box: stretch it onto the real scan so overlays land inside the picture
function fit(o) {
  if (Array.isArray(o)) return o.map(fit);
  if (o && typeof o === "object") {
    const r = {};
    for (const [k, v] of Object.entries(o)) {
      if (k === "polygon") r[k] = v.map(([x, y]) => [(x * IMG.w) / 480, (y * IMG.h) / 620]);
      else r[k] = fit(v);
    }
    return r;
  }
  return o;
}
const doors = fit(fix("sample_proof_doors.json"));
const areaBefore = fit(fix("sample_proof_area.json"));
const areaAfter = fit(fix("demo_takeoff_area.json"));
const facts = fit(fix("sample_facts.json"));

function mockEngine(state) {
  const base = (p) => ({ ...p, provenance: { ...p.provenance, file: SAMPLE } });
  return async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    const json = (b) => route.fulfill({ contentType: "application/json", headers: { "access-control-allow-origin": "*" }, body: JSON.stringify(b) });
    if (method === "OPTIONS") return route.fulfill({ status: 204, headers: { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" } });
    if (url.includes("/api/override") && method === "DELETE") return json({ cleared: true });
    if (url.includes("/api/override")) {
      state.overridden = true;
      const keep = JSON.parse(route.request().postData() ?? "{}").keep;
      const p = base(doors);
      const v0 = p.voters[0];
      const value = keep ? v0.value : p.voters[1].value;
      const ids = keep ? v0.element_ids : p.voters[1].element_ids;
      return json({
        ...p,
        value,
        tier: "green",
        voters: p.voters.map((v) => ({ ...v, value, element_ids: ids })),
        evidence: p.evidence.filter((e) => ids.includes(e.id)),
        assumptions: [...p.assumptions, { key: "your verdict on d3", value: keep ? "is a door" : "is not a door", unit: null, tag: "chosen", source: "you, on the plan", depends_on: [] }],
        notes: ["historically right 100% of the time at this agreement level"],
      });
    }
    if (url.includes("/api/scale")) return json([{ ...base(areaAfter), scale: { ...areaAfter.scale, anchors: [...areaAfter.scale.anchors, { kind: "user", px_per_m: 100, rel_sigma: 0.01, tag: "chosen", note: "you: this door is 0.9 m wide", element_ids: ["d0"] }] } }]);
    if (url.includes("/api/ask")) return json(base(state.scenario === "area" ? areaBefore : doors));
    if (url.includes("/api/facts")) return json({ ...facts, provenance: { ...facts.provenance, file: SAMPLE } });
    return route.continue();
  };
}

async function mock(scenario, query, name, act, dir = wow) {
  const state = { scenario, overridden: false };
  await page.unroute("**/api/**").catch(() => undefined);
  const h = mockEngine(state);
  await page.route("**/localhost:8000/api/**", (r) => {
    const u = r.request().url();
    // the real scan is served by the real engine; everything that computes is mocked
    if (u.includes("/api/image")) return r.continue();
    return h(r);
  });
  await page.goto(`${base}?api=live&${query}`);
  await page.waitForSelector(".stage, .hook");
  await sleep(1100);
  if (act) await act();
  await sleep(900);
  await shot(dir, name);
  await page.unroute("**/localhost:8000/api/**");
}

if (engineUp && run("mock")) {
  // beat 3: skeptic duel, keyboard only
  await mock("doors", "hook=0&sample=clean-bw", "mock-duel-1-disputed");
  await mock("doors", "hook=0&sample=clean-bw", "mock-duel-2-card", async () => {
    await page.locator(".chip--disputed").first().focus();
    await page.keyboard.press("Enter");
  });
  await mock("doors", "hook=0&sample=clean-bw", "mock-duel-3-settled", async () => {
    await page.locator(".chip--disputed").first().focus();
    await page.keyboard.press("Enter");
    await page.click(".pin-card >> text=Yes");
  });
  await mock("doors", "hook=0&sample=clean-bw&tab=receipt", "mock-duel-4-receipt", async () => {
    await page.locator(".chip--disputed").first().focus();
    await page.keyboard.press("Enter");
    await page.click(".pin-card >> text=Yes");
  });
  // beat 4: scale band collapse
  await mock("area", "hook=0&sample=clean-bw", "mock-scale-1-band");
  await mock("area", "hook=0&sample=clean-bw", "mock-scale-2-ask", async () => {
    await page.click("text=Narrow the range");
  });
  await mock("area", "hook=0&sample=clean-bw", "mock-scale-3-collapsed", async () => {
    await page.click("text=Narrow the range");
    await page.click(".modal .hit");
    await page.click("text=Yes, 0.9 m");
  });
  await mock("area", "hook=0&sample=clean-bw", "mock-scale-4-how", async () => {
    await page.click("text=Narrow the range");
    await page.click(".modal .hit");
    await page.click("text=Yes, 0.9 m");
    await sleep(600);
    await page.click("text=how this was computed");
  });
}

await browser.close();
srv.kill();
if (errors.length) {
  console.error("console errors:\n" + errors.join("\n"));
  process.exitCode = 1;
}
