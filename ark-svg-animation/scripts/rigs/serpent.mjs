// serpent 分節長體（俯視、頭朝 −y）：火龍等 Spine 部件魚的替代。節鏈沿身體傳遞正弦波（行進波）、背刺、角與鬚。
const TAU = Math.PI * 2, N = 9;
export const defaults = { r: 0.11, amp: 0.13, eye: 0.022 };
export function body(p) { return { cy: 0.45, rx: p.r, ry: 0.42 }; }
export function extent(p) { return { halfW: p.amp + p.r + 0.12, y0: -0.02, y1: 1.02 }; }
export function parts(t, p, c) {
  const x = (y) => Math.sin(t * TAU - y * 5) * p.amp * Math.min(1, y * 1.6);
  const segs = Array.from({ length: N }, (_, i) => {
    const y = 0.2 + (i / (N - 1)) * 0.72, r = p.r * (1 - i * 0.07);
    return [
      { k: 'circle', cx: x(y), cy: y, r, fill: c.main, stroke: c.dark, sw: 0.012 },
      { k: 'polygon', pts: [[x(y) - r * 0.35, y - r * 0.2], [x(y), y - r * 1.25], [x(y) + r * 0.35, y - r * 0.2]], fill: c.light },
    ];
  }).reverse().flat();
  const tx = x(0.97);
  const hx = x(0.1), whisk = Math.sin(t * TAU) * 0.03;
  return [
    { k: 'polygon', pts: [[tx, 0.93], [tx - 0.08, 1], [tx + 0.08, 1]], fill: c.dark },
    ...segs,
    ...[-1, 1].map((s) => ({ k: 'polyline', pts: [[hx + s * 0.05, 0.08], [hx + s * (0.14 + whisk), 0.05], [hx + s * (0.2 + whisk), 0.1]], stroke: c.light, sw: 0.012 })),
    { k: 'polygon', pts: [[hx, 0.0 + 0.02], [hx - 0.09, 0.08], [hx - 0.08, 0.17], [hx + 0.08, 0.17], [hx + 0.09, 0.08]], fill: c.main, stroke: c.dark, sw: 0.015 },
    ...[-1, 1].map((s) => ({ k: 'polygon', pts: [[hx + s * 0.05, 0.1], [hx + s * 0.13, 0.17], [hx + s * 0.07, 0.14]], fill: c.light })),
    { k: 'circle', cx: hx - 0.04, cy: 0.08, r: p.eye, fill: '#ffdd55' },
    { k: 'circle', cx: hx + 0.04, cy: 0.08, r: p.eye, fill: '#ffdd55' },
  ];
}
