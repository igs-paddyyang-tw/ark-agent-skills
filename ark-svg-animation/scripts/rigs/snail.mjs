// snail 海螺（俯視、頭朝 −y）：螺旋殼（同心圓偏移）固定、腹足波動、兩根觸角擺。
const TAU = Math.PI * 2;
export const defaults = { shell: 0.3, foot: 0.24 };
export function body(p) { return { cy: 0.5, rx: p.shell, ry: p.shell }; }
export function extent(p) { return { halfW: Math.max(p.shell, p.foot * 1.15) + 0.06, y0: -0.02, y1: 1.02 }; }
export function parts(t, p, c) {
  const w = Math.sin(t * TAU), a = Math.sin(t * TAU + 1) * 0.04;
  return [
    { k: 'ellipse', cx: 0, cy: 0.5, rx: p.foot * (1 + 0.08 * w), ry: 0.42, fill: c.light, stroke: c.dark, sw: 0.012 },
    ...[-1, 1].map((s) => ({ k: 'polyline', pts: [[s * 0.06, 0.14], [s * (0.1 + a), 0.04], [s * (0.13 + a), -0.0 + 0.0]], stroke: c.dark, sw: 0.02, cap: 'round' })),
    ...[0, 1, 2, 3].map((i) => ({ k: 'circle', cx: i * 0.025, cy: 0.52 - i * 0.03, r: p.shell * (1 - i * 0.24), fill: i % 2 ? c.light : c.main, stroke: c.dark, sw: 0.015 })),
  ];
}
