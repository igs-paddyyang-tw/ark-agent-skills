// lobster 龍蝦（俯視、頭朝 −y）：頭胸甲＋4 節腹部（擺動）＋尾扇開合；長觸角擺、前螯。
const TAU = Math.PI * 2;
export const defaults = { w: 0.22, sway: 0.05, ant: 0.45, eye: 0.022 };
export function body(p) { return { cy: 0.45, rx: p.w / 2, ry: 0.35 }; }
export function extent(p) { return { halfW: Math.max(p.w / 2 + 0.22, p.ant * 0.55) + 0.05, y0: -0.02, y1: 1.02 }; }
export function parts(t, p, c) {
  const s = (y) => Math.sin(t * TAU - y * 3) * p.sway * y;
  const segs = [0.48, 0.58, 0.67, 0.76].map((y, i) => ({ k: 'ellipse', cx: s(y), cy: y, rx: p.w * (0.5 - i * 0.07), ry: 0.06, fill: c.main, stroke: c.dark, sw: 0.012 }));
  const fan = Math.sin(t * TAU) * 0.04, ty = 0.84, tx = s(0.9);
  const antW = Math.sin(t * TAU) * 0.05;
  return [
    ...[-1, 1].map((sd) => ({ k: 'polyline', pts: [[sd * 0.04, 0.12], [sd * (0.18 + antW), -0.0 + 0.0], [sd * (p.ant * 0.55 + antW), 0.02]], stroke: c.dark, sw: 0.012 })),
    ...[-1, 1].map((sd) => ({ k: 'polyline', pts: [[sd * p.w * 0.4, 0.22], [sd * (p.w * 0.4 + 0.12), 0.12], [sd * (p.w * 0.4 + 0.1), 0.05]], stroke: c.dark, sw: 0.03, cap: 'round' })),
    ...[-1, 1].map((sd) => ({ k: 'ellipse', cx: sd * (p.w * 0.4 + 0.1), cy: 0.04, rx: 0.045, ry: 0.07, fill: c.main, stroke: c.dark, sw: 0.012 })),
    { k: 'polygon', pts: [[tx, ty], [tx - 0.12 - fan, 1], [tx, 0.97], [tx + 0.12 + fan, 1]], fill: c.dark },
    ...segs.reverse(),
    { k: 'ellipse', cx: 0, cy: 0.28, rx: p.w / 2, ry: 0.16, fill: 'grad', stroke: c.dark, sw: 0.015 },
    { k: 'ellipse', cx: 0, cy: 0.28, rx: p.w * 0.22, ry: 0.11, fill: c.light, op: 0.5 },
    { k: 'eye', cx: -p.w * 0.25, cy: 0.15, r: p.eye * 1.3 },
    { k: 'eye', cx: p.w * 0.25, cy: 0.15, r: p.eye * 1.3 },
  ];
}
