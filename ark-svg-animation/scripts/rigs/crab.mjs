// crab 蟹（俯視、螯朝 −y）：炸彈蟹、電磁蟹、鑽頭蟹、連環鑽頭蟹、轉輪蟹…
// 動畫：左右各 3 隻步足交替（三腳步態，相位差 1/2）、雙螯開合。配件（accessory）：bomb／electrode／drill／wheel。
const TAU = Math.PI * 2;

export const defaults = { shellW: 0.5, shellH: 0.36, leg: 0.3, claw: 0.17, open: 0.3, eye: 0.03, accessory: undefined };

export function individual(rnd) {
  return { shellW: 0.46 + rnd() * 0.08, leg: 0.27 + rnd() * 0.06 };
}

export function body(p) {
  return { cy: 0.55, rx: p.shellW / 2, ry: p.shellH / 2 };
}

export function extent(p) {
  return { halfW: p.shellW / 2 + p.leg + 0.06, y0: -0.02, y1: 1.02 };
}

function leg(side, i, t, p, c) {
  const y = 0.47 + i * 0.09, x0 = side * p.shellW * 0.42;
  const lift = Math.sin(t * TAU + (i % 2) * Math.PI + (side > 0 ? Math.PI : 0)) * 0.04;
  const knee = [x0 + side * p.leg * 0.55, y - 0.05 + lift];
  const foot = [x0 + side * p.leg, y + 0.06 + lift * 0.5];
  return { k: 'polyline', pts: [[x0, y], knee, foot], stroke: c.dark, sw: 0.035, cap: 'round' };
}

function claw(side, t, p, c) {
  const open = (Math.sin(t * TAU) * 0.5 + 0.5) * p.open;
  const base = [side * p.shellW * 0.3, 0.42], elbow = [side * p.shellW * 0.42, 0.24], hand = [side * p.shellW * 0.3, 0.12];
  const a = -Math.PI / 2 + side * open, b = -Math.PI / 2 - side * 0.15;
  const f = (ang, r) => [hand[0] + Math.cos(ang) * r, hand[1] + Math.sin(ang) * r];
  return [
    { k: 'polyline', pts: [base, elbow, hand], stroke: c.dark, sw: 0.05, cap: 'round' },
    // 螯：兩片寬刃（掌＋可動指），開合角由相位決定
    { k: 'ellipse', cx: hand[0], cy: hand[1] + 0.02, rx: p.claw * 0.38, ry: p.claw * 0.45, fill: c.main, stroke: c.dark, sw: 0.012 },
    { k: 'polygon', pts: [f(a + 0.55, p.claw * 0.3), f(a - 0.45, p.claw * 0.45), f(a, p.claw), f(a + 0.3, p.claw * 0.7)], fill: c.main, stroke: c.dark, sw: 0.012 },
    { k: 'polygon', pts: [f(b - 0.55, p.claw * 0.3), f(b + 0.45, p.claw * 0.42), f(b, p.claw * 0.9), f(b - 0.3, p.claw * 0.62)], fill: c.main, stroke: c.dark, sw: 0.012 },
  ];
}

function accessory(kind, t, p, c) {
  const cy = 0.55, pulse = Math.sin(t * TAU) * 0.01;
  switch (kind) {
    case 'bomb': return [
      { k: 'circle', cx: 0, cy, r: 0.11 + pulse, fill: '#222831', stroke: '#000000', sw: 0.012 },
      { k: 'polyline', pts: [[0.06, cy - 0.09], [0.1, cy - 0.15], [0.13, cy - 0.14]], stroke: '#c8a165', sw: 0.015 },
      { k: 'circle', cx: 0.135, cy: cy - 0.145, r: 0.02 + Math.abs(pulse), fill: '#ffb030' },
    ];
    case 'electrode': return [-1, 1].map((s) => ({ k: 'polyline', pts: [[s * 0.08, cy], [s * 0.12, cy - 0.06], [s * 0.08, cy - 0.1], [s * 0.13, cy - 0.17]], stroke: '#7fe0ff', sw: 0.035, op: 0.75 + pulse * 20 }));
    case 'drill': return [
      { k: 'polygon', pts: [[-0.07, cy - 0.02], [0.07, cy - 0.02], [0, cy - 0.24]], fill: '#b8c4d0', stroke: '#5c6b7a', sw: 0.012 },
      ...[0.06, 0.12].map((d) => ({ k: 'polyline', pts: [[-0.06 + d * 0.4, cy - 0.04 - d], [0.06 - d * 0.4, cy - 0.08 - d]], stroke: '#5c6b7a', sw: 0.01 })),
    ];
    case 'wheel': {
      // 3 根輪輻穿過圓心＝每 60° 對稱 → 一個循環轉 60°，首尾才接得上（verify 接縫檢查抓到的：原本 90°）
      const r = 0.1, a0 = t * (Math.PI / 3);
      return [
        { k: 'circle', cx: 0, cy, r, fill: c.accent, stroke: c.dark, sw: 0.012 },
        ...[0, 1, 2].map((i) => { const a = a0 + (i * Math.PI) / 3; return { k: 'polyline', pts: [[Math.cos(a) * r, cy + Math.sin(a) * r], [-Math.cos(a) * r, cy - Math.sin(a) * r]], stroke: c.dark, sw: 0.012 }; }),
      ];
    }
    default: return [];
  }
}

export function parts(t, p, c) {
  return [
    ...[0, 1, 2].flatMap((i) => [leg(-1, i, t, p, c), leg(1, i, t, p, c)]),
    ...claw(-1, t, p, c), ...claw(1, t, p, c),
    { k: 'ellipse', cx: 0, cy: 0.55, rx: p.shellW / 2, ry: p.shellH / 2, fill: 'grad', stroke: c.dark, sw: 0.02 },
    { k: 'ellipse', cx: 0, cy: 0.5, rx: p.shellW * 0.3, ry: p.shellH * 0.25, fill: c.light, op: 0.5 },
    { k: 'polyline', pts: [[-p.shellW * 0.14, 0.43], [-p.shellW * 0.14, 0.38]], stroke: c.dark, sw: 0.02 },
    { k: 'polyline', pts: [[p.shellW * 0.14, 0.43], [p.shellW * 0.14, 0.38]], stroke: c.dark, sw: 0.02 },
    { k: 'eye', cx: -p.shellW * 0.14, cy: 0.37, r: p.eye * 1.2 },
    { k: 'eye', cx: p.shellW * 0.14, cy: 0.37, r: p.eye * 1.2 },
    ...accessory(p.accessory, t, p, c),
  ];
}
