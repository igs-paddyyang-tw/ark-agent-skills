// huff-house 逐局對照（node tests/huff_parity.js <game-config.json> <go-trace.json> [--json out.json]）
//
// Go 端：go run ./cmd/sim -odds <odds.json> -trace N -seed S -out trace.json（proto-stage-trace/1，record 模式）
// JS 端：slot-core spin() 以 Go math/rand Float64 流（GoRand，Go 1 值流 float64(Int63())/2^63）逐局重算。
// 比對：轉輪組 / 停輪 / 盤面 / 主遊戲贏分 / 玩法種類 / 玩法 credits / 玩法手數 / 框數（HS）/ 到達房數與重玩（OH）/ 封頂後總贏分。
// 位置（框落格）走演出流，不比。輸出 go_parity 格式（proto_build --go-parity 可嵌入驗證台）。任一不一致 exit 1。
'use strict';
const fs = require('fs');
const path = require('path');
const S = require('../src/slot-core.js');
const GoRand = require('../src/go-rand.js');

const a = process.argv.slice(2);
const cfgPath = a[0], tracePath = a[1];
const jsonOut = a.includes('--json') ? a[a.indexOf('--json') + 1] : null;
if (!cfgPath || !tracePath) { console.error('用法：node tests/huff_parity.js <game-config.json> <go-trace.json> [--json out.json]'); process.exit(2); }
const cfg = JSON.parse(fs.readFileSync(path.resolve(cfgPath), 'utf8'));
const trace = JSON.parse(fs.readFileSync(path.resolve(tracePath), 'utf8'));
const C = S.compile(cfg);
if (C.model !== 'huff-house') { console.error(`config 玩法模型是 ${C.model}，本工具只對 huff-house`); process.exit(2); }

// Go client code → proto 符號碼（經 sym_id；W / 建材碼與規格書符號不同名）
const id2code = Object.fromEntries(Object.entries(cfg.sym_id).map(([k, v]) => [v, k]));
const CLIENT = { W: 'WILD', ST: 'SC_STRAW', SK: 'SC_STICK', BR: 'SC_BRICK', GD: 'SC_GOLD' };
const toCode = (c) => CLIENT[c] || (id2code[c] ? id2code[c] : c);

const TWO63 = 9223372036854775808;
function goFloatRng(seed) {
  const g = GoRand.create(Number(seed));
  const float = () => { for (;;) { const v = Number(g.int63()) / TWO63; if (v < 1) return v; } };
  return { float, int: (n) => Math.floor(float() * n) };
}

const seed = trace.info.seed, bet = trace.info.betBase;
const rng = goFloatRng(seed);
let bad = 0, fg = 0, capped = 0, first = null;
const byType = {};
for (let i = 0; i < trace.results.length; i++) {
  const g = trace.results[i];
  if (g.bet !== bet) { console.error(`第 ${i + 1} 局押注 ${g.bet} ≠ betBase ${bet}（本工具只對基準押注）`); process.exit(2); }
  const r = S.spin(C, i + 1, { rng });
  const d = [];
  const chk = (k, js, go) => { if (JSON.stringify(js) !== JSON.stringify(go)) d.push(`${k}: js=${JSON.stringify(js)} go=${JSON.stringify(go)}`); };
  chk('combo', r.reelset, g.reel.combo);
  chk('stops', r.stops, g.reel.stops);
  chk('grid', r.grid.map((col) => col.map((v) => C.SYM[v])), g.reel.grid.map((col) => col.map(toCode)));
  chk('mgWin', r.mgWin, g.base.win);
  const gf = g.feature, gt = gf ? gf.draw.type : null;
  chk('feature', r.fg ? r.fg.type : null, gt);
  if (r.fg && gf) {
    const sc = gf.script;
    fg++; byType[gt] = (byType[gt] || 0) + 1;
    chk('credits', r.fg.credits, sc.credits);
    chk('spinsPlayed', r.fg.spins, sc.spinsPlayed);
    if (gt === 'OH') { chk('reached', r.fg.reached, sc.reached); chk('replays', r.fg.replays, sc.replays); }
    else { chk('nFrames', r.fg.nFrames, sc.nFrames); chk('capStopped', !!r.fg.capStopped, !!sc.capStopped); }
    chk('featureWin', r.totalWin - r.mgWin, gf.win);
    if (gf.capped) capped++;
  }
  if (d.length) { bad++; if (!first) first = { round: i + 1, diff: d }; }
}
const rep = { seed, spins: trace.results.length, fg, capped, mismatch: bad, byType, rng: 'go-math-rand Float64', model: C.model, first };
console.log(`huff parity：seed ${seed}｜${rep.spins} 局（玩法 ${fg}：${JSON.stringify(byType)}）｜不一致 ${bad}`);
if (first) console.log(`第一個不一致：第 ${first.round} 局\n  ` + first.diff.join('\n  '));
if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify(rep, null, 1) + '\n');
process.exit(bad ? 1 : 0);
