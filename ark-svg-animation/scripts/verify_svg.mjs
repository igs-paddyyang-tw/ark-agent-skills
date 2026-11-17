#!/usr/bin/env node
// verify_svg.mjs —— ark-svg-animation 守門（規格 AC-1～AC-5、AC-8；0.5.0 起加 gamekit AC-G1～G3）。
//
//   node verify_svg.mjs                         # 內建樣本（每種體型＋變體）
//   node verify_svg.mjs --expect names.txt      # 每行一個物種名（例：fish-bot 41 種）；未登錄（fallback）列為警告
//   node verify_svg.mjs --expect names.txt --strict   # 未登錄也算失敗
//   node verify_svg.mjs --json
//   （gamekit：每個 kind 樣本 × 4 theme × texture／flat；生物另驗 flat profile。PixiJS 實機比對另跑 pixi_check.mjs）
// exit：0 全過／1 有違規（或掃到 0 個物種）／2 參數錯
//
// 每個檢查都是獨立匯出的函式，tests/ 直接餵壞輸入做反證。
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { creature, renderPhase, RIGS } from './svg_anim.mjs';
import { asset, assetPhase, KINDS, SAMPLES as KIT_SAMPLES, THEMES, BUDGET, COVERAGE } from './gamekit.mjs';

export const MAX_FRAME_BYTES = 4096;
const FORBIDDEN = [
  [/<script\b/i, '<script>'], [/<foreignObject\b/i, '<foreignObject>'], [/<image\b/i, '<image>'],
  [/\son[a-z]+\s*=/i, '事件屬性 on*='], [/\b(?:xlink:)?href\s*=/i, 'href（外部參照）'], [/url\(\s*['"]?(?!#)/i, 'url(…) 外部資源'],
  [/<style\b/i, '<style>'], [/<text\b/i, '<text>（依賴字型）'],
];

/** 安全：禁止元素／屬性 → 違規清單 */
export function checkSecurity(svg) {
  return FORBIDDEN.filter(([re]) => re.test(svg)).map(([, label]) => `含 ${label} → 刪除；SVG 只允許圖元（path／polygon／ellipse／circle／polyline／g）`);
}

/** 結構：開頭、viewBox、標籤成對 */
export function checkWellFormed(svg) {
  const out = [];
  if (!/^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" viewBox="0 0 [\d.]+ [\d.]+"/.test(svg)) out.push('開頭不是帶 viewBox 的 <svg> → 由 svg_anim.mjs emit 產生，不要手改');
  const open = (svg.match(/<(svg|g)\b/g) ?? []).length, close = (svg.match(/<\/(svg|g)>/g) ?? []).length;
  if (open !== close) out.push(`<svg>／<g> 開 ${open} 個、關 ${close} 個 → 標籤不成對`);
  return out;
}

/** 體積 */
export function checkSize(svg, max = MAX_FRAME_BYTES) {
  const n = Buffer.byteLength(svg);
  return n > max ? [`${(n / 1024).toFixed(1)} KB > ${(max / 1024).toFixed(0)} KB → 減少輪廓取樣段數或合併圖元`] : [];
}

// 比對前去掉 id 與 url(#…) 參照：它們含格號（s0、c1）與種子，不是座標（0.4.0 起有漸層 id）
const nums = (s) => (s.replace(/\sid="[^"]*"|url\(#[^)]*\)/g, '').match(/-?\d+(?:\.\d+)?/g) ?? []).map(Number);
function dist(a, b) {
  if (a.length !== b.length) return Infinity;
  let d = 0;
  for (let i = 0; i < a.length; i++) d += Math.abs(a[i] - b[i]);
  return d;
}

/** 排序後的數字集合距離（允許對稱零件換位，例：轉 60° 後的 3 根輪輻） */
function multisetDist(a, b) {
  if (a.length !== b.length) return Infinity;
  const x = [...a].sort((m, n) => m - n), y = [...b].sort((m, n) => m - n);
  return dist(x, y);
}

/**
 * 循環接縫（兩段）：
 *   ① 等速：每一步（含最後一格 → 下一相位 t＝1 這步）都 ≤ 全部步長中位數 × 1.5
 *      —— 用中位數不用平均：一大步會把平均拉高、自己躲過門檻（反證抓到的）
 *   ② 週期：t＝1 與第一格「排序後數字集合」相同（容差：每個數字 0.2 —— 小數 1 位的捨入）
 * 只比首尾（舊作法）會把「畫面相同、零件換位」誤判成跳動。
 */
export function checkSeam(frames, next) {
  if (frames.length < 2 || next === undefined) return [];
  const v = frames.map(nums), nx = nums(next);
  const steps = [...v.slice(1).map((x, i) => dist(v[i], x)), dist(v[v.length - 1], nx)];
  const sorted = [...steps].sort((a, b) => a - b);
  const med = sorted[Math.floor(sorted.length / 2)];
  const out = [];
  steps.forEach((d, i) => {
    if (d > med * 1.5 + 1e-9) {
      const where = i === steps.length - 1 ? '最後一格 → 下一循環' : `第 ${i} → ${i + 1} 格`;
      out.push(`${i === steps.length - 1 ? '循環接縫' : '不等速'}：${where} 變化 ${d === Infinity ? '結構不同' : d.toFixed(1)} > 中位數 ${med.toFixed(1)} × 1.5 → 相位曲線要等速（t＝i/n）`);
    }
  });
  const per = multisetDist(nx, v[0]);
  if (per > 0.2 * v[0].length) out.push(`不是週期：t＝1 與第一格不同（差 ${per === Infinity ? '結構不同' : per.toFixed(1)}）→ 相位曲線要以 2π 為週期，旋轉零件一圈要轉到對稱角`);
  return out;
}

/**
 * flat profile（PixiJS GraphicsContext.svg() 直接解析；規格 FR-10）：
 * Pixi 8.6.6 不吃漸層／裁切／transform、polygon／polyline 的 points 用 /\d+/g 解析（小數與負號會壞）、只讀 style 上色。
 */
const FLAT_FORBIDDEN = [
  [/<(?:linear|radial)Gradient\b|url\(#/, '漸層', '改用實色（draw.mjs flat 會取漸層平均色）'],
  [/<clipPath\b|clip-path=/, '裁切', 'flat 下略過被裁切的花紋'],
  [/\stransform=/, 'transform', '變換要烘焙進座標（draw.mjs 的矩陣）'],
  [/<(?:polygon|polyline|line|rect)\b/, 'polygon／polyline／line／rect', '一律改 <path>（Pixi 用 /\\d+/g 讀 points，小數與負號會被拆開）'],
  [/rgba\(|\sopacity=|\sfill-opacity=|\sstroke-opacity=/, '透明度屬性或 rgba()', '透明度寫進 style 的 fill-opacity／stroke-opacity'],
  [/\s(?:fill|stroke|stroke-width)="/, 'fill／stroke 屬性', '上色一律寫 style（Pixi 有 style 就忽略屬性；子元素也關不掉繼承的填色）'],
  [/<g\b/, '<g>', '群組攤平（樣式會往下繼承、關不掉）'],
];
export function checkFlat(svg) {
  const out = FLAT_FORBIDDEN.filter(([re]) => re.test(svg)).map(([, what, fix]) => `flat 不可有${what} → ${fix}`);
  const bare = (svg.match(/<(?:path|circle|ellipse)\b(?![^>]*\sstyle=")[^>]*>/g) ?? []).length;
  if (bare) out.push(`flat 有 ${bare} 個圖元沒有 style → 每個圖元都要自帶 style（fill:none 也要寫）`);
  if (/style="[^"]*stroke:#[^"]*"/.test(svg) && /style="(?![^"]*stroke-width)[^"]*stroke:#/.test(svg)) out.push('flat 有描邊但沒有 stroke-width → Pixi 會用預設 1 px');
  return out;
}

const sha = (x) => createHash('sha256').update(JSON.stringify(x)).digest('hex');

/** 確定性：同參數產兩次必須逐位元組相同 */
export function checkDeterminism(gen, spec) {
  const a = sha(gen(spec)), b = sha(gen(spec));
  return a === b ? [] : ['兩次輸出不同 → 找出非確定來源（Math.random、Date、物件走訪順序）'];
}

/**
 * 同頁內嵌時 id 不衝突：同一個 id 的定義（漸層、裁切）必須完全相同。
 * 完全相同的圖貼兩次（例：SINGLE_GURNARD 與 GURNARD 是同一張）不算衝突 —— 定義一樣，畫出來就一樣。
 * 真正會錯的是「同 id、不同定義」：瀏覽器只取第一個，第二張圖會套到別人的漸層或裁切（fish-bot D-285 踩過）。
 */
export function checkIdsUnique(svgs) {
  const defs = new Map(), bad = new Set();
  for (const s of svgs) for (const [whole, , id] of s.matchAll(/<(radialGradient|linearGradient|clipPath)\sid="([^"]+)"[\s\S]*?<\/\1>/g)) {
    if (defs.has(id) && defs.get(id) !== whole) bad.add(id);
    defs.set(id, whole);
  }
  return bad.size ? [`${bad.size} 個 id 定義衝突（同 id、不同內容；例：${[...bad].slice(0, 3).join('、')}）→ id 前綴要含種子＋外觀雜湊（變體、尺寸、配色、參數）＋格號`] : [];
}

/** 一隻生物的全部檢查 */
export function checkCreature(spec, { gen = creature, phase = renderPhase, registry } = {}) {
  const problems = [], warnings = [];
  let out;
  try { out = gen(spec, registry); } catch (e) { return { problems: [`產生失敗：${e.message}`], warnings }; }
  problems.push(...checkDeterminism((s) => gen(s, registry), spec));
  for (const [state, frames] of Object.entries(out.frames)) {
    if (!frames.length) problems.push(`${state} 沒有任何格`);
    frames.forEach((svg, i) => [...checkSecurity(svg), ...checkWellFormed(svg), ...checkSize(svg)].forEach((m) => problems.push(`${state}[${i}] ${m}`)));
    const vb = new Set(frames.map((s) => /viewBox="([^"]+)"/.exec(s)?.[1]));
    if (vb.size > 1) problems.push(`${state} 各格 viewBox 不同 → 錨點會跳；rig.extent 要涵蓋全部相位`);
  }
  problems.push(...checkSeam(out.frames.swim ?? [], phase(spec, 1, registry)).map((m) => `swim ${m}`));
  if (out.meta?.fallback) warnings.push(`未登錄或體型名稱不存在：以 ${out.meta.archetype} 代替 → 在 scripts/species.mjs 補登錄，或把 archetype 改成 ${Object.keys(RIGS).join('／')} 其一`);
  return { problems, warnings };
}

import { SPECIES } from './svg_anim.mjs';
/** 預設樣本＝登錄表全部物種＋前綴／旋風各一（名稱解析也一起驗） */
export const SAMPLE = [...Object.keys(SPECIES), 'TWIST_NEMO', 'SINGLE_GURNARD', 'LINE_PUFFER_FISH'];

export function verify(names, { strict = false, gen = creature, phase = renderPhase, registry, variants = [[], ['gold'], ['boss'], ['twister']] } = {}) {
  const rows = [], all = [];
  for (const name of names) for (const vs of variants) {
    const r = checkCreature({ name, length: 104, variants: vs }, { gen, phase, registry });
    rows.push({ name, variants: vs, ...r });
    try { const f = gen({ name, length: 104, variants: vs }, registry).frames; all.push(...f.swim, ...f.catch); } catch { /* 產生失敗已在 checkCreature 報 */ }
  }
  const problems = rows.flatMap((r) => r.problems.map((p) => `${r.name}${r.variants.length ? `[${r.variants}]` : ''}：${p}`));
  const warnings = [...new Set(rows.flatMap((r) => r.warnings.map((w) => `${r.name}：${w}`)))];
  problems.push(...checkIdsUnique(all).map((m) => `同頁內嵌：${m}`));
  // 生物 flat profile：每種一次（無變體＋boss 各一，boss 有 g 透明度與外圈）
  let flatN = 0;
  for (const name of names) for (const vs of [[], ['boss']]) {
    const spec = { name, length: 104, variants: vs, profile: 'flat' };
    let out; try { out = gen(spec, registry); } catch (e) { problems.push(`${name}[flat]：產生失敗 ${e.message}`); continue; }
    problems.push(...checkDeterminism((x) => gen(x, registry), spec).map((m) => `${name}[flat]：${m}`));
    for (const [state, frames] of Object.entries(out.frames)) frames.forEach((svg, i) => {
      flatN++;
      [...checkSecurity(svg), ...checkWellFormed(svg), ...checkSize(svg, MAX_FRAME_BYTES * 2), ...checkFlat(svg)].forEach((m) => problems.push(`${name}[flat] ${state}[${i}] ${m}`));
    });
  }
  if (strict) problems.push(...warnings);
  if (!names.length) problems.push('掃到 0 個物種 —— 範圍是空的，不是通過');
  return { checked: names.length, frames: rows.length, flatFrames: flatN, rigs: Object.keys(RIGS), problems, warnings, ok: problems.length === 0 };
}

/**
 * gamekit：每個 kind 的樣本 × 每個 theme × texture／flat。
 * 檢查：確定性、安全（含禁 <text>）、結構、分類尺寸預算（flat 2 倍：執行期解析、不走網路）、flat 規則、同頁 id、換 theme 會變色。
 */
export function verifyKit({ kinds = Object.keys(KINDS), themes = Object.keys(THEMES), samples = KIT_SAMPLES, gen = asset, phase = assetPhase } = {}) {
  const problems = [], all = [];
  let n = 0;
  for (const kind of kinds) {
    const list = samples[kind] ?? [];
    if (!list.length) { problems.push(`${kind}：沒有樣本 → 在 gamekit.mjs 的 SAMPLES 補，範圍是空的不是通過`); continue; }
    list.forEach((spec, si) => {
      const byTheme = new Set();
      for (const th of themes) for (const profile of ['texture', 'flat']) {
        const full = { ...spec, theme: th, profile }, tag = `${kind}#${si}[${th}/${profile}]`;
        let out; try { out = gen(kind, full); } catch (e) { problems.push(`${tag}：產生失敗 ${e.message}`); continue; }
        n++;
        problems.push(...checkDeterminism((x) => gen(kind, x), full).map((m) => `${tag}：${m}`));
        const budget = (BUDGET[out.meta.category] ?? BUDGET.ui) * (profile === 'flat' ? 2 : 1);
        const frames = out.frames ?? [out.svg];
        frames.forEach((svg, i) => [...checkSecurity(svg), ...checkWellFormed(svg), ...checkSize(svg, budget), ...(profile === 'flat' ? checkFlat(svg) : [])]
          .forEach((m) => problems.push(`${tag}${out.frames ? `[${i}]` : ''} ${m}`)));
        if (out.frames) {
          if (new Set(out.frames.map((x) => /viewBox="([^"]+)"/.exec(x)?.[1])).size > 1) problems.push(`${tag} 各格 viewBox 不同 → 動畫格尺寸要固定`);
          // 接縫一律比 flat（座標已烘焙）：texture 的旋轉藏在 transform 屬性裡，數字比對會兩頭錯 ——
          // 壓扁的放射光轉 30° 看不出跳（M6）、對稱的鎖定框轉 90° 卻被當成跳（M7）
          if (out.meta.loop !== false) { if (profile === 'flat') problems.push(...checkSeam(out.frames, phase(kind, full, 1)).map((m) => `${tag} ${m}`)); }
          else if (new Set(out.frames).size < out.frames.length) problems.push(`${tag} 一次性動畫有重複的格 → 相位要從 t＝0 走到 t＝1`);
        }
        if (profile === 'texture') { all.push(...frames); byTheme.add(out.svg); }
      }
      if (themes.length > 1 && byTheme.size < 2) problems.push(`${kind}#${si}：換 theme 輸出完全相同 → 顏色要取自 theme token，不要寫死`);
    });
  }
  problems.push(...checkIdsUnique(all).map((m) => `gamekit 同頁內嵌：${m}`));
  if (!n) problems.push('gamekit 掃到 0 張 —— 範圍是空的，不是通過');
  return { checked: n, kinds, themes, problems, ok: problems.length === 0 };
}

/**
 * 覆蓋率（計畫 AC-G4）：對照表裡每個非專屬別名都要產得出來；kind 不存在或產生失敗 → 列缺漏。
 * 專屬（kind＝null）只計數不算缺漏 —— 角色、Logo、題材物件刻意留在各專案。
 */
export function verifyCoverage(rows = COVERAGE, { gen = asset } = {}) {
  const problems = [], byGame = {};
  for (const r of rows) {
    const g = (byGame[r.game] ??= { total: 0, kit: 0, own: 0 });
    g.total++;
    if (r.kind === null) { g.own++; continue; }
    try { gen(r.kind, r.spec); g.kit++; } catch (e) { problems.push(`${r.game}／${r.alias} → ${r.kind}：${e.message}`); }
  }
  if (!rows.length) problems.push('覆蓋率對照表是空的 —— 範圍是空的，不是通過');
  const summary = Object.entries(byGame).map(([game, g]) => `${game} ${g.kit}/${g.total - g.own}（專屬 ${g.own}）`);
  return { problems, summary, ok: problems.length === 0 };
}

/** pixi_check 的樣本：gamekit 全部 kind × theme（flat）＋每種體型一隻（flat，游動第 0 格與被捕第 1 格） */
export function flatSamples() {
  const items = [];
  for (const [kind, list] of Object.entries(KIT_SAMPLES)) list.forEach((spec, i) => {
    for (const th of Object.keys(THEMES)) items.push({ name: `${kind}#${i}[${th}]`, svg: asset(kind, { ...spec, theme: th, profile: 'flat' }).svg });
  });
  const seen = new Set();
  for (const name of SAMPLE) {
    const out = creature({ name, length: 104, profile: 'flat', variants: ['boss'] });
    if (seen.has(out.meta.archetype)) continue;
    seen.add(out.meta.archetype);
    items.push({ name: `${name}.swim0`, svg: out.frames.swim[0] }, { name: `${name}.catch1`, svg: out.frames.catch[1] });
  }
  return items;
}

const isMain = process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href;
if (isMain) {
  const args = process.argv.slice(2);
  const at = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : undefined; };
  let names = SAMPLE;
  if (at('--expect')) {
    try { names = readFileSync(at('--expect'), 'utf8').split(/\r?\n/).map((s) => s.trim()).filter((s) => s && !s.startsWith('#')); }
    catch (e) { console.error(`❌ 讀不到 --expect：${e.message}`); process.exit(2); }
  }
  const rep = verify(names, { strict: args.includes('--strict') });
  const kitRep = verifyKit(), covRep = verifyCoverage();
  rep.kit = { checked: kitRep.checked, kinds: kitRep.kinds, coverage: covRep.summary };
  rep.problems.push(...kitRep.problems.map((p) => `gamekit ${p}`), ...covRep.problems.map((p) => `覆蓋率 ${p}`));
  rep.ok = rep.problems.length === 0;
  if (args.includes('--json')) console.log(JSON.stringify(rep, null, 2));
  else {
    console.log(`ark-svg-animation verify：${rep.checked} 種 × ${rep.frames / Math.max(1, rep.checked)} 變體＋flat ${rep.flatFrames} 格｜體型 ${rep.rigs.join('、')}｜gamekit ${rep.kit.checked} 張（${rep.kit.kinds.length} 種 kind）｜覆蓋率 ${rep.kit.coverage.join('、')}`);
    for (const p of rep.problems) console.log('❌', p);
    for (const w of rep.warnings) console.log('⚠️', w);
    if (rep.ok) console.log('✅ 通過');
  }
  process.exit(rep.ok ? 0 : 1);
}
