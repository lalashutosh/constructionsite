// Drives the real app (localhost:5173 + engine :8001) and saves every scene as frames + where the cursor goes.
// node docs/pitch/video/capture.mjs [scene ...]     -> docs/pitch/video/cap/<scene>/f###.png + meta.json
import { chromium } from '../../../web/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import path from 'node:path';

const ROOT = process.cwd();
const OUT = path.join(ROOT, 'docs/pitch/video/cap');
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing';
const up = (p) => fs.readdirSync(path.join(ROOT, 'cache/uploads')).filter((f) => f.startsWith(p) && f.endsWith('.png')).map((f) => path.join(ROOT, 'cache/uploads', f))[0];
const DORM = up('a92115880ee3'), PIPE = up('b25805c1c751');
const SMALL = 'data/cubicasa5k/colorful-2002.png', NOSCALE = 'data/cubicasa5k/high_quality_architectural-594.png';

const b = await chromium.launch({ headless: true, executablePath: EXE, args: ['--use-angle=metal', '--ignore-gpu-blocklist'] });
const ctx = await b.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 2, reducedMotion: 'reduce' });
await ctx.addInitScript(() => {
  const g = Storage.prototype.getItem;
  Storage.prototype.getItem = function (k) { if (k.startsWith('plumb-tour')) return 'done'; if (k === 'plumb-theme') return 'dark'; return g.call(this, k); };
});
const page = await ctx.newPage();
let scene, meta, n, cur = { x: 800, y: 450 };

function begin(name) { scene = name; meta = []; n = 0; fs.rmSync(path.join(OUT, name), { recursive: true, force: true }); fs.mkdirSync(path.join(OUT, name), { recursive: true }); }
function end() { fs.writeFileSync(path.join(OUT, scene, 'meta.json'), JSON.stringify(meta, null, 1)); console.log(scene, meta.length, 'frames'); }
async function shot(tag = '', extra = {}) {
  const f = `f${String(n++).padStart(3, '0')}.png`;
  await page.screenshot({ path: path.join(OUT, scene, f) });
  const rects = await page.evaluate((sels) => {
    const o = {};
    for (const [k, s] of Object.entries(sels)) {
      const e = document.querySelector(s); if (!e) continue;
      const r = e.getBoundingClientRect(); if (r.width < 2) continue;
      o[k] = [r.x, r.y, r.width, r.height].map((v) => Math.round(v));
    }
    return o;
  }, { answer: '.answer', ask: '.askform', ck: '.cklist', badge: '.scalebadge', sheet: 'aside.sheet', canvas: 'canvas',
       right: '.col.right', payoff: '.banner', measure: '.measure', cost: '.answer .mono, .answer [class*=cost]' });
  meta.push({ f, tag, cursor: { ...cur }, rects, ...extra });
}
const wait = (ms) => page.waitForTimeout(ms);
async function center(loc) { const r = await loc.first().boundingBox(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; }
async function click(loc, tag) {
  cur = await center(loc);
  await page.mouse.move(cur.x, cur.y);
  await shot(`move:${tag}`, { click: true });
  await loc.first().click();
}
async function open(p, name) {
  await page.goto(`http://localhost:5173/?open=${encodeURIComponent(p)}&name=${encodeURIComponent(name)}`);
  await page.waitForSelector('canvas', { timeout: 120000 });
  await page.waitForFunction(() => !!window.__plumbViewer, null, { timeout: 120000 });
  await wait(9000);
}
async function view(v) { await page.getByRole('button', { name: v, exact: true }).first().click(); await wait(1200); }
async function answered() {
  await wait(400);
  await page.waitForFunction(() => !document.querySelector('.askform button')?.textContent?.includes('Asking'), null, { timeout: 300000 });
  await wait(900);
}
async function ask(q) {
  const box = page.locator('.askform input').first();
  cur = await center(box); cur.x -= 300;
  await box.click(); await box.fill('');
  for (let i = 0; i < q.length; i += 3) { await box.type(q.slice(i, i + 3)); await shot('type'); }
  await page.keyboard.press('Enter');
  await shot('asking');
  await answered();
  await shot('answer', { hold: 1 });
}
async function proof(tag = 'proof') {
  await click(page.getByRole('button', { name: /See proof/ }), 'proof');
  await wait(2500);
  await shot(tag, { hold: 1 });
}
async function closeProof() { const x = page.getByRole('button', { name: 'Close' }); if (await x.count()) { await x.first().click(); await wait(600); } }

const S = {
  async small() {
    begin('small'); await open(SMALL, 'Apartment plan'); await view('Top');
    await shot('open', { hold: 1 });
    await ask('How many doors?');
    await proof(); end();
  },
  async dorm_open() {
    begin('dorm_open'); await open(DORM, 'A-2 Dormitory, second floor'); await view('Top');
    await shot('top', { hold: 1 }); await view('3D'); await shot('3d', { hold: 1 }); end();
  },
  async dorm_ask() {
    begin('dorm_ask'); await open(DORM, 'A-2 Dormitory, second floor'); await view('Top');
    await ask('How many doors?'); await proof('proof_doors'); await closeProof();
    await ask('Are there more doors or toilets and sinks?'); await proof('proof_cmp'); end();
  },
  async doors() {
    begin('doors'); await open(DORM, 'A-2 Dormitory, second floor'); await view('Top');
    await shot('top', { hold: 1 });
    const row = page.locator('.cklist').getByText(/^Doors/).first();
    await click(row, 'Doors'); await wait(2500); await shot('lit', { hold: 1 }); end();
  },
  async lang() {
    begin('lang'); await open(SMALL, 'Apartment plan'); await view('Top');
    await ask('Montako makuuhuonetta asunnossa on?');
    await ask('¿Cuántos dormitorios hay?'); end();
  },
  async scale() {
    begin('scale'); await open(DORM, 'A-2 Dormitory, second floor'); await view('Top');
    await shot('badge', { hold: 1 });
    await click(page.getByRole('button', { name: 'Where?' }), 'where'); await wait(2500); await shot('pins', { hold: 1 }); end();
  },
  async measure() {
    begin('measure'); await open(NOSCALE, 'Plan with no scale'); await view('Top');
    await shot('before', { hold: 1 });
    await click(page.getByRole('button', { name: /Set real size/ }), 'set'); await wait(800);
    for (const [x, y] of [[545.6, 156.9], [564.6, 156.9]]) {
      cur = await page.evaluate(([x, y]) => window.__plumbViewer.screenOfPixel(x, y), [x, y]);
      await page.mouse.move(cur.x, cur.y); await shot('pt', { click: true }); await page.mouse.click(cur.x, cur.y); await wait(500);
    }
    await shot('picked');
    const len = page.getByLabel('Real length'); cur = await center(len);
    await len.fill('0.9'); await shot('typed');
    await click(page.getByRole('button', { name: 'Set size' }), 'setsize');
    await answered(); await wait(2500); await shot('payoff', { hold: 1 }); end();
  },
  async threed() {
    begin('threed'); await open(DORM, 'A-2 Dormitory, second floor'); await view('3D');
    await shot('3d', { hold: 1 });
    const c = await center(page.locator('canvas')); cur = { x: c.x + 120, y: c.y + 60 };
    await page.mouse.move(cur.x, cur.y); await page.mouse.down();
    for (let i = 0; i < 70; i++) { cur = { x: cur.x - 4, y: cur.y - (i < 35 ? 0.6 : -0.6) }; await page.mouse.move(cur.x, cur.y); await shot('orbit', { frame: 1 }); }
    await page.mouse.up();
    for (const l of ['Furniture', 'Piping', 'Electrical']) { await click(page.getByRole('button', { name: new RegExp(l) }), l); await wait(1500); await shot(`layer:${l}`, { hold: 1 }); }
    for (const l of ['Furniture', 'Piping', 'Electrical']) { await page.getByRole('button', { name: new RegExp(l) }).first().click(); await wait(300); }
    await wait(1000);
    for (const k of ['Beds', 'Stair']) {
      const row = page.locator('.cklist').getByText(new RegExp(`^${k}`)).first();
      await row.scrollIntoViewIfNeeded(); await wait(400);
      await click(row, k); await wait(2000); await shot(`ck:${k}`, { hold: 1 });
    }
    end();
  },
  async plan() {
    begin('plan'); await open(DORM, 'A-2 Dormitory, second floor'); await view('3D');
    await click(page.getByRole('tab', { name: /Build plan/ }), 'plan'); await wait(3500); await shot('plan', { hold: 1 });
    const sc = page.locator('.col.right .kscroll, .col.right [class*=scroll]').first();
    for (let i = 0; i < 14; i++) { await sc.evaluate((e) => e.scrollBy(0, 160)).catch(() => page.mouse.wheel(0, 160)); await wait(250); await shot('scroll', { frame: 1 }); }
    await wait(800); await shot('end', { hold: 1 }); end();
  },
  async pipe() {
    begin('pipe'); await open(PIPE, 'M-101A Piping plan'); await view('Top');
    await shot('open', { hold: 1 });
    await ask('How many check valves are there?'); await proof(); end();
  },
};

const want = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(S);
for (const k of want) { try { await S[k](); } catch (e) { console.log('FAILED', k, e.message.split('\n')[0]); end(); } }
await b.close();
