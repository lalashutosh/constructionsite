// Hover on a size label after setting a real size: shows how it was measured. THEME=dark|light.
import { chromium } from "@playwright/test";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const out = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "shots", "redesign");
const theme = process.env.THEME ?? "dark";
const b = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
const page = await b.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
await page.addInitScript((t) => localStorage.setItem("plumb-theme", t), theme);
await page.goto("http://localhost:5173/", { waitUntil: "domcontentloaded", timeout: 90000 });
await page.getByRole("button", { name: "Drawings" }).first().click();
await page.locator(".drow", { hasText: "Tiny scan" }).first().click();
await page.waitForFunction(() => !!document.querySelector(".narr button.linkbtn"), null, { timeout: 120000 }).catch(() => {});
await page.waitForTimeout(3500);
await page.getByRole("button", { name: "Set real size" }).first().click();
await page.waitForTimeout(2200);
const tap = (x, y) => page.evaluate(([x, y]) => {
  const c = document.querySelector(".canvas canvas");
  const o = { clientX: x, clientY: y, pointerId: 1, pointerType: "mouse", button: 0, buttons: 1, bubbles: true };
  c.dispatchEvent(new PointerEvent("pointerdown", o));
  c.dispatchEvent(new PointerEvent("pointerup", { ...o, buttons: 0 }));
}, [x, y]);
await tap(360, 400);
await tap(640, 410);
await page.getByLabel("Real length").fill("9");
await page.getByRole("button", { name: "Set size" }).click();
await page.waitForTimeout(9000);
let found = false;
for (let y = 150; y < 500 && !found; y += 22) {
  for (let x = 120; x < 700 && !found; x += 22) {
    await page.mouse.move(x, y);
    await page.waitForTimeout(60);
    if (await page.locator(".dimtip", { hasText: process.env.WANT ?? "Length" }).count()) found = true;
  }
}
await page.waitForTimeout(400);
await page.screenshot({ path: join(out, `15-hover-measure-${theme}.png`) });
console.log("found", found);
await b.close();
