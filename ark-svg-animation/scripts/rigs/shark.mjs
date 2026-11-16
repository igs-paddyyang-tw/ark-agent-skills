// shark 鯊／鯨（俯視、頭朝 −y）：鯊、鋸鯊、虎鯨…
// 動畫：整條身體 S 形擺動（越靠尾巴擺幅越大）、尾鰭新月跟著擺、胸鰭固定。
const TAU = Math.PI * 2;
const N = 9; // 輪廓取樣段數（體積與平滑度的取捨：單格 ≤ 4 KB）

export const defaults = { bodyW: 0.26, sway: 0.07, fin: 0.34, tail: 0.3, snout: 0.12, belly: true, eye: 0.03 };

export function individual(rnd) {
  return { bodyW: 0.23 + rnd() * 0.06, fin: 0.3 + rnd() * 0.08 };
}

/** 體寬剖面：吻端尖、肩部最寬、尾柄收細 */
function halfWidth(y, p) {
  if (y < p.snout) return (p.bodyW / 2) * Math.sqrt(y / p.snout) * 0.8;
  const u = (y - p.snout) / (0.86 - p.snout);
  return (p.bodyW / 2) * (u < 0.3 ? 0.8 + (u / 0.3) * 0.2 : 1 - ((u - 0.3) / 0.7) * 0.85);
}

export function body(p) {
  return { cy: 0.43, rx: p.bodyW / 2, ry: 0.43 };
}

export function extent(p) {
  return { halfW: Math.max(p.bodyW / 2 + p.fin, p.tail + p.sway) + 0.03, y0: -0.02, y1: 1.02 };
}

export function parts(t, p, c) {
  const ph = Math.sin(t * TAU);
  const off = (y) => ph * p.sway * y * y; // 中線偏移：頭幾乎不動、尾巴擺最大
  const ys = Array.from({ length: N + 1 }, (_, i) => (0.86 * i) / N);
  const left = ys.map((y) => [off(y) - halfWidth(y, p), y]);
  const right = ys.map((y) => [off(y) + halfWidth(y, p), y]).reverse();
  const tx = off(0.9), ang = ph * 0.25;
  const tip = (s) => [tx + s * p.tail * Math.cos(ang) , 1 - s * p.tail * Math.sin(ang) * 0.4];
  const finY = 0.32;
  return [
    { k: 'polygon', pts: [[tx - 0.02, 0.84], tip(-1), [tx, 0.94], tip(1), [tx + 0.02, 0.84]], fill: c.dark },
    { k: 'polygon', pts: [[off(finY) - p.bodyW * 0.4, finY], [off(finY) - p.bodyW / 2 - p.fin, finY + 0.16], [off(finY) - p.bodyW * 0.3, finY + 0.12]], fill: c.dark },
    { k: 'polygon', pts: [[off(finY) + p.bodyW * 0.4, finY], [off(finY) + p.bodyW / 2 + p.fin, finY + 0.16], [off(finY) + p.bodyW * 0.3, finY + 0.12]], fill: c.dark },
    { k: 'polygon', pts: [...left, ...right], fill: 'grad', stroke: c.dark, sw: 0.015 },
    ...(p.belly ? [{ k: 'polyline', pts: ys.slice(2, N - 1).map((y) => [off(y), y]), stroke: c.light, sw: 0.02, op: 0.7 }] : []),
    { k: 'eye', cx: -p.bodyW * 0.22, cy: 0.1, r: p.eye },
    { k: 'eye', cx: p.bodyW * 0.22, cy: 0.1, r: p.eye },
  ];
}
