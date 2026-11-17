// kit/scene.mjs —— 關鍵字 → 原創遊戲背景（0.11.0）。
//
// 「沙漠 宮殿 夜晚」→ 解析出氛圍（night）＋元素（dunes、palace、moon、stars…）→ 依層次程序產生剪影場景。
// 只產原創幾何：參考圖（網路找的也一樣）只能透過 palette.mjs 取「顏色」，不描形、不留圖（上游公開 repo 的界線）。
// 輸出可為直式（720×1280，預設）或橫式（給 w／h）；texture 用漸層，flat 天空改色帶（Pixi Graphics 無漸層）。
import { fnv1a } from '../draw.mjs';
import { mulberry32 } from '../svg_anim.mjs';
import { rr, mix, starPts, glowFill, sparkle, WHITE } from './util.mjs';

// ── 氛圍配色（角色：天頂／地平線／光暈／遠景／中景／近景／地面／點燈／粒子／月日） ─────────────────
export const MOODS = {
  night: { skyTop: '#0b1033', skyBottom: '#3a2a6e', glow: '#7a5cff', far: '#2a2456', mid: '#17133a', near: '#0b0a1e', ground: '#1a1433', accent: '#ffd56a', particle: '#ffffff', orb: '#fff4c8' },
  dusk: { skyTop: '#2b1d5c', skyBottom: '#ff8a5c', glow: '#ffb36b', far: '#6a3a6e', mid: '#3a1f45', near: '#24122e', ground: '#4a2a3e', accent: '#ffd56a', particle: '#ffe0b0', orb: '#ffd27a' },
  day: { skyTop: '#4aa8ff', skyBottom: '#c9ecff', glow: '#ffffff', far: '#8cbde0', mid: '#4f8a6a', near: '#2f6a4a', ground: '#6cbf5a', accent: '#ffd84a', particle: '#ffffff', orb: '#fff2a8' },
  underwater: { skyTop: '#0a5a8a', skyBottom: '#03182c', glow: '#5fd3ff', far: '#0d3d63', mid: '#0a2a46', near: '#061c30', ground: '#c9a46a', accent: '#ff7aa8', particle: '#bff0ff', orb: '#bff0ff' },
  space: { skyTop: '#05030f', skyBottom: '#1f1245', glow: '#8a5cff', far: '#2a1a5a', mid: '#1a1040', near: '#0e0828', ground: '#2a2050', accent: '#5ff0ff', particle: '#ffffff', orb: '#ff9a5c' },
  snow: { skyTop: '#6fa3d8', skyBottom: '#e6f2ff', glow: '#ffffff', far: '#b4cbe6', mid: '#6b8db8', near: '#38587a', ground: '#f4f8ff', accent: '#ffd56a', particle: '#ffffff', orb: '#ffffff' },
  volcano: { skyTop: '#1a0505', skyBottom: '#7a200c', glow: '#ff5a1a', far: '#3a1010', mid: '#2a0a0a', near: '#160404', ground: '#2a1410', accent: '#ff8a1a', particle: '#ffb35a', orb: '#ffcf7a' },
  jungle: { skyTop: '#1f5a3a', skyBottom: '#a8de90', glow: '#e8ffb0', far: '#3a7a52', mid: '#1d4f33', near: '#0f3320', ground: '#3a6a2a', accent: '#ffd84a', particle: '#e8ff8a', orb: '#fff2a8' },
  oriental: { skyTop: '#2a0610', skyBottom: '#a8283a', glow: '#ffb347', far: '#6a1a26', mid: '#3a0a14', near: '#200408', ground: '#4a1a14', accent: '#ffcf4a', particle: '#ffd27a', orb: '#ffe9b0' },
  candy: { skyTop: '#ff9fd0', skyBottom: '#fff0f8', glow: '#ffffff', far: '#ffc4e6', mid: '#ff8ac4', near: '#e05aa0', ground: '#ffd1ec', accent: '#7ad7ff', particle: '#ffffff', orb: '#fff2a8' },
};
const MOOD_ORDER = ['underwater', 'space', 'volcano', 'snow', 'oriental', 'jungle', 'candy', 'dusk', 'night', 'day'];

// ── 關鍵字表（中英；子字串比對） ────────────────────────────────────────────
const MOOD_WORDS = {
  underwater: ['海底', '深海', '水下', '海洋', 'underwater', 'deep sea', 'ocean', 'reef', '魚'],
  space: ['太空', '宇宙', '星球', '外星', 'space', 'galaxy', 'planet', 'cosmic'],
  volcano: ['火山', '熔岩', '岩漿', 'volcano', 'lava', 'magma'],
  snow: ['雪', '冰', '聖誕', '冬', 'snow', 'ice', 'winter', 'christmas', 'xmas'],
  oriental: ['東方', '中國', '中式', '新年', '燈籠', '元宵', '古風', '財神', 'oriental', 'chinese', 'lantern', 'lunar'],
  jungle: ['叢林', '森林', '雨林', 'jungle', 'forest', 'rainforest'],
  candy: ['糖果', '甜點', '蛋糕', '夢幻', 'candy', 'sweet', 'dessert'],
  dusk: ['黃昏', '夕陽', '日落', '傍晚', 'dusk', 'sunset', 'twilight'],
  night: ['夜', '晚', '月', '星空', 'night', 'moon', 'midnight'],
  day: ['白天', '晴', '日間', 'day', 'sunny', 'morning'],
};
const ELEMENT_WORDS = {
  palace: ['宮殿', '皇宮', '清真', '神燈', '一千零一夜', '阿拉伯', '蘇丹', 'palace', 'arabian', 'sultan', 'mosque', 'genie'],
  pyramid: ['金字塔', '埃及', '法老', 'pyramid', 'egypt', 'pharaoh'],
  temple: ['神殿', '遺跡', '馬雅', '阿茲特克', '古文明', 'temple', 'ruins', 'aztec', 'maya'],
  castle: ['城堡', '王國', '騎士', '童話', 'castle', 'kingdom', 'knight', 'fairy'],
  pagoda: ['寶塔', '佛塔', '日式', '和風', '廟', 'pagoda', 'shrine', 'japanese'],   // 不用單字「塔」：金字塔會誤中
  city: ['城市', '賭城', '都市', '霓虹', 'city', 'vegas', 'casino', 'neon', 'downtown'],
  houses: ['房子', '房屋', '農場', '村莊', '小鎮', '小豬', 'house', 'farm', 'village', 'cottage', 'town'],
  mountains: ['山脈', '高山', '雪山', '群山', '峽谷', 'mountain', 'canyon', 'hill'],   // 不用單字「山」：火山會誤中
  dunes: ['沙漠', '沙丘', '綠洲', 'desert', 'dune', 'oasis', 'sahara'],
  palms: ['棕櫚', '椰子', '綠洲', '熱帶', '海灘', 'palm', 'oasis', 'tropical', 'beach'],
  trees: ['樹', '森林', '叢林', '果園', 'tree', 'forest', 'jungle', 'orchard'],
  coral: ['珊瑚', 'coral', 'reef'],
  seaweed: ['海草', '海藻', 'seaweed', 'kelp'],
  water: ['湖', '河', '海面', '海灘', 'lake', 'river', 'sea', 'beach'],
  lanterns: ['燈籠', '天燈', '元宵', 'lantern'],
  bubbles: ['泡泡', 'bubble'],
  snowflakes: ['雪花', 'snowflake'],
  fireflies: ['螢火蟲', 'firefly'],
  sparkles: ['寶藏', '黃金', '金幣', '財寶', 'treasure', 'gold', 'jackpot'],
  rays: ['光芒', '神光', '光束', 'rays', 'beam', 'divine'],
  clouds: ['雲', 'cloud'],
  moon: ['月', 'moon'],
  sun: ['太陽', '陽光', 'sun'],
  stars: ['星', 'star'],
  volcano: ['火山', 'volcano'],
};
const MOOD_DEFAULTS = {
  night: ['moon', 'stars'], dusk: ['sun', 'clouds'], day: ['sun', 'clouds'], candy: ['clouds', 'sparkles'],
  underwater: ['rays', 'seaweed', 'coral', 'bubbles'], space: ['planet', 'stars'], snow: ['snowflakes', 'mountains', 'pines'],
  volcano: ['volcano', 'embers'], jungle: ['trees', 'fireflies'], oriental: ['moon', 'lanterns'],
};
const LANDMARKS = ['palace', 'pyramid', 'temple', 'castle', 'pagoda', 'city', 'houses'];

/** 關鍵字 → { mood, elements, landmarks, unknown }（unknown＝沒對到任何字的詞，給使用者看漏了什麼） */
export function parseKeywords(keywords) {
  const text = String(keywords ?? '').toLowerCase();
  if (!text.trim()) throw new Error('scene：keywords 必填（例：「沙漠 宮殿 夜晚」「深海 珊瑚」「東方 燈籠 新年」）');
  const hit = (words) => words.some((w) => text.includes(w));
  const mood = MOOD_ORDER.find((m) => hit(MOOD_WORDS[m])) ?? 'day';
  const els = new Set(MOOD_DEFAULTS[mood]);
  for (const [k, words] of Object.entries(ELEMENT_WORDS)) if (hit(words)) els.add(k);
  if (els.has('trees') && mood === 'snow') { els.delete('trees'); els.add('pines'); }
  if (els.has('sun') && ['night', 'oriental'].includes(mood)) els.delete('sun');
  if (els.has('moon') && ['day', 'dusk'].includes(mood)) els.delete('moon');
  const all = [...Object.values(MOOD_WORDS).flat(), ...Object.values(ELEMENT_WORDS).flat()];
  const unknown = text.split(/[\s,，、/]+/).filter((t) => t && !all.some((w) => t.includes(w) || w.includes(t)));
  const landmarks = LANDMARKS.filter((l) => els.has(l)).slice(0, 2);
  return { mood, elements: [...els].sort(), landmarks, unknown };
}

/** 色票：預設依氛圍；可傳部分覆寫（物件）或色碼陣列（依亮度自動分派角色，見 palette.mjs） */
export function scenePalette(mood, override) {
  const base = { ...MOODS[mood] };
  if (Array.isArray(override)) return { ...base, ...assignRoles(override) };
  return { ...base, ...(override ?? {}) };
}
const lum = (h) => { const [r, g, b] = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
const sat = (h) => { const v = [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)); return (Math.max(...v) - Math.min(...v)) / 255; };
/** 色碼陣列 → 場景角色（暗→近景，亮→粒子；最飽和→點燈） */
export function assignRoles(hexes) {
  const cs = [...new Set(hexes.map((h) => h.toLowerCase()))].filter((h) => /^#[0-9a-f]{6}$/.test(h));
  if (cs.length < 3) throw new Error('palette：至少要 3 個 #rrggbb 色碼');
  const byL = [...cs].sort((a, b) => lum(a) - lum(b)), pick = (f) => byL[Math.min(byL.length - 1, Math.round(f * (byL.length - 1)))];
  const accent = [...cs].sort((a, b) => sat(b) - sat(a))[0];
  return { near: pick(0), mid: pick(0.15), ground: pick(0.25), skyTop: pick(0.3), far: pick(0.45), skyBottom: pick(0.65), glow: pick(0.85), orb: pick(1), particle: pick(1), accent };
}

// ── 元素產生器（W、H、地平線 hy、色票 P、亂數 rnd） ────────────────────────────
const onion = (x, y, r) => ({ k: 'path', d: [['M', x - r, y], ['C', x - r, y - r * 1.25, x - r * 0.15, y - r * 1.45, x, y - r * 2.1], ['C', x + r * 0.15, y - r * 1.45, x + r, y - r * 1.25, x + r, y], ['Z']] });
const lit = (x, y, w, h, P) => ({ k: 'path', d: [['M', x, y + h], ['L', x, y + w / 2], ['Q', x, y, x + w / 2, y], ['Q', x + w, y, x + w, y + w / 2], ['L', x + w, y + h], ['Z']], fill: P.accent, op: 0.85 });

const G = {
  sky: ({ W, H, P, profile }) => {
    if (profile !== 'flat') return [{ k: 'polygon', pts: [[0, 0], [W, 0], [W, H], [0, H]], fill: { lg: [[0, P.skyTop], [0.6, P.skyBottom], [1, P.skyBottom]], x1: 0, y1: 0, x2: 0, y2: 1 } }];
    return Array.from({ length: 10 }, (_, i) => ({ k: 'polygon', pts: [[0, (H * 0.62 * i) / 10], [W, (H * 0.62 * i) / 10], [W, i === 9 ? H : (H * 0.62 * (i + 1)) / 10 + 1], [0, i === 9 ? H : (H * 0.62 * (i + 1)) / 10 + 1]], fill: mix(P.skyTop, P.skyBottom, i / 9) }));
  },
  glow: ({ W, hy, P }) => [{ k: 'circle', cx: W / 2, cy: hy * 0.6, r: W * 0.7, fill: glowFill(P.glow, 0.4) }],
  moon: ({ W, H, P }) => { const x = W * 0.76, y = H * 0.13, r = Math.min(W, H) * 0.075; return [{ k: 'circle', cx: x, cy: y, r: r * 3.2, fill: glowFill(P.orb, 0.35) }, { k: 'circle', cx: x, cy: y, r, fill: P.orb }, { k: 'circle', cx: x - r * 0.3, cy: y - r * 0.15, r: r * 0.22, fill: P.near, op: 0.12 }, { k: 'circle', cx: x + r * 0.35, cy: y + r * 0.3, r: r * 0.15, fill: P.near, op: 0.12 }]; },
  sun: ({ W, H, P, mood }) => { const x = W * 0.72, y = mood === 'dusk' ? H * 0.42 : H * 0.12, r = Math.min(W, H) * 0.09; return [{ k: 'circle', cx: x, cy: y, r: r * 3, fill: glowFill(P.orb, 0.5) }, { k: 'circle', cx: x, cy: y, r, fill: P.orb }]; },
  planet: ({ W, H, P }) => { const x = W * 0.72, y = H * 0.16, r = Math.min(W, H) * 0.1; return [{ k: 'circle', cx: x, cy: y, r: r * 2.4, fill: glowFill(P.orb, 0.3) }, { k: 'circle', cx: x, cy: y, r, fill: { rg: [[0, mix(P.orb, WHITE, 0.4)], [1, mix(P.orb, P.near, 0.4)]], cx: 0.35, cy: 0.35, r: 0.7 } }, { k: 'ellipse', cx: x, cy: y, rx: r * 1.8, ry: r * 0.4, rot: -15, fill: 'none', stroke: P.particle, sw: 4, op: 0.6 }]; },
  stars: ({ W, hy, P, rnd }) => Array.from({ length: 46 }, (_, i) => { const x = rnd() * W, y = rnd() * hy * 0.8; return i % 8 ? { k: 'circle', cx: x, cy: y, r: 1.2 + rnd() * 2.2, fill: P.particle, op: 0.4 + rnd() * 0.5 } : sparkle(x, y, 6 + rnd() * 6, P.particle, 0.9); }),
  clouds: ({ W, H, P, rnd, mood }) => { const c = mood === 'dusk' ? mix(P.orb, WHITE, 0.4) : WHITE; return Array.from({ length: 4 }, (_, i) => { const x = W * (0.12 + i * 0.26) + rnd() * 40, y = H * (0.08 + rnd() * 0.2), s = 40 + rnd() * 30; return [[0, 0, 1], [-0.9, 0.25, 0.7], [0.9, 0.25, 0.75], [0.3, -0.35, 0.8]].map(([dx, dy, k]) => ({ k: 'ellipse', cx: x + dx * s, cy: y + dy * s, rx: s * k, ry: s * k * 0.62, fill: c, op: 0.75 })); }).flat(); },
  mountains: ({ W, hy, P, rnd }) => [0, 1].map((L) => { const n = 7, pts = [[0, hy]]; for (let i = 0; i <= n; i++) pts.push([(W * i) / n, hy - (L ? 0.1 : 0.18) * hy - rnd() * hy * (L ? 0.08 : 0.14)]); pts.push([W, hy]); return { k: 'polygon', pts, fill: L ? mix(P.far, P.mid, 0.5) : P.far, op: 0.95 }; }),
  volcano: ({ W, hy, P }) => { const x = W * 0.5, top = hy * 0.55; return [{ k: 'circle', cx: x, cy: top, r: W * 0.25, fill: glowFill(P.glow, 0.5) }, { k: 'polygon', pts: [[x - W * 0.42, hy], [x - W * 0.08, top], [x + W * 0.08, top], [x + W * 0.42, hy]], fill: P.far }, { k: 'polygon', pts: [[x - W * 0.08, top], [x - W * 0.03, top + hy * 0.12], [x + W * 0.02, top + hy * 0.06], [x + W * 0.06, top + hy * 0.14], [x + W * 0.08, top]], fill: P.accent }, ...[0, 1, 2].map((i) => ({ k: 'circle', cx: x + (i - 1) * 30, cy: top - 40 - i * 36, r: 30 + i * 12, fill: P.mid, op: 0.5 }))]; },
  // 金字塔群：兩側小的先畫、主塔最後（疊在前）；偏移以畫面寬為單位
  pyramid: ({ W, hy, P }, at) => [[-0.3, 0.62, 0.3], [0.3, 0.55, 0.28], [0, 1, 0.34]].flatMap(([dx, k, hw]) => { const x = at.x + dx * W * at.k, b = hw * W * k * at.k, top = hy - b * 1.15; return [{ k: 'polygon', pts: [[x - b, hy], [x, top], [x + b, hy]], fill: P.mid }, { k: 'polygon', pts: [[x, top], [x + b, hy], [x + b * 0.25, hy]], fill: P.near, op: 0.6 }]; }),
  palace: ({ hy, P }, at) => {
    const { x, s } = at, base = hy, bw = 260 * s, bh = 120 * s, r = 62 * s, out = [];
    out.push({ k: 'polygon', pts: [[x - bw / 2, base], [x - bw / 2, base - bh], [x + bw / 2, base - bh], [x + bw / 2, base]], fill: P.mid });
    out.push({ ...onion(x, base - bh, r), fill: P.mid });
    for (const sg of [-1, 1]) {
      const mx = x + sg * (bw / 2 + 26 * s);
      out.push({ k: 'polygon', pts: [[mx - 13 * s, base], [mx - 13 * s, base - 270 * s], [mx + 13 * s, base - 270 * s], [mx + 13 * s, base]], fill: P.mid }, { ...onion(mx, base - 270 * s, 18 * s), fill: P.mid });
      out.push({ ...onion(x + sg * bw * 0.32, base - bh, 32 * s), fill: P.mid });
    }
    out.push({ k: 'polygon', pts: [[x - 2 * s, base - bh - r * 2.1], [x + 2 * s, base - bh - r * 2.1], [x + 2 * s, base - bh - r * 2.1 - 24 * s], [x - 2 * s, base - bh - r * 2.1 - 24 * s]], fill: P.mid });
    for (let i = -2; i <= 2; i++) out.push(lit(x + i * 44 * s - 9 * s, base - bh * 0.7, 18 * s, 34 * s, P));
    return out;
  },
  temple: ({ hy, P }, at) => { const { x, s } = at, out = []; for (let i = 0; i < 5; i++) { const w = (300 - i * 50) * s, h = 34 * s; out.push({ k: 'polygon', pts: [[x - w / 2, hy - i * h], [x - w / 2, hy - (i + 1) * h], [x + w / 2, hy - (i + 1) * h], [x + w / 2, hy - i * h]], fill: i % 2 ? P.mid : mix(P.mid, P.far, 0.3) }); } out.push({ k: 'polygon', pts: [[x - 40 * s, hy - 170 * s], [x - 40 * s, hy - 230 * s], [x + 40 * s, hy - 230 * s], [x + 40 * s, hy - 170 * s]], fill: P.mid }, lit(x - 12 * s, hy - 222 * s, 24 * s, 46 * s, P)); return out; },
  castle: ({ hy, P }, at) => { const { x, s } = at, out = [], tower = (tx, h, w) => { out.push({ k: 'polygon', pts: [[tx - w / 2, hy], [tx - w / 2, hy - h], [tx + w / 2, hy - h], [tx + w / 2, hy]], fill: P.mid }, { k: 'polygon', pts: [[tx - w / 2 - 6 * s, hy - h], [tx, hy - h - w * 1.3], [tx + w / 2 + 6 * s, hy - h]], fill: P.near }, lit(tx - 7 * s, hy - h * 0.7, 14 * s, 24 * s, P)); }; out.push({ k: 'polygon', pts: [[x - 140 * s, hy], [x - 140 * s, hy - 110 * s], [x + 140 * s, hy - 110 * s], [x + 140 * s, hy]], fill: P.mid }); for (let i = -3; i <= 3; i++) out.push({ k: 'polygon', pts: [[x + i * 40 * s - 12 * s, hy - 110 * s], [x + i * 40 * s - 12 * s, hy - 128 * s], [x + i * 40 * s + 12 * s, hy - 128 * s], [x + i * 40 * s + 12 * s, hy - 110 * s]], fill: P.mid }); tower(x - 150 * s, 200 * s, 56 * s); tower(x + 150 * s, 200 * s, 56 * s); tower(x, 260 * s, 72 * s); out.push({ k: 'path', d: [['M', x - 30 * s, hy], ['L', x - 30 * s, hy - 50 * s], ['Q', x, hy - 80 * s, x + 30 * s, hy - 50 * s], ['L', x + 30 * s, hy], ['Z']], fill: P.near }); return out; },
  pagoda: ({ hy, P }, at) => { const { x, s } = at, out = []; let y = hy; for (let i = 0; i < 4; i++) { const w = (150 - i * 26) * s, h = 46 * s, ew = w * 0.8 + 30 * s; out.push({ k: 'polygon', pts: [[x - w / 2, y], [x - w / 2, y - h], [x + w / 2, y - h], [x + w / 2, y]], fill: P.mid }, lit(x - 9 * s, y - h * 0.8, 18 * s, 26 * s, P)); y -= h; out.push({ k: 'path', d: [['M', x - ew, y + 6 * s], ['Q', x - ew * 0.6, y - 2 * s, x - w * 0.35, y - 22 * s], ['L', x + w * 0.35, y - 22 * s], ['Q', x + ew * 0.6, y - 2 * s, x + ew, y + 6 * s], ['Z']], fill: P.near }); y -= 18 * s; } out.push({ k: 'polygon', pts: [[x - 3 * s, y], [x - 3 * s, y - 50 * s], [x + 3 * s, y - 50 * s], [x + 3 * s, y]], fill: P.near }); return out; },
  city: ({ hy, P, rnd }, at) => { const { x, s } = at, out = [], win = []; let bx = x - 300 * s; while (bx < x + 300 * s) { const w = (40 + rnd() * 50) * s, h = (120 + rnd() * 260) * s; out.push({ k: 'polygon', pts: [[bx, hy], [bx, hy - h], [bx + w, hy - h], [bx + w, hy]], fill: rnd() < 0.5 ? P.mid : mix(P.mid, P.far, 0.4) }); for (let wy = hy - h + 14 * s; wy < hy - 14 * s; wy += 22 * s) for (let wx = bx + 8 * s; wx < bx + w - 12 * s; wx += 14 * s) if (rnd() < 0.45) win.push(['M', wx, wy], ['L', wx + 6 * s, wy], ['L', wx + 6 * s, wy + 9 * s], ['L', wx, wy + 9 * s], ['Z']); bx += w + 4 * s; } out.push({ k: 'path', d: win, fill: P.accent, op: 0.8 }); return out; },
  houses: ({ hy, P, rnd }, at) => { const { x, s } = at, out = []; for (let i = -1; i <= 1; i++) { const hx = x + i * 150 * s, w = (100 + rnd() * 30) * s, h = (70 + rnd() * 20) * s; out.push({ k: 'polygon', pts: [[hx - w / 2, hy], [hx - w / 2, hy - h], [hx + w / 2, hy - h], [hx + w / 2, hy]], fill: P.mid }, { k: 'polygon', pts: [[hx - w / 2 - 12 * s, hy - h], [hx, hy - h - w * 0.55], [hx + w / 2 + 12 * s, hy - h]], fill: P.near }, lit(hx - w * 0.3, hy - h * 0.7, 20 * s, 22 * s, P), { k: 'polygon', pts: [[hx + w * 0.1, hy], [hx + w * 0.1, hy - h * 0.55], [hx + w * 0.3, hy - h * 0.55], [hx + w * 0.3, hy]], fill: P.near }); } return out; },
  dunes: ({ W, H, hy, P, mood }) => { const sand = mix('#d8a860', P.near, ['night', 'oriental', 'space'].includes(mood) ? 0.62 : mood === 'dusk' ? 0.35 : 0.08); return [0, 1, 2].map((i) => { const y = hy + (H - hy) * (i * 0.28); return { k: 'path', d: [['M', 0, y + 40], ['Q', W * (0.25 + i * 0.1), y - 50, W * 0.55, y + 20], ['Q', W * 0.8, y + 70, W, y], ['L', W, H], ['L', 0, H], ['Z']], fill: mix(sand, P.near, i * 0.22) }; }); },
  ground: ({ W, H, hy, P, mood }) => { const c = mood === 'underwater' ? mix(P.ground, P.near, 0.45) : P.ground; return [{ k: 'path', d: [['M', 0, hy], ['Q', W * 0.3, hy - 24, W * 0.55, hy + 6], ['Q', W * 0.8, hy + 30, W, hy - 4], ['L', W, H], ['L', 0, H], ['Z']], fill: c }, { k: 'path', d: [['M', 0, hy + (H - hy) * 0.45], ['Q', W * 0.4, hy + (H - hy) * 0.3, W, hy + (H - hy) * 0.5], ['L', W, H], ['L', 0, H], ['Z']], fill: mix(c, P.near, 0.35) }]; },
  water: ({ W, H, hy, P }) => [{ k: 'polygon', pts: [[0, hy], [W, hy], [W, hy + (H - hy) * 0.3], [0, hy + (H - hy) * 0.3]], fill: mix(P.skyBottom, P.near, 0.4) }, ...[0.06, 0.13, 0.21].map((f, i) => ({ k: 'polygon', pts: [[W * (0.3 + i * 0.05), hy + (H - hy) * f], [W * (0.7 - i * 0.05), hy + (H - hy) * f], [W * (0.68 - i * 0.05), hy + (H - hy) * f + 4], [W * (0.32 + i * 0.05), hy + (H - hy) * f + 4]], fill: P.orb, op: 0.35 }))],
  palms: ({ W, hy, P }) => [0.1, 0.88].flatMap((fx, i) => { const x = W * fx, top = hy - 260 + i * 50, lean = i ? -40 : 40; const fr = [-150, -110, -70, -30, 10].map((a) => { const r = (a * Math.PI) / 180, ex = x + lean + Math.cos(r) * 110 * (i ? -1 : 1), ey = top + Math.sin(r) * 60 + 70; return { k: 'path', d: [['M', x + lean, top], ['Q', (x + lean + ex) / 2, top - 40, ex, ey], ['Q', (x + lean + ex) / 2, top - 10, x + lean, top + 8], ['Z']], fill: P.near }; }); return [{ k: 'path', d: [['M', x - 12, hy + 20], ['Q', x + lean * 0.3, (hy + top) / 2, x + lean - 6, top], ['L', x + lean + 6, top], ['Q', x + lean * 0.3 + 12, (hy + top) / 2, x + 12, hy + 20], ['Z']], fill: P.near }, ...fr]; }),
  trees: ({ W, hy, P, rnd }) => Array.from({ length: 6 }, (_, i) => { const x = W * (i < 3 ? 0.03 + i * 0.1 : 0.72 + (i - 3) * 0.1), s = 0.8 + rnd() * 0.5, y = hy + 10; return [{ k: 'polygon', pts: [[x - 8 * s, y], [x - 6 * s, y - 120 * s], [x + 6 * s, y - 120 * s], [x + 8 * s, y]], fill: P.near }, ...[[0, -150, 60], [-38, -120, 44], [38, -118, 46], [0, -190, 42]].map(([dx, dy, r]) => ({ k: 'circle', cx: x + dx * s, cy: y + dy * s, r: r * s, fill: mix(P.mid, P.near, 0.3) }))]; }).flat(),
  pines: ({ W, hy, P, rnd }) => Array.from({ length: 7 }, (_, i) => { const x = W * (i < 3 ? 0.04 + i * 0.09 : 0.68 + (i - 3) * 0.09), s = 0.7 + rnd() * 0.6, y = hy + 8; return [0, 1, 2].map((k) => ({ k: 'polygon', pts: [[x - (70 - k * 16) * s, y - k * 55 * s], [x, y - (k * 55 + 110) * s], [x + (70 - k * 16) * s, y - k * 55 * s]], fill: k === 2 ? mix(P.near, WHITE, 0.15) : P.near })); }).flat(),
  coral: ({ W, H, P }) => { const out = [], branch = (x, y, s, c) => { for (const pts of [[[0, 0], [-8, -40], [-24, -62]], [[0, 0], [6, -50], [-2, -80]], [[0, 0], [18, -34], [34, -52]]]) out.push({ k: 'polyline', pts: pts.map(([a, b]) => [x + a * s, y + b * s]), stroke: c, sw: 10 * s }); for (const [a, b] of [[-24, -62], [-2, -80], [34, -52]]) out.push({ k: 'circle', cx: x + a * s, cy: y + b * s, r: 7 * s, fill: c }); }; branch(W * 0.12, H * 0.95, 2.2, P.accent); branch(W * 0.86, H * 0.97, 2.6, mix(P.accent, P.glow, 0.4)); branch(W * 0.3, H, 1.4, mix(P.accent, P.near, 0.3)); return out; },
  seaweed: ({ W, H, P }) => [0.06, 0.22, 0.7, 0.94].map((fx, i) => { const x = W * fx, h = H * (0.22 + (i % 2) * 0.08); return { k: 'path', d: [['M', x - 8, H], ['C', x - 40, H - h * 0.3, x + 40, H - h * 0.6, x, H - h], ['C', x + 46, H - h * 0.6, x - 26, H - h * 0.3, x + 8, H], ['Z']], fill: mix(P.near, '#2f9a6a', 0.5), op: 0.9 }; }),
  rays: ({ W, H, P }) => Array.from({ length: 5 }, (_, i) => { const x = W * (0.12 + i * 0.19); return { k: 'polygon', pts: [[x, 0], [x + W * 0.07, 0], [x + W * 0.2, H * 0.75], [x + W * 0.04, H * 0.75]], fill: P.glow, op: 0.07 }; }),
  lanterns: ({ W, hy, P, rnd }) => Array.from({ length: 10 }, () => { const x = W * (0.05 + rnd() * 0.9), y = hy * (0.15 + rnd() * 0.7), s = 0.6 + rnd() * 0.7; return [{ k: 'circle', cx: x, cy: y, r: 34 * s, fill: glowFill(P.accent, 0.45) }, { k: 'path', d: rr(x - 14 * s, y - 18 * s, 28 * s, 36 * s, 10 * s), fill: '#d8303a' }, { k: 'polygon', pts: [[x - 9 * s, y - 20 * s], [x + 9 * s, y - 20 * s], [x + 9 * s, y - 17 * s], [x - 9 * s, y - 17 * s]], fill: P.accent }, { k: 'polygon', pts: [[x - 9 * s, y + 17 * s], [x + 9 * s, y + 17 * s], [x + 9 * s, y + 20 * s], [x - 9 * s, y + 20 * s]], fill: P.accent }]; }).flat(),
  bubbles: ({ W, H, P, rnd }) => Array.from({ length: 22 }, () => ({ k: 'circle', cx: rnd() * W, cy: H * 0.1 + rnd() * H * 0.75, r: 3 + rnd() * 10, fill: 'none', stroke: P.particle, sw: 1.5, op: 0.35 })),
  snowflakes: ({ W, H, P, rnd }) => Array.from({ length: 40 }, (_, i) => (i % 6 ? { k: 'circle', cx: rnd() * W, cy: rnd() * H * 0.9, r: 1.5 + rnd() * 3, fill: P.particle, op: 0.8 } : sparkle(rnd() * W, rnd() * H * 0.8, 8, P.particle, 0.9))),
  fireflies: ({ W, H, hy, P, rnd }) => Array.from({ length: 16 }, () => { const x = rnd() * W, y = hy * 0.6 + rnd() * (H - hy * 0.6) * 0.6; return [{ k: 'circle', cx: x, cy: y, r: 9, fill: glowFill(P.particle, 0.6) }, { k: 'circle', cx: x, cy: y, r: 2, fill: P.particle }]; }).flat(),
  embers: ({ W, H, P, rnd }) => Array.from({ length: 26 }, () => ({ k: 'circle', cx: rnd() * W, cy: rnd() * H * 0.85, r: 1.5 + rnd() * 3, fill: P.particle, op: 0.5 + rnd() * 0.5 })),
  sparkles: ({ W, H, P, rnd }) => Array.from({ length: 12 }, () => sparkle(rnd() * W, H * 0.1 + rnd() * H * 0.7, 6 + rnd() * 10, P.accent, 0.85)),
};
export const SCENE_ELEMENTS = Object.keys(G).filter((k) => !['sky', 'glow', 'ground'].includes(k));

const scene = {
  category: 'bg',
  build(s, th) {
    const W = s.w ?? 720, H = s.h ?? 1280;
    const r = parseKeywords(s.keywords);
    const elements = s.elements ? [...new Set(s.elements)] : r.elements;
    const bad = elements.filter((e) => !G[e] || ['sky', 'glow', 'ground'].includes(e));
    if (bad.length) throw new Error(`scene：未知元素 ${bad.join('、')} → 可用：${SCENE_ELEMENTS.join('、')}`);
    const has = (e) => elements.includes(e);
    const P = scenePalette(r.mood, s.palette), hy = H * (W > H ? 0.64 : 0.68);
    const ctx = { W, H, hy, P, mood: r.mood, profile: s.profile, rnd: mulberry32(fnv1a(`${s.keywords}|${s.seed ?? 0}|${W}x${H}`)) };
    const landmarks = LANDMARKS.filter(has).slice(0, 2);
    const at = landmarks.length === 2 ? [{ x: W * 0.38, s: W / 720, k: 1 }, { x: W * 0.8, s: W / 1100, k: 0.6 }] : [{ x: W / 2, s: W / 720, k: 1 }];
    const L = (names) => names.filter(has).flatMap((n) => G[n](ctx));
    const parts = [
      ...G.sky(ctx), ...G.glow(ctx),
      ...L(['rays', 'moon', 'sun', 'planet', 'stars', 'clouds', 'mountains', 'volcano']),
      ...landmarks.flatMap((l, i) => G[l](ctx, at[i])),
      ...(has('dunes') ? G.dunes(ctx) : has('water') ? [...G.water(ctx), ...G.ground({ ...ctx, hy: hy + (H - hy) * 0.3 })] : G.ground(ctx)),
      ...L(['palms', 'trees', 'pines', 'seaweed', 'coral', 'lanterns', 'bubbles', 'snowflakes', 'fireflies', 'embers', 'sparkles']),
    ];
    // 上下暗角（UI 疊上去要看得清楚）：色取 theme，換 theme 也跟著變
    if (s.vignette !== false) {
      const v = th.bg[1];
      parts.push(...(s.profile === 'flat'
        ? [0, 1, 2].flatMap((i) => [{ k: 'polygon', pts: [[0, 0], [W, 0], [W, H * 0.04 * (3 - i)], [0, H * 0.04 * (3 - i)]], fill: v, op: 0.12 }, { k: 'polygon', pts: [[0, H - H * 0.05 * (3 - i)], [W, H - H * 0.05 * (3 - i)], [W, H], [0, H]], fill: v, op: 0.14 }])
        : [{ k: 'polygon', pts: [[0, 0], [W, 0], [W, H * 0.14], [0, H * 0.14]], fill: { lg: [[0, v, 0.45], [1, v, 0]], x1: 0, y1: 0, x2: 0, y2: 1 } },
          { k: 'polygon', pts: [[0, H * 0.82], [W, H * 0.82], [W, H], [0, H]], fill: { lg: [[0, v, 0], [1, v, 0.55]], x1: 0, y1: 0, x2: 0, y2: 1 } }]));
    }
    return { w: W, h: H, alias: s.alias ?? 'bg_scene', parts, info: { mood: r.mood, elements, landmarks, unknown: r.unknown } };
  },
};

export const SCENE_KINDS = { scene };
export const SCENE_SAMPLES = {
  scene: [
    { keywords: '沙漠 宮殿 夜晚 神燈' }, { keywords: '深海 珊瑚 海草' }, { keywords: '東方 燈籠 寶塔 新年' },
    { keywords: '農場 房子 白天' }, { keywords: '叢林 神殿 遺跡' }, { keywords: '城堡 雪 聖誕' },
    { keywords: '賭城 夜 霓虹' }, { keywords: '火山 熔岩' }, { keywords: '太空 星球' }, { keywords: '埃及 金字塔 黃昏' },
    { keywords: 'tropical beach palm sunset', w: 1280, h: 720 },
  ],
};
