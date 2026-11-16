// jelly 水母（傘頂朝 −y）：傘體收縮（寬窄交替）、5 條觸手向後拖曳擺動；arc＝電光（電弧閃爍）。
const TAU = Math.PI * 2, TEN = 5, SEG = 4;
export const defaults = { bell: 0.3, len: 0.62, arc: false };
export function body(p) { return { cy: 0.22, rx: p.bell, ry: 0.18 }; }
export function extent(p) { return { halfW: p.bell * 1.15 + 0.06, y0: -0.02, y1: 1.02 }; }
export function parts(t, p, c) {
  const k = Math.sin(t * TAU), rx = p.bell * (1 + 0.12 * k), ry = 0.18 * (1 - 0.1 * k);
  const tent = Array.from({ length: TEN }, (_, i) => {
    const x0 = ((i - (TEN - 1) / 2) / (TEN - 1)) * rx * 1.4;
    const pts = Array.from({ length: SEG + 1 }, (_, j) => [x0 * (1 - j * 0.12) + Math.sin(t * TAU + i - j) * 0.04 * j, 0.3 + (j / SEG) * p.len]);
    return { k: 'polyline', pts, stroke: c.light, sw: 0.02, op: 0.8, cap: 'round' };
  });
  const arcs = p.arc ? [-1, 1].map((s) => ({ k: 'polyline', pts: [[s * rx * 0.9, 0.2], [s * (rx + 0.05), 0.12], [s * (rx * 0.85), 0.06], [s * (rx + 0.06), -0.0 + 0.0]], stroke: '#7fe0ff', sw: 0.025, op: 0.35 + 0.6 * (k * k) })) : [];
  return [
    ...tent,
    { k: 'ellipse', cx: 0, cy: 0.22, rx, ry, fill: c.main, stroke: c.dark, sw: 0.015, op: 0.9 },
    { k: 'ellipse', cx: 0, cy: 0.18, rx: rx * 0.55, ry: ry * 0.5, fill: c.light, op: 0.6 },
    { k: 'polyline', pts: Array.from({ length: 7 }, (_, i) => [-rx + (i / 6) * rx * 2, 0.3 + (i % 2) * 0.03]), stroke: c.dark, sw: 0.015 },
    ...arcs,
  ];
}
