// kit/hud.mjs —— 老虎機／魚機 HUD（0.10.0；aidev 回饋 §2 缺項）：multiplier、fg_counter、info_bar、dialog、loading_bar。
// 數字類一律可留空槽（''），由遊戲執行期疊字；文字只用內建拉丁字形（中文由遊戲疊）。像素座標（L＝1），倍率標籤用 256 基準。
import { metal } from '../themes.mjs';
import { rr, starPts, tri, shade, glowFill, sparkle, boldText, WHITE } from './util.mjs';

const well = (x, y, w, h, r) => ({ k: 'path', d: rr(x, y, w, h, r), fill: '#000000', op: 0.38 });

// ── 倍率標籤：×2～×100（burst 爆炸星／pill 膠囊）；顏色依倍率分級，可覆寫 ──────────────
const MULT_TIER = [[100, '#ff3b5c'], [50, '#ff7a1a'], [10, '#f2b400'], [5, '#36c2ff'], [0, '#7bdc66']];
const multiplier = {
  category: 'symbol',
  build(s, th) {
    const raw = String(s.value ?? 2).replace(/^[x×X]/, '');
    if (!/^\d+(\.\d+)?$/.test(raw)) throw new Error(`multiplier：value 要是數字（例 2、10、100；可帶 ×），收到「${s.value}」`);
    const n = Number(raw), shape = s.shape ?? 'burst', size = s.size ?? 128;
    if (!['burst', 'pill'].includes(shape)) throw new Error('multiplier：shape 只能是 burst／pill');
    const col = shade(s.color ?? MULT_TIER.find(([v]) => n >= v)[1]);
    const body = shape === 'burst'
      ? { k: 'polygon', pts: starPts(128, 128, 120, 0.78, 14, -90), fill: tri(col), stroke: th.ink, sw: 8, join: 'round' }
      : { k: 'path', d: rr(10, 58, 236, 140, 70), fill: tri(col), stroke: th.ink, sw: 8 };
    return {
      w: size, h: size, L: size / 256, alias: s.alias ?? `mult_x${raw}`,
      parts: [
        { k: 'circle', cx: 128, cy: 128, r: 126, fill: glowFill(col.light, 0.45) },
        body,
        { k: 'ellipse', cx: 104, cy: shape === 'burst' ? 82 : 86, rx: 58, ry: 18, rot: -10, fill: WHITE, op: 0.3 },
        boldText(`×${raw}`, { x: 128, y: 132, maxSize: 96, maxW: shape === 'burst' ? 176 : 206, fill: metal(th, 'gold'), ink: th.ink }),
      ],
    };
  },
};

// ── FG 剩餘次數板：上方標籤帶＋下方數字槽 ─────────────────────────────────────
const fg_counter = {
  category: 'ui',
  build(s, th) {
    const w = s.w ?? 300, h = s.h ?? 120, label = s.label ?? 'FREE SPINS', g = metal(th, 'gold');
    return {
      w, h, alias: s.alias ?? 'fg_counter',
      parts: [
        { k: 'path', d: rr(3, 3, w - 6, h - 6, 18), fill: tri(th.primary), stroke: th.ink, sw: 6 },
        { k: 'path', d: rr(10, 10, w - 20, h - 20, 12), fill: 'none', stroke: g, sw: 3 },
        boldText(label, { x: w / 2, y: h * 0.27, maxSize: h * 0.2, maxW: w * 0.8, fill: WHITE, ink: th.ink }),
        well(20, h * 0.44, w - 40, h * 0.42, 12),
        boldText(s.value ?? '', { x: w / 2, y: h * 0.65, maxSize: h * 0.34, maxW: w * 0.7, fill: g, ink: th.ink }),
      ],
    };
  },
};

// ── 底部資訊列：N 格（預設 WIN／BALANCE／BET），每格標籤＋數字槽 ─────────────────────
const info_bar = {
  category: 'ui',
  build(s, th) {
    const labels = s.labels ?? ['WIN', 'BALANCE', 'BET'];
    if (!Array.isArray(labels) || labels.length < 1 || labels.length > 5) throw new Error('info_bar：labels 要 1～5 個');
    const w = s.w ?? 720, h = s.h ?? 110, pad = 12, gap = 10, cw = (w - pad * 2 - gap * (labels.length - 1)) / labels.length;
    const parts = [{ k: 'path', d: rr(2, 2, w - 4, h - 4, 16), fill: tri(shade(th.primary.dark)), stroke: th.ink, sw: 4 }];
    labels.forEach((lab, i) => {
      const x = pad + i * (cw + gap);
      parts.push(
        { k: 'path', d: rr(x, pad, cw, h - pad * 2, 12), fill: th.bg[1], stroke: metal(th, 'gold'), sw: 3 },
        boldText(lab, { x: x + cw / 2, y: pad + (h - pad * 2) * 0.24, maxSize: h * 0.17, maxW: cw * 0.8, fill: th.accent.light, ink: th.ink }),
        boldText(s.values?.[i] ?? '', { x: x + cw / 2, y: pad + (h - pad * 2) * 0.64, maxSize: h * 0.3, maxW: cw * 0.86, fill: WHITE, ink: th.ink }),
      );
    });
    return { w, h, alias: s.alias ?? 'info_bar', parts };
  },
};

// ── 彈窗框：標題帶（可空）＋內容區＋0～2 顆按鈕（字可空）＋關閉鈕 ───────────────────
const dialog = {
  category: 'ui',
  build(s, th) {
    const w = s.w ?? 560, h = s.h ?? 360, n = s.buttons ?? 2, g = metal(th, 'gold');
    if (![0, 1, 2].includes(n)) throw new Error('dialog：buttons 只能是 0／1／2');
    const th_ = h * 0.18, parts = [
      { k: 'path', d: rr(4, 4, w - 8, h - 8, 26), fill: tri(shade(th.primary.dark)), stroke: th.ink, sw: 8 },
      { k: 'path', d: rr(12, 12, w - 24, h - 24, 20), fill: 'none', stroke: g, sw: 4 },
      { k: 'path', d: rr(w * 0.18, 0, w * 0.64, th_, th_ / 2), fill: tri(th.primary), stroke: th.ink, sw: 5 },
      boldText(s.title ?? '', { x: w / 2, y: th_ / 2, maxSize: th_ * 0.5, maxW: w * 0.56, fill: g, ink: th.ink }),
      well(32, th_ + 14, w - 64, h - th_ - 14 - (n ? h * 0.24 : 32), 16),
    ];
    const bw = n === 2 ? w * 0.36 : w * 0.5, bh = h * 0.15, by = h - bh - 24;
    const xs = n === 2 ? [w * 0.27, w * 0.73] : n === 1 ? [w / 2] : [];
    xs.forEach((cx, i) => {
      const col = i === xs.length - 1 ? th.accent : th.primary;
      parts.push({ k: 'path', d: rr(cx - bw / 2, by, bw, bh, bh / 2), fill: tri(col), stroke: th.ink, sw: 5 },
        { k: 'ellipse', cx, cy: by + bh * 0.28, rx: bw * 0.36, ry: bh * 0.14, fill: WHITE, op: 0.3 },
        boldText(s.buttonText?.[i] ?? '', { x: cx, y: by + bh / 2, maxSize: bh * 0.5, maxW: bw * 0.8, fill: WHITE, ink: th.ink }));
    });
    if (s.close !== false) {
      const cx = w - 30, cy = 30;
      parts.push({ k: 'circle', cx, cy, r: 22, fill: tri(shade(th.jp.Grand)), stroke: th.ink, sw: 4 },
        { k: 'polygon', pts: [[cx - 10, cy - 13], [cx, cy - 3], [cx + 10, cy - 13], [cx + 13, cy - 10], [cx + 3, cy], [cx + 13, cy + 10], [cx + 10, cy + 13], [cx, cy + 3], [cx - 10, cy + 13], [cx - 13, cy + 10], [cx - 3, cy], [cx - 13, cy - 10]], fill: WHITE });
    }
    return { w, h, alias: s.alias ?? 'dialog', parts };
  },
};

// ── 載入條：外框＋軌道＋填滿（value 0～1）；part 可只出 track 或 fill（遊戲自己裁填滿長度） ──
const loading_bar = {
  category: 'ui',
  build(s, th) {
    const w = s.w ?? 480, h = s.h ?? 56, v = s.value ?? 0.65, part = s.part ?? 'all';
    if (!(v >= 0 && v <= 1)) throw new Error('loading_bar：value 要在 0～1');
    if (!['all', 'track', 'fill'].includes(part)) throw new Error('loading_bar：part 只能是 all／track／fill');
    const r = h / 2, inset = 7, fw = Math.max(h - inset * 2, (w - inset * 2) * (part === 'fill' ? 1 : v));
    const track = [
      { k: 'path', d: rr(2, 2, w - 4, h - 4, r), fill: th.bg[1], stroke: metal(th, 'gold'), sw: 4 },
      { k: 'path', d: rr(2, 2, w - 4, h - 4, r), fill: 'none', stroke: th.ink, sw: 1.5 },
    ];
    const fill = [
      { k: 'path', d: rr(inset, inset, fw, h - inset * 2, r - inset), fill: tri(th.accent) },
      { k: 'path', d: rr(inset + 6, inset + 3, Math.max(0, fw - 12), (h - inset * 2) * 0.32, (h - inset * 2) * 0.16), fill: WHITE, op: 0.35 },
    ];
    const parts = part === 'track' ? track : part === 'fill' ? fill : [...track, ...(v > 0 ? fill : [])];
    return { w, h, alias: s.alias ?? (part === 'all' ? 'loading_bar' : `loading_${part}`), parts };
  },
};

export const HUD_KINDS = { multiplier, fg_counter, info_bar, dialog, loading_bar };
export const HUD_SAMPLES = {
  multiplier: [{ value: 2 }, { value: '×10' }, { value: 100 }, { value: 5, shape: 'pill' }],
  fg_counter: [{}, { value: '12' }],
  info_bar: [{}, { labels: ['WIN', 'BET'], values: ['1,200', '50'] }],
  dialog: [{}, { title: 'NOTICE', buttons: 1, buttonText: ['OK'] }, { buttons: 0, close: false }],
  loading_bar: [{}, { value: 0 }, { part: 'track' }, { part: 'fill' }],
};
