// Checks UI screenshots into docs/shots/checks/. Needs the dev server (PLUMB_URL, default :5173) and an engine.
// THEME=dark|light, W=1440 H=900, TAG=mock|live, PLUMB_PATH=<drawing path>
import { mkdirSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const out = join(root, "docs", "shots", "checks");
mkdirSync(out, { recursive: true });
const base = process.env.PLUMB_URL ?? "http://localhost:5173/";
const theme = process.env.THEME ?? "dark";
const tag = process.env.TAG ?? "mock";
const W = Number(process.env.W ?? 1440), H = Number(process.env.H ?? 900);
const drawing = process.env.PLUMB_PATH ?? join(root, "cache", "stress", "stoa3.png");
const cache = join(process.env.HOME, ".cache", "ms-playwright");
const dir = readdirSync(cache).filter((d) => d.startsWith("chromium-")).sort().pop();
const browser = await chromium.launch({
  executablePath: process.env.PLUMB_CHROME ?? join(cache, dir, "chrome-linux64", "chrome"),
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
});
const page = await browser.newPage({ viewport: { width: W, height: H }, colorScheme: theme });
await page.addInitScript((t) => localStorage.setItem("plumb-theme", t), theme);
page.on("pageerror", (e) => console.log("pageerror", e.message, (e.stack ?? "").split("\n").slice(0, 4).join(" | ")));
const name = (n) => join(out, `${n}-${tag}-${theme}-${W}.png`);
await page.goto(`${base}?open=${encodeURIComponent(drawing)}&name=stoa3`, { waitUntil: "domcontentloaded", timeout: 90000 });
await page.waitForSelector(".checks", { timeout: 180000 });
await page.waitForFunction(() => document.querySelectorAll(".flist .frow.wait").length === 0 && document.querySelectorAll(".flist .frow").length >= 1, null, { timeout: 180000 }).catch(() => {});
await page.waitForTimeout(3500);
await page.screenshot({ path: name("1-open") });
await page.locator(".crow.open").first().hover();
await page.waitForTimeout(900);
await page.screenshot({ path: name("2-hover-evidence") });
await page.locator(".crow.open").first().getByRole("button", { name: "Yes" }).click();
await page.waitForSelector(".cnote:not(:empty)", { timeout: 60000 });
await page.waitForTimeout(800);
await page.screenshot({ path: name("3-after-yes") });
await page.getByRole("button", { name: /floor area/i }).first().click();
await page.waitForSelector(".scaleline", { timeout: 90000 }).catch(() => {});
await page.waitForTimeout(800);
await page.screenshot({ path: name("4-size-with-scale-confidence") });
await browser.close();
