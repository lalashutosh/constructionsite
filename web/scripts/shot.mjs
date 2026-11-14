// Screenshots into docs/shots/ui/. Builds are served by `vite preview` on :4173.
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, "..", "..", "docs", "shots", "ui");
mkdirSync(out, { recursive: true });
const base = "http://localhost:4173/";

const srv = spawn("npx", ["vite", "preview", "--port", "4173", "--strictPort"], { cwd: join(here, ".."), stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
for (let i = 0; i < 40; i++) {
  try {
    if ((await fetch(base)).ok) break;
  } catch {
    /* not up yet */
  }
  await sleep(250);
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
const shot = (n) => page.screenshot({ path: join(out, `${n}.png`) });

// hook frames: start the clock at an offset so each frame is deterministic
for (const [n, t] of [["hook-0s", 0.5], ["hook-3s", 3.4], ["hook-5s", 5.6], ["hook-7s", 7], ["hook-9s", 9]]) {
  await page.goto(`${base}?hookAt=${t}`);
  await sleep(300);
  await shot(n);
}

async function app(query, name, act) {
  await page.goto(`${base}?hook=0&${query}`);
  await page.waitForSelector(".stage");
  await sleep(900);
  if (act) await act();
  await sleep(900);
  await shot(name);
}

await app("fx=doors", "answer");
await app("fx=doors", "answer-hover", async () => {
  await page.hover(".num");
});
await app("fx=doors", "duel-resolved", async () => {
  await page.click("text=Yes, a door");
});
await app("fx=area_before&tab=receipt", "receipt");
await app("fx=area_before&tab=decide", "decide");
await app("fx=area_before&tab=findings", "findings");
await app("fx=area_before&ask=1", "scale-ask");
await app("fx=area_before", "band-before");
await app("fx=area_before&ask=1", "band-after", async () => {
  await page.click(".modal .hit");
  await page.click("text=Yes, 0.9 m");
});
await app("fx=refusal", "grey");
await app("fx=doors&view=overlay", "overlay");
await app("fx=doors&view=scan", "scan");

await page.setViewportSize({ width: 1280, height: 720 });
await app("fx=doors", "answer-1280");

await browser.close();
srv.kill();
if (errors.length) {
  console.error("console errors:\n" + errors.join("\n"));
  process.exitCode = 1;
}
