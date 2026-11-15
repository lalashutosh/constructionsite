import { chromium } from '../../../web/node_modules/playwright/index.mjs';
const ROOT = process.cwd();
const b = await chromium.launch({ headless: true, executablePath: process.env.HOME + '/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing', args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'] });
const ctx = await b.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
await ctx.addInitScript(() => { const g = Storage.prototype.getItem; Storage.prototype.getItem = function (k) { if (k.startsWith('plumb-tour')) return 'done'; if (k === 'plumb-theme') return 'dark'; return g.call(this, k); }; });
const p = await ctx.newPage();
for (const [n, path] of [['small', 'data/cubicasa5k/colorful-2002.png'], ['dorm', process.argv[2]]]) {
  const t = Date.now();
  await p.goto(`http://localhost:5173/?open=${encodeURIComponent(path)}`);
  await p.waitForTimeout(12000);
  await p.screenshot({ path: `docs/pitch/video/cap/probe_${n}.png` });
  console.log(n, Date.now() - t);
}
await b.close();
