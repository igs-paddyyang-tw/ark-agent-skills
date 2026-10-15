// slot-core 單元測試（node tests/core_test.js <game-config.json>）：
// 決定性、演出不改結果、玩法模型的內部一致性、L1 精算對 §2、模擬對精算。輸出 PASS/FAIL 行；任一 FAIL exit 1。
const path = require('path');
const S = require('../src/slot-core.js');
const cfg = require(path.resolve(process.argv[2] || path.join(__dirname, '../../golden/milefo/game-config.json')));
const C = S.compile(cfg), T = cfg.targets.summary;
let fail = 0;
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fail++; };
const CL = C.model === 'coin-lock';

// 1 決定性 + 演出 RNG 分流
let same = true, n = 0;
for (let s = 1; s < 20000; s++) {
  const a = S.spin(C, s), b = S.spin(C, s, { present: true });
  if (a.totalWin !== b.totalWin || a.reelset !== b.reelset || JSON.stringify(a.grid) !== JSON.stringify(b.grid)) same = false;
  n++;
}
ok(same, `演出不影響數學結果（${n} 局 present vs 無 present 一致）`);
ok(JSON.stringify(S.spin(C, 777, { present: true })) === JSON.stringify(S.spin(C, 777, { present: true })), '同 seed 同 SpinResult');

if (CL) {
  // 2 coin-lock：時間軸落子總數 = 鎖格數；成組值 + JACKPOT = 封頂前贏分；最左不為箭頭
  let k = 0, tlOk = true, sumOk = true, leftOk = true, jp = 0;
  for (let s = 1; s < 4e6 && k < 300; s++) {
    const r = S.spin(C, s); if (!r.fg) continue;
    const p = S.spin(C, s, { present: true }), f = p.fg; k++;
    if (f.timeline.reduce((a, t) => a + t.drops.length, 0) !== f.coins) tlOk = false;
    if (f.groups.reduce((a, g) => a + g.value, 0) + f.jpWin !== f.raw) sumOk = false;
    if (f.groups.some((g) => g.kinds[0] === 'arrow')) leftOk = false;
    if (f.jackpot) jp++;
  }
  ok(tlOk, `時間軸落子數 = 鎖格數（${k} 場 Bonus）`);
  ok(sumOk, '成組連讀值 + JACKPOT = 封頂前 Bonus 贏分');
  ok(leftOk, '每組最左顆不為箭頭（G-TD-5）');
  const g = S.settleGroup({ flip: { ...C.flip, oneT: C.flip.oneT } }, { int: (() => { const q = [0, 0, 20, 8]; let i = 0; return () => q[i++]; })() }, 2);
  ok(g.kinds.join() === 'two,two' && g.value === 1018, `連讀：兩位數 10 · 18 → 1018（實得 ${g.value}）`);
} else {
  // 2 collect-mult：復活不改贏分、序列總和 = win；聽牌找得到
  let rv = 0, seqOk = true;
  for (let s = 1; s < 3e6 && rv < 20; s++) {
    const r = S.spin(C, s); if (!r.fg || r.fg.win < 300 * C.bet) continue;
    const p = S.spin(C, s, { present: true }), last = p.fg.seq[p.fg.seq.length - 1];
    if ((last ? last.total : p.fg.base) !== p.fg.win) seqOk = false;
    if (p.fg.revive) rv++;
  }
  ok(seqOk, 'FG 演出序列最後一步總額 = 贏分（含復活重排）');
  ok(rv > 0, `找到復活局 ${rv}`);
  let tz = 0;
  for (let s = 1; s < 3e6 && !tz; s++) { const r = S.spin(C, s); if (r.nSC >= 6 && r.grid[4].includes(C.SS) && S.spin(C, s, { present: true }).tease) tz = s; }
  ok(tz > 0, '找到彩色聽牌 seed ' + tz);
}

// 3 L1 精算對規格（§2 是抽樣值；容許取 max(§2 容許, 0.2)）
const e = S.exact(C, { bonusN: 60000 }), tol = Math.max(T.tol || 0.2, 0.2);
ok(Math.abs(e.rtp_main - T.rtp_main) < (CL ? 0.5 : 0.05), `MG RTP 精算 ${e.rtp_main.toFixed(4)} vs ${T.rtp_main}`);
ok(Math.abs(e.fg_rate / T.fg_rate - 1) < (CL ? 0.02 : 0.005), `觸發率 ${e.fg_rate.toFixed(4)} vs ${T.fg_rate}`);
ok(Math.abs(e.rtp_total - T.rtp_total) < tol, `總 RTP ${e.rtp_total.toFixed(3)} vs ${T.rtp_total} (±${tol})`);

// 4 MC ≈ 精算
const st = S.simulate(C, 777, 1e6), r = S.report(C, st);
ok(Math.abs(r.rtp_main - e.rtp_main) < 2 * r.rtp_main_ci, `MC MG ${r.rtp_main.toFixed(3)} ≈ 精算 ${e.rtp_main.toFixed(3)} ±${(2 * r.rtp_main_ci).toFixed(3)}`);
ok(Math.abs(r.fg_rate - e.fg_rate) < 3 * 196 * Math.sqrt(e.fg_rate / 100 / 1e6), `MC 觸發率 ${r.fg_rate.toFixed(4)} ≈ ${e.fg_rate.toFixed(4)}`);
process.exit(fail ? 1 : 0);
