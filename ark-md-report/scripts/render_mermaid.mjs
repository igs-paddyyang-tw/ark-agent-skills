// mermaid 區塊 → SVG（build_report_html.py 呼叫）：本機 chromium＋playwright-core，mermaid 10.9.1（jsDelivr）。
// 用法：PW_DIR=<含 node_modules/playwright-core 的資料夾> node render_mermaid.mjs <in.json> <out.json>
import { createRequire } from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const [inp, outp] = process.argv.slice(2);
const { chromium } = createRequire(path.join(process.env.PW_DIR || '.', 'noop.js'))('playwright-core');
const base = path.join(os.homedir(), '.cache/ms-playwright');
let exe = '';
for (const d of fs.existsSync(base) ? fs.readdirSync(base).filter((x) => x.startsWith('chromium_headless_shell-')).sort().reverse() : []) {
  for (const sub of fs.readdirSync(path.join(base, d))) { const f = path.join(base, d, sub, 'chrome-headless-shell'); if (fs.existsSync(f)) exe = exe || f; }
}
const blocks = JSON.parse(fs.readFileSync(inp, 'utf8'));
const b = await chromium.launch({ executablePath: exe || undefined });
const p = await b.newPage();
// 先載入與報告頁相同的中文字型並等就緒：沒有字型時 mermaid 會用缺字方框量寬度，標籤被截斷、中文變方框
await p.setContent('<html><head><link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=block" rel="stylesheet"></head><body style="font-family:\'Noto Sans TC\'"><span>中文字型預載</span></body></html>', { waitUntil: 'networkidle' });
await p.evaluate(async () => { await document.fonts.load('16px "Noto Sans TC"'); await document.fonts.load('700 16px "Noto Sans TC"'); await document.fonts.ready; });
const ok = await p.evaluate(() => document.fonts.check('16px "Noto Sans TC"'));
if (!ok) throw new Error('Noto Sans TC 載入失敗（mermaid 量寬度會錯）');
await p.addScriptTag({ url: 'https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js' });
const out = await p.evaluate(async (blocks) => {
  mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'strict', flowchart: { htmlLabels: true },
    themeVariables: { fontFamily: '"Noto Sans TC", sans-serif' }, fontFamily: '"Noto Sans TC", sans-serif' });
  const r = [];
  for (const [i, code] of blocks.entries()) r.push((await mermaid.render('mmd' + i, code)).svg);
  return r;
}, blocks);
await b.close();
fs.writeFileSync(outp, JSON.stringify(out));
console.log(`mermaid：${out.length} 張`);
