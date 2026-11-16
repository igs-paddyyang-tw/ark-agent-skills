// ray 魟（俯視、頭朝 −y）：魟、光魟。動畫：雙翼上下波動（翼尖前後移）、細尾擺。
const TAU = Math.PI * 2;
export const defaults = { wing: 0.5, flap: 0.07, tail: 0.32, eye: 0.025 };
export function body(p) { return { cy: 0.4, rx: p.wing * 0.55, ry: 0.3 }; }
export function extent(p) { return { halfW: p.wing + 0.05, y0: -0.02, y1: 1.02 }; }
export function parts(t, p, c) {
  const f = Math.sin(t * TAU), tipX = p.wing * (1 - 0.06 * f), tipY = 0.42 + f * p.flap, sway = Math.sin(t * TAU - 1) * 0.05;
  return [
    { k: 'polyline', pts: [[0, 0.66], [sway * 0.5, 0.84], [sway, 1]], stroke: c.dark, sw: 0.02, cap: 'round' },
    { k: 'polygon', pts: [[0, 0.06], [-0.1, 0.14], [-tipX, tipY], [-0.14, 0.6], [0, 0.7], [0.14, 0.6], [tipX, tipY], [0.1, 0.14]], fill: c.main, stroke: c.dark, sw: 0.015 },
    { k: 'polygon', pts: [[-0.08, 0.1], [-0.13, 0.02], [-0.04, 0.08]], fill: c.dark },
    { k: 'polygon', pts: [[0.08, 0.1], [0.13, 0.02], [0.04, 0.08]], fill: c.dark },
    { k: 'ellipse', cx: 0, cy: 0.4, rx: 0.12, ry: 0.22, fill: c.light, op: 0.45 },
    { k: 'circle', cx: -0.07, cy: 0.16, r: p.eye, fill: c.eye },
    { k: 'circle', cx: 0.07, cy: 0.16, r: p.eye, fill: c.eye },
  ];
}
