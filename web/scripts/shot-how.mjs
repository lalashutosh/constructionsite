// how-it-works page only, both themes
import { chromium } from "@playwright/test";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const out = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "shots", "redesign");
const b = await chromium.launch({ executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing` });
for (const theme of ["dark", "light"]) {
  const page = await b.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
  await page.addInitScript((t) => localStorage.setItem("plumb-theme", t), theme);
  await page.goto("http://localhost:5173/", { waitUntil: "domcontentloaded", timeout: 90000 });
  await page.getByRole("button", { name: "How it works" }).click();
  await page.waitForTimeout(800);
  await page.mouse.move(700, 450);
  await page.screenshot({ path: join(out, `07-how-it-works-${theme}.png`) });
  await page.evaluate(() => document.querySelector(".how").scrollTo(0, 99999));
  await page.waitForTimeout(300);
  await page.screenshot({ path: join(out, `07b-how-numbers-${theme}.png`) });
  await page.close();
}
await b.close();
