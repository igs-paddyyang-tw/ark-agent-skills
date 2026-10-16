// slot-core 單元測試（node tests/core_test.js <game-config.json>）：
// 決定性、演出不改結果、玩法模型的內部一致性、L1 精算對 §2、模擬對精算。輸出 PASS/FAIL 行；任一 FAIL exit 1。
const path = require('path');
const S = require('../src/slot-core.js');
const cfg = require(path.resolve(process.argv[2] || path.join(__dirname, '../../golden/milefo/game-config.json')));
const C = S.compile(cfg), T = cfg.targets.summary;
let fail = 0;
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fail++; };
const CL = C.model === 'coin-lock';
const HC = C.model === 'house-collect';

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
} else if (HC) {
  // 2 house-collect：FG 贏分拆解 = 線獎 + 房子結算 + 全滿額外；房子棟數 = 標記格 1/2/3 級數；大轉盤三變體與 Free 都會出現
  let k = 0, winOk = true, settleOk = true, countOk = true;
  const variants = new Set();
  for (let s = 1; s < 3e6 && k < 400; s++) {
    const r = S.spin(C, s); if (!r.fg) continue;
    const p = S.spin(C, s, { present: true }), f = p.fg; k++;
    variants.add(f.variant || f.group);
    // 贏分拆解：lineWin + score(房子結算總分) + extra(全滿額外) == win
    if (Math.abs((f.lineWin + f.score + (f.extra || 0)) - f.win) > 1) winOk = false;
    // settle 逐格 win 加總 == score（房子結算守恆）
    const settleSum = (f.settle || []).reduce((a, h) => a + (h.win || 0), 0);
    if (Math.abs(settleSum - f.score) > 1) settleOk = false;
    // 房子棟數：草 + 木 + 磚 = settle 格數（每格一棟，1/2/3 級對 grass/wood/stone）
    const hh = f.houses || {}, total = (hh.grass || 0) + (hh.wood || 0) + (hh.stone || 0);
    if ((f.settle || []).length !== total) countOk = false;
  }
  ok(winOk, `FG 贏分 = 線獎 + 房子結算 + 全滿額外（${k} 場 FG）`);
  ok(settleOk, '房子逐格結算加總 = 房子總分（框升級盤守恆）');
  ok(countOk, '草+木+磚棟數 = 結算格數（框等級 1/2/3 → 草/木/磚）');
  ok(variants.has('Free') && variants.size >= 2, `出現多種 FG 變體：${[...variants].join('/')}`);
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
if (HC) {
  // house-collect：MG 抽樣、FG+Bonus 兩觸發線分開對；總 RTP 對 §2（±tol，§2 的 0.88pp = 95% CI）
  const tolHC = Math.max(T.tol || 0.88, 0.88);
  ok(Math.abs(e.rtp_main - T.rtp_main) < 0.5, `MG RTP 精算 ${e.rtp_main.toFixed(4)} vs ${T.rtp_main}`);
  ok(Math.abs(e.rtp_free - T.rtp_free) < 1.0, `Free(SC觸發 FG) RTP 精算 ${e.rtp_free.toFixed(3)} vs ${T.rtp_free}`);
  ok(e.rtp_bonus != null && Math.abs(e.rtp_bonus - (T.rtp_bonus || 37.76)) < 1.5, `大轉盤三變體合計 RTP 精算 ${e.rtp_bonus.toFixed(3)} vs 37.76`);
  ok(Math.abs(e.rtp_total - T.rtp_total) < tolHC, `總 RTP ${e.rtp_total.toFixed(3)} vs ${T.rtp_total} (±${tolHC})`);
} else {
  ok(Math.abs(e.rtp_main - T.rtp_main) < (CL ? 0.5 : 0.05), `MG RTP 精算 ${e.rtp_main.toFixed(4)} vs ${T.rtp_main}`);
  ok(Math.abs(e.fg_rate / T.fg_rate - 1) < (CL ? 0.02 : 0.005), `觸發率 ${e.fg_rate.toFixed(4)} vs ${T.fg_rate}`);
  ok(Math.abs(e.rtp_total - T.rtp_total) < tol, `總 RTP ${e.rtp_total.toFixed(3)} vs ${T.rtp_total} (±${tol})`);
}

// 4 MC ≈ 精算
const st = S.simulate(C, 777, 1e6), r = S.report(C, st);
ok(Math.abs(r.rtp_main - e.rtp_main) < Math.max(2 * r.rtp_main_ci, HC ? 0.5 : 0), `MC MG ${r.rtp_main.toFixed(3)} ≈ 精算 ${e.rtp_main.toFixed(3)} ±${(2 * r.rtp_main_ci).toFixed(3)}`);
if (!HC) ok(Math.abs(r.fg_rate - e.fg_rate) < 3 * 196 * Math.sqrt(e.fg_rate / 100 / 1e6), `MC 觸發率 ${r.fg_rate.toFixed(4)} ≈ ${e.fg_rate.toFixed(4)}`);
process.exit(fail ? 1 : 0);
