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
 *  - house-collect（吉屋出豬）：SC 落格框升級 → 結算抽草/木/磚屋
 *  - huff-house（Huff N' Puff Open House）：四建材各擲觸發率 → House Spin 加框 ×4 ／ ≥6 顆 Open House 四房闖關
 *    數學流只用 Float64（rng.float），與 Go internal/engine/huff 同序（C.fdraw）
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
  // Float64 抽值（Go huff 引擎 pickW / floorIdx 同語意：r = f × 總和，逐項扣減）
  function pickF(rng, w) {
    let t = 0; for (const x of w) t += x;
    let r = rng.float() * t;
    for (let i = 0; i < w.length; i++) { r -= w[i]; if (r < 0) return i; }
    return w.length - 1;
  }
  const floorF = (rng, n) => Math.floor(rng.float() * n);

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
    let trig;
    if (tr.model === 'tiger-dragon') {
      trig = { model: 'tiger-dragon', t: sid[tr.tiger], d: sid[tr.dragon], gate: tr.gate, mixed: tr.mixed, rate: tr.rate };
    } else if (tr.model === 'house') {
      // 大轉盤分流：wheel = [{variant, type, w}]（type 1..3 對應三 FG 變體，0 保留給 SC 觸發的 Free）
      const wheel = tr.wheel.map((x, i) => ({ variant: x.variant, type: i + 1, w: x.w }));
      trig = { model: 'house', sc: sid[tr.sc || 'SC'], bs: sid[tr.bs || 'BS'], gate_sc: tr.gate_sc, gate_bs: tr.gate_bs,
        wheel, wheelT: wtable(wheel), min: tr.gate_sc };
    } else if (tr.model === 'huff') {
      // 四建材：合計 ≥ min → OH；否則依 order 每顆各擲 rate，先中先得（Go engine.trigger）
      const mats = tr.materials.map((m) => ({ code: m.code, id: sid[m.sym] }));
      const midx = {}; mats.forEach((m, i) => (midx[m.id] = i));
      trig = { model: 'huff', mats, midx, min: tr.open_house_min, order: tr.order.map((c) => mats.findIndex((m) => m.code === c)), rate: mats.map((m) => tr.rate[m.code] || 0) };
    } else {
      trig = { model: 'count', ids: (tr.symbols || ['SC', 'SS']).map((s) => sid[s]), min: tr.min };
    }
    const C = {
      cfg, SYM, sid, R: cfg.board.reels, ROWS: cfg.board.rows, bet: cfg.board.bet, paySyms, pay, sets, reelsets,
      WILD, WW: WILD, SC: sid.SC, SS: sid.SS, wildFrom: Math.max(0, (cfg.board.wild_from_reel || 1) - 1),
      wm: wmc ? { from: sid[wmc.from], to: sid[wmc.to], min: wmc.min, max: wmc.max } : null,
      trig, trigMin: trig.min || trig.gate,
      reelsetT: wtable(reelsets), maxWin: cfg.board.max_win || null,
      G: cfg.fg.groups, model: cfg.fg.model || 'collect-mult',
    };
    // MG 雙神秘圖騰替換（three-pigs：MY1→歸零該 index→MY2→全盤替換；大圖騰組合主力贏分來自此）
    const mm = cfg.mg && cfg.mg.mystery;
    if (mm) {
      C.mgMy = {
        result: mm.result.map((s) => (s in sid ? sid[s] : -1)),
        my1T: wtable(mm.mystery1.map((w, i) => ({ i, w }))),
        my2raw: mm.mystery2, MY1: sid.MY1, MY2: sid.MY2,
      };
    }
    // MG 停輪前的額外權重抽（frame-chest：Go M0002 全盤事件 GetResultByWeight；結果恆 0 時只消耗一次亂數，對齊 RNG 流）
    const ab = cfg.mg && cfg.mg.all_board;
    if (ab) {
      if (ab.result.some((x) => x !== 0)) throw new Error('mg.all_board：目前只支援結果全為 0（全盤事件未啟用）');
      C.mgAllBoardT = wtable(ab.weight.map((w, i) => ({ i, w })));
    }
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
        for (let y = 0; y < C.ROWS; y++) { const v = grid[r][y]; if (v === s) a++; else if (v === C.WILD && r >= C.wildFrom) { w++; if (mult) m += mult[r][y]; } }
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
    if (T.model === 'huff') {
      const cnt = T.mats.map(() => 0);
      for (let r = 0; r < C.R; r++) for (let y = 0; y < C.ROWS; y++) { const k = T.midx[grid[r][y]]; if (k != null) cnt[k]++; }
      if (sum(cnt) >= T.min) return { cnt, type: T.mats.length, feat: 'OH' };
      for (const k of T.order) for (let i = 0; i < cnt[k]; i++) if (rng.float() < T.rate[k]) return { cnt, type: k, feat: T.mats[k].code };
      return { cnt, type: -1 };
    }
    if (T.model === 'count') {
      const cnt = T.ids.map(() => 0);
      for (let r = 0; r < C.R; r++) for (let y = 0; y < C.ROWS; y++) { const k = T.ids.indexOf(grid[r][y]); if (k >= 0) cnt[k]++; }
      return { cnt, type: sum(cnt) >= T.min ? 0 : -1 };
    }
    // house（吉屋出豬 three_pigs baseRun 同順序）：先判 BS ≥ gate_bs → 大轉盤抽變體（type 1/2/3）；再判 SC ≥ gate_sc → Free FG（type 0）。
    // 兩條觸發線各一門檻；BS 線優先（Go 先跑 BonusGame 再跑 FreeGame，但單局 BS≥3 與 SC≥6 幾乎互斥，變體以轉盤權重分流）。
    if (T.model === 'house') {
      let sc = 0, bs = 0;
      for (let r = 0; r < C.R; r++) for (let y = 0; y < C.ROWS; y++) { const v = grid[r][y]; if (v === T.sc) sc++; else if (v === T.bs) bs++; }
      const cnt = [sc, bs];
      if (bs >= T.gate_bs) { const w = pick(rng, T.wheelT); return { cnt, type: w.type, variant: w.variant, line: 'bonus' }; }   // 大轉盤三變體
      if (sc >= T.gate_sc) return { cnt, type: 0, variant: 'Free', line: 'free' };                                               // SC 觸發 Free FG
      return { cnt, type: -1 };
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
    // fdraw（huff）：Go SpinGrid 同序——轉輪組只在 >1 組時抽（Float64 pickW），停輪 floor(f × L)
    const rs = C.fdraw ? (C.reelsets.length > 1 ? C.reelsets[pickF(rng, C.rsW)] : C.reelsets[0]) : pick(rng, C.reelsetT);
    if (C.mgAllBoardT) pick(rng, C.mgAllBoardT);   // Go mainGameProcess：抽轉輪組後、停輪前先抽全盤事件（結果 0 = 不觸發）
    const stops = [], grid = [];
    for (let r = 0; r < C.R; r++) {
      const strip = rs.reels[r], L = strip.length, st = C.fdraw ? floorF(rng, L) : rng.int(L);
      stops.push(st);
      const col = [];
      for (let y = 0; y < C.ROWS; y++) col.push(strip[(st + y) % L]);
      grid.push(col);
    }
    // MG 雙神秘圖騰替換（抽 MY1 → 歸零該 index → 抽 MY2 → 全盤替換；抽值順序對齊 Go M-007）
    if (C.mgMy) {
      const i1 = pick(rng, C.mgMy.my1T).i;
      const t2 = wtable(C.mgMy.my2raw.map((w, i) => ({ i, w: i === i1 ? 0 : w })));
      const i2 = t2.total > 0 ? pick(rng, t2).i : i1;
      const s1 = C.mgMy.result[i1], s2 = C.mgMy.result[i2];
      for (let r = 0; r < C.R; r++) for (let y = 0; y < C.ROWS; y++) { const v = grid[r][y]; if (v === C.mgMy.MY1) grid[r][y] = s1; else if (v === C.mgMy.MY2) grid[r][y] = s2; }
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
    if (C.model === 'house-collect') { res.nSC = tg.cnt[0]; res.nBS = tg.cnt[1]; }
    if (C.model === 'huff-house') res.nMat = tg.cnt;
    if (C.model === 'frame-chest') res.nSC = tg.cnt[0];
    if (tg.type >= 0 && !opts.mgOnly) res.fg = M.play(C, rng, res, !!opts.present);
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

  // ───── house-collect（吉屋出豬 three-pigs）─────
  // FG = 單一引擎（Go FreeGame）：進前抽強度 → 每手抽 FG 輪帶組生盤 → SC 落格升級（1→2→3）→ 滿級溢出轉移 → 結算逐格依等級抽草/木/磚屋。
  // SC 觸發 = Free 變體（空初始框）；BS 觸發 = 大轉盤三變體（mega_hat / buzz_saw / mansions）各給不同初始框。無解析解 → L1 以固定 seed 抽樣 N 次附 CI。
  const STRENGTHS = ['WEAK', 'NORMAL', 'SUPER', 'ULTRA'];
  const HOUSE_VARIANTS = ['Free', 'mansions', 'mega_hat', 'buzz_saw'];
  MODELS['house-collect'] = {
    compile(cfg, C) {
      const fg = cfg.fg;
      // FG 符號碼（icon 名 → id）
      const hsid = (s) => (s in C.sid ? C.sid[s] : -1);
      // FG 輪帶組：fg.fg_strips 是 6 條帶（free_reels 0-5）轉成 id 陣列；fg.reel_combos 是 51 組 5 軸索引；每個 "{變體}_{強度}" 一組權重欄
      const stripIds = {};
      for (const k in fg.fg_strips) stripIds[k] = fg.fg_strips[k].map((r) => Int8Array.from(r.map((s) => hsid(s))));
      const combos = fg.reel_combos;                                   // [[a,b,c,d,e], ...] 1-based 帶索引（對應 free_reels key）
      const wsets = {};
      for (const key in fg.reel_weights) wsets[key] = wtable(combos.map((c, i) => ({ c, w: fg.reel_weights[key][i] })));
      // 強度抽選（每變體一組 [W,N,S,U]）
      const strengthT = {};
      for (const v in fg.strength) strengthT[v] = wtable(fg.strength[v].map((w, i) => ({ s: STRENGTHS[i], w })));
      // 房子獎項權重表（grass/wood/stone/stone_4plus/_2/_3）→ 值用 jackpot 名換算成倍數
      const jp = fg.jackpot || {};
      const toVal = (k) => (k in jp ? jp[k] : Number(k));
      const houseT = {};
      for (const k in fg.houses) {
        if (k === 'selector') continue;
        const t = fg.houses[k];
        houseT[k] = wtable(Object.keys(t).map((kk) => ({ v: toVal(kk), w: t[kk], name: kk })));
      }
      const sel = fg.houses.selector || { stone: 1 };
      const selT = wtable(Object.keys(sel).map((k) => ({ k, w: sel[k] })));
      // 神秘圖騰（FG）：每變體 MY1/MY2 權重（index 對 result 陣列）；僅影響 Ways 線獎
      const myT1 = {}, my2raw = {};
      if (fg.mystery) {
        for (const v in fg.mystery.mystery1) myT1[v] = wtable(fg.mystery.mystery1[v].map((w, i) => ({ i, w })));
        for (const v in fg.mystery.mystery2) my2raw[v] = fg.mystery.mystery2[v];
      }
      Object.assign(C, {
        BS: C.sid[fg.trigger.bs || 'BS'], MY1: C.sid.MY1 != null ? C.sid.MY1 : hsid('MY1'), MY2: C.sid.MY2 != null ? C.sid.MY2 : hsid('MY2'),
        hStripIds: stripIds, hCombos: combos, hWsets: wsets, hStrengthT: strengthT,
        hHouseT: houseT, hSelT: selT, hExtra: fg.extra_multi, hStone15: fg.stone15_threshold || 15,
        hSpins: fg.init_spins || 6, hVariants: fg.groups || HOUSE_VARIANTS,
        hMyT1: fg.mystery ? myT1 : null, hMyResult: fg.mystery ? fg.mystery.result.map((s) => hsid(s)) : null,
        hMyT2zero: (v, zeroIdx) => wtable((my2raw[v] || []).map((w, i) => ({ i, w: i === zeroIdx ? 0 : w }))),
      });
    },
    // 單場 FG：rng 決定一切；rec=true 時記 timeline 給演出。回 {model, variant, strength, win, ...}
    play(C, rng, res, rec) {
      const variant = res.trig.variant || 'Free';
      // 1) 抽強度 → 權重組名
      const stT = C.hStrengthT[variant] || C.hStrengthT.Free;
      const strength = pick(rng, stT).s;
      let key = variant + '_' + strength;
      if (!C.hWsets[key]) { for (const fb of ['NORMAL', 'SUPER', 'WEAK', 'ULTRA']) { if (C.hWsets[variant + '_' + fb]) { key = variant + '_' + fb; break; } } }
      const wset = C.hWsets[key] || C.hWsets[Object.keys(C.hWsets)[0]];
      // 2) 初始框盤（marks 5×3，值 0..3）
      const marks = []; for (let c = 0; c < 5; c++) marks.push([0, 0, 0]);
      const SC = C.SC, BS = C.BS;
      const initGrid = res.grid;                                       // MG 盤面（觸發此 FG 的盤）
      if (variant === 'mansions') {
        for (let c = 0; c < 5; c++) for (let r = 0; r < 3; r++) if (initGrid[c][r] === BS) marks[c][r] = 3;
      } else if (variant === 'buzz_saw') {
        for (let col = 4; col >= 0; col--) for (let row = 0; row < 3; row++) if (initGrid[col][row] === BS) for (let k = col; k < 5; k++) marks[k][row] += 1;
      } else if (variant === 'mega_hat') {
        // 從 FG 帶 0 取對齊位置，5 軸同起點，SC 格標 1
        const s0 = C.hStripIds['0'] || C.hStripIds[Object.keys(C.hStripIds)[0]];
        const len = s0[0].length, maxIdx = Math.floor((len - 3) / 3), start = rng.int(maxIdx + 1) * 3;
        for (let c = 0; c < 5; c++) for (let r = 0; r < 3; r++) if (s0[c][(start + r) % len] === SC) marks[c][r] = 1;
      } else {                                                         // Free：初始框由 MG 盤 SC 標 1
        for (let c = 0; c < 5; c++) for (let r = 0; r < 3; r++) if (initGrid[c][r] === SC) marks[c][r] = 1;
      }
      // 3) FG 迴圈
      let spinTime = C.hSpins, spins = 0, lineWin = 0, extra = 0, addSc = 0;
      const timeline = rec ? [] : null;
      while (spinTime > 0) {
        spins++; spinTime--;
        const combo = pick(rng, wset).c;                              // [a..e]：第 c 軸用 fg_strips[combo[c]] 的第 c 條帶（對齊 Go reels_data[set][col+1]）
        const grid = [];
        for (let c = 0; c < 5; c++) { const strip = C.hStripIds[String(combo[c])][c], L = strip.length, st = rng.int(L); const col = []; for (let r = 0; r < 3; r++) col.push(strip[(st + r) % L]); grid.push(col); }
        // 雙神秘圖騰替換（Go M-007 同序：抽 MY1 → 歸零該 index → 抽 MY2 → 全盤替換）；僅影響 Ways 線獎
        if (C.hMyT1 && C.hMyT1[variant]) {
          const i1 = pick(rng, C.hMyT1[variant]).i;
          const t2 = C.hMyT2zero(variant, i1);
          const i2 = t2.total > 0 ? pick(rng, t2).i : i1;
          const s1 = C.hMyResult[i1], s2 = C.hMyResult[i2];
          for (let c = 0; c < 5; c++) for (let r = 0; r < 3; r++) { if (grid[c][r] === C.MY1) grid[c][r] = s1; else if (grid[c][r] === C.MY2) grid[c][r] = s2; }
        }
        // Ways 線獎（含 wild 替代；SC/BS 不計線）
        lineWin += evalWaysGrid(C, grid);
        // 數本手 SC
        let scN = 0; const scPos = [];
        for (let c = 0; c < 5; c++) for (let r = 0; r < 3; r++) if (grid[c][r] === SC) { scN++; scPos.push([c, r]); }
        addSc += scN;
        if (scN >= 3) spinTime += 1;                                  // 加手不重置
        // SC 落格升級 + 溢出
        let overflow = 0;
        for (const [c, r] of scPos) {
          if (marks[c][r] < 3) { marks[c][r] = (variant === 'mansions') ? 3 : marks[c][r] + 1; }
          else overflow++;
        }
        for (let o = 0; o < overflow; o++) {
          const avail = [];
          for (let c = 0; c < 5; c++) for (let r = 0; r < 3; r++) if (marks[c][r] < 3) avail.push([c, r]);
          if (!avail.length) { extra += C.bet * C.hExtra; continue; }
          const p2 = avail.filter(([c, r]) => marks[c][r] === 2), p1 = avail.filter(([c, r]) => marks[c][r] === 1), p0 = avail.filter(([c, r]) => marks[c][r] === 0);
          const pool = p2.length ? p2 : (p1.length ? p1 : p0);
          const ch = pool[rng.int(pool.length)];
          marks[ch[0]][ch[1]] = (variant === 'mansions') ? 3 : marks[ch[0]][ch[1]] + 1;
        }
        if (timeline) timeline.push({ combo, scPos: scPos.slice(), marks: marks.map((c) => c.slice()), remain: spinTime });
      }
      // 4) 結算：數磚屋 → stone15 換池 → 逐格抽獎
      let stoneCount = 0; for (let c = 0; c < 5; c++) for (let r = 0; r < 3; r++) if (marks[c][r] === 3) stoneCount++;
      let stoneName = 'stone';
      if (stoneCount >= C.hStone15 && C.hSelT.total > 0) { const k = pick(rng, C.hSelT).k; stoneName = C.hHouseT[k] ? k : 'stone'; }
      let score = 0; const houses = { grass: 0, wood: 0, stone: 0 }; const settle = rec ? [] : null;
      for (let c = 0; c < 5; c++) for (let r = 0; r < 3; r++) {
        const lv = marks[c][r];
        if (lv === 1) { const v = pick(rng, C.hHouseT.grass).v * C.bet; score += v; houses.grass++; if (settle) settle.push({ c, r, kind: 'grass', win: v }); }
        else if (lv === 2) { const v = pick(rng, C.hHouseT.wood).v * C.bet; score += v; houses.wood++; if (settle) settle.push({ c, r, kind: 'wood', win: v }); }
        else if (lv === 3) { const t = C.hHouseT[stoneName] || C.hHouseT.stone; const v = pick(rng, t).v * C.bet; score += v; houses.stone++; if (settle) settle.push({ c, r, kind: 'stone', win: v }); }
      }
      const win = score + extra + lineWin;
      return { model: 'house-collect', variant, group: variant, strength, win, score, extra, lineWin, addSc, spins, stoneCount, stoneName, houses,
        ...(rec ? { timeline, settle, marks: marks.map((c) => c.slice()) } : {}) };
    },
    present(C, fx, res) {
      const tags = [];
      for (let r = 0; r < C.R; r++) for (let y = 0; y < C.ROWS; y++) { const v = res.grid[r][y]; if (v === C.SC) tags.push({ r, y, sym: 'SC' }); else if (v === C.BS) tags.push({ r, y, sym: 'BS' }); }
      res.tags = tags; res.tease = false;
    },
    statsAdd(g, f) { g.spins = (g.spins || 0) + f.spins; g.stone15 = (g.stone15 || 0) + (f.stoneCount >= 15 ? 1 : 0); g.grass = (g.grass || 0) + f.houses.grass; g.wood = (g.wood || 0) + f.houses.wood; g.stone = (g.stone || 0) + f.houses.stone;
      g.str = g.str || {}; g.str[f.strength] = (g.str[f.strength] || 0) + 1; },
    groupReport(x, b) { return { spins: x.spins / x.n, grass: x.grass / x.n, wood: x.wood / x.n, stone: x.stone / x.n, stone15_rate: (100 * (x.stone15 || 0)) / x.n }; },
  };
  // FG 盤面 Ways（符號碼直接比對；WILD 替代；SC/BS/MY 不當起手符號）—— 給 house-collect FG 用
  function evalWaysGrid(C, grid) {
    let win = 0;
    const WILD = C.WILD, SC = C.SC, BS = C.BS;
    const bases = [];
    for (let r = 0; r < 3; r++) { const s = grid[0][r]; if (s !== WILD && s !== SC && s !== BS && s >= 0 && C.pay[C.paySyms.indexOf(s)] && !bases.includes(s)) bases.push(s); }
    for (const s of bases) {
      const pi = C.paySyms.indexOf(s); if (pi < 0) continue;
      let len = 0; const counts = [];
      for (let c = 0; c < 5; c++) { let cnt = 0; for (let r = 0; r < 3; r++) { const v = grid[c][r]; if (v === s || v === WILD) cnt++; } if (!cnt) break; counts.push(cnt); len++; }
      if (len < 3 || !C.pay[pi][len]) continue;
      let ways = 1; for (let i = 0; i < len; i++) ways *= counts[i];
      win += C.pay[pi][len] * ways;
    }
    return win;
  }

  // ───── huff-house（Huff N' Puff Open House）─────
  // 逐行移植 Go internal/engine/huff/feature.go（playHS / playOH）；數學流只用 rng.float()，抽值順序與 Go 相同 → 同 Go math/rand seed 逐局一致。
  // 位置（框落在哪一格）只影響畫面：play 只記邏輯劇本（出帽框、新增框的母框），格位由 present() 用演出流 fx 指派（Go 用 Mulberry32，不納入對帳）。
  const HUFF_LABEL = { ST: 'Straw Spin', SK: 'Stick Spin', BR: 'Brick Spin', GD: 'Palace Spin', OH: 'Open House' };
  function huffValue(C, t, rng) {
    const v = t.v[pickF(rng, t.w)];
    return typeof v === 'string' ? { d: v, c: C.hf.jp[v] || 0 } : { d: v, c: v };
  }
  function huffHS(C, rng, mat, rec) {
    const H = C.hf.hs, G = H.hat_groups, gw = G.map((g) => g.w), multi = G.length > 1;
    const groupRate = () => (multi ? G[pickF(rng, gw)].rate : G[0].rate);
    let n = H.start.v[pickF(rng, H.start.w)];
    const rates = []; for (let i = 0; i < n; i++) rates.push(groupRate());
    const n0start = n, hands = rec ? [] : null;
    let left = H.spins, played = 0, stopped = false;
    while (left > 0) {
      left--; played++;
      const hats = [], add = [], n0 = n;
      for (let f = 0; f < n0 && !stopped; f++) {
        if (rng.float() >= rates[f]) continue;
        hats.push(f);
        if (n + add.length >= H.max_frames) continue;
        add.push(f);                                   // 新增框的母框（位置由演出指派）
        rates.push(groupRate());
      }
      if (add.length) left = H.spins;
      n += add.length;
      if (hands) hands.push({ hats, add, left });
      // K-019 漸進封頂：框數達門檻 → 以 p 機率全盤不再出安全帽（之後每手都不出）
      if (!stopped && H.cap && H.cap.length) {
        let p = 0; for (const c of H.cap) if (n >= c.frames && c.p > p) p = c.p;
        if (p > 0 && rng.float() < p) stopped = true;
      }
    }
    let credits = 0; const vals = rec ? [] : null;
    for (let i = 0; i < n; i++) { const v = huffValue(C, C.hf.values[mat], rng); credits += v.c; if (vals) vals.push(v); }
    return { model: 'huff-house', type: mat, group: mat, credits, win: credits, spins: played, nFrames: n, capStopped: stopped,
      ...(rec ? { start: n0start, hands, vals } : {}) };
  }
  function huffOH(C, rng, start, rec) {
    const O = C.hf.oh, mats = C.hf.mats, lvl = C.hf.lvl, top = mats.length - 1, cells = C.hf.cells, P = C.hf.pools;
    if (!start.length) start = mats.slice();
    let credits = 0, played = 0, reached = 0, replays = 0, hi = 0, bonusHands = 0;
    let carry = start.slice(), carryN = start.length;
    const houses = rec ? [] : null;
    for (let round = 0; round < O.max_rounds; round++) {
      const mat = mats[hi], need = O.keys[hi], first = hi === 0, hp = O.hat_p[hi];
      let kp = O.key_p[hi];
      if (hi === top && replays > 0 && O.replay_decay) kp = replays >= O.replay_decay.stop_after ? 0 : kp * Math.pow(O.replay_decay.mult, replays);
      const matsN = []; for (let j = 0; j < carryN; j++) matsN.push(first ? carry[j] : mat);
      const mat0 = rec ? matsN.slice() : null;
      let nFrames = carryN, keys = 0;
      const keyed = new Array(nFrames).fill(false), hands = rec ? [] : null;
      let left = O.spins;
      while (left > 0) {
        const before = left; left--; played++;
        const keyFrames = [], hats = [], ups = [], n0 = nFrames;
        for (let f = 0; f < n0; f++) {
          const r = rng.float();
          if (r < kp) { if (!keyed[f] && keys < need) { keyed[f] = true; keys++; keyFrames.push(f); } continue; }
          if (r >= kp + hp) continue;
          hats.push(f);
          let t = lvl[matsN[f]] < top ? f : -1;
          if (t < 0) for (let j = 0; j < nFrames; j++) { const lv = lvl[matsN[j]]; if (lv < top && (t < 0 || lv > lvl[matsN[t]])) t = j; }
          if (t >= 0) { matsN[t] = mats[lvl[matsN[t]] + 1]; ups.push({ from: f, to: t, mat: matsN[t] }); continue; }
          if (nFrames >= cells) continue;
          matsN.push(mat); keyed.push(false); ups.push({ from: f, to: nFrames, mat, add: true }); nFrames++;
        }
        const bonus = O.plus_one_hats > 0 && hats.length >= O.plus_one_hats ? 1 : 0;
        if (bonus) bonusHands++;
        left += bonus;
        if (hands) hands.push({ keyFrames, hats, ups, keys, before, left, bonus });
      }
      // 結算（P-06；P-11 強盤面池只換宮殿框的金額表）
      let pool = null, gdT = C.hf.values[mats[top]];
      if (P) { let nTop = 0; for (const m of matsN) if (m === mats[top]) nTop++; if (nTop >= P.threshold) { pool = pickF(rng, P.w); gdT = P.tables[pool]; } }
      let sub = 0; const vals = rec ? [] : null;
      for (const m of matsN) { const v = huffValue(C, m === mats[top] ? gdT : C.hf.values[m], rng); sub += v.c; if (vals) vals.push(v); }
      const pass = keys >= need;
      credits += sub; reached = hi + 1;
      if (houses) houses.push({ mat, need, keys, pass, carryN, mat0, mats: matsN.slice(), keyed: keyed.slice(), hands, vals, sub, cum: credits, replay: hi === top && replays > 0, round: replays, pool, kp });
      if (!pass) break;
      if (first) carry = matsN.filter((_, i) => keyed[i]);
      carryN = keys;
      if (hi < top) hi++; else replays++;
    }
    return { model: 'huff-house', type: 'OH', group: 'OH', credits, win: credits, spins: played, reached, replays, bonusHands, start: start.slice(),
      ...(rec ? { houses } : {}) };
  }
  // 演出流指派格位（Go adjFree / freeCells 同規則；用 proto fx 流，只影響畫面）
  function huffAdj(C, fx, from, taken) {
    const R = C.R, r = from % R, row = Math.floor(from / R), pool = [];
    for (const [a, b] of [[r - 1, row], [r + 1, row], [r, row - 1], [r, row + 1]]) if (a >= 0 && a < R && b >= 0 && b < C.ROWS && !taken[b * R + a]) pool.push(b * R + a);
    if (!pool.length) for (let i = 0; i < C.R * C.ROWS; i++) if (!taken[i]) pool.push(i);
    return pool[fx.int(pool.length)];
  }
  MODELS['huff-house'] = {
    compile(cfg, C) {
      const fg = cfg.fg;
      C.fdraw = true;
      C.rsW = C.reelsets.map((r) => r.w);
      C.hf = { mats: fg.trigger.materials.map((m) => m.code), lvl: Object.fromEntries(fg.trigger.materials.map((m, i) => [m.code, i])),
        hs: fg.house_spin, oh: fg.open_house, values: fg.values, pools: fg.pools || null, jp: fg.jackpot || {}, scope: fg.max_win_scope || 'total', cells: C.R * C.ROWS };
    },
    play(C, rng, res, rec) {
      const tg = res.trig;
      let f;
      if (tg.feat === 'OH') {
        // 起始框 = 觸發盤面上的建材（列優先掃描：格位 idx = 列 × 軸數 + 軸）；順序決定金額抽值歸屬 → 與 Go triggerFrames 一致
        const start = [], idx = [];
        for (let y = 0; y < C.ROWS; y++) for (let r = 0; r < C.R; r++) { const k = C.trig.midx[res.grid[r][y]]; if (k != null) { start.push(C.hf.mats[k]); idx.push(y * C.R + r); } }
        f = huffOH(C, rng, start, rec);
        if (rec) f.startIdx = idx;
      } else f = huffHS(C, rng, tg.feat, rec);
      f.label = HUFF_LABEL[f.type];
      if (C.hf.scope === 'feature' && C.maxWin && f.win > C.maxWin * C.bet) { f.raw = f.win; f.win = C.maxWin * C.bet; f.capped = true; }
      return f;
    },
    present(C, fx, res) {
      const tags = [];
      for (let r = 0; r < C.R; r++) for (let y = 0; y < C.ROWS; y++) { const k = C.trig.midx[res.grid[r][y]]; if (k != null) tags.push({ r, y, sym: C.hf.mats[k] }); }
      res.tags = tags; res.tease = false;
      const fg = res.fg; if (!fg) return;
      const N = C.R * C.ROWS;
      if (fg.type !== 'OH') {
        // House Spin：起始框隨機空格（洗牌）；加框落在母框上下左右空格
        const taken = new Array(N).fill(false), free = [...Array(N).keys()];
        for (let i = free.length - 1; i > 0; i--) { const j = fx.int(i + 1); [free[i], free[j]] = [free[j], free[i]]; }
        const pos = free.slice(0, fg.start); pos.forEach((i) => (taken[i] = true));
        for (const h of fg.hands) h.addIdx = h.add.map((parent) => { const i = huffAdj(C, fx, pos[parent], taken); taken[i] = true; pos.push(i); return i; });
        fg.pos = pos;
      } else {
        let pos = fg.startIdx.slice();
        for (const H of fg.houses) {
          const taken = new Array(N).fill(false); pos.forEach((i) => (taken[i] = true));
          H.pos0 = pos.slice();
          const cur = pos.slice();
          for (const h of H.hands) for (const u of h.ups) if (u.add) { const i = huffAdj(C, fx, cur[u.from], taken); taken[i] = true; cur.push(i); u.idx = i; }
          H.pos = cur;
          pos = cur.filter((_, i) => H.keyed[i]);
        }
      }
    },
    statsAdd(g, f) {
      g.spins = (g.spins || 0) + f.spins;
      if (f.type === 'OH') { g.reach = g.reach || [0, 0, 0, 0]; for (let i = 0; i < f.reached; i++) g.reach[i]++; g.replays = (g.replays || 0) + f.replays; g.plus1 = (g.plus1 || 0) + f.bonusHands; }
      else { g.frames = (g.frames || 0) + f.nFrames; g.capStop = (g.capStop || 0) + (f.capStopped ? 1 : 0); g.full = (g.full || 0) + (f.nFrames >= 15 ? 1 : 0); }
    },
    groupReport(x) {
      return x.reach ? { spins: x.spins / x.n, reach: x.reach.map((v) => (100 * v) / x.n), replays: x.replays / x.n, plus1: x.plus1 / x.n }
        : { spins: x.spins / x.n, frames: x.frames / x.n, cap_stop: (100 * x.capStop) / x.n, full: (100 * x.full) / x.n };
    },
  };


  // ═════════ frame-chest（神燈寶藏）：SC 落點掛框 → FG 中同格再出 SC 升級（銅→銀→金，金框再中給額外獎）→ 結算依框等級開木／銀／金箱 ═════════
  // 抽值順序 = Go game_process.freeGameProcess：強度組（表 F-2，依進場 SC 數）→ 保底手（表 F-1）→ 逐手〔FG 輪帶組（表 F-3，依強度）→ 保底手才抽替換模式（表 F-4）→ 5 軸停輪〕
  //   → 結算逐格（格位 idx = 軸 × 3 + 列，由 0 到 14）木／銀／金箱各抽一次 → 金箱 ≥ 門檻再抽特殊事件（表 F-8；事件 1、2 = 抽一個分數 × 金箱數，取代原金箱總分）
  const FC_LV = ['', 'wood', 'silver', 'gold'];
  MODELS['frame-chest'] = {
    compile(cfg, C) {
      const F = cfg.fg, sid = C.sid;
      const toIds = (reels) => reels.map((r) => Int8Array.from(r.map((s) => (s in sid ? sid[s] : -1))));
      const fstrips = {}; for (const k in F.strips) fstrips[k] = toIds(F.strips[k]);
      const rsets = F.reelsets.map((r) => ({ ...r, reels: r.use.map((u, i) => fstrips[String(u)][i]) }));
      const vt = (a) => wtable(a.map((x, i) => ({ ...x, i })));
      C.fc = {
        minSC: F.trigger.min, spins: F.spins, rgate: F.retrigger.gate, radd: F.retrigger.add, over: F.over_level,
        typeT: F.type_by_sc.map((row) => wtable(row.w.map((w, i) => ({ i, w })))), typeSC: F.type_by_sc.map((row) => row.sc),
        brT: wtable(F.bonus_round.map((w, i) => ({ i, w }))),
        rsT: C.G.map((g) => wtable(rsets.map((r) => ({ r, w: r.w[g] || 0 })))), rsets,
        guar: fstrips[String(F.guarantee.strip)], patT: wtable(F.guarantee.patterns.map((p, i) => ({ i, mask: p.mask, w: p.w }))),
        chestT: { wood: vt(F.chests.wood), silver: vt(F.chests.silver), gold: vt(F.chests.gold) },
        evMin: F.gold_event.min, evT: wtable(F.gold_event.w.map((w, i) => ({ i, w }))), evDist: F.gold_event.dists.map((d) => (d ? vt(d) : null)),
        lb: cfg.board.line_bet || 1,
      };
    },
    play(C, rng, res, rec) {
      const F = C.fc, R = C.R, RW = C.ROWS, SC = C.SC;
      const nSC = res.trig.cnt[0];
      const k = F.typeSC.indexOf(nSC);
      const type = pick(rng, F.typeT[k >= 0 ? k : (nSC < F.typeSC[0] ? 0 : F.typeT.length - 1)]).i;
      const br = pick(rng, F.brT).i;
      const sit = new Array(R * RW).fill(0);
      for (let r = 0; r < R; r++) for (let y = 0; y < RW; y++) if (res.grid[r][y] === SC) sit[r * RW + y] = 1;
      const start = rec ? sit.slice() : null;
      let remain = F.spins, spins = 0, lineWin = 0, overWin = 0, overN = 0, retrig = 0, totalSC = 0;
      const timeline = rec ? [] : null;
      for (let i = 0; i < remain; i++) {
        spins++;
        const rs = pick(rng, F.rsT[type]).r;
        const reels = rs.reels.slice();
        let pat = -1;
        if (i === br) { const p = pick(rng, F.patT); pat = p.i; p.mask.forEach((m, j) => { if (m) reels[j] = F.guar[j]; }); }
        const grid = [], stops = [];
        for (let r = 0; r < R; r++) { const st = reels[r], L = st.length, s0 = rng.int(L); stops.push(s0); const col = []; for (let y = 0; y < RW; y++) col.push(st[(s0 + y) % L]); grid.push(col); }
        const ev = evalWays(C, grid, null);
        let win = ev.win, scN = 0, ow = 0; const ups = [];
        for (let r = 0; r < R; r++) for (let y = 0; y < RW; y++) if (grid[r][y] === SC) {
          scN++; const ix = r * RW + y;
          if (sit[ix] === 3) { ow += F.over * F.lb; overN++; ups.push({ ix, lv: 3, over: true }); }
          else { sit[ix]++; ups.push({ ix, lv: sit[ix] }); }
        }
        win += ow; overWin += ow; lineWin += ev.win; totalSC += scN;
        const re = scN >= F.rgate;
        if (re) { remain += F.radd; retrig++; }
        if (timeline) timeline.push({ i, rs: rs.idx, pat, guar: i === br, stops, grid: grid.map((c) => c.map((v) => C.SYM[v] || '?')), ways: ev.ways, line: ev.win, over: ow, ups, sit: sit.slice(), remain: remain - i - 1, re });
      }
      // 結算：逐格開箱（格位順序 = Go Situation 陣列順序）
      let chest = 0; const gold = []; const lv = [0, 0, 0, 0]; const settle = rec ? [] : null;
      const sum = { wood: 0, silver: 0, gold: 0 };
      for (let ix = 0; ix < sit.length; ix++) {
        const s = sit[ix]; lv[s]++;
        if (!s) continue;
        const kind = FC_LV[s], x = pick(rng, F.chestT[kind]), v = x.v * F.lb;
        chest += v; sum[kind] += v;
        if (s === 3) gold.push(v);
        if (settle) settle.push({ ix, kind, v, label: x.label || '' });
      }
      let event = -1, eventWin = 0;
      if (gold.length >= F.evMin) {
        event = pick(rng, F.evT).i;
        if (event > 0) {
          const g0 = gold.reduce((a, b) => a + b, 0), x = pick(rng, F.evDist[event]);
          eventWin = x.v * F.lb * gold.length; chest += eventWin - g0; sum.gold += eventWin - g0;
          if (settle) settle.push({ event, each: x.v * F.lb, label: x.label || '', n: gold.length, replaced: g0 });
        }
      }
      const win = lineWin + overWin + chest;
      return { model: 'frame-chest', type, group: C.G[type], win, lineWin, overWin, overN, chest, chestSum: sum, lv, nGold: gold.length, event, eventWin,
        spins, retrig, totalSC, br, ...(rec ? { start, timeline, settle } : {}) };
    },
    present(C, fx, res) {
      const tags = [];
      for (let r = 0; r < C.R; r++) for (let y = 0; y < C.ROWS; y++) if (res.grid[r][y] === C.SC) tags.push({ r, y, sym: 'SC' });
      res.tags = tags; res.tease = false;
    },
    statsAdd(g, f) {
      g.spins = (g.spins || 0) + f.spins; g.retrig = (g.retrig || 0) + (f.retrig ? 1 : 0);
      g.gold4 = (g.gold4 || 0) + (f.nGold >= 4 ? 1 : 0); g.ev1 = (g.ev1 || 0) + (f.event === 1 ? 1 : 0); g.ev2 = (g.ev2 || 0) + (f.event === 2 ? 1 : 0);
      g.lv = (g.lv || [0, 0, 0, 0]).map((v, i) => v + f.lv[i]); g.over = (g.over || 0) + f.overWin; g.line = (g.line || 0) + f.lineWin;
      g.wood = (g.wood || 0) + f.chestSum.wood; g.silver = (g.silver || 0) + f.chestSum.silver; g.goldW = (g.goldW || 0) + f.chestSum.gold;
    },
    groupReport(x, b) {
      return { spins: x.spins / x.n, retrig: (100 * x.retrig) / x.n, gold4: (100 * x.gold4) / x.n, ev1: (100 * x.ev1) / x.n, ev2: (100 * x.ev2) / x.n,
        lv: (x.lv || [0, 0, 0, 0]).map((v) => v / x.n), over: x.over / x.n / b, line: x.line / x.n / b, wood: x.wood / x.n / b, silver: x.silver / x.n / b, goldW: x.goldW / x.n / b };
    },
  };

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
    for (const g in b.group) for (const k in b.group[g]) {
      const x = a.group[g][k], y = b.group[g][k];
      if (Array.isArray(y)) a.group[g][k] = y.map((v, i) => ((x && x[i]) || 0) + v);          // 陣列欄位（huff OH 到達各房）逐元素加
      else if (y && typeof y === 'object') { const o = a.group[g][k] = x || {}; for (const kk in y) o[kk] = (o[kk] || 0) + y[kk]; }   // 計數表（house-collect 強度）
      else a.group[g][k] = k === 'max' ? Math.max(x || 0, y) : (x || 0) + y;
    }
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
    const isWild = (v, ri) => (v === C.WILD && (ri == null || ri >= C.wildFrom)) || (C.wm && v === C.wm.from);
    const mMean = C.wm ? (C.wm.min + C.wm.max) / 2 : 0;
    const conv2 = (A, B) => {
      const out = []; for (let i = 0; i < A.length + B.length - 1; i++) out.push(new Array(A[0].length + B[0].length - 1).fill(0));
      A.forEach((ra, i) => ra.forEach((pa, j) => { if (pa) B.forEach((rb, k) => rb.forEach((pb, l) => { if (pb) out[i + k][j + l] += pa * pb; })); }));
      return out;
    };
    const pairIds = C.trig.model === 'count' ? C.trig.ids : (C.trig.model === 'house' ? [C.trig.sc, C.trig.bs] : [C.trig.t, C.trig.d]);
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
            for (let y = 0; y < C.ROWS; y++) { const v = st[(i + y) % L]; if (v === s) a++; else if (isWild(v, ri)) w++; }
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
      if (C.trig.model === 'huff') {
        const h = huffTrigExact(C, rs, joint, rs.w / W);
        rsOut.push({ idx: rs.idx, w: rs.w, mg_rtp: (100 * mg) / b, trig: 100 * sum(h), trigs: h.map((x) => 100 * x), spec_mg: null });
        mgW += (mg * rs.w) / W;
        continue;
      }
      let D = [[1]];
      for (const st of rs.reels) {
        const L = st.length, d2 = []; for (let i = 0; i <= C.ROWS; i++) d2.push(new Array(C.ROWS + 1).fill(0));
        for (let i = 0; i < L; i++) { let a = 0, c = 0; for (let y = 0; y < C.ROWS; y++) { const v = st[(i + y) % L]; if (v === pairIds[0]) a++; else if (v === pairIds[1]) c++; } d2[a][c] += 1 / L; }
        D = conv2(D, d2);
      }
      const nType = C.trig.model === 'house' ? C.trig.wheel.length + 1 : 3;
      const pt = new Array(nType).fill(0);
      D.forEach((row, a) => row.forEach((p, c) => {
        if (!p) return;
        const k = a + ',' + c;
        joint[k] = (joint[k] || 0) + (p * rs.w) / W;
        trigProb(C, a, c).forEach((q, i) => (pt[i] += p * q));
      }));
      rsOut.push({ idx: rs.idx, w: rs.w, mg_rtp: (100 * mg) / b, trig: 100 * sum(pt), trigs: pt.map((x) => 100 * x), spec_mg: rs.spec_total != null ? 100 * (rs.spec_total - rs.spec_fg) : null });
      mgW += (mg * rs.w) / W;
    }
    const nType = C.trig.model === 'huff' ? C.G.length : C.trig.model === 'house' ? C.trig.wheel.length + 1 : 3;
    const trigs = Array.from({ length: nType }, (_, i) => sum(rsOut.map((r) => (r.trigs[i] * r.w) / W)));
    const base = { reelsets: rsOut, rtp_main: (100 * mgW) / b, fg_rate: sum(trigs), trigs };
    const fg = EXACT_FG[C.model](C, joint, base, opts);
    const mainRtp = fg.rtp_main != null ? fg.rtp_main : base.rtp_main;
    return { ...base, ...fg, rtp_main: mainRtp, rtp_total: mainRtp + fg.rtp_free + (fg.rtp_bonus || 0) };
  }
  // huff：四建材顆數逐軸卷積（狀態 = 各建材顆數，≤ 16⁴）→ 各玩法觸發機率；OH 狀態（合計 ≥ min）累進 joint 供 OH 抽樣
  function huffTrigExact(C, rs, joint, wRS) {
    const T = C.trig, K = T.mats.length, B = 16;
    const enc = (c) => c.reduce((s, x, i) => s + x * Math.pow(B, i), 0);
    const dec = (k) => { const c = []; for (let i = 0; i < K; i++) { c.push(k % B); k = Math.floor(k / B); } return c; };
    let D = new Map([[0, 1]]);
    for (const st of rs.reels) {
      const L = st.length, d = new Map();
      for (let i = 0; i < L; i++) { let k = 0; for (let y = 0; y < C.ROWS; y++) { const m = T.midx[st[(i + y) % L]]; if (m != null) k += Math.pow(B, m); } d.set(k, (d.get(k) || 0) + 1 / L); }
      const nd = new Map();
      for (const [a, pa] of D) for (const [c, pc] of d) nd.set(a + c, (nd.get(a + c) || 0) + pa * pc);
      D = nd;
    }
    const out = new Array(K + 1).fill(0);
    for (const [k, p] of D) {
      const cnt = dec(k), q = huffTrigProb(T, cnt);
      for (let i = 0; i <= K; i++) out[i] += p * q[i];
      if (q[K] > 0) { const key = cnt.join(','); joint[key] = (joint[key] || 0) + p * wRS; }
    }
    return out;
  }
  function huffTrigProb(T, cnt) {
    const K = T.mats.length, out = new Array(K + 1).fill(0);
    if (sum(cnt) >= T.min) { out[K] = 1; return out; }
    let left = 1;
    for (const k of T.order) { const miss = Math.pow(1 - T.rate[k], cnt[k]); out[k] = left * (1 - miss); left *= miss; }
    return out;
  }
  // 觸發機率（給定盤面 (a,c) 顆數）→ [P(type0), P(type1), …]
  function trigProb(C, a, c) {
    const T = C.trig;
    if (T.model === 'count') return [a + c >= T.min ? 1 : 0, 0, 0];
    if (T.model === 'house') {
      // a=SC, c=BS。BS≥gate_bs → 大轉盤（依 wheel 權重分流 type 1..n）；否則 SC≥gate_sc → Free（type 0）
      const out = new Array(T.wheel.length + 1).fill(0);
      if (c >= T.gate_bs) { const tot = T.wheelT.total; T.wheel.forEach((w, i) => (out[i + 1] = w.w / tot)); }
      else if (a >= T.gate_sc) out[0] = 1;
      return out;
    }
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

    // frame-chest：MG 與觸發率逐停點解析；FG 與進場盤面（SC 位置）相關、框升級路徑相依 → 依「觸發盤」條件分布抽整場 FG（固定 seed、附 95% CI）。
    // 條件分布：先以 權重 × 該組觸發率 抽 MG 轉輪組，再在該組內拒絕抽樣停輪直到 SC ≥ 門檻（= 真實觸發盤的分布）。
    'frame-chest'(C, joint, base, opts) {
      const N = opts.bonusN || 20000, b = C.bet, F = C.fc;
      const rsW = base.reelsets.map((r) => r.w * r.trig);
      const rng = createRng(0x1a3f);
      const acc = C.G.map(() => ({ n: 0, s: 0, s2: 0, sp: 0, re: 0, g4: 0, e1: 0, e2: 0, lv: [0, 0, 0, 0] }));
      const all = { n: 0, s: 0, s2: 0, sp: 0, re: 0, g4: 0, e1: 0, e2: 0, lv: [0, 0, 0, 0], over: 0, line: 0, wood: 0, silver: 0, gold: 0 };
      let tries = 0;
      for (let k = 0; k < N; k++) {
        const rs = C.reelsets[pickF(rng, rsW)];
        let grid, sc;
        do {
          tries++; grid = []; sc = 0;
          for (let r = 0; r < C.R; r++) { const st = rs.reels[r], L = st.length, s0 = rng.int(L); const col = []; for (let y = 0; y < C.ROWS; y++) { const v = st[(s0 + y) % L]; col.push(v); if (v === C.SC) sc++; } grid.push(col); }
        } while (sc < F.minSC);
        const f = MODELS['frame-chest'].play(C, rng, { grid, trig: { cnt: [sc] } }, false);
        for (const a of [acc[f.type], all]) {
          a.n++; a.s += f.win; a.s2 += f.win * f.win; a.sp += f.spins; a.re += f.retrig ? 1 : 0; a.g4 += f.nGold >= 4 ? 1 : 0;
          a.e1 += f.event === 1 ? 1 : 0; a.e2 += f.event === 2 ? 1 : 0; f.lv.forEach((v, i) => (a.lv[i] += v));
        }
        all.over += f.overWin; all.line += f.lineWin; all.wood += f.chestSum.wood; all.silver += f.chestSum.silver; all.gold += f.chestSum.gold;
      }
      const ci = (a) => { const m = a.s / a.n, sd = Math.sqrt(Math.max(a.s2 / a.n - m * m, 0)); return (1.96 * sd) / Math.sqrt(a.n) / b; };
      const rate = base.fg_rate, grp = {};
      C.G.forEach((g, t) => {
        const a = acc[t];
        grp[g] = a.n ? { n: a.n, share: (100 * a.n) / N, rate: (rate * a.n) / N, avg_win: a.s / a.n / b, avg_ci: ci(a), spins: a.sp / a.n, retrig: (100 * a.re) / a.n,
          gold4: (100 * a.g4) / a.n, rtp: ((rate / 100) * a.s) / N / b * 100 } : { n: 0, share: 0, rate: 0 };
      });
      // 進場 SC 顆數分布（解析：joint 的 SC 顆數邊際）
      const trigW = rate / 100, entry = {};
      for (const key in joint) { const a = +key.split(',')[0]; if (a >= F.minSC) entry[a] = (entry[a] || 0) + (100 * joint[key]) / trigW; }
      const m = all.s / N;
      return { fg_avg: m / b, fg_avg_ci: ci(all), rtp_free: (100 * trigW * m) / b, groups: grp, entry, bonusN: N, tries,
        fc: { spins: all.sp / N, retrig: (100 * all.re) / N, gold4: (100 * all.g4) / N, ev1: (100 * all.e1) / Math.max(all.g4, 1), ev2: (100 * all.e2) / Math.max(all.g4, 1),
          lv: all.lv.map((v) => v / N), share: { line: all.line / all.s, over: all.over / all.s, wood: all.wood / all.s, silver: all.silver / all.s, gold: all.gold / all.s } } };
    },
    // huff-house：觸發率解析（四維卷積）；House Spin 與盤面無關 → 直接抽樣；OH 依「觸發盤建材組成」條件分布抽樣（固定 seed、附 95% CI）
    'huff-house'(C, joint, base, opts) {
      const N = opts.bonusN || 20000, b = C.bet, K = C.hf.mats.length, grp = {};
      let fgWin = 0;
      const ohC = Object.keys(joint).map((k) => k.split(',').map(Number)), ohW = Object.keys(joint).map((k) => joint[k]);   // 機率值（≪1）→ 用浮點 pickF，不能用整數權重 pick
      C.G.forEach((g, t) => {
        const rng = createRng(0x4f0f + t), isOH = t === K;
        let s = 0, s2 = 0, sp = 0, fr = 0, cs = 0, full = 0, re = 0;
        const reach = [0, 0, 0, 0];
        for (let i = 0; i < N; i++) {
          let f;
          if (isOH) { const c = ohC[pickF(rng, ohW)], start = []; c.forEach((n, m) => { for (let j = 0; j < n; j++) start.push(C.hf.mats[m]); }); f = huffOH(C, rng, start, false); for (let j = 0; j < f.reached; j++) reach[j]++; re += f.replays; }
          else { f = huffHS(C, rng, g, false); fr += f.nFrames; cs += f.capStopped ? 1 : 0; full += f.nFrames >= 15 ? 1 : 0; }
          s += f.win; s2 += f.win * f.win; sp += f.spins;
        }
        const m = s / N, sd = Math.sqrt(Math.max(s2 / N - m * m, 0)), rate = base.trigs[t];
        grp[g] = { rate, n: N, avg_win: m / b, avg_ci: (1.96 * sd) / Math.sqrt(N) / b, spins: sp / N, rtp: (rate * m) / b,
          ...(isOH ? { reach: reach.map((v) => (100 * v) / N), replays: re / N } : { frames: fr / N, cap_stop: (100 * cs) / N, full: (100 * full) / N }) };
        fgWin += (rate / 100) * m;
      });
      const tr = base.fg_rate / 100;
      return { fg_avg: tr ? fgWin / tr / b : 0, rtp_free: (100 * fgWin) / b, groups: grp, bonusN: N };
    },
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
    // house-collect（吉屋出豬）：觸發率精算（trigProb 卷積），每變體平均贏分以「抽真的會觸發的盤面 → 跑整場 FG」估（固定 seed、附 95% CI）。
    // 無解析解（框升級＋溢出路徑相依）；初始框與觸發盤面相關，故用整盤抽樣而非合成框。
    'house-collect'(C, joint, base, opts) {
      const N = opts.bonusN || 20000, b = C.bet, T = C.trig;
      // 只保留「能觸發」的 reelset（strip 內含 SC 或 BS）→ 加速 rejection sampling
      const hasTrig = (rs) => rs.reels.some((st) => { for (const v of st) if (v === T.sc || v === T.bs) return true; return false; });
      const trigRS = C.reelsets.filter(hasTrig);
      const trigRST = trigRS.length ? wtable(trigRS.map((r) => ({ r, w: r.w }))) : C.reelsetT;
      const variants = C.G;                                            // ['Free','mansions','mega_hat','buzz_saw']
      const acc = {}; variants.forEach((v) => (acc[v] = { s: 0, s2: 0, sp: 0, n: 0, g: 0, w: 0, st: 0, s15: 0 }));
      const rng = createRng(0x7013);
      const maxTries = N * 400;
      let got = 0, tries = 0;
      const want = N;
      while (got < want * variants.length && tries < maxTries) {
        tries++;
        const rs = pick(rng, trigRST).r;
        const grid = [];
        for (let r = 0; r < C.R; r++) { const strip = rs.reels[r], L = strip.length, st = rng.int(L); const col = []; for (let y = 0; y < C.ROWS; y++) col.push(strip[(st + y) % L]); grid.push(col); }
        let sc = 0, bs = 0; for (let r = 0; r < C.R; r++) for (let y = 0; y < C.ROWS; y++) { const v = grid[r][y]; if (v === T.sc) sc++; else if (v === T.bs) bs++; }
        let variant = null;
        if (bs >= T.gate_bs) variant = pick(rng, T.wheelT).variant;
        else if (sc >= T.gate_sc) variant = 'Free';
        if (!variant) continue;
        const a = acc[variant]; if (a.n >= want) continue;
        const f = MODELS['house-collect'].play(C, rng, { grid, trig: { type: 0, variant } }, false);
        a.s += f.win; a.s2 += f.win * f.win; a.sp += f.spins; a.g += f.houses.grass; a.w += f.houses.wood; a.st += f.houses.stone; a.s15 += (f.stoneCount >= 15 ? 1 : 0); a.n++; got++;
      }
      // 觸發率：type 1..n = 變體（對應 wheel 順序），type 0 = Free
      const rateOf = (variant) => {
        if (variant === 'Free') return base.trigs[0];
        const idx = T.wheel.findIndex((w) => w.variant === variant);
        return idx >= 0 ? base.trigs[idx + 1] : 0;
      };
      const grp = {}; let fgWin = 0;
      for (const v of variants) {
        const a = acc[v]; const rate = rateOf(v) || 0;
        if (!a.n) { grp[v] = { rate, n: 0, avg_win: 0, rtp: 0 }; continue; }
        const m = a.s / a.n, sd = Math.sqrt(Math.max(a.s2 / a.n - m * m, 0));
        grp[v] = { rate, n: a.n, avg_win: m / b, avg_ci: (1.96 * sd) / Math.sqrt(a.n) / b, spins: a.sp / a.n,
          grass: a.g / a.n, wood: a.w / a.n, stone: a.st / a.n, stone15_rate: (100 * a.s15) / a.n, rtp: (rate * m) / b };
        fgWin += (rate / 100) * m;
      }
      // §2 口徑：Free = 免費遊戲 RTP；三變體合計 = 大轉盤 RTP
      const freeRtp = grp.Free ? grp.Free.rtp : 0;
      const bonusRtp = variants.filter((v) => v !== 'Free').reduce((s, v) => s + (grp[v] ? grp[v].rtp : 0), 0);
      const trFree = (grp.Free ? grp.Free.rate : 0) / 100;
      // MG RTP：含神秘圖騰替換無解析解（MY 全盤替換相關），以抽樣估（固定 seed）覆蓋 base.rtp_main（純帶面低估）
      let mgRtp = base.rtp_main;
      if (C.mgMy) {
        const mn = opts.mgN || 300000, mr = createRng(0x3a9f); let s = 0;
        for (let i = 0; i < mn; i++) { const rr = spin(C, (i + 1) >>> 0, { rng: mr, mgOnly: true }); s += rr.mgWin; }
        mgRtp = (100 * s) / mn / b;
      }
      return { fg_avg: trFree ? (grp.Free ? grp.Free.avg_win : 0) : 0, rtp_free: freeRtp, rtp_bonus: bonusRtp, rtp_main: mgRtp,
        groups: grp, bonusN: N, sampled: got, tries, fg_total_rtp: freeRtp + bonusRtp };
    },
  };

  const API = { createRng, compile, spin, evalWays, simulate, newStats, addSpin, merge, report, exact, findSeed, winType, WIN_TIERS, settleGroup };
  root.SlotCore = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof self !== 'undefined' ? self : globalThis);
