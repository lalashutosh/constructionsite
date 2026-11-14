// Project (folder upload) explorer + progress states, and the object close-up. THEME=dark|light.
import { chromium } from "@playwright/test";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const out = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "shots", "redesign");
const theme = process.env.THEME ?? "dark";
const folder = process.env.PLUMB_FOLDER ?? `${process.env.HOME}/Downloads/junction-dataset-preview/data/opening_design/Sports_Complex`;
const b = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
const page = await b.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
await page.addInitScript((t) => localStorage.setItem("plumb-theme", t), theme);
page.on("pageerror", (e) => console.log("pageerror", e.message));
const shot = (n) => page.screenshot({ path: join(out, `${n}-${theme}.png`) });

if (!process.env.ONLY_PROJECT) {
// object close-up on a plan with toilet / sink / doors / windows
await page.goto("http://localhost:5173/", { waitUntil: "domcontentloaded", timeout: 90000 });
await page.getByRole("button", { name: "Drawings" }).first().click();
await page.locator(".drow", { hasText: "Clean black" }).first().click();
await page.waitForTimeout(500);
await shot("11a-single-progress");
await page.waitForFunction(() => !!document.querySelector(".narr button.linkbtn"), null, { timeout: 120000 }).catch(() => {});
await page.waitForTimeout(3500);
await page.mouse.move(520, 330);
for (let i = 0; i < 4; i++) { await page.mouse.wheel(0, -400); await page.waitForTimeout(120); }
await page.waitForTimeout(1800);
await shot("12-objects-closeup");

await page.goto("http://localhost:5173/", { waitUntil: "domcontentloaded", timeout: 90000 });
await page.getByRole("button", { name: "Drawings" }).first().click();
await page.locator(".drow", { hasText: "Tall" }).first().click();
await page.waitForFunction(() => !!document.querySelector(".narr button.linkbtn"), null, { timeout: 120000 }).catch(() => {});
await page.waitForTimeout(4500);
await shot("14-tall-rowhouse");

}
// folder upload
await page.goto("http://localhost:5173/", { waitUntil: "domcontentloaded", timeout: 90000 });
await page.locator('input[type=file][webkitdirectory]').setInputFiles(folder);
await page.waitForTimeout(9000);
await shot("13a-project-progress");
await page.waitForFunction(() => !document.querySelector(".prog") || /Building floor|Done/.test(document.querySelector(".prog")?.textContent ?? ""), null, { timeout: 420000 }).catch(() => {});
await page.waitForTimeout(4000);
await shot("13b-project-explorer");
const flatRow = page.locator(".prow:not(.folder)").filter({ has: page.locator(".ptype", { hasText: /Section|Schedule|3D render|Elevation|Detail/ }) }).first();
if (await flatRow.count()) {
  await flatRow.click();
  await page.waitForTimeout(2500);
  await shot("13c-project-flat-file");
}
await b.close();
