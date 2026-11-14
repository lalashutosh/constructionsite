// Scale wording + 422 message shots. The engine responses for /api/plan (printed scale) and /api/scale (422) are MOCKED here
// so the two UI states can be shown on demand; everything else is live.
import { chromium } from "@playwright/test";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const out = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "shots", "redesign");
const b = await chromium.launch({
  executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
for (const theme of ["dark", "light"]) {
  const page = await b.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
  await page.addInitScript((t) => localStorage.setItem("plumb-theme", t), theme);
  await page.route("**/api/plan**", async (route) => {
    const r = await route.fetch();
    const j = await r.json();
    j.basis.scale_px_per_m = { value: 12, unit: "px/m", tag: "specified", source: "measurements printed on the drawing: opening sizes 248x149" };
    await route.fulfill({ response: r, json: j });
  });
  await page.route("**/api/scale", (route) =>
    route.fulfill({ status: 422, contentType: "application/json", body: JSON.stringify({ detail: { message: "Rooms would be 5,515 m², far above the typical 14 m².", median_room_m2: 5515, suggestion: { label: "Use 248 cm", length_m: 2.48 } } }) }),
  );
  await page.goto("http://localhost:5173/", { waitUntil: "domcontentloaded", timeout: 90000 });
  await page.getByRole("button", { name: "Drawings" }).first().click();
  await page.locator(".drow", { hasText: "Tiny scan" }).first().click();
  await page.waitForTimeout(6000);
  await page.getByRole("tab", { name: "Build plan" }).click();
  await page.waitForTimeout(3500);
  await page.screenshot({ path: join(out, `10a-printed-scale-${theme}.png`) });
  await page.getByRole("button", { name: "Check real size" }).first().click();
  await page.waitForTimeout(2000);
  const tap = (x, y) =>
    page.evaluate(([x, y]) => {
      const c = document.querySelector(".canvas canvas");
      const o = { clientX: x, clientY: y, pointerId: 1, pointerType: "mouse", button: 0, buttons: 1, bubbles: true };
      c.dispatchEvent(new PointerEvent("pointerdown", o));
      c.dispatchEvent(new PointerEvent("pointerup", { ...o, buttons: 0 }));
    }, [x, y]);
  await tap(520, 420);
  await tap(780, 440);
  await page.waitForTimeout(600);
  await page.getByLabel("Real length").fill("248");
  await page.getByRole("button", { name: "Set size" }).click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: join(out, `10b-scale-422-${theme}.png`) });
  await page.close();
}
await b.close();
