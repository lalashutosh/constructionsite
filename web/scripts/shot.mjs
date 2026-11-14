// Redesign screenshots (live engine on :8000, dev server on :5173) into docs/shots/redesign/.
// THEME=dark|light selects the theme; files are suffixed -dark / -light.
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const out = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "shots", "redesign");
mkdirSync(out, { recursive: true });
const base = process.env.PLUMB_URL ?? "http://localhost:5173/";
const theme = process.env.THEME ?? "dark";
const browser = await chromium.launch({
  executablePath: process.env.PLUMB_CHROME ?? `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
await page.addInitScript((t) => localStorage.setItem("plumb-theme", t), theme);
page.on("pageerror", (e) => console.log("pageerror", e.message));
const shot = (n) => page.screenshot({ path: join(out, n.replace(".png", `-${theme}.png`)) });
const sleep = (ms) => page.waitForTimeout(ms);

async function openSample(label) {
  await page.goto(base, { waitUntil: "domcontentloaded", timeout: 90000 });
  await page.getByRole("button", { name: "Drawings" }).first().click();
  await page.locator(".drow", { hasText: label }).first().click();
}
const settle = async (ms = 90000) => {
  await page.waitForFunction(() => document.querySelectorAll(".flist .frow.wait").length === 0 && document.querySelectorAll(".flist .frow").length >= 3, null, { timeout: ms }).catch(() => {});
  await page.waitForFunction(() => !!document.querySelector(".narr button.linkbtn"), null, { timeout: ms }).catch(() => {});
  await sleep(1500);
};
// pointerdown + pointerup straight onto the canvas, no pointermove before (like a tap)
const tap = (x, y) =>
  page.evaluate(
    ([x, y]) => {
      const c = document.querySelector(".canvas canvas");
      const o = { clientX: x, clientY: y, pointerId: 1, pointerType: "mouse", button: 0, buttons: 1, bubbles: true };
      c.dispatchEvent(new PointerEvent("pointerdown", o));
      c.dispatchEvent(new PointerEvent("pointerup", { ...o, buttons: 0 }));
    },
    [x, y],
  );

// a) Read: the scan line and the story line
await openSample("Tiny scan");
await page.waitForFunction(() => !!document.querySelector(".canvas canvas"), null, { timeout: 30000 });
await sleep(900);
await shot("01a-read-scan.png");
await sleep(2600);
await shot("01b-read-built.png");
// b) Know
await settle();
await shot("02-know-findings.png");
// sentence answer with pins
await page.locator(".fmain", { hasText: "window" }).first().click();
await sleep(1500);
await shot("03-sentence-answer.png");
// Why sheet
await page.locator(".frow .why").first().click();
await sleep(700);
await shot("04-why-sheet.png");
await page.getByRole("button", { name: "Close" }).click();

// scale: before / pick / measure / payoff / after
await shot("05a-scale-before.png");
await page.getByRole("button", { name: "Set real size" }).first().click();
await sleep(2200);
await shot("05b-scale-pick.png");
await tap(520, 420);
await tap(780, 440);
await sleep(700);
await shot("05c-scale-measure.png");
await page.getByLabel("Real length in metres").fill("4");
await page.getByRole("button", { name: "Set size" }).click();
await sleep(2600);
await shot("05d-scale-payoff.png");
await sleep(7000);
await shot("05e-scale-after.png");

// c) Build
await page.getByRole("tab", { name: "Build plan" }).click();
await sleep(2500);
await shot("06a-build-materials.png");
await page.getByRole("button", { name: "Build steps" }).click();
await page.locator(".stp").nth(4).click();
await sleep(2500);
await shot("06b-build-roof.png");

// how it works
await page.getByRole("button", { name: "How it works" }).click();
await sleep(800);
await shot("07-how-it-works.png");

await openSample("Swiss");
await settle(120000);
await shot("08-swiss.png");
await openSample("Elevation");
await settle();
await shot("09-refusal.png");
await browser.close();
