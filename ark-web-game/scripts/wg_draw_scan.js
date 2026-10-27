#!/usr/bin/env node
// wg_draw_scan — ⑧ 抽離第 1 步：掃描 game.js（Stage 遊戲包）一局內向「數學亂數流」取值的位置與順序，產 trace-map 草稿。
//
//   node wg_draw_scan.js --game <game.js> [--odds <odds.json>] [--n 20000] [--seed 1] [--proto <ark-game-proto 路徑>]
//        [--out <草稿.md>] [--json <統計.json>] [--dump-spec <spec.json>] [--compare <trace-map.md> [--alias 'afterGrid=Engine.trigger,drawValue=Engine.valueOf'] [--strict]]
//
// 作法：用 ark-game-proto 的 node 載入器載入引擎層＋game.js，LocalService（rng=go）跑 n 局；把數學流包一層，
//   每次取值記下呼叫堆疊，取第一個「不是共用小工具」的函式當抽值點（pickW、rnd、put… 視為工具，往上找呼叫者）。
// 輸出：
//   抽值點清單（第一次出現的順序＝抽值順序）、每局平均次數、出現局數比例（< 100% 表示有條件才抽）；
//   trace-map 草稿（六欄格式，參數／SpinResult 欄位／演出步驟留「待填」由人補）；
//   --compare：每個抽值點是否能在既有 trace-map 的「Go」欄找到（同名或 --alias 對照）；--strict 時有找不到的 exit 1。
'use strict';
const fs = require('fs');
const path = require('path');
const os = require('os');

const a = process.argv.slice(2);
const arg = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
const game = arg('--game');
if (!game) { console.error('需要 --game <game.js>'); process.exit(2); }
const proto = path.resolve(arg('--proto', path.join(__dirname, '..', '..', 'ark-game-proto')));
const { load } = require(path.join(proto, 'scripts', 'stage', 'tests', 'load.js'));
const n = Number(arg('--n', 20000));
const seed = Number(arg('--seed', 1));
const HELPERS = new Set(['pickW', 'rnd', 'put', 'f', 'rng', 'next', 'shuffleWith', 'Object.<anonymous>', '<anonymous>', 'Array.from', 'Array.map', 'Array.filter', 'Array.forEach']);

let extra = [];
if (arg('--odds')) {
  const tmp = path.join(os.tmpdir(), `wg-scan-odds-${process.pid}.js`);
  fs.writeFileSync(tmp, `globalThis.HUFF_ODDS = ${fs.readFileSync(path.resolve(arg('--odds')), 'utf8')};`);
  extra = [tmp];
}
const P = load(path.resolve(game), extra);
if (arg('--dump-spec')) {                                   // ⑧ 抽離：game.js 的 spec（數值正本）原樣輸出成 Go 機率模組的設定檔
  const spec = JSON.parse(JSON.stringify(P.config.spec, (k, v) => (typeof v === 'function' ? undefined : v)));
  fs.writeFileSync(arg('--dump-spec'), JSON.stringify({ _meta: { source: path.relative(process.cwd(), path.resolve(game)), dumped: new Date().toISOString().slice(0, 10), profile: 'game-js-spec' }, spec }, null, 1));
}
const svc = new P.svc.LocalService(P.config.spec, { seed, rng: 'go', balance: 1e12 });
const orig = svc.rng;
let cur = null;
const sites = new Map();   // key → { key, fn, file, line, first, total, rounds }
let order = 0;
function frameOf(stack) {
  const lines = String(stack).split('\n').slice(2);   // 0: Error、1: 本包裝函式
  let helper = null;
  for (const ln of lines) {
    const m = ln.match(/at (?:async )?(?:([^\s(]+) \()?(.*?):(\d+):\d+\)?$/);
    if (!m) continue;
    const file = m[2];
    const fn = m[1] ? m[1].replace(/^Object\./, '') : `(匿名)@${path.basename(file)}:${m[3]}`;
    if (/service[\\/]service\.js$/.test(file)) break;
    if (HELPERS.has(fn) || /^Array\./.test(fn)) { helper = helper || fn; continue; }
    return { fn, file: path.basename(file), line: Number(m[3]), via: helper };
  }
  return { fn: helper || '<unknown>', file: '?', line: 0, via: null };
}
const wrapped = function () {
  const f = frameOf(new Error().stack);
  const key = `${f.fn}@${f.file}`;
  let s = sites.get(key);
  if (!s) { s = { key, fn: f.fn, file: f.file, line: f.line, via: f.via, first: order++, total: 0, rounds: 0 }; sites.set(key, s); }
  s.total++;
  if (cur && !cur.has(key)) { cur.add(key); s.rounds++; }
  return orig();
};
Object.assign(wrapped, orig);
svc.rng = wrapped;

(async () => {
  const bet = P.slotLogic.prepare(P.config.spec).bet.def;
  let feats = 0;
  for (let i = 0; i < n; i++) {
    cur = new Set();
    const r = await svc.spin({ bet });
    if (r.feature) feats++;
  }
  const list = [...sites.values()].sort((x, y) => x.first - y.first).map((s) => ({ ...s, perRound: +(s.total / n).toFixed(4), roundShare: +(s.rounds / n).toFixed(4), conditional: s.rounds < n }));
  const tag = path.basename(path.dirname(path.resolve(game)));
  const md = [
    '---', `title: "${P.config.name || tag} 抽選點對照表（草稿，wg_draw_scan 產生）"`, 'type: trace-map', `slug: ${tag}`,
    'prob_spec: 待填', 'schema: proto-stage-result/1', `generated: "wg_draw_scan ${new Date().toISOString().slice(0, 10)}，seed ${seed}，${n} 局（玩法 ${feats}）"`, '---', '',
    `# ${P.config.name || tag} 抽選點對照表（草稿）`, '',
    '> 由 wg_draw_scan 掃出的抽值點，順序＝第一次出現的順序（抽值順序）。「參數」「SpinResult 欄位」「演出步驟」需人工補齊後再跑 wg_trace_check。', '',
    '| # | 抽選點 | 參數 | Go | SpinResult 欄位 | 演出步驟 |', '|---|---|---|---|---|---|',
    ...list.map((s, i) => `| D-${i + 1} | ${s.fn}（${s.file}:${s.line}${s.via ? `，經 ${s.via}` : ''}；每局 ${s.perRound} 次、${(s.roundShare * 100).toFixed(1)}% 的局${s.conditional ? '，有條件' : ''}） | 待填 | 待移植：${s.fn} | 待填 | 待填 |`),
    '',
  ].join('\n');
  if (arg('--out')) fs.writeFileSync(arg('--out'), md);
  const rep = { schema: 'wg-draw-scan/1', game: path.resolve(game), seed, rounds: n, features: feats, sites: list };
  if (arg('--compare')) {
    const tm = fs.readFileSync(arg('--compare'), 'utf8');
    const goCol = tm.split('\n').filter((l) => /^\|\s*[^|#-]/.test(l) && !/^\|\s*#/.test(l)).map((l) => (l.split('|')[4] || ''));
    const names = new Set(goCol.flatMap((c) => [...c.matchAll(/`([^`]+)`/g)].map((m) => m[1])).flatMap((x) => x.split(/[＋+、,\/／\s]+/)).map((x) => x.replace(/^Engine\./, '').toLowerCase()).filter(Boolean));
    const alias = Object.fromEntries((arg('--alias', '') || '').split(',').filter(Boolean).map((kv) => kv.split('=').map((x) => x.trim())));
    rep.compare = list.map((s) => {
      const target = (alias[s.fn] || s.fn).replace(/^Engine\./, '').toLowerCase();
      return { site: s.fn, matchedAs: alias[s.fn] || s.fn, found: names.has(target) || names.has(s.fn.toLowerCase()) };
    });
    rep.unmatched = rep.compare.filter((c) => !c.found).map((c) => c.site);
  }
  if (arg('--json')) fs.writeFileSync(arg('--json'), JSON.stringify(rep, null, 1));
  console.log(`wg_draw_scan：${n} 局（玩法 ${feats}）｜抽值點 ${list.length} 個：${list.map((s) => `${s.fn}${s.conditional ? '?' : ''}`).join(' → ')}`);
  if (rep.compare) console.log(`對照 trace-map：${rep.compare.length - rep.unmatched.length}/${rep.compare.length} 找到${rep.unmatched.length ? '；找不到：' + rep.unmatched.join('、') : ''}`);
  process.exit(rep.unmatched && rep.unmatched.length && a.includes('--strict') ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
