#!/usr/bin/env node
// ark-svg-animation —— 原創向量生物逐格動畫產生器（規格 kiro-cli docs/specs/ark-svg-animation-spec.md）。
//
// 零相依、瀏覽器與 node 共用。同一組參數＋同一版號 → 逐位元組相同的 SVG（不用 Math.random、時間、字型）。
// 座標慣例（rig 內）：頭在 y=0、尾在 y=1、x 以 0 為中線，身長＝1；facing 'up'（預設）＝頭朝 −y 俯視（對齊海王素材）。
//
// 函式庫：
//   import { creature } from './svg_anim.mjs';
//   const { frames, meta } = creature({ name: 'SHARK', length: 160 });   // frames.swim／frames.catch：SVG 字串陣列
// CLI：
//   node svg_anim.mjs frames SHARK --length 160 [--state swim|catch] [--facing up|right] [--variant gold,twister] [--json]
import * as fusiform from './rigs/fusiform.mjs';
import * as shark from './rigs/shark.mjs';
import * as crab from './rigs/crab.mjs';
import * as ray from './rigs/ray.mjs';
import * as flat from './rigs/flat.mjs';
import * as puffer from './rigs/puffer.mjs';
import * as lobster from './rigs/lobster.mjs';
import * as cephalopod from './rigs/cephalopod.mjs';
import * as jelly from './rigs/jelly.mjs';
import * as turtle from './rigs/turtle.mjs';
import * as snail from './rigs/snail.mjs';
import * as serpent from './rigs/serpent.mjs';
import * as token from './rigs/token.mjs';
import SPECIES from './species.mjs';
import { fnv1a, num, mix, draw, mul, translate, rotate, scale, I } from './draw.mjs';
export { fnv1a, num, mix };

export const VERSION = '0.10.0';
export const RIGS = { fusiform, shark, crab, ray, flat, puffer, lobster, cephalopod, jelly, turtle, snail, serpent, token };
export { SPECIES };
export const DEFAULT_FRAMES = { swim: 4, catch: 3 };

// ── 確定性工具 ────────────────────────────────────────────────────────────────
/** mulberry32：只在 resolve 抽「個體差」；動畫一律用相位函式，不用亂數 */
export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hslToHex(h, s, l) {
  s /= 100; l /= 100;
  const k = (n) => (n + h / 30) % 12, a = s * Math.min(l, 1 - l);
  const f = (n) => Math.round(255 * (l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))));
  return '#' + [f(0), f(8), f(4)].map((v) => v.toString(16).padStart(2, '0')).join('');
}

/** 配色：色相由種子決定；gold 變體改金色系 */
export function palette(seed, variants = []) {
  const h = variants.includes('gold') ? 45 : seed % 360;
  const s = variants.includes('gold') ? 90 : 70;
  return {
    main: hslToHex(h, s, 52), dark: hslToHex(h, s + 5, 32), light: hslToHex((h + 40) % 360, 85, 72),
    eye: '#0b1626', white: '#ffffff', accent: hslToHex((h + 180) % 360, 70, 55),
  };
}

// ── 名稱解析（registry 在 T5 補；這裡是關鍵字規則） ─────────────────────────────
const CRAB_ACCESSORY = [['SERIAL_DRILL', 'drill'], ['DRILL', 'drill'], ['BOMB', 'bomb'], ['LASER', 'electrode'], ['WHEEL', 'wheel']];

/** 名字 → { base, archetype, variants, accessory, fallback }；registry（物種登錄表）優先 */
export function classify(name, registry = SPECIES) {
  let base = String(name).toUpperCase();
  const variants = [];
  for (const pre of ['SINGLE_', 'LINE_']) if (base.startsWith(pre)) base = base.slice(pre.length);
  const tw = /^(TWISTER|TWIST)_(.+)$/.exec(base);
  if (tw) { variants.push('twister'); base = tw[2]; }
  const reg = registry[base];
  if (reg) return { base, archetype: reg.archetype, variants: [...variants, ...(reg.variants ?? [])], accessory: reg.accessory, params: reg.params ?? {}, palette: reg.palette, size: reg.size, fallback: !RIGS[reg.archetype] };
  if (/_CRAB$/.test(base)) {
    const acc = CRAB_ACCESSORY.find(([k]) => base.startsWith(k));
    return { base, archetype: 'crab', variants, accessory: acc?.[1], params: {}, fallback: false };
  }
  if (/(SHARK|WHALE)$/.test(base)) return { base, archetype: 'shark', variants, params: {}, fallback: false };
  return { base, archetype: 'fusiform', variants, params: {}, fallback: true };
}

/** 規格 → 完整參數（種子、配色、rig 預設＋個體差＋覆寫） */
export function resolve(spec, registry = SPECIES) {
  if (!spec || !spec.name) throw new Error('creature：name 必填');
  for (const k of ['image', 'href', 'src']) if (k in spec) throw new Error(`creature：不接受外部圖片參數「${k}」（只產原創向量圖）`);
  const c = classify(spec.name, registry);
  const archetype = spec.archetype ?? c.archetype;
  const rig = RIGS[archetype] ?? RIGS.fusiform;
  const seed = spec.seed ?? fnv1a(c.base);
  const rnd = mulberry32(seed);
  const p = { ...rig.defaults, ...(rig.individual ? rig.individual(rnd) : {}), ...c.params, ...(spec.params ?? {}) };
  if (spec.accessory ?? c.accessory) p.accessory = spec.accessory ?? c.accessory;
  const variants = [...new Set([...(c.variants ?? []), ...(spec.variants ?? [])])].sort();
  // 配色優先序：種子配色 < 登錄表 < 呼叫端；gold 變體蓋過登錄表（金色是變體的意思）
  const pal = { ...palette(seed, variants), ...(variants.includes('gold') ? {} : c.palette ?? {}), ...(spec.palette ?? {}) };
  return {
    name: c.base, archetype: RIGS[archetype] ? archetype : 'fusiform', rig, p, pal, seed, variants, size: c.size ?? 1,
    length: spec.length ?? 100, facing: spec.facing ?? 'up', profile: spec.profile === 'flat' ? 'flat' : 'texture',
    frames: { ...DEFAULT_FRAMES, ...(spec.frames ?? {}) },
    fallback: !RIGS[archetype] || (spec.archetype ? false : c.fallback),
  };
}

function variantParts(r, ext) {
  const out = { before: [], after: [] };
  const R = Math.min(ext.halfW, (ext.y1 - ext.y0) / 2) * 0.98, cy = (ext.y0 + ext.y1) / 2;
  if (r.variants.includes('glow')) out.before.push({ k: 'circle', cx: 0, cy, r: R, fill: 'glow' });
  if (r.variants.includes('twister')) out.before.push({ k: 'circle', cx: 0, cy, r: R, fill: 'none', stroke: '#7fe0ff', sw: 0.025, op: 0.6, dash: [R * 0.6, R * 0.3] });
  if (r.variants.includes('boss')) out.before.push({ k: 'circle', cx: 0, cy, r: R, fill: 'none', stroke: r.pal.light, sw: 0.022, op: 0.28 });
  return out;
}

/** 被捕曲線（3 格基準，格數不同時內插）：閃白比例、旋轉、縮放、透明度 */
const CATCH_KEYS = [
  { white: 0.6, rot: 0, scale: 1, op: 1 },
  { white: 0.25, rot: 12, scale: 1.05, op: 1 },
  { white: 0.1, rot: -6, scale: 0.8, op: 0.4 },
];
export function catchKey(i, n) {
  const u = n <= 1 ? 0 : (i / (n - 1)) * (CATCH_KEYS.length - 1);
  const a = CATCH_KEYS[Math.floor(u)], b = CATCH_KEYS[Math.min(CATCH_KEYS.length - 1, Math.floor(u) + 1)], f = u - Math.floor(u);
  const lerp = (x, y) => x + (y - x) * f;
  return { white: lerp(a.white, b.white), rot: lerp(a.rot, b.rot), scale: lerp(a.scale, b.scale), op: lerp(a.op, b.op) };
}

function frame(r, t, ext, ck, tag = 'x') {
  const L = r.length, pad = Math.max(2, L * 0.04);
  const vw = ext.halfW * 2 * L + pad * 2, vh = (ext.y1 - ext.y0) * L + pad * 2;
  const parts = r.rig.parts(t, r.p, r.pal);
  const v = variantParts(r, ext);
  // id 前綴＝物種種子＋外觀雜湊（變體、尺寸、朝向、配色、參數）＋狀態格號 —— 同種魚不同版本同頁也不撞（裁切依尺寸而定，撞了會切錯）
  const look = fnv1a(JSON.stringify([r.variants, r.length, r.facing, r.pal, r.p])).toString(36);
  const all = [...v.before, ...parts, ...v.after];
  const ox = ext.halfW * L + pad, oy = -ext.y0 * L + pad, cy = ((ext.y0 + ext.y1) / 2) * L;
  let W = vw, H = vh;
  if (r.facing === 'right') { W = vh; H = vw; }
  const head = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${num(W)} ${num(H)}" width="${num(W)}" height="${num(H)}">`;
  const ctx = { L, pal: r.pal, k: ck ? ck.white : 0, id: `a${r.seed.toString(36)}${look}${tag}`, defs: new Map(), profile: r.profile };
  if (r.profile === 'flat') {
    // flat：外層變換全部烘焙進座標（Pixi Graphics 不吃 transform）
    let m = r.facing === 'right' ? mul(translate(vh, 0), rotate(90)) : I;
    m = mul(m, translate(ox, oy));
    if (ck) m = mul(m, mul(translate(0, cy), mul(rotate(ck.rot), mul(scale(Math.round(ck.scale * 100) / 100), translate(0, -cy)))));
    const { body } = draw(all, { ...ctx, m, op: ck ? ck.op : 1 });
    return `${head}${body}</svg>`;
  }
  const { body, defs } = draw(all, ctx);
  let tf = `translate(${num(ox)} ${num(oy)})`;
  if (ck) tf += ` translate(0 ${num(cy)}) rotate(${num(ck.rot)}) scale(${num(ck.scale * 100) / 100}) translate(0 ${num(-cy)})`;
  const outer = r.facing === 'right' ? ` transform="translate(${num(vh)} 0) rotate(90)"` : '';
  const op = ck && ck.op !== 1 ? ` opacity="${num(ck.op)}"` : '';
  return `${head}${defs}<g${outer}><g transform="${tf}"${op}>${body}</g></g></svg>`;
}

/**
 * 產生一隻生物的逐格動畫。
 * @param {object} spec  { name, length?, archetype?, facing?, palette?, frames?, variants?, seed?, params?, accessory? }
 * @param {object} registry 物種登錄表（name → { archetype, variants?, accessory?, params? }）
 * @returns {{ frames: { swim: string[], catch: string[] }, meta: object }}
 */
export function creature(spec, registry = SPECIES) {
  const r = resolve(spec, registry);
  const ext = r.rig.extent(r.p);
  const swim = Array.from({ length: r.frames.swim }, (_, i) => frame(r, i / r.frames.swim, ext, undefined, `s${i}`));
  const caught = Array.from({ length: r.frames.catch }, (_, i) => frame(r, (i / Math.max(1, r.frames.catch)) * 0.5, ext, catchKey(i, r.frames.catch), `c${i}`));
  const L = r.length, pad = Math.max(2, L * 0.04);
  const vw = ext.halfW * 2 * L + pad * 2, vh = (ext.y1 - ext.y0) * L + pad * 2;
  const [W, H] = r.facing === 'right' ? [vh, vw] : [vw, vh];
  const body = r.rig.body(r.p);                       // 身體框（正規化），不含擺動外擴
  const anchorY = ((body.cy - ext.y0) * L + pad) / vh;
  const meta = {
    version: VERSION, profile: r.profile, name: r.name, archetype: r.archetype, variants: r.variants, seed: r.seed, fallback: r.fallback, size: r.size,
    viewBox: [Number(num(W)), Number(num(H))],
    anchor: r.facing === 'right' ? [Number(num(1 - anchorY)), 0.5] : [0.5, Number(num(anchorY))],
    bodyBox: { w: Number(num(body.rx * 2 * L)), h: Number(num(body.ry * 2 * L)) },
    hitRadius: Number(num(Math.min(body.rx, body.ry) * L)),
  };
  return { frames: { swim, catch: caught }, meta };
}

/** 任意相位 t 的單格（swim 狀態）—— verify 用 t＝1 檢查循環接縫與週期性 */
export function renderPhase(spec, t, registry = SPECIES) {
  const r = resolve(spec, registry);
  return frame(r, t, r.rig.extent(r.p), undefined, 'p');
}

// ── CLI（node 專用；fs 動態載入，函式庫在瀏覽器照常可用） ───────────────────────
const isMain = typeof process !== 'undefined' && process.argv?.[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href;
const USAGE = `用法：
  node svg_anim.mjs list                                              # 登錄的物種
  node svg_anim.mjs frames <NAME> [--length 100] [--state swim|catch] [--facing up|right] [--variant gold,twister,boss] [--json]
  node svg_anim.mjs gen --out <DIR> [--names A,B|all] [--length 100] [--facing up|right]   # 逐格 .svg＋manifest.json
  node svg_anim.mjs preview --out <FILE.html> [--names A,B|all] [--base 90]                # 單檔預覽（依 size 縮放、可暫停／看被捕）`;

function pick(names) {
  return !names || names === 'all' ? Object.keys(SPECIES) : names.split(',').map((x) => x.trim()).filter(Boolean);
}

function previewHtml(list, base) {
  const data = list.map((name) => {
    const size = classify(name).size ?? 1;
    const { frames, meta } = creature({ name, length: Math.round(base * size) });
    return { name, meta, frames };
  });
  const cells = data.map((d, i) => `<figure data-i="${i}"><div class="stage">${d.frames.swim[0]}</div><figcaption>${d.name}<br><small>${d.meta.archetype}${d.meta.variants.length ? ' · ' + d.meta.variants.join(',') : ''}${d.meta.fallback ? ' · ⚠️未登錄' : ''}</small></figcaption></figure>`).join('');
  return `<!doctype html><html lang="zh-TW"><meta charset="utf-8"><title>ark-svg-animation ${VERSION} 預覽</title>
<style>body{margin:12px;background:#0e3a5c;color:#e8f4ff;font:13px system-ui,sans-serif}header{display:flex;gap:12px;align-items:center;margin-bottom:10px}
main{display:flex;flex-wrap:wrap;gap:10px}figure{margin:0;padding:6px;background:#0b2f4a;border-radius:8px;text-align:center;min-width:120px;cursor:pointer}
.stage{display:flex;align-items:center;justify-content:center;min-height:150px}figcaption small{opacity:.7}button{font:inherit}</style>
<header><b>ark-svg-animation ${VERSION}</b><span>${data.length} 種 · 點一下看被捕</span><button id="pp">暫停</button></header><main>${cells}</main>
<script>const D=${JSON.stringify(data.map((d) => d.frames))};let f=0,run=true,catchI=new Map();
document.getElementById('pp').onclick=e=>{run=!run;e.target.textContent=run?'暫停':'播放'};
document.querySelectorAll('figure').forEach(el=>el.onclick=()=>catchI.set(+el.dataset.i,0));
setInterval(()=>{if(!run)return;f++;document.querySelectorAll('figure').forEach(el=>{const i=+el.dataset.i,c=catchI.get(i);
let s;if(c!==undefined){s=D[i].catch[Math.min(c,D[i].catch.length-1)];catchI.set(i,c+1);if(c>=D[i].catch.length+4)catchI.delete(i);}else s=D[i].swim[f%D[i].swim.length];
el.firstElementChild.innerHTML=s;});},125);</script></html>`;
}

if (isMain) {
  const [cmd, ...rest] = process.argv.slice(2);
  const opt = (k, d) => { const i = rest.indexOf(`--${k}`); return i >= 0 ? rest[i + 1] : d; };
  const fs = await import('node:fs'), path = await import('node:path');
  if (cmd === 'list') {
    for (const [n, r] of Object.entries(SPECIES)) console.log(`${n.padEnd(20)} ${r.archetype.padEnd(11)} size ${r.size ?? 1}${r.variants ? '  ' + r.variants.join(',') : ''}`);
  } else if (cmd === 'frames' && rest[0] && !rest[0].startsWith('--')) {
    const out = creature({ name: rest[0], length: Number(opt('length', 100)), facing: opt('facing', 'up'), variants: (opt('variant', '') || '').split(',').filter(Boolean) });
    if (rest.includes('--json')) console.log(JSON.stringify(out, null, 2));
    else { for (const x of out.frames[opt('state', 'swim')]) console.log(x); console.error(JSON.stringify(out.meta)); }
  } else if (cmd === 'gen' && opt('out')) {
    const dir = opt('out'), manifest = { version: VERSION, length: Number(opt('length', 100)), species: {} };
    for (const name of pick(opt('names'))) {
      const { frames, meta } = creature({ name, length: manifest.length, facing: opt('facing', 'up') });
      const sub = path.join(dir, meta.name); fs.mkdirSync(sub, { recursive: true });
      const files = {};
      for (const [state, list] of Object.entries(frames)) files[state] = list.map((svg, i) => { const f = `${state}_${i}.svg`; fs.writeFileSync(path.join(sub, f), svg); return `${meta.name}/${f}`; });
      manifest.species[meta.name] = { meta, frames: files };
    }
    fs.writeFileSync(path.join(dir, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
    console.log(`✅ ${Object.keys(manifest.species).length} 種 → ${dir}（manifest.json）`);
  } else if (cmd === 'preview' && opt('out')) {
    const list = pick(opt('names'));
    fs.writeFileSync(opt('out'), previewHtml(list, Number(opt('base', 90))));
    console.log(`✅ 預覽 ${list.length} 種 → ${opt('out')}`);
  } else {
    console.error(USAGE);
    process.exit(2);
  }
}
