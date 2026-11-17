#!/usr/bin/env node
// gamekit.mjs —— 魚機／老虎機必要圖元素（0.5.0 起；規格 kiro-cli docs/specs/ark-svg-animation-spec.md §7）。
//
// 函式庫：
//   import { asset, KINDS } from './gamekit.mjs';
//   asset('label', { text: 'BIG WIN', size: 72, theme: 'royal-gold' })    // → { svg, meta }
//   asset('royal', { letter: 'K', theme: 'deep-sea', profile: 'flat' })    // flat＝PixiJS Graphics.svg() 可直接解析
//   asset('win_banner', { tier: 'mega' })                                  // 動畫 kind → { svg（第 0 格）, frames, meta }
// 每個 kind：build(spec, theme, t?) → { w, h, L?, parts, anchor?, alias }；座標 × L（符號以 256 為基準、L＝size/256）。
// 動畫 kind 另有 anim: { frames, loop? }：循環（預設）第 i 格 t＝i/n；一次性（loop:false，例：網張開）t＝i/(n-1)，最後一格＝t＝1。
// 零相依、確定性：同參數＋同版號 → 逐位元組相同；不接受外部圖片、不輸出 <text>（字一律走 glyphs.mjs 轉 path）。
import { draw, num } from './draw.mjs';
import { measure } from './glyphs.mjs';
import { theme, metal, THEMES } from './themes.mjs';
import { VERSION } from './svg_anim.mjs';
import { plateParts, PLATES, BOLD } from './kit/util.mjs';
import { SLOT_KINDS, SLOT_SAMPLES } from './kit/slot.mjs';
import { UI_KINDS, UI_SAMPLES } from './kit/ui.mjs';
import { FX_KINDS, FX_SAMPLES } from './kit/fx.mjs';
import { FISH_KINDS, FISH_SAMPLES } from './kit/fish.mjs';
import { HUD_KINDS, HUD_SAMPLES } from './kit/hud.mjs';
import { SCENE_KINDS, SCENE_SAMPLES } from './kit/scene.mjs';

export { THEMES };

/** 尺寸預算（bytes，單張／單格）—— verify_svg 用；flat 另乘 2（執行期解析、不走網路） */
export const BUDGET = { frame: 4096, symbol: 6144, ui: 8192, text: 8192, fx: 12288, bg: 16384 };

/** 文字顏色：'gold'／'silver'／'bronze' → 金屬漸層；其他照用 */
const textFill = (v, th) => (v === undefined ? th.text.fill : th.metal[v] ? metal(th, v) : v);

const BASE_KINDS = {
  /** 描邊字（橫幅、倍率、按鈕字）：size＝字高 px */
  label: {
    category: 'text',
    build(s, th) {
      const text = String(s.text ?? '');
      if (!text.trim()) throw new Error('label：text 必填');
      const size = s.size ?? 64, u = size / 6, weight = s.weight ?? BOLD;
      const outline = s.outline ?? u * 0.55, padX = u * weight * 0.5 + outline + 2, padY = padX;
      const w = Math.ceil(measure(text, { spacing: s.spacing ?? 2, weight }) * u + padX * 2), h = Math.ceil(size + padY * 2);
      return {
        w, h, alias: s.alias ?? `label_${text.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'x'}`,
        parts: [{ k: 'text', str: text, x: w / 2, y: h / 2, size, weight, align: 'center', spacing: s.spacing, fill: textFill(s.fill, th), ink: s.ink ?? th.text.stroke, outline }],
      };
    },
  },
  /** 符號底板：arch／circle／shield／diamond；color＝'primary'｜'accent'｜{ main, dark, light } */
  plate: {
    category: 'symbol',
    build(s, th) {
      const size = s.size ?? 256, shape = s.shape ?? 'arch';
      return { w: size, h: size, L: size / 256, alias: s.alias ?? `plate_${shape}`, parts: plateParts(th, shape, s.color ?? 'primary', s.rim ?? 'gold') };
    },
  },
};

export const KINDS = { ...BASE_KINDS, ...SLOT_KINDS, ...UI_KINDS, ...HUD_KINDS, ...FX_KINDS, ...FISH_KINDS, ...SCENE_KINDS };

function render(b, th, profile) {
  const ctx = { L: b.L ?? 1, pal: { white: '#ffffff', eye: th.ink, ...th.primary }, k: 0, id: 'k', gid: 'k', defs: new Map(), profile };
  const { body, defs } = draw(b.parts.filter(Boolean), ctx);   // null＝空槽（boldText 收到空字串）
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${num(b.w)} ${num(b.h)}" width="${num(b.w)}" height="${num(b.h)}">${profile === 'flat' ? '' : defs}${body}</svg>`;
}

function prep(kind, spec) {
  const def = KINDS[kind];
  if (!def) throw new Error(`未知 kind「${kind}」→ 可用：${Object.keys(KINDS).join('、')}`);
  for (const k of ['image', 'href', 'src']) if (k in spec) throw new Error(`asset：不接受外部圖片參數「${k}」（只產原創向量圖）`);
  return { def, th: theme(spec.theme), profile: spec.profile === 'flat' ? 'flat' : 'texture' };
}

/**
 * 產生一張 gamekit 素材（動畫 kind 另回 frames）。
 * @param {string} kind  KINDS 的鍵
 * @param {object} spec  各 kind 的參數＋ theme（名稱或覆寫物件）＋ profile（'texture'｜'flat'）＋ alias ＋ frames（動畫格數）
 * @returns {{ svg: string, frames?: string[], meta: { version, kind, alias, category, w, h, anchor, theme, profile, frames? } }}
 */
export function asset(kind, spec = {}) {
  const { def, th, profile } = prep(kind, spec);
  const n = def.anim ? Math.max(2, spec.frames ?? def.anim.frames) : 0, loop = def.anim?.loop !== false;
  const builds = def.anim ? Array.from({ length: n }, (_, i) => def.build(spec, th, loop ? i / n : i / (n - 1))) : [def.build(spec, th, 0)];
  const b = builds[0], svgs = builds.map((x) => render(x, th, profile));
  const meta = { version: VERSION, kind, alias: b.alias, category: def.category, w: Number(num(b.w)), h: Number(num(b.h)), anchor: b.anchor ?? [0.5, 0.5], theme: th.name, profile, ...(b.info ? { recipe: b.info } : {}) };
  return def.anim ? { svg: svgs[0], frames: svgs, meta: { ...meta, frames: n, loop } } : { svg: svgs[0], meta };
}

/** 動畫 kind 在任意相位 t 的單格（verify 用 t＝1 檢查循環接縫） */
export function assetPhase(kind, spec, t) {
  const { def, th, profile } = prep(kind, spec);
  return render(def.build(spec, th, t), th, profile);
}

/** verify 與預覽用的樣本：每個 kind 至少涵蓋所有選項 */
export const SAMPLES = {
  label: [{ text: 'BIG WIN', size: 72 }, { text: 'FREE GAMES', size: 48, fill: 'gold' }, { text: 'X10', size: 64, fill: 'silver' },
    { text: 'ABCDEFGHIJKLM', size: 40 }, { text: 'NOPQRSTUVWXYZ', size: 40 }, { text: '0123456789', size: 40 }, { text: '+-×.,!?:/%$¥#', size: 40 }],
  plate: Object.keys(PLATES).flatMap((shape) => [{ shape }, { shape, color: 'accent', rim: 'silver', size: 200 }]),
  ...SLOT_SAMPLES, ...UI_SAMPLES, ...HUD_SAMPLES, ...FX_SAMPLES, ...FISH_SAMPLES, ...SCENE_SAMPLES,
};

/**
 * 覆蓋率對照（計畫 AC-G4）：aidev 兩款老虎機的素材別名 → kit 的 kind。
 * kind 為 null＝遊戲專屬（角色、Logo、題材物件），刻意不收進 kit，由各專案自己畫。
 */
export const COVERAGE = [
  ...['bg_main'].map((a) => ['magic-lamp', a, 'bg', { motif: 'stars' }]),
  ['magic-lamp', 'chest_gold', 'icon', { name: 'chest', metal: 'gold' }], ['magic-lamp', 'chest_silver', 'icon', { name: 'chest', metal: 'silver' }],
  ['magic-lamp', 'chest_wood', 'icon', { name: 'chest', metal: 'bronze' }],
  ['magic-lamp', 'fg_banner', 'fg_banner', {}],
  ...[1, 2, 3].map((l) => ['magic-lamp', `frame_${l}`, 'frame', { level: l }]),
  ...['Grand', 'Major', 'Minor', 'Mini'].map((t) => ['magic-lamp', `jp_${t}`, 'jp_plate', { tier: t }]),
  ['magic-lamp', 'logo', null, '遊戲 Logo（專屬）'],
  ['magic-lamp', 'reel_bg', 'reel_bg', {}], ['magic-lamp', 'reel_frame', 'reel_frame', {}],
  ...['A', 'K', 'Q', 'J'].map((l) => ['magic-lamp', `sym_${l}${l}`, 'royal', { letter: l }]),
  ['magic-lamp', 'sym_M1', 'icon', { name: 'crown' }], ['magic-lamp', 'sym_M2', null, '魔毯（題材物件）'], ['magic-lamp', 'sym_M3', null, '彎刀（題材物件）'],
  ['magic-lamp', 'sym_M4', 'icon', { name: 'trophy' }], ['magic-lamp', 'sym_M5', 'icon', { name: 'gem' }],
  ['magic-lamp', 'sym_SC', 'badge', { type: 'scatter' }], ['magic-lamp', 'sym_WW', 'badge', { type: 'wild' }],
  ...['auto', 'minus', 'plus', 'spin'].map((i) => ['magic-lamp', `ui_${i}`, 'button', { icon: i }]),
  ['magic-lamp', 'ui_panel', 'panel', {}],
  ...['big', 'mega', 'super'].map((t) => ['magic-lamp', `win_${t}`, 'win_banner', { tier: t }]),
  ['huffnpuff', 'bg_main', 'bg', { motif: 'rays' }],
  ...['BR', 'GD', 'SK', 'ST'].map((m, i) => ['huffnpuff', `frame_${m}`, 'frame', { level: [2, 3, 1, 1][i], metal: ['bronze', 'gold', 'silver', 'bronze'][i] }]),
  ['huffnpuff', 'fx_coin', 'coin', {}],
  ...['BR', 'GD', 'SK', 'ST'].flatMap((m) => [['huffnpuff', `house_${m}`, null, '房屋（題材物件）'], ['huffnpuff', `room_${m}`, null, '房間場景（題材）']]),
  ['huffnpuff', 'key_badge', 'icon', { name: 'key', plate: 'circle', size: 128 }],
  ['huffnpuff', 'logo', null, '遊戲 Logo（專屬）'],
  ['huffnpuff', 'reel_bg', 'reel_bg', {}], ['huffnpuff', 'reel_frame', 'reel_frame', {}],
  ...[['A', 'A'], ['J', 'J'], ['K', 'K'], ['Q', 'Q'], ['N9', '9'], ['T10', '10']].map(([a, l]) => ['huffnpuff', `sym_${a}`, 'royal', { letter: l }]),
  ['huffnpuff', 'sym_GD', 'icon', { name: 'goldbar' }], ['huffnpuff', 'sym_BR', null, '磚頭（題材物件）'], ['huffnpuff', 'sym_SK', null, '木材（題材物件）'], ['huffnpuff', 'sym_ST', null, '稻草（題材物件）'],
  ['huffnpuff', 'sym_FG', 'badge', { type: 'free' }], ['huffnpuff', 'sym_KEY', 'icon', { name: 'key' }],
  ...['M1', 'M2', 'M3'].map((a) => ['huffnpuff', `sym_${a}`, null, '角色（專屬）']),
  ['huffnpuff', 'sym_M4', null, '工具箱（題材物件）'], ['huffnpuff', 'sym_M5', null, '捲尺（題材物件）'],
  ['huffnpuff', 'sym_W', 'badge', { type: 'wild' }],
  ...['auto', 'minus', 'plus', 'spin'].map((i) => ['huffnpuff', `ui_${i}`, 'button', { icon: i }]),
  ['huffnpuff', 'ui_panel', 'panel', {}],
  ...['big', 'mega', 'super'].map((t) => ['huffnpuff', `win_${t}`, 'win_banner', { tier: t }]),
  ['huffnpuff', 'wolf_huff', null, '角色演出（專屬）'],
  // aidev 魚機（fish／cat-fish 的 svg.ts）：魚種走 creature()，不算 kit
  ...[1, 2, 3].map((l) => ['fish', `cannonSvg(${l})`, 'cannon', { level: l }]),
  ['fish', 'BULLET_SVG', 'bullet', {}], ['fish', 'NET_SVG', 'net', {}], ['fish', 'BG_SVG', 'bg', { motif: 'sea' }],
  ['fish', 'FISH_SVG', null, '魚種（走 creature()）'],
  ['cat-fish', 'CANNON_SVG', 'cannon', { level: 1 }], ['cat-fish', 'BULLET_SVG', 'bullet', {}], ['cat-fish', 'BEAD_SVG', 'bead', {}],
  ['cat-fish', 'catBodySvg／CAT_ARM／CAT_TAIL', null, '主角貓（專屬）'], ['cat-fish', 'foeBodySvg／FOE_TAIL', null, '對手（專屬）'],
  ['cat-fish', 'PUMPKIN_SVG', null, '題材物件'], ['cat-fish', 'FISH_SVG', null, '魚種（走 creature()）'],
].map(([game, alias, kind, spec]) => (kind ? { game, alias, kind, spec } : { game, alias, kind: null, reason: spec }));

// ── CLI ──────────────────────────────────────────────────────────────────────
const isMain = typeof process !== 'undefined' && process.argv?.[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href;
if (isMain) {
  const argv = process.argv.slice(2);
  const [cmd, ...rest] = argv[0]?.startsWith('--') ? ['gen', ...argv] : argv;
  const opt = (k, d) => { const i = rest.indexOf(`--${k}`); return i >= 0 ? rest[i + 1] : d; };
  const fs = await import('node:fs'), path = await import('node:path');
  if (cmd === 'gen' && opt('config')) {
    // 產生器契約（ark-web-game wg_pack_assets 的 generator）：--out <dir> 產 <別名>.svg；動畫另產 <別名>_<i>.svg；--list 列別名與尺寸
    let cfg;
    try { cfg = JSON.parse(fs.readFileSync(opt('config'), 'utf8')); } catch (e) { console.error(`❌ 讀不到 kit 設定：${e.message}`); process.exit(2); }
    const entries = Object.entries(cfg.assets ?? {});
    if (!entries.length) { console.error('❌ kit 設定沒有 assets（{ "assets": { "<別名>": { "kind": "royal", … } } }）—— 範圍是空的'); process.exit(2); }
    const only = opt('only') ? new Set(opt('only').split(',')) : null;
    const missing = only ? [...only].filter((a) => !cfg.assets[a]) : [];
    if (missing.length) { console.error(`❌ --only 的別名不在設定裡：${missing.join('、')}`); process.exit(2); }
    const out = [], fail = [];
    for (const [alias, a] of entries) {
      if (only && !only.has(alias)) continue;
      const { kind, ...spec } = a;
      try { out.push([alias, asset(kind, { theme: cfg.theme, profile: opt('profile', cfg.profile), ...spec, alias })]); } catch (e) { fail.push(`${alias}（${kind}）：${e.message}`); }
    }
    if (fail.length) { for (const f of fail) console.error('❌', f); process.exit(2); }
    if (rest.includes('--list')) { for (const [alias, r] of out) console.log(`${alias} ${r.meta.w}x${r.meta.h}${r.frames ? ` ×${r.frames.length}` : ''}`); process.exit(0); }
    if (!opt('out')) { console.error('❌ 缺 --out <資料夾>'); process.exit(2); }
    fs.mkdirSync(opt('out'), { recursive: true });
    const manifest = { version: VERSION, theme: out[0]?.[1].meta.theme, assets: {} };
    for (const [alias, r] of out) {
      fs.writeFileSync(path.join(opt('out'), `${alias}.svg`), r.svg);
      r.frames?.forEach((f, i) => fs.writeFileSync(path.join(opt('out'), `${alias}_${i}.svg`), f));
      manifest.assets[alias] = r.meta;
    }
    fs.writeFileSync(path.join(opt('out'), 'kit-manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
    console.log(`✅ ${out.length} 個別名 → ${opt('out')}（kit-manifest.json）`);
  } else if (cmd === 'list') {
    for (const [k, d] of Object.entries(KINDS)) console.log(`${k.padEnd(12)} ${d.category.padEnd(7)} ${d.anim ? `動畫 ${d.anim.frames} 格` : '靜態    '}  樣本 ${SAMPLES[k]?.length ?? 0}`);
    console.log(`themes：${Object.keys(THEMES).join('、')}`);
  } else if (cmd === 'preview' && opt('out')) {
    const profile = opt('profile', 'texture'), anims = [];
    const themes = opt('themes', Object.keys(THEMES).join(',')).split(',');
    const rows = themes.map((t) => {
      const cells = Object.entries(SAMPLES).flatMap(([k, list]) => list.map((s) => asset(k, { ...s, theme: t, profile }))).map(({ svg, frames, meta }) => {
        const id = frames ? anims.push(frames) - 1 : -1;
        return `<figure${id >= 0 ? ` data-a="${id}"` : ''}><div>${svg}</div><figcaption>${meta.alias}<br><small>${meta.w}×${meta.h} · ${(svg.length / 1024).toFixed(1)} KB${frames ? ` · ${frames.length} 格` : ''}</small></figcaption></figure>`;
      }).join('');
      return `<h2>${t}</h2><main>${cells}</main>`;
    }).join('');
    fs.mkdirSync(path.dirname(path.resolve(opt('out'))), { recursive: true });
    fs.writeFileSync(opt('out'), `<!doctype html><html lang="zh-TW"><meta charset="utf-8"><title>gamekit ${VERSION} 預覽（${profile}）</title><style>body{margin:12px;background:#1a1a24;color:#eee;font:13px system-ui,sans-serif}main{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end}figure{margin:0;padding:6px;background:#26263a;border-radius:8px;text-align:center}figure svg{max-width:300px;max-height:420px;height:auto;width:auto}small{opacity:.7}</style><h1>gamekit ${VERSION}（${profile}）</h1>${rows}
<script>const A=${JSON.stringify(anims)};let f=0;setInterval(()=>{f++;document.querySelectorAll('figure[data-a]').forEach(el=>{const a=A[+el.dataset.a];el.firstElementChild.innerHTML=a[f%a.length];});},140);</script></html>`);
    console.log(`✅ 預覽 → ${opt('out')}`);
  } else {
    console.error('用法：\n  node gamekit.mjs --config kit.json --out <DIR> [--only a,b] [--list] [--profile texture|flat]   # 產生器（wg_pack_assets 相容）\n  node gamekit.mjs list\n  node gamekit.mjs preview --out <FILE.html> [--profile texture|flat] [--themes a,b]');
    process.exit(2);
  }
}
