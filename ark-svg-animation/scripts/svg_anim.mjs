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

export const VERSION = '0.1.0';
export const RIGS = { fusiform, shark, crab };
export const DEFAULT_FRAMES = { swim: 4, catch: 3 };

// ── 確定性工具 ────────────────────────────────────────────────────────────────
/** FNV-1a 32 位元（名字 → 種子） */
export function fnv1a(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
}

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

/** 數字輸出：小數 1 位、去掉多餘的 0 與 -0 —— 逐位元組穩定 */
export function num(n) {
  const r = Math.round(n * 10) / 10;
  return Object.is(r, -0) || r === 0 ? '0' : String(r);
}

function hslToHex(h, s, l) {
  s /= 100; l /= 100;
  const k = (n) => (n + h / 30) % 12, a = s * Math.min(l, 1 - l);
  const f = (n) => Math.round(255 * (l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))));
  return '#' + [f(0), f(8), f(4)].map((v) => v.toString(16).padStart(2, '0')).join('');
}

/** 兩個 #rrggbb 依比例混色（被捕閃白用） */
export function mix(hex, toHex, k) {
  const p = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const a = p(hex), b = p(toHex);
  return '#' + a.map((v, i) => Math.round(v + (b[i] - v) * k).toString(16).padStart(2, '0')).join('');
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
export function classify(name, registry = {}) {
  let base = String(name).toUpperCase();
  const variants = [];
  for (const pre of ['SINGLE_', 'LINE_']) if (base.startsWith(pre)) base = base.slice(pre.length);
  const tw = /^(TWISTER|TWIST)_(.+)$/.exec(base);
  if (tw) { variants.push('twister'); base = tw[2]; }
  const reg = registry[base];
  if (reg) return { base, archetype: reg.archetype, variants: [...variants, ...(reg.variants ?? [])], accessory: reg.accessory, params: reg.params ?? {}, fallback: !RIGS[reg.archetype] };
  if (/_CRAB$/.test(base)) {
    const acc = CRAB_ACCESSORY.find(([k]) => base.startsWith(k));
    return { base, archetype: 'crab', variants, accessory: acc?.[1], params: {}, fallback: false };
  }
  if (/(SHARK|WHALE)$/.test(base)) return { base, archetype: 'shark', variants, params: {}, fallback: false };
  return { base, archetype: 'fusiform', variants, params: {}, fallback: true };
}

/** 規格 → 完整參數（種子、配色、rig 預設＋個體差＋覆寫） */
export function resolve(spec, registry = {}) {
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
  const pal = { ...palette(seed, variants), ...(spec.palette ?? {}) };
  return {
    name: c.base, archetype: RIGS[archetype] ? archetype : 'fusiform', rig, p, pal, seed, variants,
    length: spec.length ?? 100, facing: spec.facing ?? 'up',
    frames: { ...DEFAULT_FRAMES, ...(spec.frames ?? {}) },
    fallback: !RIGS[archetype] || (spec.archetype ? false : c.fallback),
  };
}

// ── 圖元 → SVG ──────────────────────────────────────────────────────────────
/** 樣式：筆寬、虛線一律是正規化單位（× 身長），透明度 0～1 */
function paint(o, pal, k, L) {
  const col = (v) => (v && k ? mix(v, pal.white, k) : v);
  let s = '';
  if (o.fill !== undefined) s += ` fill="${o.fill === 'none' ? 'none' : col(o.fill)}"`;
  if (o.stroke) s += ` stroke="${col(o.stroke)}" stroke-width="${num(Math.max(0.6, (o.sw ?? 0.015) * L))}"`;
  if (o.cap) s += ` stroke-linecap="${o.cap}"`;
  if (o.op !== undefined && o.op !== 1) s += ` opacity="${num(o.op)}"`;
  if (o.dash) s += ` stroke-dasharray="${o.dash.map((d) => num(d * L)).join(' ')}"`;
  return s;
}

function shape(o, L, pal, k) {
  const X = (v) => num(v * L), P = (pts) => pts.map(([x, y]) => `${X(x)},${X(y)}`).join(' ');
  switch (o.k) {
    case 'ellipse': return `<ellipse cx="${X(o.cx)}" cy="${X(o.cy)}" rx="${X(o.rx)}" ry="${X(o.ry)}"${o.rot ? ` transform="rotate(${num(o.rot)} ${X(o.cx)} ${X(o.cy)})"` : ''}${paint(o, pal, k, L)}/>`;
    case 'circle': return `<circle cx="${X(o.cx)}" cy="${X(o.cy)}" r="${X(o.r)}"${paint(o, pal, k, L)}/>`;
    case 'polygon': return `<polygon points="${P(o.pts)}"${paint(o, pal, k, L)}/>`;
    case 'polyline': return `<polyline points="${P(o.pts)}" fill="none"${paint({ ...o, fill: undefined }, pal, k, L)}/>`;
    default: throw new Error(`未知圖元 ${o.k}`);
  }
}

function variantParts(r, ext) {
  const out = { before: [], after: [] };
  const R = Math.min(ext.halfW, (ext.y1 - ext.y0) / 2) * 0.98, cy = (ext.y0 + ext.y1) / 2;
  if (r.variants.includes('twister')) out.before.push({ k: 'circle', cx: 0, cy, r: R, fill: 'none', stroke: '#7fe0ff', sw: 0.025, op: 0.6, dash: [R * 0.6, R * 0.3] });
  if (r.variants.includes('boss')) out.before.push({ k: 'circle', cx: 0, cy, r: R, fill: 'none', stroke: r.pal.light, sw: 0.05, op: 0.35 });
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

function frame(r, t, ext, ck) {
  const L = r.length, pad = Math.max(2, L * 0.04);
  const vw = ext.halfW * 2 * L + pad * 2, vh = (ext.y1 - ext.y0) * L + pad * 2;
  const parts = r.rig.parts(t, r.p, r.pal);
  const v = variantParts(r, ext);
  const k = ck ? ck.white : 0;
  const body = [...v.before, ...parts, ...v.after].map((o) => shape(o, L, r.pal, k)).join('');
  const ox = ext.halfW * L + pad, oy = -ext.y0 * L + pad, cy = ((ext.y0 + ext.y1) / 2) * L;
  let tf = `translate(${num(ox)} ${num(oy)})`;
  if (ck) tf += ` translate(0 ${num(cy)}) rotate(${num(ck.rot)}) scale(${num(ck.scale * 100) / 100}) translate(0 ${num(-cy)})`;
  let W = vw, H = vh, outer = '';
  if (r.facing === 'right') { W = vh; H = vw; outer = ` transform="translate(${num(vh)} 0) rotate(90)"`; }
  const op = ck && ck.op !== 1 ? ` opacity="${num(ck.op)}"` : '';
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${num(W)} ${num(H)}" width="${num(W)}" height="${num(H)}"><g${outer}><g transform="${tf}"${op}>${body}</g></g></svg>`;
}

/**
 * 產生一隻生物的逐格動畫。
 * @param {object} spec  { name, length?, archetype?, facing?, palette?, frames?, variants?, seed?, params?, accessory? }
 * @param {object} registry 物種登錄表（name → { archetype, variants?, accessory?, params? }）
 * @returns {{ frames: { swim: string[], catch: string[] }, meta: object }}
 */
export function creature(spec, registry = {}) {
  const r = resolve(spec, registry);
  const ext = r.rig.extent(r.p);
  const swim = Array.from({ length: r.frames.swim }, (_, i) => frame(r, i / r.frames.swim, ext));
  const caught = Array.from({ length: r.frames.catch }, (_, i) => frame(r, (i / Math.max(1, r.frames.catch)) * 0.5, ext, catchKey(i, r.frames.catch)));
  const L = r.length, pad = Math.max(2, L * 0.04);
  const vw = ext.halfW * 2 * L + pad * 2, vh = (ext.y1 - ext.y0) * L + pad * 2;
  const [W, H] = r.facing === 'right' ? [vh, vw] : [vw, vh];
  const body = r.rig.body(r.p);                       // 身體框（正規化），不含擺動外擴
  const anchorY = ((body.cy - ext.y0) * L + pad) / vh;
  const meta = {
    version: VERSION, name: r.name, archetype: r.archetype, variants: r.variants, seed: r.seed, fallback: r.fallback,
    viewBox: [Number(num(W)), Number(num(H))],
    anchor: r.facing === 'right' ? [Number(num(1 - anchorY)), 0.5] : [0.5, Number(num(anchorY))],
    bodyBox: { w: Number(num(body.rx * 2 * L)), h: Number(num(body.ry * 2 * L)) },
    hitRadius: Number(num(Math.min(body.rx, body.ry) * L)),
  };
  return { frames: { swim, catch: caught }, meta };
}

/** 任意相位 t 的單格（swim 狀態）—— verify 用 t＝1 檢查循環接縫與週期性 */
export function renderPhase(spec, t, registry = {}) {
  const r = resolve(spec, registry);
  return frame(r, t, r.rig.extent(r.p));
}

// ── CLI ────────────────────────────────────────────────────────────────────
const isMain = typeof process !== 'undefined' && process.argv?.[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href;
if (isMain) {
  const [cmd, name, ...rest] = process.argv.slice(2);
  const opt = (k, d) => { const i = rest.indexOf(`--${k}`); return i >= 0 ? rest[i + 1] : d; };
  if (cmd !== 'frames' || !name) {
    console.error('用法：node svg_anim.mjs frames <NAME> [--length 100] [--state swim|catch] [--facing up|right] [--variant gold,twister] [--json]');
    process.exit(2);
  }
  const out = creature({ name, length: Number(opt('length', 100)), facing: opt('facing', 'up'), variants: (opt('variant', '') || '').split(',').filter(Boolean) });
  if (rest.includes('--json')) console.log(JSON.stringify(out, null, 2));
  else { for (const s of out.frames[opt('state', 'swim')]) console.log(s); console.error(JSON.stringify(out.meta)); }
}
