// Redesign screenshots (live engine on :8000, dev server on :5173) into docs/shots/redesign/.
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const out = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "shots", "redesign");
mkdirSync(out, { recursive: true });
const base = process.env.PLUMB_URL ?? "http://localhost:5173/";
const browser = await chromium.launch({
  executablePath: process.env.PLUMB_CHROME ?? `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const theme = process.env.THEME ?? "dark";
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
await page.addInitScript((t) => localStorage.setItem("plumb-theme", t), theme);
page.on("pageerror", (e) => console.log("pageerror", e.message));
page.on("console", (m) => m.type() === "error" && console.log("console", m.text().slice(0, 200)));

async function openSample(label) {
  await page.goto(base, { waitUntil: "domcontentloaded", timeout: 90000 });
  await page.getByRole("button", { name: "Drawings" }).first().click();
  await page.locator(".drow", { hasText: label }).first().click();
}
const settle = async (ms = 90000) => {
  await page.waitForFunction(() => !document.querySelector(".flist .frow.wait"), null, { timeout: ms }).catch(() => {});
  await page.waitForFunction(() => !document.querySelector(".loading"), null, { timeout: ms }).catch(() => {});
  await page.waitForTimeout(1800);
};
const shot = (n) => page.screenshot({ path: join(out, n.replace(".png", `-${theme}.png`)) });

await openSample("Tiny scan");
await settle();
await shot("01-cubicasa-findings.png");
await page.locator("button.frow", { hasText: "windows" }).first().click();
await page.waitForTimeout(1500);
await shot("02-cubicasa-windows-pins.png");

await page.getByPlaceholder("Ask anything").fill("Which room is the largest?");
await page.getByRole("button", { name: "Ask", exact: true }).click();
await page.waitForFunction(() => !document.querySelector(".answer.stale"), null, { timeout: 60000 }).catch(() => {});
await page.waitForTimeout(1500);
await shot("03-hard-question.png");
await page.getByRole("button", { name: "Are there more windows than doors?" }).click();
await page.waitForTimeout(4000);
await shot("04-hard-question-2.png");

await page.getByRole("tab", { name: "Build plan" }).click();
await page.waitForTimeout(2500);
await page.locator(".stp").nth(2).click();
await page.waitForTimeout(2500);
await shot("05a-plan-step3-floor.png");
await page.locator(".stp").nth(3).click();
await page.waitForTimeout(2500);
await shot("05b-plan-step4-walls.png");
await page.locator(".stp").nth(4).click();
await page.waitForTimeout(2500);
await shot("05c-plan-step5-roof.png");
await page.getByRole("button", { name: "off", exact: true }).click();
await page.waitForTimeout(1000);
await shot("05d-drawing-off.png");
await page.getByRole("button", { name: "Checklist" }).click();
await page.waitForTimeout(500);
await shot("05e-checklist.png");

await openSample("Clean");
await settle();
await shot("05f-text-readable.png");
await openSample("Upside-down");
await settle();
await shot("05-cubicasa-rotated.png");

await openSample("Swiss");
await settle(120000);
await shot("06-swiss.png");

await openSample("Elevation");
await settle();
await shot("07-refusal.png");
await browser.close();
