// token 角色徽章（俯視）：非水生角色（野牛、金猴爺、孫悟空、貓魚）。動畫：上下浮動＋耳／角小擺。
// kind：bison（雙角＋鼻環）、monkey（圓耳＋臉盤）、wukong（monkey＋金箍）、cat（尖耳＋鬍鬚＋魚尾）
const TAU = Math.PI * 2;
export const defaults = { r: 0.3, kind: 'monkey', bob: 0.03 };
export function body(p) { return { cy: 0.48, rx: p.r, ry: p.r }; }
export function extent(p) { return { halfW: p.r + 0.18, y0: -0.02, y1: 1.02 }; }
export function parts(t, p, c) {
  const s = Math.sin(t * TAU), cy = 0.48 + s * p.bob, r = p.r, wig = s * 0.04;
  const ears = {
    bison: [-1, 1].map((d) => ({ k: 'polygon', pts: [[d * r * 0.6, cy - r * 0.6], [d * (r + 0.14), cy - r * 0.95 + wig], [d * (r + 0.1), cy - r * 0.6], [d * r * 0.85, cy - r * 0.45]], fill: '#f1e6c8', stroke: '#6b5a3a', sw: 0.012 })),
    monkey: [-1, 1].map((d) => ({ k: 'circle', cx: d * (r + 0.04 + wig * d * 0.3), cy: cy - 0.02, r: r * 0.32, fill: c.dark })),
    cat: [-1, 1].map((d) => ({ k: 'polygon', pts: [[d * r * 0.3, cy - r * 0.8], [d * (r * 0.75 + wig * d), cy - r * 1.35], [d * r * 0.95, cy - r * 0.45]], fill: c.dark })),
  };
  const kind = p.kind === 'wukong' ? 'monkey' : p.kind;
  const face = kind === 'monkey' ? [{ k: 'ellipse', cx: 0, cy: cy + r * 0.12, rx: r * 0.68, ry: r * 0.6, fill: '#f4d7b0' }] : [];
  const extra = [];
  if (p.kind === 'wukong') extra.push({ k: 'polyline', pts: [[-r * 0.8, cy - r * 0.45], [0, cy - r * 0.72], [r * 0.8, cy - r * 0.45]], stroke: '#ffcc33', sw: 0.035, cap: 'round' });
  if (p.kind === 'bison') extra.push({ k: 'ellipse', cx: 0, cy: cy + r * 0.45, rx: r * 0.4, ry: r * 0.25, fill: c.light }, { k: 'circle', cx: 0, cy: cy + r * 0.62, r: r * 0.16, fill: 'none', stroke: '#ffcc33', sw: 0.02 });
  if (p.kind === 'cat') {
    extra.push(...[-1, 1].flatMap((d) => [0, 1].map((j) => ({ k: 'polyline', pts: [[d * r * 0.3, cy + r * (0.25 + j * 0.12)], [d * r * 1.1, cy + r * (0.15 + j * 0.25)]], stroke: c.white, sw: 0.01, op: 0.8 }))));
    extra.unshift({ k: 'polygon', pts: [[0, cy + r * 0.8], [-0.14 + wig, 0.98], [0.14 + wig, 0.98]], fill: c.accent });
  }
  return [
    ...ears[kind] ?? [],
    ...extra.filter((o) => o.k === 'polygon' && o.fill === c.accent),
    { k: 'circle', cx: 0, cy, r, fill: 'grad', stroke: c.dark, sw: 0.02 },
    ...face,
    { k: 'eye', cx: -r * 0.32, cy: cy - r * 0.05, r: r * 0.13 },
    { k: 'eye', cx: r * 0.32, cy: cy - r * 0.05, r: r * 0.13 },
    { k: 'ellipse', cx: 0, cy: cy + r * 0.3, rx: r * 0.18, ry: r * 0.1, fill: c.dark, op: 0.7 },
    ...extra.filter((o) => !(o.k === 'polygon' && o.fill === c.accent)),
  ];
}
