// fusiform 紡錘魚（俯視、頭朝 −y）：小丑魚、蝴蝶魚、獅子魚、旗魚、鮟鱇、鯒…
// 0.4.0：貝茲流線身形＋放射漸層、尾鰭以尾柄為軸旋轉擺動、花紋裁切在身體內、中線脊、眼白＋瞳孔＋反光。
// 動畫：尾鰭角 sin(2πt)·swing、胸鰭相位差 π/2。座標：頭 y=0、尾 y=1、中線 x=0、身長＝1。
const TAU = Math.PI * 2;

export const defaults = { bodyW: 0.42, bodyLen: 0.72, tailW: 0.45, swing: 16, fin: 0.55, stripes: 3, eye: 0.05 };

/** 個體差（只在 resolve 抽一次）：紋路數、體寬微調 */
export function individual(rnd) {
  return { stripes: 2 + Math.floor(rnd() * 3), bodyW: 0.38 + rnd() * 0.1 };
}

export function body(p) {
  return { cy: p.bodyLen / 2, rx: p.bodyW * 0.47, ry: p.bodyLen / 2 };
}

/** 動畫外擴範圍（含尾鰭旋轉、胸鰭）—— 所有格共用同一個 viewBox，錨點才不會跳 */
export function extent(p) {
  const tailX = p.bodyW * p.tailW + (1 - p.bodyLen) * Math.sin((p.swing * Math.PI) / 180) + 0.02;
  const halfW = Math.max(p.bodyW * 0.47 + p.bodyW * p.fin * 0.6, tailX) + 0.03;
  return { halfW, y0: -0.02, y1: 1.08 };
}

/** 流線身形：吻端 y=0、最寬約 0.35 身長、尾柄 y=bodyLen */
function bodyD(W, Lb) {
  return [['M', 0, 0], ['C', W * 0.62, 0.02, W * 0.62, Lb * 0.75, W * 0.14, Lb], ['L', -W * 0.14, Lb], ['C', -W * 0.62, Lb * 0.75, -W * 0.62, 0.02, 0, 0], ['Z']];
}

export function parts(t, p, c) {
  const W = p.bodyW, Lb = p.bodyLen, s = Math.sin(t * TAU), flap = Math.sin(t * TAU + Math.PI / 2) * 0.03;
  const tw = W * p.tailW, fin = W * p.fin;
  const stripes = Array.from({ length: p.stripes }, (_, i) => {
    const y = Lb * (0.22 + (0.5 * i) / Math.max(1, p.stripes - 1));
    return { k: 'path', d: [['M', -W * 0.6, y], ['Q', 0, y - 0.05, W * 0.6, y]], fill: 'none', stroke: c.light, sw: 0.045, op: 0.85 };
  });
  const bd = bodyD(W, Lb);
  return [
    { k: 'g', rot: s * p.swing, ox: 0, oy: Lb - 0.02, children: [
      { k: 'path', d: [['M', 0, Lb - 0.03], ['C', W * 0.3, Lb + 0.05, tw, 0.97, tw, 1], ['Q', 0, 0.92, -tw, 1], ['C', -tw, 0.97, -W * 0.3, Lb + 0.05, 0, Lb - 0.03], ['Z']], fill: c.dark },
    ] },
    ...[-1, 1].map((d) => ({ k: 'path', d: [['M', d * W * 0.36, Lb * 0.3], ['Q', d * (W * 0.36 + fin + d * flap), Lb * 0.42, d * W * 0.4, Lb * 0.55], ['Z']], fill: c.dark, op: 0.9 })),
    { k: 'path', d: bd, fill: 'grad', stroke: c.dark, sw: 0.02 },
    { k: 'clip', shape: { k: 'path', d: bd }, children: stripes },
    { k: 'path', d: [['M', 0, Lb * 0.1], ['L', 0, Lb * 0.92]], fill: 'none', stroke: c.dark, sw: 0.02, op: 0.4 },
    { k: 'eye', cx: -W * 0.24, cy: Lb * 0.14, r: p.eye },
    { k: 'eye', cx: W * 0.24, cy: Lb * 0.14, r: p.eye },
  ];
}
