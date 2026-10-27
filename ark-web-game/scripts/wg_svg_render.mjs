#!/usr/bin/env node
// wg_svg_render — 用瀏覽器（Playwright Chromium）把 SVG 轉 PNG（透明底）；wg_pack_assets 在沒有 cairosvg 或指定 --svg-engine browser 時呼叫
//   node wg_svg_render.mjs <jobs.json>      jobs = [{ "svg": "<路徑>", "png": "<路徑>", "scale": 1 }]
//   需要 playwright（npm 套件）＋ Chromium；找不到時 exit 3（呼叫端改用 cairosvg 或報錯）
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); } catch { console.error('需要 playwright（npm i -D playwright）'); process.exit(3); }
const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const launch = async () => {
  try { return await chromium.launch(); } catch (e) {
    if (process.env.PLAYWRIGHT_CHROMIUM) return chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM });
    throw e;
  }
};
const b = await launch();
const page = await b.newPage();
let n = 0;
for (const j of jobs) {
  const svg = fs.readFileSync(j.svg, 'utf8');
  const m = svg.match(/<svg[^>]*\bwidth="([\d.]+)"[^>]*\bheight="([\d.]+)"/);
  if (!m) { console.error(`缺 width／height：${j.svg}`); process.exit(2); }
  const s = Number(j.scale || 1), w = Math.round(Number(m[1]) * s), h = Math.round(Number(m[2]) * s);
  await page.setViewportSize({ width: w, height: h });
  await page.setContent(`<!doctype html><html><head><style>html,body{margin:0;background:transparent}img{display:block;width:${w}px;height:${h}px}</style></head><body><img src="data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}"></body></html>`);
  await page.waitForFunction(() => document.images[0]?.complete);
  await page.screenshot({ path: j.png, omitBackground: true, clip: { x: 0, y: 0, width: w, height: h } });
  n++;
}
await b.close();
console.log(JSON.stringify({ ok: true, rendered: n }));
