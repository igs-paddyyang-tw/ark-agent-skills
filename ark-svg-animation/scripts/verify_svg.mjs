#!/usr/bin/env node
// verify_svg.mjs —— ark-svg-animation 守門（規格 AC-1～AC-5、AC-8）。
//
//   node verify_svg.mjs                         # 內建樣本（每種體型＋變體）
//   node verify_svg.mjs --expect names.txt      # 每行一個物種名（例：fish-bot 41 種）；未登錄（fallback）列為警告
//   node verify_svg.mjs --expect names.txt --strict   # 未登錄也算失敗
//   node verify_svg.mjs --json
// exit：0 全過／1 有違規（或掃到 0 個物種）／2 參數錯
//
// 每個檢查都是獨立匯出的函式，tests/ 直接餵壞輸入做反證。
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { creature, renderPhase, RIGS } from './svg_anim.mjs';

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

const nums = (s) => (s.match(/-?\d+(?:\.\d+)?/g) ?? []).map(Number);
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

const sha = (x) => createHash('sha256').update(JSON.stringify(x)).digest('hex');

/** 確定性：同參數產兩次必須逐位元組相同 */
export function checkDeterminism(gen, spec) {
  const a = sha(gen(spec)), b = sha(gen(spec));
  return a === b ? [] : ['兩次輸出不同 → 找出非確定來源（Math.random、Date、物件走訪順序）'];
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
  const rows = [];
  for (const name of names) for (const vs of variants) {
    const r = checkCreature({ name, length: 104, variants: vs }, { gen, phase, registry });
    rows.push({ name, variants: vs, ...r });
  }
  const problems = rows.flatMap((r) => r.problems.map((p) => `${r.name}${r.variants.length ? `[${r.variants}]` : ''}：${p}`));
  const warnings = [...new Set(rows.flatMap((r) => r.warnings.map((w) => `${r.name}：${w}`)))];
  if (strict) problems.push(...warnings);
  if (!names.length) problems.push('掃到 0 個物種 —— 範圍是空的，不是通過');
  return { checked: names.length, frames: rows.length, rigs: Object.keys(RIGS), problems, warnings, ok: problems.length === 0 };
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
  if (args.includes('--json')) console.log(JSON.stringify(rep, null, 2));
  else {
    console.log(`ark-svg-animation verify：${rep.checked} 種 × ${rep.frames / Math.max(1, rep.checked)} 變體｜體型 ${rep.rigs.join('、')}`);
    for (const p of rep.problems) console.log('❌', p);
    for (const w of rep.warnings) console.log('⚠️', w);
    if (rep.ok) console.log('✅ 通過');
  }
  process.exit(rep.ok ? 0 : 1);
}
