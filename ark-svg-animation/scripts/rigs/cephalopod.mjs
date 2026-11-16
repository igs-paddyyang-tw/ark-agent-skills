// cephalopod 章魚（俯視、頭朝 −y）：外套膜＋8 隻觸手向後展開，各觸手正弦波（相位依序錯開＝行進波）。
const TAU = Math.PI * 2, ARMS = 8, SEG = 4;
export const defaults = { head: 0.22, arm: 0.62, wave: 0.07, eye: 0.03 };
export function body(p) { return { cy: 0.24, rx: p.head * 0.9, ry: p.head }; }
export function extent(p) { return { halfW: p.arm * 0.7 + p.wave + 0.05, y0: -0.02, y1: 1.02 }; }
export function parts(t, p, c) {
  const arms = Array.from({ length: ARMS }, (_, i) => {
    const a = Math.PI / 2 + ((i - (ARMS - 1) / 2) / ARMS) * 1.6;          // 向後（+y）扇形展開
    const pts = Array.from({ length: SEG + 1 }, (_, j) => {
      const d = (j / SEG) * p.arm, w = Math.sin(t * TAU + i * 0.8 - j * 0.9) * p.wave * (j / SEG);
      return [Math.cos(a) * d - Math.sin(a) * w, 0.32 + Math.sin(a) * d * 0.95 + Math.cos(a) * w];
    });
    return { k: 'polyline', pts, stroke: i % 2 ? c.dark : c.main, sw: 0.05 - 0.004 * Math.abs(i - 3.5), cap: 'round' };
  });
  return [
    ...arms,
    { k: 'ellipse', cx: 0, cy: 0.24, rx: p.head * 0.9, ry: p.head, fill: 'grad', stroke: c.dark, sw: 0.015 },
    { k: 'ellipse', cx: 0, cy: 0.17, rx: p.head * 0.45, ry: p.head * 0.35, fill: c.light, op: 0.45 },
    { k: 'eye', cx: -p.head * 0.45, cy: 0.33, r: p.eye * 1.4 },
    { k: 'eye', cx: p.head * 0.45, cy: 0.33, r: p.eye * 1.4 },
  ];
}
