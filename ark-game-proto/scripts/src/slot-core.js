/* slot-core — 老虎機雛型數學核心（純函式、無 DOM；瀏覽器 / Web Worker / node 共用）
 *
 * 契約（對齊 docs/designs/2026-09-18-spinresult-config-contract-alignment.md）：
 *  - 金額一律整數 credit（bet = config.board.bet）；倍數 = credit / bet
 *  - spin(C, seed) 可重現：同 seed → 同 SpinResult；opts.rng 可換成 GoRand（與 Go 快測逐局對照）
 *  - 數學 RNG 與演出 RNG 分流：演出抽選（假轉分數 / 聽牌 / 出場順序 / 復活）用 fx 流，不吃數學流
 *  - 結果先決、演出後演：SpinResult 一次算完，Presentation 只讀不改
 *  - 抽值順序與 Go 引擎一致（輪帶組 → 各軸停點 → 倍數 WILD → 觸發 → FG），改順序 = 破壞逐局對照
 *
 * 玩法模型（cfg.fg.model）：
 *  - collect-mult（彌勒佛）：FG 贏分 = (基底 + Σ加分物件) × (1 + Σ乘倍物件)
 *  - coin-lock（Tiger and Dragon）：金幣鎖格 → 相鄰成組 → 翻值連讀成數（+ 解鎖列 / JACKPOT）
 */
(function (root) {
  'use strict';

  // ───────── RNG：splitmix32 播種 + xoshiro128** ─────────
  function splitmix32(a) {
    return function () {
      a |= 0; a = (a + 0x9e3779b9) | 0;
      let t = a ^ (a >>> 16); t = Math.imul(t, 0x21f0aaad);
      t = t ^ (t >>> 15); t = Math.imul(t, 0x735a2d97);
      return (t ^ (t >>> 15)) >>> 0;
    };
  }
  function createRng(seed) {
    const sm = splitmix32(seed >>> 0);
    let s0 = sm(), s1 = sm(), s2 = sm(), s3 = sm();
    function rotl(x, k) { return (x << k) | (x >>> (32 - k)); }
    function u32() {
      const r = Math.imul(rotl(Math.imul(s1, 5), 7), 9);
      const t = s1 << 9;
      s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = rotl(s3, 11);
      return r >>> 0;
    }
    return { seed: seed >>> 0, u32, int(n) { return Math.floor((u32() / 4294967296) * n); }, float() { return u32() / 4294967296; } };
  }

  // ───────── 權重表（與 Go GetIndexByWeight 同語意：Intn(total)，第一個累計 > r 的格）─────────
  function wtable(items, wkey) {
    const w = items.map((x) => (typeof x === 'number' ? x : x[wkey || 'w']));
    const cum = []; let s = 0;
    for (const v of w) { s += v; cum.push(s); }
    return { items, cum, total: s };
  }
  function pick(rng, t) {
    if (t.total <= 0) return t.items[0];
    const r = rng.int(t.total);
    let lo = 0, hi = t.cum.length - 1;
    while (lo < hi) { const m = (lo + hi) >> 1; if (r < t.cum[m]) hi = m; else lo = m + 1; }
    return t.items[lo];
  }
  const mean = (t, f) => t.items.reduce((s, x, i) => s + f(x) * (t.cum[i] - (i ? t.cum[i - 1] : 0)), 0) / t.total;
  const sum = (a) => a.reduce((x, y) => x + y, 0);

  // ═════════ compile：config → 執行期結構 ═════════
  function compile(cfg) {
    const pays = Object.keys(cfg.paytable);
    const SYM = cfg.symbols || pays.concat(['WW', 'SC', 'SS']);
    const sid = Object.fromEntries(SYM.map((s, i) => [s, i]));
    const toIds = (reels) => reels.map((r) => Int8Array.from(r.map((s) => (s in sid ? sid[s] : -1))));
    const sets = (cfg.strips.sets || [cfg.strips.set0, cfg.strips.set1]).map(toIds);
    const paySyms = pays.map((s) => sid[s]);
    const pay = paySyms.map((i) => { const p = cfg.paytable[SYM[i]]; return [0, 0, 0, p['3'] || 0, p['4'] || 0, p['5'] || 0]; });
    const reelsets = cfg.reelsets.map((r) => ({ ...r, use: r.use || r.flags, reels: (r.use || r.flags).map((u, i) => sets[u][i]) }));
    const WILD = sid[cfg.board.wild || 'WW'];
    const wmc = cfg.mg && cfg.mg.wild_mult;
    const tr = cfg.fg.trigger;
    const trig = tr.model === 'tiger-dragon'
      ? { model: 'tiger-dragon', t: sid[tr.tiger], d: sid[tr.dragon], gate: tr.gate, mixed: tr.mixed, rate: tr.rate }
      : { model: 'count', ids: (tr.symbols || ['SC', 'SS']).map((s) => sid[s]), min: tr.min };
    const C = {
      cfg, SYM, sid, R: cfg.board.reels, ROWS: cfg.board.rows, bet: cfg.board.bet, paySyms, pay, sets, reelsets,
      WILD, WW: WILD, SC: sid.SC, SS: sid.SS,
      wm: wmc ? { from: sid[wmc.from], to: sid[wmc.to], min: wmc.min, max: wmc.max } : null,
      trig, trigMin: trig.min || trig.gate,
      reelsetT: wtable(reelsets), maxWin: cfg.board.max_win || null,
      G: cfg.fg.groups, model: cfg.fg.model || 'collect-mult',
    };
    MODELS[C.model].compile(cfg, C);
    return C;
  }

  // ───────── win 分級（M-16 門檻）─────────
  const WIN_TIERS = [[100, 'GOLDEN'], [50, 'SUPER'], [25, 'MEGA'], [10, 'BIG'], [5, 'SMALL'], [1, 'LIGHT'], [0, 'NORMAL']];
  function winType(win, bet) {
    if (!win) return 'NO_WIN';
    const x = win / bet;
    for (const [t, n] of WIN_TIERS) if (x >= t) return n;
    return 'NORMAL';
  }

  // ═════════ MG：All Ways（第一軸須有該符號；WILD 可替代；倍數 WILD 同一 Way 相加）═════════
  // 每個符號的 Σ_路徑 倍數因子 = Π a_i + Σ_i M_i · Π_{j≠i} (a_j + w_j)   （a=該符號格數、w=WILD 格數、M=該軸 WILD 倍數和）
  function evalWays(C, grid, mult) {
    const ways = []; let win = 0;
    const A = new Array(C.R), N = new Array(C.R), Ms = new Array(C.R);
    for (let p = 0; p < C.paySyms.length; p++) {
      const s = C.paySyms[p];
      let len = 0;
      for (let r = 0; r < C.R; r++) {
        let a = 0, w = 0, m = 0;
        for (let y = 0; y < C.ROWS; y++) { const v = grid[r][y]; if (v === s) a++; else if (v === C.WILD) { w++; if (mult) m += mult[r][y]; } }
        if (r === 0 && !a) break;
        if (!(a + w)) break;
        A[r] = a; N[r] = a + w; Ms[r] = m; len++;
      }
      if (len < 3 || !C.pay[p][len]) continue;
      let nWays = 1; for (let i = 0; i < len; i++) nWays *= N[i];
      let factor = nWays;
      if (mult) {
        let pa = 1; for (let i = 0; i < len; i++) pa *= A[i];
        let pm = 0;
        for (let i = 0; i < len; i++) { if (!Ms[i]) continue; let q = Ms[i]; for (let j = 0; j < len; j++) if (j !== i) q *= N[j]; pm += q; }
        factor = pa + pm;
      }
      const w = C.pay[p][len] * factor;
      win += w;
      ways.push({ sym: C.SYM[s], len, ways: nWays, odds: C.pay[p][len], win: w, ...(mult && factor !== nWays ? { factor } : {}) });
    }
    return { win, ways };
  }

  // ═════════ 觸發 ═════════
  function trigger(C, rng, grid) {
    const T = C.trig;
    if (T.model === 'count') {
      const cnt = T.ids.map(() => 0);
      for (let r = 0; r < C.R; r++) for (let y = 0; y < C.ROWS; y++) { const k = T.ids.indexOf(grid[r][y]); if (k >= 0) cnt[k]++; }
      return { cnt, type: sum(cnt) >= T.min ? 0 : -1 };
    }
    // tiger-dragon（Go check.specialGameCheck 同順序）：混合 ≥5 → T&D；虎 ≥3；龍 ≥3；否則隨機觸發（rate 萬分率 × 顆數）
    let t = 0, d = 0;
    for (let r = 0; r < C.R; r++) for (let y = 0; y < C.ROWS; y++) { const v = grid[r][y]; if (v === T.t) t++; else if (v === T.d) d++; }
    const mixed = t + d, cnt = [t, d];
    if (mixed >= T.mixed) return { cnt, type: 2 };
    if (t >= T.gate) return { cnt, type: 0 };
    if (d >= T.gate) return { cnt, type: 1 };
    if (T.rate > 0) {
      if (t >= 1 && d >= 1 && rng.int(10000) < T.rate * mixed) return { cnt, type: 2, mystery: true };
      if (t >= 1 && rng.int(10000) < T.rate * t) return { cnt, type: 0, mystery: true };
      if (d >= 1 && rng.int(10000) < T.rate * d) return { cnt, type: 1, mystery: true };
    }
    return { cnt, type: -1 };
  }

  // ═════════ 單局 ═════════
  function spin(C, seed, opts) {
    opts = opts || {};
    const rng = opts.rng || createRng(seed);
    const fx = createRng((seed ^ 0x5bd1e995) >>> 0);
    const rs = pick(rng, C.reelsetT);
    const stops = [], grid = [];
    for (let r = 0; r < C.R; r++) {
      const strip = rs.reels[r], L = strip.length, st = rng.int(L);
      stops.push(st);
      const col = [];
      for (let y = 0; y < C.ROWS; y++) col.push(strip[(st + y) % L]);
      grid.push(col);
    }
    let mult = null, preGrid = null;
    if (C.wm) {                                   // 銅鑼 → 倍數 WILD（逐軸逐列，各自擲倍數）
      preGrid = opts.present ? grid.map((c) => c.slice()) : null;
      mult = grid.map((col) => col.map(() => 0));
      for (let r = 0; r < C.R; r++) for (let y = 0; y < C.ROWS; y++) if (grid[r][y] === C.wm.from) { grid[r][y] = C.wm.to; mult[r][y] = C.wm.min + rng.int(C.wm.max - C.wm.min + 1); }
    }
    const mg = evalWays(C, grid, mult);
    const tg = trigger(C, rng, grid);
    const M = MODELS[C.model];
    const res = { seed: seed >>> 0, reelset: rs.idx, flags: rs.use, stops, grid, mult, mgWin: mg.win, ways: mg.ways, trig: tg, fg: null, bet: C.bet };
    if (C.model === 'collect-mult') { res.nSC = tg.cnt[0]; res.nSS = tg.cnt[1]; }
    if (tg.type >= 0) res.fg = M.play(C, rng, res, !!opts.present);
    // MaxWin：MG + FG 合計封頂（fg.win 保留未封頂自然值）
    const raw = mg.win + (res.fg ? res.fg.win : 0), cap = C.maxWin ? C.maxWin * C.bet : Infinity;
    res.totalWin = Math.min(raw, cap); res.capped = raw > cap;
    res.winType = winType(res.totalWin, C.bet);
    if (opts.present) {
      res.symGrid = grid.map((col) => col.map((v) => C.SYM[v]));
      if (preGrid) res.preGrid = preGrid.map((col) => col.map((v) => C.SYM[v]));
      M.present(C, fx, res);
    }
    return res;
  }

  // ═════════ 玩法模型 ═════════
  const MODELS = {};

  // ───── collect-mult（彌勒佛）─────
  const TYPES = [['coin', '金幣'], ['carp', '鯉魚'], ['gold', '金龍'], ['color', '彩龍']];
  MODELS['collect-mult'] = {
    compile(cfg, C) {
      const fg = cfg.fg, it = fg.items, yes = (tab, g) => wtable([{ v: true, w: tab[g][0] }, { v: false, w: tab[g][1] }]);
      const per = {};
      for (const g of C.G) {
        per[g] = {
          preview: yes(fg.preview, g), all888: yes(fg.all888, g),
          coinN: wtable(it.coin.count.values.map((v, i) => ({ v, w: it.coin.count[g][i] }))),
          coinV: wtable(it.coin.odds.values.map((v, i) => ({ v, w: it.coin.odds[g][i] }))),
          carpN: wtable(it.carp.count.values.map((v, i) => ({ v, w: it.carp.count[g][i] }))),
          carpV: wtable(it.carp.odds.values.map((v, i) => ({ v, w: it.carp.odds[g][i] }))),
          goldN: wtable(it.gold.count.values.map((v, i) => ({ v, w: it.gold.count[g][i] }))),
          colorN: wtable(it.color.count.values.map((v, i) => ({ v, w: it.color.count[g][i] }))),
        };
      }
      const tease = cfg.mg.tease;
      Object.assign(C, {
        per, groupT: wtable(C.G.map((g) => ({ g, w: fg.group_w[g] }))),
        entrySC: wtable(fg.entry_scores.sc), entrySS: wtable(fg.entry_scores.ss),
        fakeSC: wtable(cfg.mg.fake_scores.sc), fakeSS: wtable(cfg.mg.fake_scores.ss),
        teaseT: wtable([{ v: true, w: tease['是'] || 0 }, { v: false, w: tease['否'] || 0 }]),
        orderT: ['first2', 'later'].map((k) => fg.order[k]), revive: fg.revive,
        ssMode: fg.ss_mul_mode || 'sc_sum', itemMult: { gold: it.gold.mult, color: it.color.mult },
      });
    },
    play(C, rng, res) {
      const nSC = res.nSC, nSS = res.nSS;
      const g = pick(rng, C.groupT).g, P = C.per[g];
      const preview = pick(rng, P.preview).v;
      const all888 = preview && pick(rng, P.all888).v;
      const entry = { sc: [], ss: [] };
      let scSum = 0, ssNum = 0, mul = 1;
      for (let i = 0; i < nSC; i++) { const v = all888 ? 888 : pick(rng, C.entrySC).v; scSum += v; entry.sc.push(v); }
      for (let i = 0; i < nSS; i++) { const x = pick(rng, C.entrySS); if (x.mul) mul *= x.mul; else ssNum += x.v; entry.ss.push(x.mul ? { mul: x.mul } : { v: x.v }); }
      const base = C.ssMode === 'total' ? (scSum + ssNum) * mul : scSum * mul + ssNum;
      const nc = pick(rng, P.coinN).v, nk = pick(rng, P.carpN).v, ng = pick(rng, P.goldN).v, nr = pick(rng, P.colorN).v;
      const coins = [], carps = [];
      for (let i = 0; i < nc; i++) coins.push(pick(rng, P.coinV).v);
      for (let i = 0; i < nk; i++) carps.push(pick(rng, P.carpV).v);
      const mult = 1 + ng * C.itemMult.gold + nr * C.itemMult.color;
      return { model: 'collect-mult', group: g, preview, all888, entry, base, coins, carps, gold: ng, color: nr, mult, win: (base + sum(coins) + sum(carps)) * mult };
    },
    present(C, fx, res) {
      const fg = res.fg, grid = res.grid, tags = [];
      let ei = 0, si = 0, nSC14 = 0;
      for (let r = 0; r < C.R; r++) for (let y = 0; y < C.ROWS; y++) {
        const v = grid[r][y];
        if (v === C.SC) { if (r < 4) nSC14++; tags.push({ r, y, sym: 'SC', ...(fg ? { v: fg.entry.sc[ei++] } : { v: pick(fx, C.fakeSC).v }) }); }
        if (v === C.SS) tags.push({ r, y, sym: 'SS', ...(fg ? fg.entry.ss[si++] : (() => { const x = pick(fx, C.fakeSS); return x.mul ? { mul: x.mul } : { v: x.v }; })()) });
      }
      res.tags = tags;
      res.tease = nSC14 >= 6 && grid[4].includes(C.SS) ? pick(fx, C.teaseT).v : false;
      if (fg) Object.assign(fg, stageCollect(C, fx, fg));
    },
    statsAdd(g, f) { g.base = (g.base || 0) + f.base; g.mult = (g.mult || 0) + f.mult; g.gold = (g.gold || 0) + f.gold; g.color = (g.color || 0) + f.color; g.coin = (g.coin || 0) + sum(f.coins); g.carp = (g.carp || 0) + sum(f.carps); },
    groupReport(x, b) { return { base: x.base / x.n / b, mult: x.mult / x.n, coin_win: x.coin / x.n / b, carp_win: x.carp / x.n / b, gold: x.gold / x.n, color: x.color / x.n }; },
  };
  function stageCollect(C, fx, fg) {
    const left = { coin: fg.coins.slice(), carp: fg.carps.slice(), gold: fg.gold, color: fg.color };
    const remain = (k) => (Array.isArray(left[k]) ? left[k].length : left[k]);
    const seq = [];
    let acc = fg.base, mult = 1;
    for (let k = 0; ; k++) {
      const pool = TYPES.filter(([t]) => remain(t) > 0);
      if (!pool.length) break;
      const w = C.orderT[k < 2 ? 0 : 1];
      let t = wtable(pool.map(([tt, zh]) => ({ t: tt, w: w[zh] || 0 })));
      if (t.total <= 0) t = wtable(pool.map(([tt]) => ({ t: tt, w: 1 })));
      const ty = pick(fx, t).t;
      let v = null;
      if (ty === 'coin' || ty === 'carp') { v = left[ty].shift(); acc += v; } else { left[ty]--; mult += C.itemMult[ty]; }
      seq.push({ type: ty, v, acc, mult, total: acc * mult });
    }
    let revive = null;
    const rv = C.revive;
    if (rv && fg.win >= rv.threshold * C.bet && (fg.gold + fg.color) > 0) {
      const yesT = wtable([{ v: true, w: rv.chance['是'] || 0 }, { v: false, w: rv.chance['否'] || 0 }]);
      if (pick(fx, yesT).v) {
        const kg = pick(fx, wtable(rv.keep.gold.map((w, i) => ({ v: i, w })))).v;
        const kc = pick(fx, wtable(rv.keep.color.map((w, i) => ({ v: i, w })))).v;
        revive = { keepGold: Math.min(kg, fg.gold), keepColor: Math.min(kc, fg.color) };
        const held = [];
        let hg = revive.keepGold, hc = revive.keepColor;
        for (let i = seq.length - 1; i >= 0 && (hg || hc); i--) {
          if (seq[i].type === 'gold' && hg) { held.unshift(seq.splice(i, 1)[0]); hg--; }
          else if (seq[i].type === 'color' && hc) { held.unshift(seq.splice(i, 1)[0]); hc--; }
        }
        let a = fg.base, m = 1;
        for (const s of seq) { if (s.v != null) a += s.v; else m += C.itemMult[s.type]; s.acc = a; s.mult = m; s.total = a * m; }
        revive.at = seq.length;
        for (const s of held) { m += C.itemMult[s.type]; s.acc = a; s.mult = m; s.total = a * m; s.revived = true; seq.push(s); }
      }
    }
    return { seq, revive };
  }

  // ───── coin-lock（Tiger and Dragon）─────
  MODELS['coin-lock'] = {
    compile(cfg, C) {
      const fg = cfg.fg, F = fg.flip;
      Object.assign(C, { bonus: fg.bonus, flip: { ...F, oneT: wtable(F.one_dist.map((w, i) => ({ v: i + 1, w }))) }, unlock: fg.unlock, jackpot: fg.jackpot });
    },
    // Go freeGameProcess 同順序：每手逐軸逐列擲停入率 → 解鎖 / JACKPOT → 重置 → 滿盤提前結束；結算逐列由左至右成組翻值
    play(C, rng, res, rec) {
      const type = res.trig.type, B = C.bonus[type], U = C.unlock, J = C.jackpot;
      const reels = B.reels, rows = B.rows, isTD = type === U.bonus;
      const locked = []; for (let c = 0; c < reels; c++) locked.push(new Uint8Array(rows));
      let unlocked = isTD ? U.base_rows : rows, coins = 0, jp = false, remain = B.spins, spins = 0;
      const timeline = rec ? [] : null;
      while (remain > 0) {
        remain--; spins++;
        let dropped = false; const drops = rec ? [] : null;
        for (let c = 0; c < reels; c++) for (let r = 0; r < rows; r++) {
          if (locked[c][r] || (isTD && r >= unlocked)) continue;
          if (rng.int(10000) < B.coin_rate) {
            locked[c][r] = 1; dropped = true; if (drops) drops.push([c, r]);
            if (isTD) {
              coins++;
              while (unlocked < rows) { const i = unlocked - U.base_rows; if (i >= 0 && i < U.thresholds.length && coins >= U.thresholds[i]) unlocked++; else break; }
              if (!jp && J && type === J.bonus && coins >= J.threshold) jp = true;
            }
          }
        }
        if (dropped && B.reset) remain = B.spins;
        let full = true;
        for (let c = 0; c < reels && full; c++) for (let r = 0; r < (isTD ? unlocked : rows); r++) if (!locked[c][r]) { full = false; break; }
        if (timeline) timeline.push({ drops, unlocked, remain: full ? 0 : remain, coins });
        if (full) break;
      }
      const groups = []; let win = 0;
      for (let r = 0; r < rows; r++) {
        let c = 0;
        while (c < reels) {
          if (!locked[c][r]) { c++; continue; }
          const start = c; while (c < reels && locked[c][r]) c++;
          const len = c - start;
          if (len >= 2) { const g = settleGroup(C, rng, len); win += g.value; if (rec) groups.push({ row: r, start, len, ...g }); }
        }
      }
      const jpWin = jp ? J.multiple * C.bet : 0;
      win += jpWin;
      // MaxWin（Go：對 MG + 本次 Bonus 合計封頂，扣在 Bonus；Bonus 統計記封頂後的值）
      const raw = win, mgW = res.mgWin || 0;
      if (C.maxWin && mgW + win > C.maxWin * C.bet) win = Math.max(0, C.maxWin * C.bet - mgW);
      let lockedN = 0; for (let c = 0; c < reels; c++) for (let r = 0; r < rows; r++) lockedN += locked[c][r];
      return { model: 'coin-lock', type, group: C.G[type], mystery: !!res.trig.mystery, win, raw, capped: raw > win, spins, coins: lockedN, jackpot: jp, jpWin,
        unlocked, reels, rows, ...(rec ? { timeline, groups, locked: locked.map((col) => Array.from(col)) } : {}) };
    },
    present(C, fx, res) {
      const tags = [];
      if (res.mult) for (let r = 0; r < C.R; r++) for (let y = 0; y < C.ROWS; y++) if (res.mult[r][y]) tags.push({ r, y, sym: C.SYM[C.WILD], mul: res.mult[r][y] });
      res.tags = tags; res.tease = false;
    },
    statsAdd(g, f) { g.spins = (g.spins || 0) + f.spins; g.jp = (g.jp || 0) + (f.jackpot ? 1 : 0); g.myst = (g.myst || 0) + (f.mystery ? 1 : 0); g.coins = (g.coins || 0) + f.coins; },
    groupReport(x) { return { spins: x.spins / x.n, jp_rate: (100 * x.jp) / x.n, mystery: (100 * x.myst) / x.n, coins: x.coins / x.n }; },
  };
  // 一組相鄰金幣翻值：最左不可箭頭；箭頭值 0 並把 +N 加到最左位；兩位數佔兩位；由左至右連讀
  function settleGroup(C, rng, len) {
    const F = C.flip, vals = [], kinds = []; let add = 0;
    for (let i = 0; i < len; i++) {
      const aw = i === 0 ? 0 : F.arrow_w, n = rng.int(aw + F.two_w + F.one_w);
      if (n < aw) { kinds.push('arrow'); vals.push(0); add += F.arrow_add_min + rng.int(F.arrow_add_max - F.arrow_add_min + 1); }
      else if (n < aw + F.two_w) { kinds.push('two'); vals.push(F.two_min + rng.int(F.two_max - F.two_min + 1)); }
      else { kinds.push('one'); vals.push(pick(rng, F.oneT).v); }
    }
    const raw = vals.slice();
    vals[0] += add;
    let value = 0;
    for (const v of vals) value = v < 10 ? value * 10 + v : value * 100 + v;
    return { value, vals, raw, kinds, arrowAdd: add };
  }

  // ═════════ 情境搜尋：「強制」= 找出真的會出這個結果的 seed（不改結果）═════════
  function findSeed(C, pred, start, limit) {
    let s = (start >>> 0) || 1;
    for (let i = 0; i < (limit || 5e6); i++, s = (s + 1) >>> 0) if (pred(spin(C, s))) return s;
    return null;
  }

  // ═════════ 蒙地卡羅累加器（可合併；給 Worker 分段跑）═════════
  function newStats(C) {
    return {
      spins: 0, mgWin: 0, mgWin2: 0, mgHit: 0, mgMax: 0, totWin: 0, totWin2: 0, capN: 0,
      fgN: 0, fgWin: 0, fgWin2: 0, fgMax: 0, fgBase: 0, fgBase2: 0, all888N: 0, all888Win: 0,
      group: Object.fromEntries(C.G.map((g) => [g, { n: 0, win: 0, win2: 0, max: 0 }])),
      trig: {}, entrySC: {}, reelset: C.reelsets.map(() => ({ n: 0, mg: 0, fg: 0 })),
      symHit: Object.fromEntries(C.paySyms.map((s) => [C.SYM[s], 0])), tiers: {},
    };
  }
  function addSpin(st, r, C) {
    st.spins++;
    st.mgWin += r.mgWin; st.mgWin2 += r.mgWin * r.mgWin;
    if (r.mgWin > 0) st.mgHit++;
    if (r.mgWin > st.mgMax) st.mgMax = r.mgWin;
    for (const w of r.ways) st.symHit[w.sym]++;
    st.totWin += r.totalWin; st.totWin2 += r.totalWin * r.totalWin; if (r.capped) st.capN++;
    st.tiers[r.winType] = (st.tiers[r.winType] || 0) + 1;
    const rs = st.reelset[r.reelset]; rs.n++; rs.mg += r.mgWin;
    if (r.fg) {
      const f = r.fg, g = st.group[f.group];
      st.fgN++; st.fgWin += f.win; st.fgWin2 += f.win * f.win;
      if (f.win > st.fgMax) st.fgMax = f.win;
      g.n++; g.win += f.win; g.win2 += f.win * f.win; if (f.win > g.max) g.max = f.win;
      MODELS[f.model].statsAdd(g, f);
      if (f.model === 'collect-mult') {
        st.fgBase += f.base; st.fgBase2 += f.base * f.base;
        if (f.all888) { st.all888N++; st.all888Win += f.win; }
        const k = r.nSC + r.nSS; st.trig[k] = (st.trig[k] || 0) + 1;
        const e = st.entrySC[r.nSC] || (st.entrySC[r.nSC] = { n: 0, win: 0 }); e.n++; e.win += f.win;
      }
      rs.fg += f.win;
    }
  }
  function merge(a, b) {
    for (const k of ['spins', 'mgWin', 'mgWin2', 'mgHit', 'totWin', 'totWin2', 'capN', 'fgN', 'fgWin', 'fgWin2', 'fgBase', 'fgBase2', 'all888N', 'all888Win']) a[k] += b[k] || 0;
    a.mgMax = Math.max(a.mgMax, b.mgMax); a.fgMax = Math.max(a.fgMax, b.fgMax);
    for (const g in b.group) for (const k in b.group[g]) a.group[g][k] = k === 'max' ? Math.max(a.group[g][k] || 0, b.group[g][k]) : (a.group[g][k] || 0) + b.group[g][k];
    for (const k in b.trig) a.trig[k] = (a.trig[k] || 0) + b.trig[k];
    for (const k in b.entrySC) { const e = a.entrySC[k] || (a.entrySC[k] = { n: 0, win: 0 }); e.n += b.entrySC[k].n; e.win += b.entrySC[k].win; }
    b.reelset.forEach((r, i) => { a.reelset[i].n += r.n; a.reelset[i].mg += r.mg; a.reelset[i].fg += r.fg; });
    for (const k in b.symHit) a.symHit[k] += b.symHit[k];
    for (const k in b.tiers) a.tiers[k] = (a.tiers[k] || 0) + b.tiers[k];
    return a;
  }
  function simulate(C, seed0, n, st) {
    st = st || newStats(C);
    for (let i = 0; i < n; i++) addSpin(st, spin(C, (seed0 + i) >>> 0), C);
    return st;
  }
  // 累加器 → 與 §2 同口徑的指標（%、倍）＋ 95% 信賴區間半寬
  function report(C, st) {
    const N = st.spins, b = C.bet, pct = (x) => (100 * x) / N / b;
    const ci = (s, s2, n) => { n = n || N; const m = s / n, v = s2 / n - m * m; return (196 * Math.sqrt(Math.max(v, 0) / n)) / b; };
    const G = {};
    for (const g of C.G) {
      const x = st.group[g];
      G[g] = x.n ? { n: x.n, share: (100 * x.n) / st.fgN, rate: (100 * x.n) / N, avg_win: x.win / x.n / b, avg_ci: ci(x.win, x.win2, x.n) / 100, max: x.max / b,
        rtp: pct(x.win), ...MODELS[C.model].groupReport(x, b) } : { n: 0 };
    }
    const trig = {}, entry = {};
    for (const k in st.trig) trig[k] = (100 * st.trig[k]) / st.fgN;
    for (const k in st.entrySC) entry[k] = { share: (100 * st.entrySC[k].n) / st.fgN, avg_win: st.entrySC[k].win / st.entrySC[k].n / b, n: st.entrySC[k].n };
    return {
      spins: N,
      rtp_total: pct(st.totWin), rtp_total_ci: ci(st.totWin, st.totWin2),
      rtp_main: pct(st.mgWin), rtp_main_ci: ci(st.mgWin, st.mgWin2),
      rtp_free: pct(st.fgWin),
      mg_hit: (100 * st.mgHit) / N, mg_max: st.mgMax / b,
      fg_rate: (100 * st.fgN) / N, fg_freq: st.fgN ? N / st.fgN : null,
      fg_avg: st.fgN ? st.fgWin / st.fgN / b : null, fg_max: st.fgMax / b,
      fg_base: st.fgN && st.fgBase ? st.fgBase / st.fgN / b : null,
      all888_rate: st.fgN && C.model === 'collect-mult' ? (100 * st.all888N) / st.fgN : null, all888_avg: st.all888N ? st.all888Win / st.all888N / b : null,
      groups: G, trig, entry,
      reelsets: st.reelset.map((r) => ({ n: r.n, mg: r.n ? (100 * r.mg) / r.n / b : null, fg: r.n ? (100 * r.fg) / r.n / b : null })),
      cap_rate: (100 * st.capN) / N,
      symhit_total: (100 * Object.values(st.symHit).reduce((a, c) => a + c, 0)) / N,
      tiers: st.tiers,
    };
  }

  // ═════════ L1 精算（MG 與觸發不抽樣；coin-lock Bonus 以直接抽樣估期望）═════════
  function exact(C, opts) {
    opts = typeof opts === 'string' ? { ssMode: opts } : opts || {};
    const b = C.bet, W = C.reelsetT.total;
    const isWild = (v) => v === C.WILD || (C.wm && v === C.wm.from);
    const mMean = C.wm ? (C.wm.min + C.wm.max) / 2 : 0;
    const conv2 = (A, B) => {
      const out = []; for (let i = 0; i < A.length + B.length - 1; i++) out.push(new Array(A[0].length + B[0].length - 1).fill(0));
      A.forEach((ra, i) => ra.forEach((pa, j) => { if (pa) B.forEach((rb, k) => rb.forEach((pb, l) => { if (pb) out[i + k][j + l] += pa * pb; })); }));
      return out;
    };
    const pairIds = C.trig.model === 'count' ? C.trig.ids : [C.trig.t, C.trig.d];
    const rsOut = []; let mgW = 0; const joint = {};
    for (const rs of C.reelsets) {
      let mg = 0;
      for (let p = 0; p < C.paySyms.length; p++) {
        const s = C.paySyms[p];
        const EA = [], EN = [], EM = [], P0 = [];
        rs.reels.forEach((st, ri) => {
          const L = st.length; let ea = 0, en = 0, em = 0, p0 = 0;
          for (let i = 0; i < L; i++) {
            let a = 0, w = 0;
            for (let y = 0; y < C.ROWS; y++) { const v = st[(i + y) % L]; if (v === s) a++; else if (isWild(v)) w++; }
            if (!(a + w)) p0++;
            if (ri === 0 && !a) continue;        // 第一軸須有該符號本身
            ea += a; en += a + w; em += w * mMean;
          }
          EA.push(ea / L); EN.push(en / L); EM.push(em / L); P0.push(p0 / L);
        });
        for (let k = 3; k <= C.R; k++) {
          if (!C.pay[p][k]) continue;
          let f;
          if (C.wm) {
            let pa = 1; for (let i = 0; i < k; i++) pa *= EA[i];
            let pm = 0; for (let i = 0; i < k; i++) { let q = EM[i]; for (let j = 0; j < k; j++) if (j !== i) q *= EN[j]; pm += q; }
            f = pa + pm;
          } else { f = 1; for (let i = 0; i < k; i++) f *= EN[i]; }
          mg += C.pay[p][k] * f * (k < C.R ? P0[k] : 1);
        }
      }
      let D = [[1]];
      for (const st of rs.reels) {
        const L = st.length, d2 = []; for (let i = 0; i <= C.ROWS; i++) d2.push(new Array(C.ROWS + 1).fill(0));
        for (let i = 0; i < L; i++) { let a = 0, c = 0; for (let y = 0; y < C.ROWS; y++) { const v = st[(i + y) % L]; if (v === pairIds[0]) a++; else if (v === pairIds[1]) c++; } d2[a][c] += 1 / L; }
        D = conv2(D, d2);
      }
      const pt = [0, 0, 0];
      D.forEach((row, a) => row.forEach((p, c) => {
        if (!p) return;
        const k = a + ',' + c;
        joint[k] = (joint[k] || 0) + (p * rs.w) / W;
        trigProb(C, a, c).forEach((q, i) => (pt[i] += p * q));
      }));
      rsOut.push({ idx: rs.idx, w: rs.w, mg_rtp: (100 * mg) / b, trig: 100 * sum(pt), trigs: pt.map((x) => 100 * x), spec_mg: rs.spec_total != null ? 100 * (rs.spec_total - rs.spec_fg) : null });
      mgW += (mg * rs.w) / W;
    }
    const trigs = [0, 1, 2].map((i) => sum(rsOut.map((r) => (r.trigs[i] * r.w) / W)));
    const base = { reelsets: rsOut, rtp_main: (100 * mgW) / b, fg_rate: sum(trigs), trigs };
    const fg = EXACT_FG[C.model](C, joint, base, opts);
    return { ...base, ...fg, rtp_total: base.rtp_main + fg.rtp_free };
  }
  // 觸發機率（給定盤面 (a,c) 顆數）→ [P(type0), P(type1), P(type2)]
  function trigProb(C, a, c) {
    const T = C.trig;
    if (T.model === 'count') return [a + c >= T.min ? 1 : 0, 0, 0];
    const m = a + c, r = T.rate / 10000;
    if (m >= T.mixed) return [0, 0, 1];
    if (a >= T.gate) return [1, 0, 0];
    if (c >= T.gate) return [0, 1, 0];
    let left = 1; const out = [0, 0, 0];
    if (a >= 1 && c >= 1) { const q = Math.min(1, r * m); out[2] = q; left *= 1 - q; }
    if (a >= 1) { const q = Math.min(1, r * a); out[0] = left * q; left *= 1 - q; }
    if (c >= 1) { const q = Math.min(1, r * c); out[1] = left * q; }
    return out;
  }
  const EXACT_FG = {
    'collect-mult'(C, joint, base, opts) {
      const ssMode = opts.ssMode || C.ssMode, b = C.bet, trigW = base.fg_rate / 100;
      for (const k in joint) { const [a, c] = k.split(',').map(Number); if (a + c < C.trig.min) delete joint[k]; }
      const muSC = mean(C.entrySC, (x) => x.v);
      const Em = mean(C.entrySS, (x) => x.mul || 1), Enum = mean(C.entrySS, (x) => (x.mul ? 0 : x.v));
      const baseOf = (a, c, all888) => { const A = a * (all888 ? 888 : muSC); return ssMode === 'total' ? A * Em ** c + (c ? c * Enum * Em ** (c - 1) : 0) : A * Em ** c + c * Enum; };
      const grp = {}; let fgWin = 0, Ebase = 0;
      for (const g of C.G) {
        const P = C.per[g], pg = C.groupT.items.find((x) => x.g === g).w / C.groupT.total;
        const p888 = (P.preview.items[0].w / P.preview.total) * (P.all888.items[0].w / P.all888.total);
        const nC = mean(P.coinN, (x) => x.v), vC = mean(P.coinV, (x) => x.v), nK = mean(P.carpN, (x) => x.v), vK = mean(P.carpV, (x) => x.v);
        const nG = mean(P.goldN, (x) => x.v), nR = mean(P.colorN, (x) => x.v);
        const mult = 1 + nG * C.itemMult.gold + nR * C.itemMult.color, add = nC * vC + nK * vK;
        let eb = 0;
        for (const k in joint) { const [a, c] = k.split(',').map(Number); const q = joint[k] / trigW; eb += q * (p888 * baseOf(a, c, true) + (1 - p888) * baseOf(a, c, false)); }
        grp[g] = { p: pg, p888, coin: nC, carp: nK, gold: nG, color: nR, mult, coin_win: (nC * vC) / b, carp_win: (nK * vK) / b, base: eb / b, avg_win: ((eb + add) * mult) / b };
        fgWin += pg * (eb + add) * mult; Ebase += pg * eb;
      }
      const entry = {}, bySC = {};
      for (const k in joint) { const [a] = k.split(',').map(Number); (bySC[a] = bySC[a] || []).push(k); }
      for (const a in bySC) {
        let pa = 0, w = 0;
        for (const k of bySC[a]) {
          const c = Number(k.split(',')[1]), q = joint[k]; pa += q;
          for (const g of C.G) { const x = grp[g]; w += q * x.p * ((x.p888 * baseOf(+a, c, true) + (1 - x.p888) * baseOf(+a, c, false) + (x.coin_win + x.carp_win) * b) * x.mult); }
        }
        entry[a] = { share: (100 * pa) / trigW, avg_win: w / pa / b };
      }
      const trig = {};
      for (const k in joint) { const [a, c] = k.split(',').map(Number); trig[a + c] = (trig[a + c] || 0) + (100 * joint[k]) / trigW; }
      return { ssMode, fg_avg: fgWin / b, fg_base: Ebase / b, rtp_free: (100 * trigW * fgWin) / b, groups: grp, entry, trig,
        avg_mult: C.G.reduce((s, g) => s + grp[g].p * grp[g].mult, 0) };
    },
    // coin-lock：觸發率精算；每種 Bonus 期望以「直接抽樣 N 次」估（固定 seed，附 95% CI）
    'coin-lock'(C, joint, base, opts) {
      const N = opts.bonusN || 50000, b = C.bet, grp = {};
      let fgWin = 0;
      C.G.forEach((g, t) => {
        const rng = createRng(0xb0b0 + t);
        let s = 0, s2 = 0, sp = 0, jp = 0;
        for (let i = 0; i < N; i++) { const f = MODELS['coin-lock'].play(C, rng, { trig: { type: t } }, false); s += f.win; s2 += f.win * f.win; sp += f.spins; jp += f.jackpot ? 1 : 0; }
        const m = s / N, sd = Math.sqrt(Math.max(s2 / N - m * m, 0));
        grp[g] = { rate: base.trigs[t], avg_win: m / b, avg_ci: (1.96 * sd) / Math.sqrt(N) / b, spins: sp / N, jp_rate: (100 * jp) / N, n: N,
          rtp: (base.trigs[t] * m) / b };
        fgWin += (base.trigs[t] / 100) * m;
      });
      const tr = base.fg_rate / 100;
      return { fg_avg: tr ? fgWin / tr / b : 0, rtp_free: (100 * fgWin) / b, groups: grp, bonusN: N };
    },
  };

  const API = { createRng, compile, spin, evalWays, simulate, newStats, addSpin, merge, report, exact, findSeed, winType, WIN_TIERS, settleGroup };
  root.SlotCore = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof self !== 'undefined' ? self : globalThis);
