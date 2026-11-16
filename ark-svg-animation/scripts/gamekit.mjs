#!/usr/bin/env node
// gamekit.mjs —— 魚機／老虎機必要圖元素（0.5.0 起；規格 kiro-cli docs/specs/ark-svg-animation-spec.md §7）。
//
// 函式庫：
//   import { asset, KINDS } from './gamekit.mjs';
//   asset('label', { text: 'BIG WIN', size: 72, theme: 'royal-gold' })   // → { svg, meta }
//   asset('plate', { shape: 'arch', theme: 'deep-sea', profile: 'flat' }) // flat＝PixiJS Graphics.svg() 可直接解析
// 每個 kind：build(spec, theme) → { w, h, L?, parts, anchor?, alias, category }；座標 × L（符號以 256 為基準、L＝size/256）。
// 零相依、確定性：同參數＋同版號 → 逐位元組相同；不接受外部圖片、不輸出 <text>（字一律走 glyphs.mjs 轉 path）。
import { draw, num } from './draw.mjs';
import { measure } from './glyphs.mjs';
import { theme, metal, THEMES } from './themes.mjs';
import { VERSION } from './svg_anim.mjs';

export { THEMES };

/** 尺寸預算（bytes，單張）—— verify_svg 用 */
export const BUDGET = { frame: 4096, symbol: 6144, ui: 8192, text: 8192, bg: 16384 };

/** 文字顏色：'gold'／'silver'／'bronze' → 金屬漸層；其他照用 */
const textFill = (v, th) => (v === undefined ? th.text.fill : th.metal[v] ? metal(th, v) : v);

// ── 底板外形（256 基準；k＝相對中心縮放，畫內框用） ────────────────────────────
const C = 128;
const sc = (k) => ([x, y]) => [C + (x - C) * k, C + (y - C) * k];
const PLATES = {
  arch: (k) => { const [a, b, c, d, e, f, g, h, i] = [[28, 240], [28, 104], [28, 48], [72, 16], [128, 16], [184, 16], [228, 48], [228, 104], [228, 240]].map(sc(k)); return { k: 'path', d: [['M', ...a], ['L', ...b], ['C', ...c, ...d, ...e], ['C', ...f, ...g, ...h], ['L', ...i], ['Z']] }; },
  circle: (k) => ({ k: 'circle', cx: C, cy: C, r: 110 * k }),
  shield: (k) => { const p = sc(k); const q = [[128, 14], [230, 42], [222, 146], [212, 198], [172, 230], [128, 246], [84, 230], [44, 198], [34, 146], [26, 42]].map(p); return { k: 'path', d: [['M', ...q[0]], ['L', ...q[1]], ['L', ...q[2]], ['C', ...q[3], ...q[4], ...q[5]], ['C', ...q[6], ...q[7], ...q[8]], ['L', ...q[9]], ['Z']] }; },
  diamond: (k) => ({ k: 'polygon', pts: [[128, 10], [246, 128], [128, 246], [10, 128]].map(sc(k)) }),
};

export const KINDS = {
  /** 描邊字（橫幅、倍率、按鈕字）：size＝字高 px */
  label: {
    category: 'text',
    build(s, th) {
      const text = String(s.text ?? '');
      if (!text.trim()) throw new Error('label：text 必填');
      const size = s.size ?? 64, u = size / 6;
      const outline = s.outline ?? u * 0.45, padX = u * 0.5 + outline + 2, padY = padX;
      const w = Math.ceil(measure(text, { spacing: s.spacing ?? 2 }) * u + padX * 2), h = Math.ceil(size + padY * 2);
      return {
        w, h, alias: s.alias ?? `label_${text.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'x'}`,
        parts: [{ k: 'text', str: text, x: w / 2, y: h / 2, size, align: 'center', spacing: s.spacing, fill: textFill(s.fill, th), ink: s.ink ?? th.text.stroke, outline }],
      };
    },
  },
  /** 符號底板：arch／circle／shield／diamond；color＝'primary'｜'accent'｜{ main, dark, light } */
  plate: {
    category: 'symbol',
    build(s, th) {
      const shape = s.shape ?? 'arch';
      if (!PLATES[shape]) throw new Error(`plate：未知外形「${shape}」→ 可用：${Object.keys(PLATES).join('、')}`);
      const col = typeof s.color === 'object' ? s.color : th[s.color ?? 'primary'];
      const size = s.size ?? 256;
      return {
        w: size, h: size, L: size / 256, alias: s.alias ?? `plate_${shape}`,
        parts: [
          { ...PLATES[shape](1), fill: { lg: [[0, col.light], [0.55, col.main], [1, col.dark]], x1: 0, y1: 0, x2: 0, y2: 1 }, stroke: th.ink, sw: th.inkW },
          { ...PLATES[shape](0.9), fill: 'none', stroke: metal(th, s.rim ?? 'gold'), sw: 5 },
          { k: 'ellipse', cx: 104, cy: 72, rx: 62, ry: 24, rot: -12, fill: '#ffffff', op: 0.28 },
        ],
      };
    },
  },
};

/**
 * 產生一張 gamekit 素材。
 * @param {string} kind  KINDS 的鍵
 * @param {object} spec  各 kind 的參數＋ theme（名稱或覆寫物件）＋ profile（'texture'｜'flat'）＋ alias
 * @returns {{ svg: string, meta: { version, kind, alias, category, w, h, anchor, theme, profile } }}
 */
export function asset(kind, spec = {}) {
  const def = KINDS[kind];
  if (!def) throw new Error(`未知 kind「${kind}」→ 可用：${Object.keys(KINDS).join('、')}`);
  for (const k of ['image', 'href', 'src']) if (k in spec) throw new Error(`asset：不接受外部圖片參數「${k}」（只產原創向量圖）`);
  const th = theme(spec.theme);
  const profile = spec.profile === 'flat' ? 'flat' : 'texture';
  const b = def.build(spec, th);
  const ctx = { L: b.L ?? 1, pal: { white: '#ffffff', eye: th.ink, ...th.primary }, k: 0, id: 'k', gid: 'k', defs: new Map(), profile };
  const { body, defs } = draw(b.parts, ctx);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${num(b.w)} ${num(b.h)}" width="${num(b.w)}" height="${num(b.h)}">${profile === 'flat' ? '' : defs}${body}</svg>`;
  return { svg, meta: { version: VERSION, kind, alias: b.alias, category: def.category, w: b.w, h: b.h, anchor: b.anchor ?? [0.5, 0.5], theme: th.name, profile } };
}

/** verify 與預覽用的樣本：每個 kind 至少涵蓋所有選項 */
export const SAMPLES = {
  label: [{ text: 'BIG WIN', size: 72 }, { text: 'FREE GAMES', size: 48, fill: 'gold' }, { text: 'X10', size: 64, fill: 'silver' },
    { text: 'ABCDEFGHIJKLM', size: 40 }, { text: 'NOPQRSTUVWXYZ', size: 40 }, { text: '0123456789', size: 40 }, { text: '+-×.,!?:/%$¥#', size: 40 }],
  plate: Object.keys(PLATES).flatMap((shape) => [{ shape }, { shape, color: 'accent', rim: 'silver', size: 200 }]),
};

// ── CLI（M7 補 --config／generator 契約；M5 先提供 sample 與 preview） ─────────────
const isMain = typeof process !== 'undefined' && process.argv?.[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href;
if (isMain) {
  const [cmd, ...rest] = process.argv.slice(2);
  const opt = (k, d) => { const i = rest.indexOf(`--${k}`); return i >= 0 ? rest[i + 1] : d; };
  const fs = await import('node:fs'), path = await import('node:path');
  if (cmd === 'list') {
    for (const [k, d] of Object.entries(KINDS)) console.log(`${k.padEnd(12)} ${d.category.padEnd(7)} 樣本 ${SAMPLES[k]?.length ?? 0}`);
    console.log(`themes：${Object.keys(THEMES).join('、')}`);
  } else if (cmd === 'preview' && opt('out')) {
    const profile = opt('profile', 'texture');
    const rows = Object.keys(THEMES).map((t) => {
      const cells = Object.entries(SAMPLES).flatMap(([k, list]) => list.map((s) => asset(k, { ...s, theme: t, profile }))).map(({ svg, meta }) => `<figure>${svg}<figcaption>${meta.alias}<br><small>${meta.w}×${meta.h} · ${(svg.length / 1024).toFixed(1)} KB</small></figcaption></figure>`).join('');
      return `<h2>${t}</h2><main>${cells}</main>`;
    }).join('');
    fs.mkdirSync(path.dirname(path.resolve(opt('out'))), { recursive: true });
    fs.writeFileSync(opt('out'), `<!doctype html><html lang="zh-TW"><meta charset="utf-8"><title>gamekit ${VERSION} 預覽（${profile}）</title><style>body{margin:12px;background:#1a1a24;color:#eee;font:13px system-ui,sans-serif}main{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end}figure{margin:0;padding:6px;background:#26263a;border-radius:8px;text-align:center}figure svg{max-width:360px;height:auto}small{opacity:.7}</style><h1>gamekit ${VERSION}（${profile}）</h1>${rows}</html>`);
    console.log(`✅ 預覽 → ${opt('out')}`);
  } else {
    console.error('用法：\n  node gamekit.mjs list\n  node gamekit.mjs preview --out <FILE.html> [--profile texture|flat]');
    process.exit(2);
  }
}
