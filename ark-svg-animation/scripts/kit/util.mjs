// kit/util.mjs —— gamekit 共用幾何（0.6.0）。座標單位由呼叫端決定（符號 256 基準、UI 用像素）。
import { mix } from '../draw.mjs';

export { mix };
export const WHITE = '#ffffff';

/** 圓角矩形 → path 指令 */
export function rr(x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  return [['M', x + r, y], ['L', x + w - r, y], ['Q', x + w, y, x + w, y + r], ['L', x + w, y + h - r], ['Q', x + w, y + h, x + w - r, y + h],
    ['L', x + r, y + h], ['Q', x, y + h, x, y + h - r], ['L', x, y + r], ['Q', x, y, x + r, y], ['Z']];
}

/** 圓弧取樣點（角度：0°＝右、順時針，螢幕座標 y 向下） */
export function arcPts(cx, cy, r, a0, a1, n = 12) {
  return Array.from({ length: n + 1 }, (_, i) => {
    const a = ((a0 + ((a1 - a0) * i) / n) * Math.PI) / 180;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  });
}

/** n 角星（rot＝第一個尖角的角度，預設朝上） */
export function starPts(cx, cy, r, inner = 0.45, n = 5, rot = -90) {
  const pts = [];
  for (let i = 0; i < n * 2; i++) {
    const a = ((rot + (180 / n) * i) * Math.PI) / 180, rr_ = i % 2 ? r * inner : r;
    pts.push([cx + rr_ * Math.cos(a), cy + rr_ * Math.sin(a)]);
  }
  return pts;
}

/** 三段縱向漸層（亮→主→暗） */
export const tri = (c) => ({ lg: [[0, c.light], [0.55, c.main], [1, c.dark]], x1: 0, y1: 0, x2: 0, y2: 1 });
/** 單色延伸成亮主暗 */
export const shade = (hex) => ({ light: mix(hex, WHITE, 0.45), main: hex, dark: mix(hex, '#000000', 0.45) });
/** 放射亮點（中心亮色淡出） */
export const glowFill = (hex, a = 0.6) => ({ rg: [[0, hex, a], [1, hex, 0]], cx: 0.5, cy: 0.5, r: 0.5 });

/** 高光（左上斜橢圓） */
export const highlight = (cx, cy, rx, ry, op = 0.28) => ({ k: 'ellipse', cx, cy, rx, ry, rot: -12, fill: WHITE, op });

/** 四芒星閃光 */
export const sparkle = (cx, cy, r, fill, op = 1) => ({ k: 'polygon', pts: starPts(cx, cy, r, 0.28, 4, -90), fill, op });

/** 底板外形（256 基準；k＝相對中心縮放） */
const C = 128;
const sc = (k) => ([x, y]) => [C + (x - C) * k, C + (y - C) * k];
export const PLATES = {
  arch: (k) => { const [a, b, c, d, e, f, g, h, i] = [[28, 240], [28, 104], [28, 48], [72, 16], [128, 16], [184, 16], [228, 48], [228, 104], [228, 240]].map(sc(k)); return { k: 'path', d: [['M', ...a], ['L', ...b], ['C', ...c, ...d, ...e], ['C', ...f, ...g, ...h], ['L', ...i], ['Z']] }; },
  circle: (k) => ({ k: 'circle', cx: C, cy: C, r: 110 * k }),
  shield: (k) => { const q = [[128, 14], [230, 42], [222, 146], [212, 198], [172, 230], [128, 246], [84, 230], [44, 198], [34, 146], [26, 42]].map(sc(k)); return { k: 'path', d: [['M', ...q[0]], ['L', ...q[1]], ['L', ...q[2]], ['C', ...q[3], ...q[4], ...q[5]], ['C', ...q[6], ...q[7], ...q[8]], ['L', ...q[9]], ['Z']] }; },
  diamond: (k) => ({ k: 'polygon', pts: [[128, 10], [246, 128], [128, 246], [10, 128]].map(sc(k)) }),
};

/** 底板圖元（主體漸層＋金屬內框＋高光） */
export function plateParts(th, shape = 'arch', color = 'primary', rim = 'gold') {
  if (!PLATES[shape]) throw new Error(`未知底板外形「${shape}」→ 可用：${Object.keys(PLATES).join('、')}`);
  const col = typeof color === 'object' ? color : th[color];
  return [
    { ...PLATES[shape](1), fill: tri(col), stroke: th.ink, sw: th.inkW },
    { ...PLATES[shape](0.9), fill: 'none', stroke: { lg: th.metal[rim], x1: 0, y1: 0, x2: 0, y2: 1 }, sw: 5 },
    highlight(104, 72, 62, 24),
  ];
}

/** 文字自動縮到寬度內（size＝最大字高；maxW＝可用寬度；同單位） */
export function fitSize(measureGrid, maxSize, maxW) {
  return Math.min(maxSize, (maxW * 6) / Math.max(1, measureGrid));
}
