// Go 快測逐局對照：node tests/go_parity.js <game-config.json> <trace.txt>
// trace.txt 由 goparity/<model>_trace.go 產生；JS 以 GoRand（Go math/rand 逐位元移植）跑同一 seed，逐局比對
// 輪帶組 / MG 贏分 / FG 贏分 / 封頂後總贏分 / FG 組別 / 觸發顆數。全部一致 = 雛型引擎與 Go 引擎同一套規則。
const fs = require('fs'), path = require('path');
const S = require('../src/slot-core.js'), G = require('../src/go-rand.js');
const cfg = JSON.parse(fs.readFileSync(path.resolve(process.argv[2]), 'utf8'));
const lines = fs.readFileSync(path.resolve(process.argv[3]), 'utf8').trim().split('\n');
const head = Object.fromEntries(lines[0].replace(/^#\s*/, '').split(/\s+/).map((kv) => kv.split('=')).map(([k, v]) => [k, v === 'true' ? true : v === 'false' ? false : Number(v)]));
const C = S.compile(cfg);
const mwSpec = C.maxWin;
if (!C.maxWin && head.max_win) C.maxWin = head.max_win;            // 規格書沒寫 MaxWin 時用 Go 設定值對照（G-6）
const rng = G.create(head.seed), lb = head.line_bet || 1;
let diff = 0, n = 0, fgN = 0, capN = 0, jpN = 0; const firstDiffs = [];
let cur = 0;
const skipTo = (i) => { for (; cur < i; cur++) { const r = S.spin(C, cur, { rng }); n++; if (r.fg) { diff++; if (firstDiffs.length < 5) firstDiffs.push({ i: cur, js: 'FG', go: '未列出（無 FG）' }); } } };
for (const ln of lines.slice(1)) {
  const [i, set, mg, fgw, total, grp, sp] = ln.split(' ').map(Number);
  skipTo(i); cur = i + 1;
  const r = S.spin(C, i, { rng });
  const js = [set < 0 ? -1 : r.reelset, r.mgWin * lb, (r.fg ? r.fg.win : 0) * lb, r.totalWin * lb, r.fg ? C.G.indexOf(r.fg.group) : -1,
    C.model === 'collect-mult' && r.fg ? r.nSC + r.nSS : sp];        // trace 未提供的欄位（-1 / 0）不比
  const go = [set, mg, fgw, total, grp, sp];
  n++; if (r.fg) fgN++; if (r.capped || (r.fg && r.fg.capped)) capN++; if (r.fg && r.fg.jackpot) jpN++;
  if (js.join() !== go.join()) { diff++; if (firstDiffs.length < 5) firstDiffs.push({ i, js, go }); }
}
skipTo(head.n);
const out = { seed: head.seed, model: C.model, spins: n, fg: fgN, capped: capN, jackpot: jpN, mismatch: diff, max_win_src: mwSpec ? (cfg.board.max_win_src || 'spec') : 'trace header', first: firstDiffs };
console.log(JSON.stringify(out));
process.exit(diff ? 1 : 0);
