// fusiform 紡錘魚（俯視、頭朝 −y）：小丑魚、蝴蝶魚、獅子魚、旗魚、鮟鱇、鯒…
// 動畫：尾鰭左右擺（週期 1）、胸鰭拍動（相位差 1/4）。座標：頭 y=0、尾 y=1、中線 x=0、身長＝1。
const TAU = Math.PI * 2;

export const defaults = { bodyW: 0.42, bodyLen: 0.72, tailW: 0.45, sway: 0.08, fin: 0.55, stripes: 3, eye: 0.035 };

/** 個體差（只在 resolve 抽一次）：紋路數、體寬微調 */
export function individual(rnd) {
  return { stripes: 2 + Math.floor(rnd() * 3), bodyW: 0.38 + rnd() * 0.1 };
}

export function body(p) {
  return { cy: p.bodyLen / 2, rx: p.bodyW / 2, ry: p.bodyLen / 2 };
}

/** 動畫外擴範圍（含擺動、胸鰭）—— 所有格共用同一個 viewBox，錨點才不會跳 */
export function extent(p) {
  const halfW = Math.max(p.bodyW / 2 + p.bodyW * p.fin * 0.85, p.bodyW * p.tailW + p.sway) + 0.02;
  return { halfW, y0: -0.02, y1: 1.02 };
}

export function parts(t, p, c) {
  const W = p.bodyW, Lb = p.bodyLen, sway = Math.sin(t * TAU) * p.sway, flap = Math.sin(t * TAU + Math.PI / 2) * 0.03;
  const fin = W * p.fin;
  const stripes = Array.from({ length: p.stripes }, (_, i) => {
    const y = Lb * (0.25 + (0.5 * i) / Math.max(1, p.stripes - 1));
    return { k: 'ellipse', cx: 0, cy: y, rx: W * 0.36, ry: 0.03, fill: c.light, op: 0.75 };
  });
  return [
    { k: 'polygon', pts: [[0, Lb - 0.03], [-W * p.tailW + sway, 1], [sway, 0.93], [W * p.tailW + sway, 1]], fill: c.dark },
    { k: 'polygon', pts: [[-W * 0.4, Lb * 0.35], [-W * 0.4 - fin, Lb * 0.55 - flap], [-W * 0.35, Lb * 0.6]], fill: c.dark },
    { k: 'polygon', pts: [[W * 0.4, Lb * 0.35], [W * 0.4 + fin, Lb * 0.55 + flap], [W * 0.35, Lb * 0.6]], fill: c.dark },
    { k: 'ellipse', cx: 0, cy: Lb / 2, rx: W / 2, ry: Lb / 2, fill: c.main, stroke: c.dark, sw: 0.02 },
    ...stripes,
    { k: 'circle', cx: -W * 0.22, cy: Lb * 0.14, r: p.eye, fill: c.eye },
    { k: 'circle', cx: W * 0.22, cy: Lb * 0.14, r: p.eye, fill: c.eye },
  ];
}
