// flat 比目魚（俯視）：橢圓身＋一圈緣鰭波動（行進波），兩眼在同一側。
const TAU = Math.PI * 2, N = 18;
export const defaults = { rx: 0.3, ry: 0.4, fringe: 0.07, eye: 0.03 };
export function body(p) { return { cy: 0.45, rx: p.rx, ry: p.ry }; }
export function extent(p) { return { halfW: p.rx + p.fringe * 1.6 + 0.03, y0: -0.02, y1: 1.02 }; }
export function parts(t, p, c) {
  const ring = Array.from({ length: N }, (_, i) => {
    const a = (i / N) * TAU, r = 1 + (p.fringe / p.rx) * (1.2 + Math.sin(a * 3 - t * TAU));
    return [Math.cos(a) * p.rx * r, 0.45 + Math.sin(a) * p.ry * (1 + (r - 1) * 0.8)];
  });
  const sway = Math.sin(t * TAU) * 0.04;
  return [
    { k: 'polygon', pts: [[0, 0.82], [-0.12 + sway, 1], [0.12 + sway, 1]], fill: c.dark },
    { k: 'polygon', pts: ring, fill: c.dark, op: 0.85 },
    { k: 'ellipse', cx: 0, cy: 0.45, rx: p.rx, ry: p.ry, fill: 'grad', stroke: c.dark, sw: 0.015 },
    ...[[-0.1, 0.4], [0.08, 0.55], [-0.05, 0.62], [0.12, 0.35]].map(([x, y]) => ({ k: 'circle', cx: x, cy: y, r: 0.03, fill: c.light, op: 0.6 })),
    { k: 'eye', cx: 0.04, cy: 0.15, r: p.eye * 1.2 },
    { k: 'eye', cx: 0.12, cy: 0.2, r: p.eye * 1.2 },
  ];
}
