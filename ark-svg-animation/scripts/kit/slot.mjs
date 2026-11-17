// kit/slot.mjs —— 老虎機符號（0.6.0；計畫 T4）：royal、badge、icon、frame。256 基準、L＝size/256。
// 造型全為本 skill 原創的通用物件；遊戲專屬角色（主角、反派、吉祥物）不在 kit 內。
import { metal } from '../themes.mjs';
import { rr, starPts, tri, shade, glowFill, highlight, sparkle, plateParts, boldText, ROYAL_WEIGHT, WHITE } from './util.mjs';

// 撲克字色相（固定，玩家靠顏色辨識；描邊與裝飾寶石跟 theme 走）
const ROYAL = { A: '#e8424f', K: '#3f6fe0', Q: '#a046d8', J: '#2fae57', 10: '#f08a1c', 9: '#1fb3b0' };
const ROYAL_ORDER = ['A', 'K', 'Q', 'J', '10', '9'];   // 物件的數字鍵會排到最前面 → 訊息與樣本用固定順序

const royal = {
  category: 'symbol',
  build(s, th) {
    const ch = String(s.letter ?? 'A').toUpperCase();
    if (!ROYAL[ch]) throw new Error(`royal：letter 只能是 ${ROYAL_ORDER.join('／')}（收到「${ch}」）`);
    const col = shade(s.color ?? ROYAL[ch]), size = s.size ?? 256;
    const letter = [
      // 0.9.0：實心粗體（aidev 回饋：空心描邊字縮到盤面大小不好認）
      boldText(ch, { x: 128, y: 136, maxSize: 156, maxW: 214, weight: ROYAL_WEIGHT, spacing: 1.2, fill: tri(col), ink: th.ink }),
      { k: 'polygon', pts: [[128, 18], [142, 34], [128, 50], [114, 34]], fill: tri(th.accent), stroke: th.ink, sw: 3 },
      sparkle(206, 200, 16, WHITE, 0.85),
    ];
    // plate：放進底板（0.8.0；整組符號同一種底板時用 —— 例：全部 arch）
    const parts = s.plate
      ? [...plateParts(th, s.plate, s.plateColor ?? 'primary'), { k: 'g', s: 0.8, ox: 128, oy: 140, children: letter }]
      : [{ k: 'circle', cx: 128, cy: 132, r: 112, fill: glowFill(col.light, 0.45) }, ...letter];
    return { w: size, h: size, L: size / 256, alias: s.alias ?? `sym_${ch}`, parts };
  },
};

const BADGE = {
  wild: { text: 'WILD', shape: 'shield', color: 'primary' },
  scatter: { text: 'SCATTER', shape: 'circle', color: 'accent' },
  free: { text: 'FREE', shape: 'diamond', color: 'primary' },
  bonus: { text: 'BONUS', shape: 'arch', color: 'accent' },
};
const badge = {
  category: 'symbol',
  build(s, th) {
    if (s.kind !== undefined) throw new Error('badge：參數 kind 已改名為 type（0.7.0；kind 和 kit 設定的 kind 撞名）');
    const kind = s.type ?? 'wild', b = BADGE[kind];
    if (!b) throw new Error(`badge：type 只能是 ${Object.keys(BADGE).join('／')}`);
    const text = s.text ?? b.text, size = s.size ?? 256;
    return {
      w: size, h: size, L: size / 256, alias: s.alias ?? `sym_${kind}`,
      parts: [
        ...plateParts(th, s.shape ?? b.shape, s.color ?? b.color),
        sparkle(128, 70, 30, th.accent.light),
        { k: 'path', d: rr(14, 104, 228, 60, 14), fill: { lg: [[0, th.primary.dark], [1, th.ink]], x1: 0, y1: 0, x2: 0, y2: 1 }, stroke: metal(th, 'gold'), sw: 4 },
        boldText(text, { x: 128, y: 134, maxSize: 48, maxW: 206, fill: metal(th, 'gold'), ink: th.ink }),
        sparkle(60, 196, 12, WHITE, 0.8), sparkle(198, 190, 9, WHITE, 0.7),
      ],
    };
  },
};

// ── 通用物件圖示 ────────────────────────────────────────────────────────────
const gold = (th) => metal(th, 'gold');
const ICONS = {
  crown: (th) => [
    { k: 'polygon', pts: [[48, 186], [36, 86], [88, 128], [128, 60], [168, 128], [220, 86], [208, 186]], fill: gold(th), stroke: th.ink, sw: 6, join: 'round' },
    { k: 'path', d: rr(42, 178, 172, 32, 8), fill: metal(th, 'bronze'), stroke: th.ink, sw: 6 },
    ...[[36, 86], [128, 60], [220, 86]].map(([x, y]) => ({ k: 'circle', cx: x, cy: y, r: 14, fill: tri(th.accent), stroke: th.ink, sw: 4 })),
    { k: 'polygon', pts: [[128, 180], [142, 194], [128, 208], [114, 194]], fill: tri(th.primary), stroke: th.ink, sw: 3 },
    highlight(98, 120, 30, 10, 0.35),
  ],
  gem: (th) => [
    { k: 'polygon', pts: [[60, 98], [96, 52], [160, 52], [196, 98], [128, 214]], fill: tri(th.primary), stroke: th.ink, sw: 6, join: 'round' },
    { k: 'polygon', pts: [[96, 52], [160, 52], [146, 98], [110, 98]], fill: th.primary.light },
    { k: 'polygon', pts: [[60, 98], [110, 98], [128, 214]], fill: th.primary.main, op: 0.85 },
    { k: 'polygon', pts: [[146, 98], [196, 98], [128, 214]], fill: th.primary.dark, op: 0.85 },
    { k: 'polyline', pts: [[60, 98], [196, 98]], stroke: th.ink, sw: 3 },
    sparkle(104, 76, 14, WHITE, 0.9),
  ],
  chest: (th, s) => {
    // metal：寶箱材質（0.8.0 起改變箱體，不只是箱帶）—— gold 金箱、silver 銀箱、bronze 木箱；不給＝theme 主色箱＋金箱帶
    const MAT = { gold: [th.metal.gold[1][1], 'bronze'], silver: [th.metal.silver[1][1], 'gold'], bronze: ['#8a5a2b', 'bronze'] };
    if (s.metal !== undefined && !MAT[s.metal]) throw new Error('icon chest：metal 只能是 gold／silver／bronze');
    const body = s.metal ? shade(MAT[s.metal][0]) : th.primary, strap = s.metal ? MAT[s.metal][1] : 'gold';
    return [
      { k: 'path', d: [['M', 44, 116], ['L', 44, 96], ['Q', 44, 52, 128, 52], ['Q', 212, 52, 212, 96], ['L', 212, 116], ['Z']], fill: tri(body), stroke: th.ink, sw: 6 },
      { k: 'path', d: rr(40, 112, 176, 100, 10), fill: tri(shade(body.dark)), stroke: th.ink, sw: 6 },
      ...[60, 180].map((x) => ({ k: 'path', d: rr(x, 54, 18, 158, 4), fill: metal(th, strap), stroke: th.ink, sw: 3 })),
      { k: 'path', d: rr(108, 100, 40, 48, 8), fill: metal(th, strap), stroke: th.ink, sw: 4 },
      { k: 'circle', cx: 128, cy: 120, r: 6, fill: th.ink },
      { k: 'polygon', pts: [[124, 122], [132, 122], [134, 138], [122, 138]], fill: th.ink },
      highlight(100, 72, 40, 10, 0.3),
    ];
  },
  coin: (th) => [
    { k: 'circle', cx: 128, cy: 128, r: 96, fill: { rg: th.metal.gold, cx: 0.4, cy: 0.35, r: 0.7 }, stroke: th.ink, sw: 6 },
    { k: 'circle', cx: 128, cy: 128, r: 74, fill: 'none', stroke: th.metal.gold[2][1], sw: 6 },
    { k: 'polygon', pts: starPts(128, 130, 48, 0.45), fill: { lg: th.metal.gold, x1: 0, y1: 1, x2: 0, y2: 0 }, stroke: th.metal.gold[2][1], sw: 3 },
    highlight(98, 82, 34, 12, 0.4),
  ],
  key: (th) => [{
    k: 'g', rot: -35, ox: 128, oy: 128, children: [
      { k: 'circle', cx: 82, cy: 128, r: 42, fill: 'none', stroke: th.ink, sw: 30 },
      { k: 'circle', cx: 82, cy: 128, r: 42, fill: 'none', stroke: th.metal.gold[1][1], sw: 18 },
      { k: 'polygon', pts: [[120, 118], [226, 118], [226, 138], [120, 138]], fill: gold(th), stroke: th.ink, sw: 5 },
      { k: 'polygon', pts: [[184, 138], [200, 138], [200, 172], [184, 172]], fill: gold(th), stroke: th.ink, sw: 5 },
      { k: 'polygon', pts: [[208, 138], [224, 138], [224, 162], [208, 162]], fill: gold(th), stroke: th.ink, sw: 5 },
      { k: 'circle', cx: 82, cy: 128, r: 14, fill: tri(th.accent), stroke: th.ink, sw: 3 },
    ],
  }],
  bell: (th) => [
    { k: 'circle', cx: 128, cy: 40, r: 14, fill: gold(th), stroke: th.ink, sw: 5 },
    { k: 'path', d: [['M', 128, 46], ['C', 82, 46, 72, 92, 72, 130], ['C', 72, 162, 58, 176, 44, 190], ['L', 212, 190], ['C', 198, 176, 184, 162, 184, 130], ['C', 184, 92, 174, 46, 128, 46], ['Z']], fill: gold(th), stroke: th.ink, sw: 6 },
    { k: 'path', d: rr(38, 184, 180, 22, 11), fill: metal(th, 'bronze'), stroke: th.ink, sw: 5 },
    { k: 'circle', cx: 128, cy: 218, r: 16, fill: tri(th.accent), stroke: th.ink, sw: 5 },
    highlight(104, 98, 18, 40, 0.35),
  ],
  trophy: (th) => [
    { k: 'path', d: [['M', 82, 74], ['C', 40, 74, 44, 128, 92, 132]], fill: 'none', stroke: th.ink, sw: 20 },
    { k: 'path', d: [['M', 174, 74], ['C', 216, 74, 212, 128, 164, 132]], fill: 'none', stroke: th.ink, sw: 20 },
    { k: 'path', d: [['M', 82, 74], ['C', 40, 74, 44, 128, 92, 132]], fill: 'none', stroke: th.metal.gold[1][1], sw: 10 },
    { k: 'path', d: [['M', 174, 74], ['C', 216, 74, 212, 128, 164, 132]], fill: 'none', stroke: th.metal.gold[1][1], sw: 10 },
    { k: 'path', d: [['M', 72, 50], ['L', 184, 50], ['C', 184, 122, 162, 156, 128, 160], ['C', 94, 156, 72, 122, 72, 50], ['Z']], fill: gold(th), stroke: th.ink, sw: 6 },
    { k: 'polygon', pts: [[116, 158], [140, 158], [146, 190], [110, 190]], fill: gold(th), stroke: th.ink, sw: 5 },
    { k: 'path', d: rr(76, 186, 104, 28, 8), fill: tri(th.primary), stroke: th.ink, sw: 5 },
    { k: 'polygon', pts: starPts(128, 100, 24, 0.45), fill: tri(th.accent), stroke: th.ink, sw: 3 },
    highlight(98, 72, 14, 30, 0.35),
  ],
  star: (th) => [
    { k: 'polygon', pts: starPts(128, 134, 112, 0.47), fill: { rg: th.metal.gold, cx: 0.45, cy: 0.4, r: 0.6 }, stroke: th.ink, sw: 7, join: 'round' },
    { k: 'polygon', pts: starPts(128, 134, 60, 0.47), fill: th.metal.gold[0][1], op: 0.7 },
    sparkle(196, 54, 16, WHITE, 0.9),
  ],
  seven: (th) => [
    { k: 'circle', cx: 128, cy: 128, r: 108, fill: glowFill(th.accent.light, 0.5) },
    boldText('7', { x: 128, y: 132, maxSize: 176, maxW: 200, weight: ROYAL_WEIGHT, fill: tri(shade('#e8303f')), ink: th.ink }),
    sparkle(196, 60, 16, WHITE, 0.9),
  ],
  goldbar: (th) => {
    const bar = (x, y) => [
      { k: 'polygon', pts: [[x, y + 46], [x + 92, y + 46], [x + 78, y], [x + 14, y]], fill: gold(th), stroke: th.ink, sw: 5, join: 'round' },
      { k: 'polygon', pts: [[x + 14, y], [x + 78, y], [x + 70, y + 10], [x + 22, y + 10]], fill: th.metal.gold[0][1] },
    ];
    return [...bar(28, 164), ...bar(136, 164), ...bar(82, 112), sparkle(170, 100, 14, WHITE, 0.9)];
  },
  clover: (th) => {
    const g = shade('#2fae57');
    const leaf = (rot) => ({ k: 'g', rot, ox: 128, oy: 120, children: [
      { k: 'circle', cx: 106, cy: 74, r: 30, fill: tri(g), stroke: th.ink, sw: 5 },
      { k: 'circle', cx: 150, cy: 74, r: 30, fill: tri(g), stroke: th.ink, sw: 5 },
      { k: 'polygon', pts: [[80, 86], [176, 86], [128, 124]], fill: g.main },
    ] });
    return [
      { k: 'path', d: [['M', 128, 128], ['Q', 140, 190, 176, 226]], fill: 'none', stroke: th.ink, sw: 16 },
      { k: 'path', d: [['M', 128, 128], ['Q', 140, 190, 176, 226]], fill: 'none', stroke: g.dark, sw: 8 },
      leaf(0), leaf(90), leaf(180), leaf(270),
      { k: 'circle', cx: 128, cy: 120, r: 12, fill: tri(th.accent), stroke: th.ink, sw: 3 },
    ];
  },
  heart: (th) => [
    { k: 'path', d: [['M', 128, 214], ['C', 60, 162, 34, 128, 34, 92], ['C', 34, 58, 60, 38, 90, 38], ['C', 108, 38, 120, 50, 128, 66], ['C', 136, 50, 148, 38, 166, 38], ['C', 196, 38, 222, 58, 222, 92], ['C', 222, 128, 196, 162, 128, 214], ['Z']], fill: tri(shade('#f0476a')), stroke: th.ink, sw: 7 },
    highlight(84, 80, 26, 14, 0.45),
    sparkle(178, 76, 14, WHITE, 0.85),
  ],
};
export const ICON_NAMES = Object.keys(ICONS);

const icon = {
  category: 'symbol',
  build(s, th) {
    const name = s.name ?? 'crown';
    if (!ICONS[name]) throw new Error(`icon：name 只能是 ${ICON_NAMES.join('／')}（收到「${name}」）`);
    const size = s.size ?? 256, parts = ICONS[name](th, s);
    return {
      w: size, h: size, L: size / 256, alias: s.alias ?? `icon_${name}${s.metal ? `_${s.metal}` : ''}`,
      parts: s.plate ? [...plateParts(th, s.plate, s.plateColor ?? 'primary'), { k: 'g', s: 0.72, ox: 128, oy: 134, children: parts }] : parts,
    };
  },
};

// ── 符號框：等級 1～3（銅／銀／金；2 級加角釘、3 級加寶石） ──────────────────────
const LV_METAL = { 1: 'bronze', 2: 'silver', 3: 'gold' };
const frame = {
  category: 'symbol',
  build(s, th) {
    const lv = Number(s.level ?? 1);
    if (!LV_METAL[lv]) throw new Error('frame：level 只能是 1／2／3');
    const size = s.size ?? 256, m = s.metal ?? LV_METAL[lv];
    const parts = [
      { k: 'path', d: rr(4, 4, 248, 248, 30), fill: 'none', stroke: th.ink, sw: 22 + lv * 2 },
      { k: 'path', d: rr(4, 4, 248, 248, 30), fill: 'none', stroke: metal(th, m), sw: 14 + lv * 2 },
      { k: 'path', d: rr(20 + lv, 20 + lv, 216 - 2 * lv, 216 - 2 * lv, 18), fill: 'none', stroke: th.ink, sw: 3 },
    ];
    if (lv >= 2) for (const [x, y] of [[14, 14], [242, 14], [14, 242], [242, 242]]) parts.push({ k: 'circle', cx: x, cy: y, r: 13, fill: metal(th, m), stroke: th.ink, sw: 4 });
    if (lv >= 3) {
      for (const [x, y] of [[14, 14], [242, 14], [14, 242], [242, 242]]) parts.push({ k: 'polygon', pts: [[x, y - 8], [x + 8, y], [x, y + 8], [x - 8, y]], fill: tri(th.accent) });
      for (const [x, y] of [[128, 8], [128, 248], [8, 128], [248, 128]]) parts.push({ k: 'polygon', pts: [[x, y - 12], [x + 12, y], [x, y + 12], [x - 12, y]], fill: tri(th.primary), stroke: th.ink, sw: 3 });
    }
    return { w: size, h: size, L: size / 256, alias: s.alias ?? `frame_${lv}`, parts };
  },
};

export const SLOT_KINDS = { royal, badge, icon, frame };
export const SLOT_SAMPLES = {
  royal: [...ROYAL_ORDER.map((letter) => ({ letter })), { letter: 'K', plate: 'arch' }, { letter: '10', plate: 'circle', plateColor: 'accent' }],
  badge: Object.keys(BADGE).map((type) => ({ type })),
  icon: [...ICON_NAMES.map((name) => ({ name })), ...['gold', 'silver', 'bronze'].map((metal) => ({ name: 'chest', metal })), { name: 'key', plate: 'circle' }],
  frame: [{ level: 1 }, { level: 2 }, { level: 3 }],
};
