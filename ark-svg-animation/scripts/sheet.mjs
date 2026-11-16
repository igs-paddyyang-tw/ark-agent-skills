#!/usr/bin/env node
// sheet.mjs —— 建置期：逐格 SVG → PixiJS spritesheet（每種一組 <NAME>.png＋<NAME>.json）。
//
// 作法：把該物種所有格依座標排進一個透明背景的 HTML，用 headless Chromium 截一張圖 = 拼圖 PNG。
//   與瀏覽器執行時 Graphics.svg() 同一個繪製引擎；座標是自己排的，JSON 與 PNG 一定對得上。
// Chromium：$ARK_SVGA_CHROME → ~/.cache/ms-playwright/*/chrome-headless-shell|chrome → PATH 的 chromium／google-chrome。
//   都找不到 → 明說跳過（exit 3），不產半套檔案。
//
//   node sheet.mjs --out out/sheets [--names A,B|all] [--length 100] [--scale 1|2] [--facing up|right]
//   node sheet.mjs --check out/sheets      # 驗 PNG 尺寸＝JSON、每格非空白、animations 與 frames 對得上
//   node sheet.mjs --check out/sheets --pixi <pixi.min.js>   # 另外用真的 PixiJS 在 headless Chromium 跑 Spritesheet.parse（AC-6）
// exit：0 成功／1 驗證失敗／2 參數錯／3 沒有 Chromium
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { homedir, tmpdir } from 'node:os';
import path from 'node:path';
import { inflateSync } from 'node:zlib';
import { creature, SPECIES, VERSION } from './svg_anim.mjs';

const GAP = 2; // 格與格之間的透明間隔（避免縮放取樣時互相滲色）

/** 找 headless Chromium；找不到回 null */
export function findChrome() {
  const env = process.env.ARK_SVGA_CHROME;
  if (env && existsSync(env)) return env;
  const base = path.join(homedir(), '.cache', 'ms-playwright');
  if (existsSync(base)) {
    for (const d of readdirSync(base).sort().reverse()) {
      for (const sub of ['chrome-linux/chrome-headless-shell', 'chrome-headless-shell-linux64/chrome-headless-shell', 'chrome-linux/chrome', 'chrome-linux64/chrome']) {
        const p = path.join(base, d, sub);
        if (existsSync(p)) return p;
      }
    }
  }
  for (const n of ['chromium', 'chromium-browser', 'google-chrome']) {
    try { const p = execFileSync('which', [n], { encoding: 'utf8' }).trim(); if (p) return p; } catch { /* 沒有 */ }
  }
  return null;
}

/** 排版：所有格一列（swim 再 catch），格寬高＝viewBox 取整 */
export function layout(frames, meta) {
  const [w, h] = meta.viewBox.map((v) => Math.ceil(v));
  const cells = [];
  let x = 0;
  for (const [state, list] of Object.entries(frames)) list.forEach((svg, i) => { cells.push({ key: `${meta.name}/${state}_${i}`, state, svg, x, y: 0, w, h }); x += w + GAP; });
  return { cells, width: x - GAP, height: h };
}

/** PixiJS（TexturePacker hash 格式）JSON：frames＋animations＋meta.image */
export function sheetJson(name, lay, meta, scale) {
  const frames = {}, animations = {};
  for (const c of lay.cells) {
    const r = { x: c.x * scale, y: c.y * scale, w: c.w * scale, h: c.h * scale };
    frames[c.key] = { frame: r, rotated: false, trimmed: false, spriteSourceSize: { x: 0, y: 0, w: r.w, h: r.h }, sourceSize: { w: r.w, h: r.h }, anchor: { x: meta.anchor[0], y: meta.anchor[1] } };
    (animations[c.state] ??= []).push(c.key);
  }
  return {
    frames, animations,
    meta: { app: 'ark-svg-animation', version: VERSION, image: `${name}.png`, format: 'RGBA8888', size: { w: lay.width * scale, h: lay.height * scale }, scale: String(scale), creature: meta },
  };
}

function render(chrome, lay, scale, png) {
  const tmp = mkdtempSync(path.join(tmpdir(), 'svga-sheet-'));
  const html = path.join(tmp, 'sheet.html');
  const body = lay.cells.map((c) => `<div style="position:absolute;left:${c.x}px;top:${c.y}px;width:${c.w}px;height:${c.h}px">${c.svg}</div>`).join('');
  writeFileSync(html, `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;background:transparent;overflow:hidden}svg{display:block}</style></head><body>${body}</body></html>`);
  execFileSync(chrome, ['--headless', '--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--default-background-color=00000000',
    `--force-device-scale-factor=${scale}`, `--window-size=${lay.width},${lay.height}`, `--screenshot=${png}`, `file://${html}`], { stdio: 'ignore', timeout: 60000 });
}

// ── PNG 最小解碼（RGBA8、不交錯）：只為了驗「每格非空白」，不引第三方 ─────────
export function decodePng(buf) {
  if (buf.readUInt32BE(0) !== 0x89504e47) throw new Error('不是 PNG');
  let off = 8, w = 0, h = 0, ct = 0, depth = 0;
  const idat = [];
  while (off < buf.length) {
    const len = buf.readUInt32BE(off), type = buf.toString('ascii', off + 4, off + 8), data = buf.subarray(off + 8, off + 8 + len);
    if (type === 'IHDR') { w = data.readUInt32BE(0); h = data.readUInt32BE(4); depth = data[8]; ct = data[9]; if (data[12]) throw new Error('不支援交錯 PNG'); }
    if (type === 'IDAT') idat.push(data);
    off += 12 + len;
  }
  if (depth !== 8 || (ct !== 6 && ct !== 2)) throw new Error(`不支援的 PNG 格式（depth ${depth}、color ${ct}）`);
  const bpp = ct === 6 ? 4 : 3, stride = w * bpp, raw = inflateSync(Buffer.concat(idat)), px = Buffer.alloc(h * stride);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)], src = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1)), row = px.subarray(y * stride, (y + 1) * stride), prev = y ? px.subarray((y - 1) * stride, y * stride) : null;
    for (let i = 0; i < stride; i++) {
      const a = i >= bpp ? row[i - bpp] : 0, b = prev ? prev[i] : 0, c = prev && i >= bpp ? prev[i - bpp] : 0;
      let v = src[i];
      if (f === 1) v += a; else if (f === 2) v += b; else if (f === 3) v += (a + b) >> 1;
      else if (f === 4) { const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c); v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c; }
      row[i] = v & 0xff;
    }
  }
  return { w, h, bpp, px };
}

/** 驗一組 sheet：PNG 尺寸＝JSON、每格有不透明像素、animations 只指向存在的 frame */
export function checkSheet(dir, name) {
  const out = [];
  const j = JSON.parse(readFileSync(path.join(dir, `${name}.json`), 'utf8'));
  const img = decodePng(readFileSync(path.join(dir, j.meta.image)));
  if (img.w !== j.meta.size.w || img.h !== j.meta.size.h) out.push(`${name}：PNG ${img.w}×${img.h} ≠ JSON ${j.meta.size.w}×${j.meta.size.h} → 重產`);
  if (img.bpp !== 4) out.push(`${name}：PNG 沒有透明通道 → Chromium 要帶 --default-background-color=00000000`);
  for (const [k, f] of Object.entries(j.frames)) {
    let ink = 0;
    for (let y = f.frame.y; y < f.frame.y + f.frame.h && y < img.h; y += 2) for (let x = f.frame.x; x < f.frame.x + f.frame.w && x < img.w; x += 2) if (img.bpp === 4 && img.px[(y * img.w + x) * 4 + 3] > 16) ink++;
    if (ink < 10) out.push(`${name}：${k} 是空白格 → 繪製失敗（SVG 錯誤或 Chromium 沒畫出來）`);
  }
  for (const [a, list] of Object.entries(j.animations)) for (const k of list) if (!j.frames[k]) out.push(`${name}：animations.${a} 指向不存在的 ${k}`);
  if (!j.animations.swim?.length || !j.animations.catch?.length) out.push(`${name}：缺 swim 或 catch 動畫`);
  return out;
}

/**
 * 用真的 PixiJS（使用方提供的瀏覽器版 pixi.min.js）在 headless Chromium 解析每組 sheet：
 * 解析出的 texture 數、animations 名稱與格數要等於 JSON。回傳問題清單。
 */
export function pixiParse(dir, names, pixiPath, chrome = findChrome()) {
  if (!chrome) return ['找不到 headless Chromium —— 無法做 PixiJS 解析檢查'];
  const sheets = names.map((n) => {
    const json = JSON.parse(readFileSync(path.join(dir, `${n}.json`), 'utf8'));
    return { n, json };
  });
  // 像素由 checkSheet 驗；這裡只驗「PixiJS 讀得懂 JSON」→ 用同尺寸的空 TextureSource（圖片非同步解碼會在 --dump-dom 之後才完成）
  // PixiJS 與資料用 <script src> 引用，不內嵌：--dump-dom 只回傳小小的 DOM（內嵌 1 MB 會撐爆輸出緩衝，ENOBUFS）
  const tmp = mkdtempSync(path.join(tmpdir(), 'svga-pixi-'));
  writeFileSync(path.join(tmp, 'data.js'), `window.S = ${JSON.stringify(sheets)};`);
  const html = path.join(tmp, 'parse.html');
  writeFileSync(html, `<!doctype html><html><head><meta charset="utf-8"><script src="file://${path.resolve(pixiPath)}"></script><script src="data.js"></script></head><body><pre id="r"></pre><script>
(async () => {
  const out = {};
  for (const s of window.S) {
    try {
      const src = new PIXI.TextureSource({ width: s.json.meta.size.w, height: s.json.meta.size.h });
      const sheet = new PIXI.Spritesheet(new PIXI.Texture({ source: src }), s.json);
      await sheet.parse();
      out[s.n] = { textures: Object.keys(sheet.textures).length, animations: Object.fromEntries(Object.entries(sheet.animations).map(([k, v]) => [k, v.length])) };
    } catch (e) { out[s.n] = { error: String(e) }; }
  }
  document.getElementById('r').textContent = JSON.stringify(out);
})().catch((e) => { document.getElementById('r').textContent = JSON.stringify({ __error: String(e) }); });
</script></body></html>`);
  const dom = execFileSync(chrome, ['--headless', '--no-sandbox', '--disable-gpu', '--virtual-time-budget=20000', '--allow-file-access-from-files', '--dump-dom', `file://${html}`],
    { encoding: 'utf8', timeout: 90000, maxBuffer: 64 * 1024 * 1024, stdio: ['ignore', 'pipe', 'ignore'] });
  const m = /<pre id="r">([\s\S]*?)<\/pre>/.exec(dom);
  if (!m || !m[1].trim()) return ['PixiJS 解析頁沒有產出結果（腳本錯誤或逾時）→ 確認 --pixi 是瀏覽器版 pixi.min.js（有 window.PIXI）'];
  const got = JSON.parse(m[1].replace(/&quot;/g, '"').replace(/&amp;/g, '&'));
  const problems = [];
  for (const s of sheets) {
    const g = got[s.n];
    if (!g || g.error) { problems.push(`${s.n}：PixiJS 解析失敗 ${g?.error ?? '（沒有結果）'}`); continue; }
    if (g.textures !== Object.keys(s.json.frames).length) problems.push(`${s.n}：PixiJS 解析出 ${g.textures} 格 ≠ JSON ${Object.keys(s.json.frames).length} 格`);
    for (const [a, list] of Object.entries(s.json.animations)) if (g.animations[a] !== list.length) problems.push(`${s.n}：PixiJS animations.${a} ${g.animations[a] ?? 0} 格 ≠ JSON ${list.length} 格`);
  }
  return problems;
}

export function buildSheets({ out, names, length = 100, scale = 1, facing = 'up', chrome = findChrome() }) {
  if (!chrome) return { skipped: '找不到 headless Chromium（設 ARK_SVGA_CHROME 或安裝 playwright chromium）—— 跳過，未產任何檔案', built: [] };
  mkdirSync(out, { recursive: true });
  const built = [];
  for (const name of names) {
    const { frames, meta } = creature({ name, length, facing });
    const lay = layout(frames, meta);
    render(chrome, lay, scale, path.join(out, `${meta.name}.png`));
    writeFileSync(path.join(out, `${meta.name}.json`), JSON.stringify(sheetJson(meta.name, lay, meta, scale), null, 1) + '\n');
    built.push(meta.name);
  }
  writeFileSync(path.join(out, 'index.json'), JSON.stringify({ version: VERSION, length, scale, facing, sheets: built.map((n) => `${n}.json`) }, null, 2) + '\n');
  return { built };
}

const isMain = process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href;
if (isMain) {
  const a = process.argv.slice(2), opt = (k, d) => { const i = a.indexOf(`--${k}`); return i >= 0 ? a[i + 1] : d; };
  if (opt('check')) {
    const dir = opt('check');
    const names = existsSync(path.join(dir, 'index.json')) ? JSON.parse(readFileSync(path.join(dir, 'index.json'), 'utf8')).sheets.map((s) => s.replace(/\.json$/, '')) : [];
    const problems = names.flatMap((n) => checkSheet(dir, n));
    if (!names.length) problems.push(`${dir} 沒有任何 sheet（index.json）—— 範圍是空的，不是通過`);
    if (opt('pixi') && names.length) { problems.push(...pixiParse(dir, names, opt('pixi'))); if (!problems.length) console.log(`PixiJS（${path.basename(opt('pixi'))}）Spritesheet.parse：${names.length} 組全部讀進`); }
    problems.forEach((p) => console.log('❌', p));
    console.log(problems.length ? `${problems.length} 項問題` : `✅ ${names.length} 組 sheet 通過`);
    process.exit(problems.length ? 1 : 0);
  }
  if (!opt('out')) { console.error('用法：node sheet.mjs --out <DIR> [--names A,B|all] [--length 100] [--scale 1|2] [--facing up|right]｜--check <DIR>'); process.exit(2); }
  const n = opt('names');
  const names = !n || n === 'all' ? Object.keys(SPECIES) : n.split(',').map((x) => x.trim()).filter(Boolean);
  const r = buildSheets({ out: opt('out'), names, length: Number(opt('length', 100)), scale: Number(opt('scale', 1)), facing: opt('facing', 'up') });
  if (r.skipped) { console.error(`⏭  ${r.skipped}`); process.exit(3); }
  console.log(`✅ ${r.built.length} 組 sheet → ${opt('out')}（index.json）`);
}
