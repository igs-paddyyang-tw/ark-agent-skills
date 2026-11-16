// kit/ui.mjs —— 老虎機／魚機介面（0.6.0；計畫 T5）：reel_bg、reel_frame、panel、button、bg。
// reel／panel／bg 用像素座標（L＝1）；button 用 256 基準（L＝size/256）。框類一律拆成四條邊（不用挖洞路徑：Pixi Graphics 不支援洞）。
import { fnv1a } from '../draw.mjs';
import { metal, vgrad } from '../themes.mjs';
import { mulberry32 } from '../svg_anim.mjs';
import { rr, arcPts, starPts, tri, highlight, glowFill, WHITE } from './util.mjs';

const reelDims = (s) => {
  const cols = s.cols ?? 5, rows = s.rows ?? 3, cell = s.cell ?? 120, gap = s.gap ?? 6;
  if (cols < 1 || rows < 1 || cols > 8 || rows > 8) throw new Error('reel：cols／rows 要在 1～8');
  return { cols, rows, cell, gap, w: cols * cell + (cols + 1) * gap, h: rows * cell + (rows + 1) * gap };
};

const reel_bg = {
  category: 'ui',
  build(s, th) {
    const d = reelDims(s), parts = [{ k: 'path', d: rr(0, 0, d.w, d.h, 14), fill: vgrad(th.bg[0], th.bg[1]) }];
    for (let c = 0; c < d.cols; c++) {
      const x = d.gap + c * (d.cell + d.gap);
      parts.push({ k: 'path', d: rr(x, d.gap, d.cell, d.h - 2 * d.gap, 10), fill: vgrad(th.primary.dark, th.bg[1]), op: 0.6 });
    }
    for (let r = 1; r < d.rows; r++) {
      const y = d.gap / 2 + r * (d.cell + d.gap);
      parts.push({ k: 'polyline', pts: [[d.gap, y], [d.w - d.gap, y]], stroke: th.primary.light, sw: 1.5, op: 0.18 });
    }
    return { w: d.w, h: d.h, alias: s.alias ?? 'reel_bg', parts };
  },
};

const reel_frame = {
  category: 'ui',
  build(s, th) {
    const d = reelDims(s), b = s.border ?? 28, W = d.w + 2 * b, H = d.h + 2 * b, m = metal(th, s.metal ?? 'gold');
    const bar = (pts) => ({ k: 'polygon', pts, fill: m, stroke: th.ink, sw: 4, join: 'round' });
    const parts = [
      bar([[0, 0], [W, 0], [W - b, b], [b, b]]), bar([[b, H - b], [W - b, H - b], [W, H], [0, H]]),
      bar([[0, 0], [b, b], [b, H - b], [0, H]]), bar([[W - b, b], [W, 0], [W, H], [W - b, H - b]]),
      { k: 'path', d: rr(b - 3, b - 3, d.w + 6, d.h + 6, 6), fill: 'none', stroke: th.ink, sw: 5 },
      { k: 'path', d: rr(2, 2, W - 4, H - 4, 10), fill: 'none', stroke: th.ink, sw: 4 },
    ];
    for (const [x, y] of [[b / 2, b / 2], [W - b / 2, b / 2], [b / 2, H - b / 2], [W - b / 2, H - b / 2]]) {
      parts.push({ k: 'circle', cx: x, cy: y, r: b * 0.62, fill: tri(th.accent), stroke: th.ink, sw: 4 }, highlight(x - b * 0.18, y - b * 0.2, b * 0.24, b * 0.12, 0.5));
    }
    const cx = W / 2, r = b * 0.9;
    parts.push({ k: 'polygon', pts: [[cx, -r * 0.2 + b / 2 - r], [cx + r * 1.4, b / 2], [cx, b / 2 + r], [cx - r * 1.4, b / 2]].map(([x, y]) => [x, Math.max(1, y)]), fill: tri(th.primary), stroke: th.ink, sw: 4 });
    return { w: W, h: H, alias: s.alias ?? 'reel_frame', parts };
  },
};

const panel = {
  category: 'ui',
  build(s, th) {
    const w = s.w ?? 680, h = s.h ?? 200, r = s.r ?? 28;
    return {
      w, h, alias: s.alias ?? 'ui_panel',
      parts: [
        { k: 'path', d: rr(3, 3, w - 6, h - 6, r), fill: tri(th.primary), stroke: th.ink, sw: 6 },
        { k: 'path', d: rr(12, 12, w - 24, h - 24, r - 8), fill: 'none', stroke: metal(th, 'gold'), sw: 4 },
        { k: 'path', d: rr(26, 26, w - 52, h - 52, r - 14), fill: th.bg[1], op: 0.55 },
        { k: 'ellipse', cx: w / 2, cy: 22, rx: w * 0.36, ry: 8, fill: WHITE, op: 0.18 },
      ],
    };
  },
};

// ── 圓鈕 ────────────────────────────────────────────────────────────────────
const ICON_STYLE = (th) => ({ fill: WHITE, stroke: th.ink, sw: 6, join: 'round' });
function arrowArc(a0, a1, th) {
  const outer = arcPts(128, 128, 64, a0, a1, 10), inner = arcPts(128, 128, 40, a1, a0, 10);
  const end = (a1 * Math.PI) / 180, tip = [128 + 52 * Math.cos(end) - 30 * Math.sin(end), 128 + 52 * Math.sin(end) + 30 * Math.cos(end)];
  return [
    { k: 'polygon', pts: [...outer, ...inner], ...ICON_STYLE(th) },
    { k: 'polygon', pts: [[128 + 80 * Math.cos(end), 128 + 80 * Math.sin(end)], tip, [128 + 24 * Math.cos(end), 128 + 24 * Math.sin(end)]], ...ICON_STYLE(th) },
  ];
}
const BUTTON_ICONS = {
  spin: (th) => [...arrowArc(200, 330, th), ...arrowArc(20, 150, th)],
  auto: (th) => [{ k: 'text', str: 'AUTO', x: 128, y: 130, size: 46, fill: WHITE, ink: th.ink, outline: 5 }],
  plus: (th) => [{ k: 'polygon', pts: [[112, 64], [144, 64], [144, 112], [192, 112], [192, 144], [144, 144], [144, 192], [112, 192], [112, 144], [64, 144], [64, 112], [112, 112]], ...ICON_STYLE(th) }],
  minus: (th) => [{ k: 'polygon', pts: [[64, 112], [192, 112], [192, 144], [64, 144]], ...ICON_STYLE(th) }],
  turbo: (th) => [{ k: 'polygon', pts: [[146, 40], [84, 142], [124, 142], [106, 218], [178, 108], [136, 108], [160, 40]], ...ICON_STYLE(th) }],
  stop: (th) => [{ k: 'path', d: rr(80, 80, 96, 96, 14), ...ICON_STYLE(th) }],
};
export const BUTTON_NAMES = Object.keys(BUTTON_ICONS);

const button = {
  category: 'ui',
  build(s, th) {
    const ic = s.icon ?? 'spin';
    if (!BUTTON_ICONS[ic]) throw new Error(`button：icon 只能是 ${BUTTON_NAMES.join('／')}`);
    const size = s.size ?? (ic === 'spin' ? 200 : 120), face = ic === 'spin' ? th.accent : th.primary;
    return {
      w: size, h: size, L: size / 256, alias: s.alias ?? `ui_${ic}`,
      parts: [
        { k: 'circle', cx: 128, cy: 128, r: 122, fill: metal(th, ic === 'spin' ? 'gold' : 'silver'), stroke: th.ink, sw: 6 },
        { k: 'circle', cx: 128, cy: 128, r: 100, fill: { rg: [[0, face.light], [0.6, face.main], [1, face.dark]], cx: 0.42, cy: 0.38, r: 0.62 }, stroke: th.ink, sw: 4 },
        ...BUTTON_ICONS[ic](th),
        highlight(96, 70, 52, 20, 0.3),
      ],
    };
  },
};

// ── 直式背景：rays（放射）／stars（星空）／sea（海底） ─────────────────────────
const MOTIFS = {
  rays: (w, h, th) => Array.from({ length: 16 }, (_, i) => {
    const a = ((i * 22.5 - 90) * Math.PI) / 180, b = a + (9 * Math.PI) / 180, R = h, cx = w / 2, cy = h * 0.42;
    return { k: 'polygon', pts: [[cx, cy], [cx + R * Math.cos(a), cy + R * Math.sin(a)], [cx + R * Math.cos(b), cy + R * Math.sin(b)]], fill: th.primary.light, op: 0.07 };
  }),
  stars: (w, h, th, rnd) => Array.from({ length: 70 }, (_, i) => {
    const x = rnd() * w, y = rnd() * h * 0.8, r = 1.5 + rnd() * 3;
    return i % 7 ? { k: 'circle', cx: x, cy: y, r, fill: WHITE, op: 0.35 + rnd() * 0.5 } : { k: 'polygon', pts: starPts(x, y, r * 3, 0.3, 4), fill: th.accent.light, op: 0.8 };
  }),
  sea: (w, h, th, rnd) => [
    ...Array.from({ length: 6 }, (_, i) => {
      const x = w * (0.1 + i * 0.17);
      return { k: 'polygon', pts: [[x, 0], [x + w * 0.08, 0], [x + w * 0.22, h * 0.75], [x + w * 0.02, h * 0.75]], fill: th.primary.light, op: 0.06 };
    }),
    ...Array.from({ length: 24 }, () => ({ k: 'circle', cx: rnd() * w, cy: h * 0.15 + rnd() * h * 0.65, r: 3 + rnd() * 9, fill: 'none', stroke: WHITE, sw: 1.5, op: 0.3 })),
    { k: 'path', d: [['M', 0, h * 0.86], ['Q', w * 0.25, h * 0.8, w * 0.5, h * 0.85], ['Q', w * 0.75, h * 0.9, w, h * 0.83], ['L', w, h], ['L', 0, h], ['Z']], fill: vgrad(th.accent.dark, th.bg[1]) },
  ],
};
export const BG_MOTIFS = Object.keys(MOTIFS);

const bg = {
  category: 'bg',
  build(s, th) {
    const w = s.w ?? 720, h = s.h ?? 1280, motif = s.motif ?? 'rays';
    if (!MOTIFS[motif]) throw new Error(`bg：motif 只能是 ${BG_MOTIFS.join('／')}`);
    const rnd = mulberry32(fnv1a(`${motif}:${w}x${h}`));
    return {
      w, h, alias: s.alias ?? `bg_${motif}`,
      parts: [
        { k: 'polygon', pts: [[0, 0], [w, 0], [w, h], [0, h]], fill: vgrad(th.bg[0], th.bg[1]) },
        { k: 'circle', cx: w / 2, cy: h * 0.42, r: w * 0.75, fill: glowFill(th.primary.light, 0.4) },
        ...MOTIFS[motif](w, h, th, rnd),
      ],
    };
  },
};

export const UI_KINDS = { reel_bg, reel_frame, panel, button, bg };
export const UI_SAMPLES = {
  reel_bg: [{}, { cols: 3, rows: 3, cell: 140 }],
  reel_frame: [{}, { cols: 6, rows: 4, cell: 100, metal: 'silver' }],
  panel: [{}, { w: 400, h: 120, r: 20 }],
  button: BUTTON_NAMES.map((icon) => ({ icon })),
  bg: BG_MOTIFS.map((motif) => ({ motif })),
};
