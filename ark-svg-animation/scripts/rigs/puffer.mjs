// puffer 河豚（俯視）：圓身脹縮、一圈短刺、小尾鰭擺動、大眼。
const TAU = Math.PI * 2, SPIKES = 12;
export const defaults = { r: 0.3, pulse: 0.06, spike: 0.06, eye: 0.05 };
export function body(p) { return { cy: 0.45, rx: p.r, ry: p.r }; }
export function extent(p) { return { halfW: p.r * (1 + p.pulse) + p.spike + 0.03, y0: -0.02, y1: 1.02 }; }
export function parts(t, p, c) {
  const k = 1 + Math.sin(t * TAU) * p.pulse, r = p.r * k, cy = 0.45, sway = Math.sin(t * TAU) * 0.06;
  const spikes = Array.from({ length: SPIKES }, (_, i) => {
    const a = (i / SPIKES) * TAU, b = 0.12;
    return { k: 'polygon', pts: [[Math.cos(a - b) * r, cy + Math.sin(a - b) * r], [Math.cos(a) * (r + p.spike), cy + Math.sin(a) * (r + p.spike)], [Math.cos(a + b) * r, cy + Math.sin(a + b) * r]], fill: c.dark };
  });
  return [
    { k: 'polygon', pts: [[0, cy + r * 0.9], [-0.12 + sway, 0.98], [0.12 + sway, 0.98]], fill: c.dark },
    ...spikes,
    { k: 'circle', cx: 0, cy, r, fill: 'grad', stroke: c.dark, sw: 0.015 },
    { k: 'ellipse', cx: 0, cy: cy + r * 0.25, rx: r * 0.6, ry: r * 0.45, fill: c.light, op: 0.55 },
    { k: 'eye', cx: -r * 0.42, cy: cy - r * 0.5, r: p.eye },
    { k: 'eye', cx: r * 0.42, cy: cy - r * 0.5, r: p.eye },
  ];
}
