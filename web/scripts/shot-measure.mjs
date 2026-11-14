// one-off: measure tool screenshot (dark) into docs/shots/redesign/
import { chromium } from "@playwright/test";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const out = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "shots", "redesign");
const b = await chromium.launch({ executablePath: `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`, args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.addInitScript(() => localStorage.setItem("plumb-theme", "dark"));
await page.goto("http://localhost:5173/", { waitUntil: "domcontentloaded", timeout: 90000 });
await page.getByRole("button", { name: "Drawings" }).first().click();
await page.locator(".drow", { hasText: "Tiny scan" }).first().click();
await page.waitForTimeout(8000);
await page.getByLabel("Set real size").click();
await page.mouse.click(300, 330);
await page.mouse.click(520, 360);
await page.waitForTimeout(800);
await page.screenshot({ path: join(out, "04c-measure-dots-dark.png") });
await b.close();
