// 物種登錄表（伺服器名 → 體型＋參數）。JS 模組而非 JSON：瀏覽器、node、Vite 都能直接 import，使用方只需複製 scripts/ 一個目錄。
// 第一批：fish-bot 海王2 4.5.6 上場魚種（kiro-cli docs/specs/ark-svg-animation-spec.md §3、design §3）。
// 前綴（SINGLE_／LINE_）與旋風（TWIST_／TWISTER_）由 classify() 處理，這裡只登錄本體。
// size：相對大小建議（給 preview 與沒有自己級距的使用方；fish-bot 用自己的 TIERS）。
// palette：有辨識特徵的物種才指定（main／dark／light 皆 #rrggbb）；沒指定＝名字種子配色。
const P = (main, dark, light) => ({ main, dark, light });

export default {
  // ── fusiform 紡錘魚 ──
  GURNARD: { archetype: 'fusiform', size: 0.6, params: { bodyW: 0.36, stripes: 2 }, palette: P('#d9663a', '#8a3518', '#f4b98a') },
  NEMO: { archetype: 'fusiform', size: 0.45, params: { bodyW: 0.44, stripes: 3 }, palette: P('#ff7a1a', '#2b1a10', '#ffffff') },
  GIANT_NEMO: { archetype: 'fusiform', size: 1.2, params: { bodyW: 0.44, stripes: 3 }, palette: P('#ff7a1a', '#2b1a10', '#ffffff'), variants: ['boss'] },
  BUTTERFLY: { archetype: 'fusiform', size: 0.5, params: { bodyW: 0.6, stripes: 2 }, palette: P('#ffd23f', '#3d3020', '#ffffff') },
  GIANT_BUTTERFLY: { archetype: 'fusiform', size: 1.25, params: { bodyW: 0.6, stripes: 2 }, palette: P('#ffd23f', '#3d3020', '#ffffff'), variants: ['boss'] },
  LION_FISH: { archetype: 'fusiform', size: 0.8, params: { bodyW: 0.42, stripes: 4, fin: 0.9 }, palette: P('#e2483d', '#5a1414', '#fff1e0') },
  ANGLER_FISH: { archetype: 'fusiform', size: 0.85, params: { bodyW: 0.55, stripes: 2 }, palette: P('#5b4a7a', '#241a33', '#c9f0ff') },
  SAIL_FISH: { archetype: 'fusiform', size: 1.0, params: { bodyW: 0.3, bodyLen: 0.76, stripes: 4 } },
  RED_SAIL_FISH: { archetype: 'fusiform', size: 1.05, params: { bodyW: 0.3, bodyLen: 0.76, stripes: 4 }, palette: P('#d8323a', '#6e1219', '#ffb3a8') },
  // ── shark 鯊／鯨 ──
  SHARK: { archetype: 'shark', size: 1.3, palette: P('#6f8a9e', '#33475a', '#e6eef3') },
  SAWTOOTH_SHARK: { archetype: 'shark', size: 1.35, params: { snout: 0.18 }, palette: P('#8a9a6a', '#3f4a2c', '#eef0dc') },
  KILLER_WHALE: { archetype: 'shark', size: 1.5, params: { bodyW: 0.3 }, palette: P('#1b1f27', '#000000', '#ffffff') },
  // ── ray 魟 ──
  MANTARAY: { archetype: 'ray', size: 1.2, palette: P('#3b4a63', '#1a2232', '#d9e4f2') },
  LIGHT_MANTARAY: { archetype: 'ray', size: 1.3, palette: P('#3fb7d9', '#14566b', '#e8fbff'), variants: ['boss', 'glow'] },
  // ── 其他體型 ──
  FLAT_FISH: { archetype: 'flat', size: 0.8, palette: P('#b59a6a', '#5c4a2c', '#efe2c4') },
  PUFFER_FISH: { archetype: 'puffer', size: 0.55, palette: P('#e9c46a', '#7a5a1a', '#fff6d8') },
  GIANT_PUFFER_FISH: { archetype: 'puffer', size: 1.2, palette: P('#e9c46a', '#7a5a1a', '#fff6d8'), variants: ['boss'] },
  LOBSTER: { archetype: 'lobster', size: 0.9, palette: P('#c8402e', '#5e150c', '#ffb8a0') },
  OCTOPUS: { archetype: 'cephalopod', size: 0.9, palette: P('#b04a8c', '#54163e', '#f7c6e6') },
  SMALL_JELLY_FISH: { archetype: 'jelly', size: 0.55, palette: P('#c69cf2', '#6c3fa3', '#f5ecff') },
  FLASH_SHARK: { archetype: 'jelly', size: 1.0, params: { arc: true }, palette: P('#59c8f2', '#1a5a7a', '#e9fbff') }, // 電光水母（伺服器名沿用 SHARK）
  SEA_TURTLE: { archetype: 'turtle', size: 1.0, palette: P('#4a8a5a', '#1e3d26', '#d6efb8') },
  SNAIL_FISH: { archetype: 'snail', size: 0.6, palette: P('#c98a5a', '#5a3218', '#f6dcc0') },  // 海螺魚
  FIRE_DRAGON: { archetype: 'serpent', size: 1.8, palette: P('#d8361e', '#5e0f05', '#ffb43a'), variants: ['boss', 'glow'] },  // Spine 部件魚的替代
  // ── crab 蟹（配件見 classify 規則；這裡固定登錄，讓 --strict 不報未登錄）──
  BOMB_CRAB: { archetype: 'crab', size: 0.9, accessory: 'bomb' },
  LASER_CRAB: { archetype: 'crab', size: 0.9, accessory: 'electrode' },
  DRILL_CRAB: { archetype: 'crab', size: 0.9, accessory: 'drill' },
  SERIAL_DRILL_CRAB: { archetype: 'crab', size: 1.0, accessory: 'drill', variants: ['boss'] },
  WHEEL_CRAB: { archetype: 'crab', size: 0.95, accessory: 'wheel' },
  // ── token 角色徽章（非水生）──
  BISON: { archetype: 'token', size: 1.2, params: { kind: 'bison' }, palette: P('#6b4a2e', '#2e1d10', '#c9a77c') },
  HOYEAH_FISH: { archetype: 'token', size: 1.2, params: { kind: 'monkey' }, variants: ['gold', 'glow'] },   // 金猴爺
  SUN_WUKONG: { archetype: 'token', size: 1.3, params: { kind: 'wukong' }, palette: P('#c8742e', '#5a2e0e', '#ffd28a') , variants: ['glow'] },
  CAT_FISH: { archetype: 'token', size: 1.1, params: { kind: 'cat' }, palette: P('#8c8c99', '#3a3a44', '#e6e6ee') },
};
