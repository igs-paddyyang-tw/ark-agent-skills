// kit/fish.mjs —— 魚機元素（0.7.0；計畫 T7）：cannon、bullet、net（一次性動畫）、bead、lock（循環動畫）。
// 魚種本身走 creature()（生物 rig），不在這裡。座標：cannon 以 200×280 為基準、其他 256 基準；L＝size／基準。
import { metal } from '../themes.mjs';
import { rr, arcPts, starPts, tri, shade, glowFill, highlight, sparkle, boldText, WHITE } from './util.mjs';

// ── 砲台：砲管朝上（−y），旋轉中心＝底座圓心 (100, 196) → meta.anchor ────────────────
// 等級：1 單管銀、2 雙管金、3 三管金、4 三管＋側翼、5 三管＋側翼＋光環（上限 5；遊戲自己對應倍率）
const CW = 200, CH = 280, PX = 100, PY = 196;
const cannon = {
  category: 'symbol',
  build(s, th) {
    const lv = Number(s.level ?? 1);
    if (!Number.isInteger(lv) || lv < 1 || lv > 5) throw new Error('cannon：level 只能是 1～5');
    const size = s.size ?? 140, L = size / CH, m = metal(th, lv === 1 ? 'silver' : 'gold'), body = lv >= 3 ? th.accent : th.primary;
    const n = Math.min(lv, 3), bw = [0, 44, 34, 28][n], gap = 6, total = n * bw + (n - 1) * gap;
    const parts = [];
    if (lv >= 5) parts.push({ k: 'circle', cx: PX, cy: PY, r: 84, fill: glowFill(th.accent.light, 0.6) });   // r ≤ CH－PY：光暈不出畫布
    if (lv >= 4) for (const sgn of [-1, 1]) {
      parts.push({ k: 'polygon', pts: [[PX + sgn * 52, PY - 30], [PX + sgn * 96, PY - 70], [PX + sgn * 90, PY + 6], [PX + sgn * 60, PY + 30]], fill: tri(body), stroke: th.ink, sw: 5, join: 'round' });
    }
    for (let i = 0; i < n; i++) {
      const x = PX - total / 2 + i * (bw + gap), top = n === 3 && i !== 1 ? 36 : 14;
      parts.push(
        { k: 'path', d: rr(x, top, bw, PY - top, bw * 0.3), fill: m, stroke: th.ink, sw: 5 },
        { k: 'path', d: rr(x - 4, top - 4, bw + 8, 22, 6), fill: metal(th, 'bronze'), stroke: th.ink, sw: 5 },
        { k: 'path', d: rr(x + bw * 0.2, top + 30, bw * 0.18, PY - top - 70, 3), fill: WHITE, op: 0.35 },
      );
    }
    parts.push(
      { k: 'circle', cx: PX, cy: PY, r: 72, fill: m, stroke: th.ink, sw: 6 },
      { k: 'circle', cx: PX, cy: PY, r: 52, fill: tri(body), stroke: th.ink, sw: 4 },
      ...Array.from({ length: 8 }, (_, i) => { const a = (i * Math.PI) / 4; return { k: 'circle', cx: PX + 62 * Math.cos(a), cy: PY + 62 * Math.sin(a), r: 4, fill: th.ink }; }),
      { k: 'polygon', pts: [[PX, PY - 22], [PX + 22, PY], [PX, PY + 22], [PX - 22, PY]], fill: tri(lv >= 2 ? th.primary : shade(th.jp.Grand)), stroke: th.ink, sw: 4 },
      highlight(PX - 22, PY - 34, 26, 10, 0.35),
    );
    for (let i = 0; i < lv; i++) parts.push({ k: 'circle', cx: PX - (lv - 1) * 8 + i * 16, cy: PY + 36, r: 5, fill: th.accent.light, stroke: th.ink, sw: 2 });   // 等級點（在底座內）
    return { w: size * (CW / CH), h: size, L, alias: s.alias ?? `cannon_${lv}`, anchor: [PX / CW, PY / CH], parts };
  },
};

const bullet = {
  category: 'symbol',
  build(s, th) {
    const size = s.size ?? 32, col = s.color ? shade(s.color) : th.accent;
    return {
      w: size, h: size, L: size / 256, alias: s.alias ?? 'bullet',
      parts: [
        { k: 'circle', cx: 128, cy: 128, r: 124, fill: glowFill(col.light, 0.7) },
        { k: 'circle', cx: 128, cy: 128, r: 78, fill: th.ink },
        { k: 'circle', cx: 128, cy: 128, r: 70, fill: { rg: [[0, WHITE], [0.4, col.light], [1, col.main]], cx: 0.42, cy: 0.38, r: 0.62 }, stroke: col.dark, sw: 12 },
        { k: 'circle', cx: 106, cy: 104, r: 22, fill: WHITE, op: 0.85 },
      ],
    };
  },
};

// 網：一次性（loop:false），第 0 格小、最後一格最大且淡出；6 條放射線＋2 圈六角網
const net = {
  category: 'fx', anim: { frames: 6, loop: false },
  build(s, th, t = 0) {
    const size = s.size ?? 160, col = s.color ? shade(s.color) : th.primary;
    const e = 1 - (1 - t) * (1 - t), k = 0.35 + 0.65 * e, op = t < 0.6 ? 1 : 1 - ((t - 0.6) / 0.4) * 0.85, R = 118 * k;
    const hex = (r) => Array.from({ length: 6 }, (_, i) => [128 + r * Math.cos((i * Math.PI) / 3), 128 + r * Math.sin((i * Math.PI) / 3)]);
    return {
      w: size, h: size, L: size / 256, alias: s.alias ?? 'net',
      parts: [
        { k: 'circle', cx: 128, cy: 128, r: R, fill: glowFill(col.light, 0.45 * op) },
        { k: 'polygon', pts: hex(R * 0.95), fill: 'none', stroke: col.light, sw: 5, op },
        { k: 'polygon', pts: hex(R * 0.55), fill: 'none', stroke: WHITE, sw: 3, op: op * 0.8 },
        ...hex(R * 0.95).map(([x, y]) => ({ k: 'polyline', pts: [[128, 128], [x, y]], stroke: WHITE, sw: 3, op: op * 0.8 })),
        ...hex(R * 0.95).map(([x, y]) => ({ k: 'circle', cx: x, cy: y, r: 7 * k, fill: col.light, stroke: th.ink, sw: 2, op })),
        sparkle(128, 128, 22 * k, WHITE, op),
      ],
    };
  },
};

const bead = {
  category: 'symbol',
  build(s, th) {
    const size = s.size ?? 60, col = s.color ? shade(s.color) : th.primary;
    return {
      w: size, h: size, L: size / 256, alias: s.alias ?? 'bead',
      parts: [
        { k: 'circle', cx: 128, cy: 128, r: 124, fill: glowFill(col.light, 0.55) },
        { k: 'circle', cx: 128, cy: 128, r: 84, fill: { rg: [[0, col.light], [0.6, col.main], [1, col.dark]], cx: 0.4, cy: 0.36, r: 0.66 }, stroke: th.ink, sw: 8 },
        { k: 'circle', cx: 128, cy: 128, r: 64, fill: 'none', stroke: WHITE, sw: 4, op: 0.35 },
        { k: 'ellipse', cx: 104, cy: 96, rx: 30, ry: 18, rot: -30, fill: WHITE, op: 0.75 },
        { k: 'polygon', pts: starPts(160, 164, 16, 0.3, 4), fill: WHITE, op: 0.6 },
      ],
    };
  },
};

// 鎖定框：4 個角括號，一循環轉 90°（4 重對稱 → t＝1 與 t＝0 同一組）；中心點脈動
const lock = {
  category: 'fx', anim: { frames: 4 },
  build(s, th, t = 0) {
    const size = s.size ?? 120, col = s.color ? shade(s.color) : shade(th.jp.Grand);
    const bracket = (rot) => ({ k: 'g', rot, ox: 128, oy: 128, children: [
      { k: 'polygon', pts: [...arcPts(128, 128, 104, -130, -50, 6), ...arcPts(128, 128, 84, -50, -130, 6)], fill: col.main, stroke: th.ink, sw: 4 },
    ] });
    const pulse = 0.75 + 0.25 * Math.cos(2 * Math.PI * t);
    return {
      w: size, h: size, L: size / 256, alias: s.alias ?? 'lock',
      parts: [
        { k: 'circle', cx: 128, cy: 128, r: 64, fill: 'none', stroke: col.light, sw: 4, op: 0.7 },
        { k: 'g', rot: t * 90, ox: 128, oy: 128, children: [0, 90, 180, 270].map(bracket) },
        ...[[128, 54, 128, 82], [128, 174, 128, 202], [54, 128, 82, 128], [174, 128, 202, 128]].map(([a, b, c, d]) => ({ k: 'polyline', pts: [[a, b], [c, d]], stroke: col.light, sw: 6 })),
        { k: 'circle', cx: 128, cy: 128, r: 14, fill: col.main, stroke: th.ink, sw: 3, op: pulse },
      ],
    };
  },
};


// ── 魚潮來襲橫幅（循環 6 格）：兩層正弦浪由右往左捲動，一循環前進 1 個波長（t＝1 與 t＝0 同形）＋主字 ───────────
const tide_banner = {
  category: 'fx', anim: { frames: 6 },
  build(s, th, t = 0) {
    const w = s.w ?? 720, h = s.h ?? 220, SAMPLES = 24, x0 = 18, x1 = w - 18, bottom = h * 0.92 - 6, lam = (x1 - x0) / 2;
    // 浪只畫在橫幅內（flat 沒有裁切 → 範圍自己收：左右內縮避開圓角、底部停在橫幅底緣）
    const wave = (base, amp, phase, fill, op) => {
      const pts = Array.from({ length: SAMPLES + 1 }, (_, i) => {
        const x = x0 + ((x1 - x0) * i) / SAMPLES;
        return [x, base + amp * Math.sin(2 * Math.PI * ((x - x0) / lam + t + phase))];
      });
      return { k: 'polygon', pts: [...pts, [x1, bottom], [x0, bottom]], fill, op };
    };
    return {
      w, h, alias: s.alias ?? 'tide_banner',
      parts: [
        { k: 'path', d: rr(2, h * 0.08, w - 4, h * 0.84, 22), fill: tri(shade(th.primary.dark)), stroke: th.ink, sw: 5 },
        wave(h * 0.66, h * 0.07, 0, th.primary.light, 0.45),
        wave(h * 0.76, h * 0.06, 0.5, th.accent.light, 0.5),
        { k: 'path', d: rr(2, h * 0.08, w - 4, h * 0.84, 22), fill: 'none', stroke: metal(th, 'gold'), sw: 4 },
        boldText(s.text ?? 'FISH TIDE', { x: w / 2, y: h * 0.42, maxSize: h * 0.3, maxW: w * 0.78, fill: metal(th, 'gold'), ink: th.ink }),
      ],
    };
  },
};

// ── Boss 出場警示（循環 4 格）：暗紅帶＋上下警示斜紋（固定）＋WARNING 與外光脈動 ─────────────────────────
const boss_warning = {
  category: 'fx', anim: { frames: 4 },
  build(s, th, t = 0) {
    const w = s.w ?? 720, h = s.h ?? 200, red = shade(s.color ?? '#e0202f'), pulse = 0.5 + 0.5 * Math.cos(2 * Math.PI * t);
    const stripes = (y0, y1) => {
      const out = [], sw = 28, slant = y1 - y0;
      for (let x = -slant; x < w; x += sw * 2) {
        const pts = [[x, y1], [x + sw, y1], [x + sw + slant, y0], [x + slant, y0]].map(([px, py]) => [Math.min(w - 4, Math.max(4, px)), py]);
        out.push({ k: 'polygon', pts, fill: '#ffd21a' });
      }
      return out;
    };
    return {
      w, h, alias: s.alias ?? 'boss_warning',
      parts: [
        { k: 'ellipse', cx: w / 2, cy: h / 2, rx: w * 0.5, ry: h * 0.5, fill: glowFill(red.light, 0.25 + 0.35 * pulse) },
        { k: 'path', d: rr(4, h * 0.18, w - 8, h * 0.64, 10), fill: tri(red), stroke: th.ink, sw: 5 },
        { k: 'polygon', pts: [[4, h * 0.18], [w - 4, h * 0.18], [w - 4, h * 0.3], [4, h * 0.3]], fill: '#1a0a0a' },
        ...stripes(h * 0.18, h * 0.3),
        { k: 'polygon', pts: [[4, h * 0.7], [w - 4, h * 0.7], [w - 4, h * 0.82], [4, h * 0.82]], fill: '#1a0a0a' },
        ...stripes(h * 0.7, h * 0.82),
        ...[w * 0.08, w * 0.92].map((x) => ({ k: 'polygon', pts: [[x, h * 0.36], [x + h * 0.15, h * 0.62], [x - h * 0.15, h * 0.62]], fill: '#ffd21a', stroke: th.ink, sw: 4, join: 'round' })),
        boldText(s.text ?? 'WARNING', { x: w / 2, y: h / 2, maxSize: h * 0.3, maxW: w * 0.66, fill: WHITE, ink: '#1a0a0a' }),
        { k: 'path', d: rr(4, h * 0.18, w - 8, h * 0.64, 10), fill: WHITE, op: 0.18 * pulse },
      ],
    };
  },
};

export const FISH_KINDS = { cannon, bullet, net, bead, lock, tide_banner, boss_warning };
export const FISH_SAMPLES = {
  cannon: [1, 2, 3, 4, 5].map((level) => ({ level })),
  bullet: [{}, { color: '#ff5a7a', size: 48 }],
  net: [{}, { color: '#3ee0d0' }],
  bead: [{}, { color: '#36c2ff' }],
  lock: [{}],
  tide_banner: [{}, { text: 'WAVE' }],
  boss_warning: [{}, { text: 'BOSS', color: '#9b30ff' }],
};
