// themes.mjs —— gamekit 主題 token（0.5.0；規格 FR-8）。4 組預設全為本 skill 原創配色，不取自任何遊戲素材。
//
//   ink      描邊色            primary／accent  { main, dark, light }
//   text     { fill, stroke }   bg  [上, 下]     jp  { Grand, Major, Minor, Mini }
//   metal    { gold, silver, bronze }：線性漸層 stops [[offset, color]…]（上亮下暗）
//   inkW     描邊寬（以 256 px 符號為基準）

const METAL = {
  gold: [[0, '#fff6c2'], [0.45, '#f5c542'], [1, '#9c6a12']],
  silver: [[0, '#ffffff'], [0.5, '#c9d3e3'], [1, '#6f7c94']],
  bronze: [[0, '#ffd9b0'], [0.5, '#c1773a'], [1, '#6a3815']],
};

export const THEMES = {
  'royal-gold': {
    ink: '#22103a', inkW: 7,
    primary: { main: '#7a3fc0', dark: '#3a1668', light: '#c7a4ff' },
    accent: { main: '#f2a900', dark: '#9a6200', light: '#ffe48a' },
    text: { fill: '#ffe066', stroke: '#22103a' },
    bg: ['#2b0f4e', '#0b0420'],
    jp: { Grand: '#ff4d5e', Major: '#ff9f1c', Minor: '#36c2ff', Mini: '#7bdc66' },
    metal: METAL,
  },
  'jade-jungle': {
    ink: '#0f2a1c', inkW: 7,
    primary: { main: '#1f9e5a', dark: '#0b5a32', light: '#8ff0b8' },
    accent: { main: '#ffcc33', dark: '#a67c00', light: '#fff1a6' },
    text: { fill: '#fff4b8', stroke: '#0f2a1c' },
    bg: ['#11402a', '#04140c'],
    jp: { Grand: '#ff5a3d', Major: '#ffb21c', Minor: '#2fd0c0', Mini: '#a8e05a' },
    metal: METAL,
  },
  'deep-sea': {
    ink: '#081a33', inkW: 6,
    primary: { main: '#1d7fd1', dark: '#0b3f78', light: '#8fd4ff' },
    accent: { main: '#ff8a3d', dark: '#a8471a', light: '#ffd0a8' },
    text: { fill: '#e8f8ff', stroke: '#081a33' },
    bg: ['#0f4c7a', '#041526'],
    jp: { Grand: '#ff4f7a', Major: '#ffa43a', Minor: '#3ee0d0', Mini: '#9be36a' },
    metal: METAL,
  },
  'neon-night': {
    ink: '#120a24', inkW: 6,
    primary: { main: '#e0389a', dark: '#7a1250', light: '#ffa6d8' },
    accent: { main: '#27e1ff', dark: '#0b7c99', light: '#b8f6ff' },
    text: { fill: '#ffffff', stroke: '#120a24' },
    bg: ['#2a0d45', '#07020f'],
    jp: { Grand: '#ff3b5c', Major: '#ffb000', Minor: '#2ee6ff', Mini: '#8cff6a' },
    metal: METAL,
  },
};
export const DEFAULT_THEME = 'royal-gold';

/** 名稱或物件 → 完整 theme（物件只需給要覆寫的 token；`base` 指定底稿） */
export function theme(t) {
  if (t === undefined) t = DEFAULT_THEME;
  if (typeof t === 'string') {
    if (!THEMES[t]) throw new Error(`未知 theme「${t}」→ 可用：${Object.keys(THEMES).join('、')}，或傳物件覆寫`);
    return { name: t, ...THEMES[t] };
  }
  const base = theme(t.base ?? DEFAULT_THEME);
  const out = { ...base, name: t.name ?? `${base.name}+custom` };
  for (const [k, v] of Object.entries(t)) {
    if (k === 'base' || k === 'name') continue;
    out[k] = v && typeof v === 'object' && !Array.isArray(v) ? { ...base[k], ...v } : v;
  }
  return out;
}

/** 金屬漸層（上亮下暗）→ draw 的漸層物件 */
export const metal = (th, kind = 'gold') => ({ lg: th.metal[kind], x1: 0, y1: 0, x2: 0, y2: 1 });
/** 兩色縱向漸層 */
export const vgrad = (top, bottom) => ({ lg: [[0, top], [1, bottom]], x1: 0, y1: 0, x2: 0, y2: 1 });
