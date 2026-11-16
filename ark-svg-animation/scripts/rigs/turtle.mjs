// turtle 海龜（俯視、頭朝 −y）：龜殼＋殼紋、前鰭划水（大幅）、後鰭小擺（反相）、頭。
const TAU = Math.PI * 2;
export const defaults = { rx: 0.27, ry: 0.32, flip: 0.24, eye: 0.02 };
export function body(p) { return { cy: 0.5, rx: p.rx, ry: p.ry }; }
export function extent(p) { return { halfW: p.rx + p.flip + 0.06, y0: -0.02, y1: 1.02 }; }
function flipper(sd, y, len, ang, c) {
  const a = (sd > 0 ? 0 : Math.PI) + sd * ang, x0 = sd * 0.22;
  const tip = [x0 + Math.cos(a) * len, y + Math.sin(a) * len];
  return { k: 'polygon', pts: [[x0, y - 0.05], tip, [x0, y + 0.05]], fill: c.dark };
}
export function parts(t, p, c) {
  const s = Math.sin(t * TAU);
  return [
    flipper(-1, 0.38, p.flip, -0.5 + s * 0.45, c), flipper(1, 0.38, p.flip, -0.5 + s * 0.45, c),
    flipper(-1, 0.72, p.flip * 0.5, 0.5 - s * 0.3, c), flipper(1, 0.72, p.flip * 0.5, 0.5 - s * 0.3, c),
    { k: 'polygon', pts: [[-0.03, 0.8], [0, 0.92], [0.03, 0.8]], fill: c.dark },
    { k: 'ellipse', cx: 0, cy: 0.12, rx: 0.09, ry: 0.11, fill: c.light, stroke: c.dark, sw: 0.012 },
    { k: 'ellipse', cx: 0, cy: 0.5, rx: p.rx, ry: p.ry, fill: 'grad', stroke: c.dark, sw: 0.02 },
    ...[[0, 0.38], [-0.11, 0.5], [0.11, 0.5], [0, 0.62]].map(([x, y]) => ({ k: 'ellipse', cx: x, cy: y, rx: 0.07, ry: 0.06, fill: c.dark, op: 0.45 })),
    { k: 'eye', cx: -0.04, cy: 0.08, r: p.eye * 1.2 },
    { k: 'eye', cx: 0.04, cy: 0.08, r: p.eye * 1.2 },
  ];
}
