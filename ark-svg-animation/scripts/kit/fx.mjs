// kit/fx.mjs —— 魚機／老虎機共用演出物（0.6.0；計畫 T6）：jp_plate、win_banner（動畫）、fg_banner、coin（動畫）。
// 動畫 kind：build(spec, theme, t) 以相位 t＝i/n 產生，t＝1 必須回到 t＝0（verify 的 checkSeam 驗等速＋週期）。
import { metal } from '../themes.mjs';
import { fnv1a } from '../draw.mjs';
import { mulberry32 } from '../svg_anim.mjs';
import { rr, starPts, tri, shade, glowFill, sparkle, boldText, WHITE } from './util.mjs';

const TIERS = ['Grand', 'Major', 'Minor', 'Mini'];

const jp_plate = {
  category: 'ui',
  build(s, th) {
    const tier = s.tier ?? 'Grand';
    if (!TIERS.includes(tier)) throw new Error(`jp_plate：tier 只能是 ${TIERS.join('／')}`);
    const w = s.w ?? 328, h = s.h ?? 108, col = shade(th.jp[tier]), label = tier.toUpperCase();
    const parts = [
      { k: 'path', d: rr(3, 3, w - 6, h - 6, h * 0.28), fill: { lg: [[0, col.light], [0.5, col.main], [1, col.dark]], x1: 0, y1: 0, x2: 0, y2: 1 }, stroke: th.ink, sw: 6 },
      { k: 'path', d: rr(10, 10, w - 20, h - 20, h * 0.22), fill: 'none', stroke: metal(th, 'gold'), sw: 4 },
      { k: 'ellipse', cx: w / 2, cy: h * 0.22, rx: w * 0.38, ry: h * 0.09, fill: WHITE, op: 0.25 },
    ];
    if (s.value === '') {
      // 空金額槽（0.8.0）：上方級別帶＋下方深色槽，數字由遊戲執行期疊上去（aidev 的做法）
      parts.length = 0;
      parts.push(
        { k: 'path', d: rr(3, 3, w - 6, h - 6, h * 0.24), fill: th.bg[1], stroke: metal(th, 'gold'), sw: 6 },
        { k: 'path', d: rr(12, 10, w - 24, h * 0.34, h * 0.14), fill: { lg: [[0, col.light], [0.5, col.main], [1, col.dark]], x1: 0, y1: 0, x2: 0, y2: 1 }, stroke: th.ink, sw: 3 },
        boldText(label, { x: w / 2, y: 10 + h * 0.17, maxSize: h * 0.22, maxW: w * 0.7, fill: WHITE, ink: th.ink }),
        { k: 'path', d: rr(16, h * 0.5, w - 32, h * 0.38, h * 0.1), fill: '#000000', op: 0.35 },
      );
    } else if (s.value !== undefined) {
      const v = String(s.value);
      parts.push(boldText(label, { x: w / 2, y: h * 0.27, maxSize: h * 0.16, maxW: w * 0.6, fill: WHITE, ink: th.ink }),
        boldText(v, { x: w / 2, y: h * 0.64, maxSize: h * 0.32, maxW: w * 0.84, fill: metal(th, 'gold'), ink: th.ink }));
    } else {
      parts.push(boldText(label, { x: w / 2, y: h / 2 + 1, maxSize: h * 0.44, maxW: w * 0.84, fill: metal(th, 'gold'), ink: th.ink }));
    }
    return { w, h, alias: s.alias ?? `jp_${tier}`, parts };
  },
};

/** 橫幅緞帶（中段＋兩端折角） */
function ribbon(w, h, th, col, { y0f = 0.3, y1f = 0.72 } = {}) {
  const y0 = h * y0f, y1 = h * y1f, x0 = w * 0.1, x1 = w * 0.9, f = h * 0.12;
  return [
    { k: 'polygon', pts: [[x0 - w * 0.08, y0 + f], [x0 + w * 0.04, y0 + f], [x0 + w * 0.04, y1 + f], [x0 - w * 0.08, y1 + f], [x0 - w * 0.03, (y0 + y1) / 2 + f]], fill: col.dark, stroke: th.ink, sw: 4, join: 'round' },
    { k: 'polygon', pts: [[x1 + w * 0.08, y0 + f], [x1 - w * 0.04, y0 + f], [x1 - w * 0.04, y1 + f], [x1 + w * 0.08, y1 + f], [x1 + w * 0.03, (y0 + y1) / 2 + f]], fill: col.dark, stroke: th.ink, sw: 4, join: 'round' },
    { k: 'path', d: rr(x0, y0, x1 - x0, y1 - y0, h * 0.06), fill: { lg: [[0, col.light], [0.5, col.main], [1, col.dark]], x1: 0, y1: 0, x2: 0, y2: 1 }, stroke: th.ink, sw: 5 },
    { k: 'path', d: rr(x0 + 6, y0 + 6, x1 - x0 - 12, y1 - y0 - 12, h * 0.04), fill: 'none', stroke: metal(th, 'gold'), sw: 3 },
  ];
}

const WIN = { big: { text: 'BIG WIN', col: (th) => th.accent }, mega: { text: 'MEGA WIN', col: (th) => th.primary }, super: { text: 'SUPER WIN', col: (th) => shade(th.jp.Grand) } };
const RAYS = 12;
const win_banner = {
  category: 'fx', anim: { frames: 6 },
  build(s, th, t = 0) {
    const tier = s.tier ?? 'big', cfg = WIN[tier];
    if (!cfg) throw new Error(`win_banner：tier 只能是 ${Object.keys(WIN).join('／')}`);
    const w = s.w ?? 640, h = s.h ?? 240, col = cfg.col(th), text = s.text ?? cfg.text, cx = w / 2, cy = h / 2;
    // 放射光：12 道，一循環轉 360/12 度 → t＝1 與 t＝0 是同一組光（換位對稱）。
    // 🔴 不可先壓扁再轉（舊版 y×0.5）：壓扁後轉 30° 不再對稱，每循環跳一下 —— flat（座標烘焙）守門抓到，texture 的 transform 看不出來
    const R = w * 0.48, rays = Array.from({ length: RAYS }, (_, i) => {
      const a = ((i * 360) / RAYS) * (Math.PI / 180), b = a + 0.16;
      return { k: 'polygon', pts: [[cx, cy], [cx + R * Math.cos(a), cy + R * Math.sin(a)], [cx + R * Math.cos(b), cy + R * Math.sin(b)]], fill: col.light, op: 0.3 };
    });
    const tw = (p) => 0.55 + 0.45 * Math.cos(2 * Math.PI * (t + p));   // 閃爍：以 1 為週期
    return {
      w, h, alias: s.alias ?? `win_${tier}`,
      parts: [
        { k: 'ellipse', cx, cy, rx: w * 0.46, ry: h * 0.46, fill: glowFill(col.light, 0.5) },
        { k: 'g', rot: (t * 360) / RAYS, ox: cx, oy: cy, children: rays },
        ...ribbon(w, h, th, col),
        boldText(text, { x: cx, y: h * 0.51, maxSize: h * 0.32, maxW: w * 0.76, fill: metal(th, 'gold'), ink: th.ink }),
        sparkle(w * 0.16, h * 0.2, h * 0.08, WHITE, tw(0)), sparkle(w * 0.84, h * 0.24, h * 0.07, WHITE, tw(0.33)),
        sparkle(w * 0.74, h * 0.86, h * 0.06, WHITE, tw(0.66)), sparkle(w * 0.27, h * 0.84, h * 0.05, WHITE, tw(0.5)),
      ],
    };
  },
};

// FG 橫幅（0.9.0 加份量：aidev 回饋「太細、進場沒份量」）—— 預設 760×280、緞帶佔 50% 高、上方徽冠（寶石＋雙翼）、下方次數槽
const fg_banner = {
  category: 'fx',
  build(s, th) {
    const w = s.w ?? 760, h = s.h ?? 280, text = s.text ?? 'FREE GAMES', cx = w / 2;
    const y0 = h * 0.3, y1 = h * 0.8, g = metal(th, 'gold');
    const parts = [
      { k: 'ellipse', cx, cy: h * 0.55, rx: w * 0.48, ry: h * 0.46, fill: glowFill(th.primary.light, 0.5) },
      // 徽冠：雙翼＋中央寶石（壓在緞帶上緣）
      ...[-1, 1].map((sg) => ({ k: 'polygon', pts: [[cx + sg * 30, y0 + 6], [cx + sg * 150, y0 - h * 0.16], [cx + sg * 120, y0 - h * 0.04], [cx + sg * 190, y0 - h * 0.08], [cx + sg * 120, y0 + 10]], fill: g, stroke: th.ink, sw: 4, join: 'round' })),
      ...ribbon(w, h, th, th.primary, { y0f: 0.3, y1f: 0.8 }),
      { k: 'polygon', pts: [[cx, y0 - h * 0.2], [cx + h * 0.13, y0], [cx, y0 + h * 0.08], [cx - h * 0.13, y0]], fill: { lg: [[0, th.accent.light], [0.5, th.accent.main], [1, th.accent.dark]], x1: 0, y1: 0, x2: 0, y2: 1 }, stroke: th.ink, sw: 4 },
      sparkle(cx - h * 0.04, y0 - h * 0.1, h * 0.04, WHITE, 0.9),
    ];
    // text：''＝空橫幅（0.8.0；字由遊戲執行期疊上，例：多語系）
    const tx = boldText(text, { x: cx, y: (y0 + y1) / 2 + 2, maxSize: h * 0.3, maxW: w * 0.7, fill: g, ink: th.ink });
    if (tx) parts.push(tx);
    if (s.sub !== undefined) {
      // sub：次數槽（例 '×10'；''＝空槽，次數由遊戲疊）
      const pw = w * 0.26, ph = h * 0.16, py = y1 - ph * 0.35;
      parts.push({ k: 'path', d: rr(cx - pw / 2, py, pw, ph, ph / 2), fill: th.ink, stroke: g, sw: 4 });
      const st = boldText(s.sub, { x: cx, y: py + ph / 2, maxSize: ph * 0.62, maxW: pw * 0.8, fill: th.accent.light, ink: th.ink });
      if (st) parts.push(st);
    }
    parts.push(sparkle(w * 0.08, h * 0.3, h * 0.07, WHITE, 0.9), sparkle(w * 0.92, h * 0.34, h * 0.06, WHITE, 0.85), sparkle(w * 0.85, h * 0.9, h * 0.05, WHITE, 0.7));
    return { w, h, alias: s.alias ?? 'fg_banner', parts };
  },
};

// 金幣翻轉：寬度＝|cos(πt)|，一循環轉半圈（正反面同圖）→ t＝1 回到 t＝0
const coin = {
  category: 'fx', anim: { frames: 6 },
  build(s, th, t = 0) {
    const size = s.size ?? 64, k = Math.max(0.08, Math.abs(Math.cos(Math.PI * t)));
    const g = th.metal.gold, R = 108, ex = 10 * (1 - k);    // ex：翻到側面時露出的金幣厚度
    const sx = (x) => 128 + (x - 128) * k;
    return {
      w: size, h: size, L: size / 256, alias: s.alias ?? 'fx_coin',
      parts: [
        { k: 'ellipse', cx: 128 + ex, cy: 128, rx: R * k + 1, ry: R, fill: g[2][1], stroke: th.ink, sw: 6 },
        { k: 'ellipse', cx: 128, cy: 128, rx: R * k, ry: R, fill: { rg: g, cx: 0.4, cy: 0.35, r: 0.7 }, stroke: th.ink, sw: 6 },
        { k: 'ellipse', cx: 128, cy: 128, rx: 84 * k, ry: 84, fill: 'none', stroke: g[2][1], sw: 6 },
        { k: 'polygon', pts: starPts(128, 130, 52, 0.45).map(([x, y]) => [sx(x), y]), fill: g[1][1], stroke: g[2][1], sw: 3 },
        { k: 'ellipse', cx: sx(96), cy: 80, rx: 30 * k, ry: 12, fill: WHITE, op: 0.4 },
      ],
    };
  },
};


// ── FG／Bonus 進場（0.10.0）：16 道放射光一循環轉 22.5°＋緞帶主字＋次數圓章（count：'' 空槽）＋單位字 ──────────
const INTRO = { free: { text: 'FREE GAMES', col: (th) => th.primary }, bonus: { text: 'BONUS', col: (th) => th.accent } };
const fg_intro = {
  category: 'fx', anim: { frames: 6 },
  build(s, th, t = 0) {
    const mode = s.mode ?? 'free', cfg = INTRO[mode];
    if (!cfg) throw new Error(`fg_intro：mode 只能是 ${Object.keys(INTRO).join('／')}`);
    const w = s.w ?? 720, h = s.h ?? 520, cx = w / 2, cy = h * 0.42, col = cfg.col(th), g = metal(th, 'gold'), N = 16, R = w * 0.5;
    const rays = Array.from({ length: N }, (_, i) => {
      const a = (i * 2 * Math.PI) / N, b = a + 0.12;
      return { k: 'polygon', pts: [[cx, cy], [cx + R * Math.cos(a), cy + R * Math.sin(a)], [cx + R * Math.cos(b), cy + R * Math.sin(b)]], fill: col.light, op: 0.28 };
    });
    const dy = h * 0.74, dr = h * 0.17;
    return {
      w, h, alias: s.alias ?? `fg_intro_${mode}`,
      parts: [
        { k: 'circle', cx, cy, r: R * 0.9, fill: glowFill(col.light, 0.5) },
        { k: 'g', rot: (t * 360) / N, ox: cx, oy: cy, children: rays },
        ...ribbon(w, h * 0.84, th, col, { y0f: 0.3, y1f: 0.68 }),
        boldText(s.text ?? cfg.text, { x: cx, y: h * 0.84 * 0.49, maxSize: h * 0.17, maxW: w * 0.72, fill: g, ink: th.ink }),
        { k: 'circle', cx, cy: dy, r: dr + 10, fill: g, stroke: th.ink, sw: 6 },
        { k: 'circle', cx, cy: dy, r: dr, fill: tri(shade(th.jp.Grand)), stroke: th.ink, sw: 4 },
        { k: 'ellipse', cx: cx - dr * 0.25, cy: dy - dr * 0.5, rx: dr * 0.55, ry: dr * 0.2, fill: WHITE, op: 0.3 },
        boldText(s.count ?? '', { x: cx, y: dy - dr * 0.1, maxSize: dr * 0.8, maxW: dr * 1.5, fill: WHITE, ink: th.ink }),
        boldText(s.unit ?? 'SPINS', { x: cx, y: dy + dr * 0.62, maxSize: dr * 0.3, maxW: dr * 1.3, fill: th.accent.light, ink: th.ink }),
        sparkle(w * 0.14, h * 0.16, h * 0.05, WHITE, 0.55 + 0.45 * Math.cos(2 * Math.PI * t)),
        sparkle(w * 0.86, h * 0.2, h * 0.045, WHITE, 0.55 + 0.45 * Math.cos(2 * Math.PI * (t + 0.5))),
      ],
    };
  },
};

// ── 金幣噴發（一次性 8 格）：N 枚金幣從底部中央往上拋、受重力落下、各自翻轉，最後 30% 淡出 ──────────────
const coin_burst = {
  category: 'fx', anim: { frames: 8, loop: false },
  build(s, th, t = 0) {
    // 1.0.0（aidev 複驗建議）：改成從中央往四周放射（原本像往下灑、擠在中間且被底邊切掉）；
    // 位移上限＋重力＋幣徑 ≤ 畫框半寬 → 整段動畫都在框內（測試鎖住）
    const size = s.size ?? 360, n = s.count ?? 14, rnd = mulberry32(fnv1a(`coin_burst:${n}:${s.seed ?? 0}`));
    if (!(n >= 1 && n <= 40)) throw new Error('coin_burst：count 要在 1～40');
    const g = th.metal.gold, op = t < 0.7 ? 1 : 1 - (t - 0.7) / 0.3 * 0.9, parts = [], C = 124, e = 1 - (1 - t) * (1 - t);
    for (let i = 0; i < n; i++) {
      const ang = (2 * Math.PI * (i + 0.6 * rnd())) / n, D = 62 + 30 * rnd(), r = 9 + 5 * rnd(), spin = 1 + Math.floor(rnd() * 3), ph = rnd();
      const x = 128 + Math.cos(ang) * D * e, y = C + Math.sin(ang) * D * e + 18 * t * t;
      const k = Math.max(0.12, Math.abs(Math.cos(Math.PI * (spin * t + ph))));
      parts.push({ k: 'ellipse', cx: x, cy: y, rx: r * k, ry: r, fill: g[1][1], stroke: g[2][1], sw: 2.5, op },
        { k: 'ellipse', cx: x - r * 0.25 * k, cy: y - r * 0.3, rx: r * 0.35 * k, ry: r * 0.25, fill: WHITE, op: op * 0.7 });
    }
    parts.unshift({ k: 'circle', cx: 128, cy: C, r: 50 + 60 * t, fill: glowFill(th.accent.light, 0.6 * (1 - t)) });   // 光暈取 theme（金幣本身固定金色）
    return { w: size, h: size, L: size / 256, alias: s.alias ?? 'fx_coin_burst', parts };
  },
};

// ── 彩池跑馬燈底板（循環 4 格）：外框燈泡追逐（每 4 顆亮 1 顆，一循環前進 4 步）＋中央數字槽 ─────────────
const jp_marquee = {
  category: 'fx', anim: { frames: 4 },
  build(s, th, t = 0) {
    const tier = s.tier ?? 'Grand';
    if (!TIERS.includes(tier)) throw new Error(`jp_marquee：tier 只能是 ${TIERS.join('／')}`);
    const w = s.w ?? 600, h = s.h ?? 170, col = shade(th.jp[tier]), g = metal(th, 'gold'), step = Math.round(t * 4) % 4;
    const parts = [
      { k: 'path', d: rr(3, 3, w - 6, h - 6, 24), fill: tri(col), stroke: th.ink, sw: 6 },
      { k: 'path', d: rr(14, 14, w - 28, h - 28, 16), fill: 'none', stroke: g, sw: 3 },
    ];
    const bulbs = [], gapX = (w - 40) / 14, gapY = (h - 40) / 3;
    for (let i = 0; i <= 14; i++) bulbs.push([20 + i * gapX, 9]);
    for (let i = 1; i <= 3; i++) bulbs.push([w - 9, 20 + i * gapY - gapY / 2]);
    for (let i = 14; i >= 0; i--) bulbs.push([20 + i * gapX, h - 9]);
    for (let i = 3; i >= 1; i--) bulbs.push([9, 20 + i * gapY - gapY / 2]);
    bulbs.forEach(([x, y], i) => {
      const on = (i + step) % 4 === 0;
      parts.push({ k: 'circle', cx: x, cy: y, r: on ? 6.5 : 4.5, fill: on ? WHITE : th.accent.dark });   // 燈泡不描邊（flat 體積；各格結構一致，接縫只比半徑與顏色）
    });
    // 1.0.0（aidev 複驗建議：級別字太小）：改上下兩列 —— 上排級別字（labelSize 可調）、下排數字槽
    parts.push(boldText(s.label ?? `${tier.toUpperCase()}`, { x: w / 2, y: h * 0.3, maxSize: s.labelSize ?? h * 0.22, maxW: w * 0.62, fill: WHITE, ink: th.ink }),
      { k: 'path', d: rr(w * 0.1, h * 0.47, w * 0.8, h * 0.37, 14), fill: '#000000', op: 0.4 },
      boldText(s.value ?? '', { x: w / 2, y: h * 0.655, maxSize: h * 0.28, maxW: w * 0.74, fill: g, ink: th.ink }));
    return { w, h, alias: s.alias ?? `jp_marquee_${tier}`, parts };
  },
};

export const FX_KINDS = { jp_plate, win_banner, fg_banner, coin, fg_intro, coin_burst, jp_marquee };
export const FX_SAMPLES = {
  jp_plate: [...TIERS.map((tier) => ({ tier })), { tier: 'Major', value: '12,345.00' }, { tier: 'Grand', value: '' }],
  win_banner: Object.keys(WIN).map((tier) => ({ tier })),
  fg_banner: [{}, { sub: '×10' }, { text: '' }, { sub: '' }],
  coin: [{}, { size: 96 }],
  fg_intro: [{}, { mode: 'bonus', count: '10' }],
  coin_burst: [{}, { count: 24, seed: 3 }],
  jp_marquee: [{}, { tier: 'Minor', value: '8,888.88' }],
};
