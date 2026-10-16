// ============================================================
//  [ark-game-proto stage] 老虎機純邏輯（Logic + 內建 freeSpins）
//  來源：Proto 試玩模板 老虎機模組/slot.js（sha256 d83b578b819bf061）
//  只保留純邏輯段（到 document 判斷為止），邏輯行一字未改；畫面段由 Stage 的 Pixi 版取代
// ============================================================
// ============================================================
//  老虎機模組
//  分成兩部分：
//    Logic   純邏輯（停輪、Ways／連線判定、Scatter、解析 RTP、模擬），不碰畫面，Node 也能跑
//    Module  畫面與流程（版面區塊、轉輪手感、贏分、四階報獎、玩法模組串接、INFO、除錯分頁）
//  單位：Logic 回傳的贏分一律是「總押注的倍數」（× Bet），畫面上才乘上押注
//  設定格式見 說明.md
// ============================================================
(function () {
  'use strict';
  const root = typeof window !== 'undefined' ? window : globalThis;
  const Proto = root.Proto;

  // ==================== 純邏輯 ====================
  const parseStrip = (s) => (Array.isArray(s) ? s.map((x) => String(x).trim()) : String(s).split(/[\s,]+/).filter(Boolean));

  // 依權重陣列抽一個索引（與八尺／Go 快測同一種抽法：r = rng() × 總和，逐項累加）
  function pickW(rng, w) {
    let t = 0;
    for (const x of w) t += x;
    const r = rng() * t;
    let a = 0;
    for (let i = 0; i < w.length; i++) {
      a += w[i];
      if (r < a) return i;
    }
    return w.length - 1;
  }

  // 賠付表可寫 { 3: 20, 4: 60, 5: 250 } 或 [20, 60, 250]（陣列從 3 連開始）
  function normPay(t) {
    if (!t) return {};
    if (Array.isArray(t)) {
      const o = {};
      t.forEach((v, i) => { if (v) o[i + 3] = v; });
      return o;
    }
    const o = {};
    for (const [k, v] of Object.entries(t)) if (v) o[Number(k)] = v;
    return o;
  }

  const Logic = {
    pickW,

    // 把設定整理成計算用的格式（結果快取在 spec 上；改了 spec 要先呼叫 Logic.reset(spec)）
    prepare(spec) {
      if (spec.__prepared) return spec.__prepared;
      const symbols = spec.symbols || {};
      // 符號順序：JS 物件會把數字代號（10、9）排到最前面，要固定順序就寫 symbolOrder
      const ids = spec.symbolOrder ? spec.symbolOrder.filter((k) => symbols[k]) : Object.keys(symbols);
      const wild = new Set(ids.filter((k) => symbols[k].wild));
      const scatter = ids.find((k) => symbols[k].scatter) || null;
      const reels = spec.reels || 5;
      const rows = spec.rows || 3;
      const pays = spec.pays || (spec.lines ? 'lines' : 'ways');
      const pay = {};
      for (const [k, v] of Object.entries(spec.paytable || {})) pay[k] = normPay(v);

      // 押注：新格式 { base, steps, default }；舊格式（連線）{ lines, lineBets, defaultIndex }
      const b = spec.bet || {};
      let bet;
      if (b.steps) {
        const base = b.base || b.steps[0];
        bet = { base, steps: b.steps.slice(), def: b.default ?? base };
      } else {
        const n = b.lines || (spec.lines || []).length || 1;
        const lb = b.lineBets || [1, 2, 5, 10];
        bet = { base: n, steps: lb.map((x) => x * n), def: lb[b.defaultIndex ?? 0] * n };
      }

      let feature = spec.feature || null;
      if (!feature && spec.freeSpins) feature = { type: 'freeSpins', ...spec.freeSpins };
      const sc = spec.scatter || {};
      const awardMin = feature && feature.award ? Math.min(...Object.keys(feature.award).map(Number)) : 3;
      const trigger = sc.trigger ?? awardMin;

      // 輪帶：每個模式（base、fs…）是一組「代號輪帶＋組合權重」
      //   簡單寫法 strips: { base: ['軸1', '軸2', ...] } → 只有一個組合
      //   八尺寫法 reelSets: { base: { strips: { 0: [...], 1: [...] }, combos: [{ name, use: [1,0,1,0,1], weight }] } }
      const modes = {};
      const addMode = (name, def) => {
        if (Array.isArray(def)) {
          modes[name] = { codes: { 0: def.map(parseStrip) }, combos: [{ name, use: def.map(() => 0), weight: 1 }] };
        } else {
          const codes = {};
          for (const [c, rs] of Object.entries(def.strips || {})) codes[c] = rs.map(parseStrip);
          modes[name] = { codes, combos: (def.combos || [{ name, use: Array(reels).fill(Object.keys(codes)[0]), weight: 1 }]).map((c) => ({ name: c.name, use: c.use.slice(), weight: c.weight ?? 1 })) };
        }
      };
      for (const [k, v] of Object.entries(spec.strips || {})) addMode(k, v);
      for (const [k, v] of Object.entries(spec.reelSets || {})) addMode(k, v);

      const p = {
        reels, rows, symbols, ids, wild, scatter, pays, pay, bet, feature, modes,
        lines: spec.lines || [],
        // 第三層掛勾（選填）：spec.custom = { afterGrid(g, rng, p), evaluate(p, grid, mult, Logic) }，見 說明.md 6-1
        custom: spec.custom || null,
        // Ways 時 WILD 從第幾軸開始可以替代（預設第 2 軸，第 1 軸一定要是本尊，和八尺／Go checkways 一樣）
        wildFrom: (spec.wildFromReel ?? (pays === 'ways' ? 2 : 1)) - 1,
        scReels: (sc.reels || Array.from({ length: reels }, (_, i) => i + 1)).map((r) => r - 1),
        trigger,
        payIds: ids.filter((k) => !wild.has(k) && k !== scatter && pay[k] && Object.keys(pay[k]).length),
        minLen: 3,
      };
      const lens = p.payIds.flatMap((k) => Object.keys(pay[k]).map(Number));
      if (lens.length) p.minLen = Math.min(...lens);
      Object.defineProperty(spec, '__prepared', { value: p, enumerable: false, configurable: true });
      return p;
    },

    reset(spec) {
      delete spec.__prepared;
      return Logic.prepare(spec);
    },

    mode(p, name) {
      return p.modes[name] ? name : 'base';
    },

    stripOf(p, mode, combo, reel) {
      const m = p.modes[Logic.mode(p, mode)];
      const c = m.combos[combo] || m.combos[0];
      return m.codes[c.use[reel]][reel];
    },

    pickCombo(p, mode, rng) {
      const m = p.modes[Logic.mode(p, mode)];
      return m.combos.length === 1 ? 0 : pickW(rng, m.combos.map((c) => c.weight));
    },

    // 停輪。opts：stops 指定停輪位置、combo 指定組合、forceScatter 讓 Scatter 軸的視窗都含 Scatter（測試用）
    spinGrid(p, mode, rng, opts = {}) {
      mode = Logic.mode(p, mode);
      const combo = opts.combo ?? Logic.pickCombo(p, mode, rng);
      const strips = [];
      const stops = [];
      const grid = [];
      // 強制觸發時只挑「剛好觸發顆數」的 Scatter 軸（Scatter 軸比觸發顆數多時隨機挑）
      let forceReels = p.scReels;
      if (opts.forceScatter && p.scReels.length > p.trigger) {
        const pool = p.scReels.slice();
        forceReels = [];
        while (forceReels.length < p.trigger) forceReels.push(pool.splice(Math.floor(rng() * pool.length), 1)[0]);
      }
      for (let r = 0; r < p.reels; r++) {
        const strip = Logic.stripOf(p, mode, combo, r);
        const L = strip.length;
        strips.push(strip);
        let start;
        if (opts.stops) start = ((opts.stops[r] % L) + L) % L;
        else {
          const scPos = opts.forceScatter && forceReels.includes(r) ? strip.flatMap((s, i) => (s === p.scatter ? [i] : [])) : [];
          start = scPos.length ? (scPos[Math.floor(rng() * scPos.length)] - Math.floor(rng() * p.rows) + L) % L : Math.floor(rng() * L);
        }
        stops.push(start);
        grid.push(Array.from({ length: p.rows }, (_, row) => strip[(start + row) % L]));
      }
      const out = { mode, combo, stops, strips, grid };
      // 盤面後處理（例：神秘圖騰變身）。要保留停輪當下的畫面就把原盤面放在 out.view
      if (p.custom && p.custom.afterGrid) p.custom.afterGrid(out, rng, p);
      return out;
    },

    // 計算盤面贏分（× 總押注）。mult：倍數（免費旋轉用）
    evaluate(p, grid, mult = 1) {
      if (p.custom && p.custom.evaluate) return p.custom.evaluate(p, grid, mult, Logic);
      const wins = [];
      let x = 0;
      const n = p.reels;
      const base = p.bet.base;
      if (p.pays === 'ways') {
        for (const sym of p.payIds) {
          let ways = 1;
          let len = 0;
          let natural = false;
          for (let r = 0; r < n; r++) {
            let c = 0;
            for (let row = 0; row < p.rows; row++) {
              const s = grid[r][row];
              if (s === sym) { c++; natural = true; } else if (r >= p.wildFrom && p.wild.has(s)) c++;
            }
            if (!c) break;
            ways *= c;
            len++;
          }
          const pv = p.pay[sym][len];
          if (!pv || !natural) continue;
          const win = (pv * ways * mult) / base;
          x += win;
          const cells = [];
          for (let r = 0; r < len; r++) for (let row = 0; row < p.rows; row++) {
            const s = grid[r][row];
            if (s === sym || (r >= p.wildFrom && p.wild.has(s))) cells.push([r, row]);
          }
          wins.push({ symbol: sym, count: len, ways, x: win, cells });
        }
      } else {
        p.lines.forEach((line, li) => {
          const syms = line.map((row, reel) => grid[reel][row]);
          let wildRun = 0;
          while (wildRun < n && p.wild.has(syms[wildRun])) wildRun++;
          const wildPay = wildRun > 0 ? (p.pay[syms[0]] || {})[wildRun] || 0 : 0;
          const first = syms.find((s) => !p.wild.has(s));
          let best = { pay: wildPay, symbol: syms[0], count: wildRun };
          if (first !== undefined && first !== p.scatter) {
            let count = 0;
            while (count < n && (syms[count] === first || p.wild.has(syms[count]))) count++;
            const pv = (p.pay[first] || {})[count] || 0;
            if (pv > best.pay) best = { pay: pv, symbol: first, count };
          }
          if (best.pay > 0) {
            const win = (best.pay * mult) / base;
            x += win;
            wins.push({ line: li, symbol: best.symbol, count: best.count, x: win, cells: line.slice(0, best.count).map((row, reel) => [reel, row]) });
          }
        });
      }
      let scatter = null;
      let trigger = false;
      if (p.scatter) {
        const cells = [];
        for (const r of p.scReels) for (let row = 0; row < p.rows; row++) if (grid[r][row] === p.scatter) cells.push([r, row]);
        const sx = ((p.pay[p.scatter] || {})[cells.length] || 0) * mult;
        trigger = !!p.feature && cells.length >= p.trigger;
        scatter = { symbol: p.scatter, count: cells.length, cells, x: sx };
        x += sx;
      }
      return { wins, scatter, x, trigger };
    },

    // ---------- 主遊戲解析解（不是模擬，是算出來的；只支援 Ways） ----------
    // RTP：某符號恰好 k 連的期望 ways ＝ Π(軸1..k 視窗內符合格數的期望) × P(軸 k+1 完全沒有)。各軸獨立取窗，所以可以直接相乘
    // HIT：把每個視窗壓成位元遮罩（WILD 視為全部符號），窮舉前 minLen 軸的所有起點組合，完全精確
    // Scatter：每軸「視窗含 Scatter」的機率（精確數起點），再用逐軸累積算出顆數分布
    analyze(p, mode = 'base') {
      if (p.pays !== 'ways') return { ok: false, warnings: ['連線（lines）沒有解析解，請用「數值模擬」'] };
      if (p.custom && p.custom.evaluate) return { ok: false, warnings: ['使用自訂判定（spec.custom.evaluate），解析解不適用，請用「數值模擬」'] };
      mode = Logic.mode(p, mode);
      const m = p.modes[mode];
      const R = p.rows;
      const warnings = [];
      const bits = {};
      p.payIds.forEach((s, i) => (bits[s] = 1 << i));
      const ALL = p.payIds.length >= 31 ? -1 : (1 << p.payIds.length) - 1;
      const cache = new Map();
      const memo = (key, f) => (cache.has(key) ? cache.get(key) : (cache.set(key, f()), cache.get(key)));

      const reelStat = (code, r, sym) => memo(`s|${code}|${r}|${sym}`, () => {
        const st = m.codes[code][r];
        const L = st.length;
        const allowWild = r >= p.wildFrom;
        let sum = 0;
        let zero = 0;
        for (let i = 0; i < L; i++) {
          let c = 0;
          for (let d = 0; d < R; d++) {
            const x = st[(i + d) % L];
            if (x === sym || (allowWild && p.wild.has(x))) c++;
          }
          sum += c;
          if (!c) zero++;
        }
        return { e: sum / L, z: zero / L };
      });
      const reelMask = (code, r) => memo(`m|${code}|${r}`, () => {
        const st = m.codes[code][r];
        const L = st.length;
        const freq = new Map();
        for (let i = 0; i < L; i++) {
          let mk = 0;
          for (let d = 0; d < R; d++) {
            const x = st[(i + d) % L];
            if (p.wild.has(x) && r >= p.wildFrom) mk |= ALL;
            else if (bits[x] !== undefined) mk |= bits[x];
          }
          freq.set(mk, (freq.get(mk) || 0) + 1 / L);
        }
        return freq;
      });
      const scHit = (code, r) => memo(`c|${code}|${r}`, () => {
        const st = m.codes[code][r];
        const L = st.length;
        let n = 0;
        let close = false;
        let last = -Infinity;
        st.forEach((s, i) => {
          if (s !== p.scatter) return;
          if (i - last < R) close = true;
          last = i;
        });
        const firstSc = st.indexOf(p.scatter);
        if (firstSc >= 0 && firstSc + L - last < R && st.filter((s) => s === p.scatter).length > 1) close = true;
        for (let i = 0; i < L; i++) {
          for (let d = 0; d < R; d++) if (st[(i + d) % L] === p.scatter) { n++; break; }
        }
        return { q: n / L, close };
      });

      const comboRtp = (use) => {
        let total = 0;
        for (const sym of p.payIds) {
          const tbl = p.pay[sym];
          let prod = 1;
          for (let k = 1; k <= p.reels; k++) {
            prod *= reelStat(use[k - 1], k - 1, sym).e;
            if (!prod) break;
            if (tbl[k]) total += tbl[k] * prod * (k < p.reels ? reelStat(use[k], k, sym).z : 1);
          }
        }
        return total / p.bet.base;
      };
      const comboHit = (use) => {
        let dist = new Map([[ALL, 1]]);
        for (let r = 0; r < p.minLen; r++) {
          const next = new Map();
          for (const [a, pa] of dist) for (const [b, pb] of reelMask(use[r], r)) {
            const k = a & b;
            if (!k) continue;
            next.set(k, (next.get(k) || 0) + pa * pb);
          }
          dist = next;
        }
        let hit = 0;
        for (const v of dist.values()) hit += v;
        return hit;
      };
      // Scatter 顆數分布（每軸最多一顆）
      const scDist = (use) => {
        let d = [1];
        for (const r of p.scReels) {
          const { q, close } = scHit(use[r], r);
          if (close) warnings.push(`輪帶「${m.combos.find((c) => c.use === use)?.name || ''}」第 ${r + 1} 軸的 Scatter 間距小於 ${R} 格，一個視窗可能出現兩顆，解析解會偏低`);
          const nd = Array(d.length + 1).fill(0);
          d.forEach((v, k) => { nd[k] += v * (1 - q); nd[k + 1] += v * q; });
          d = nd;
        }
        return d;
      };
      const scPay = p.pay[p.scatter] || {};
      const scEvent = Math.min(p.feature ? p.trigger : Infinity, ...Object.keys(scPay).map(Number));
      for (const [i, c] of m.combos.entries()) {
        for (let r = 0; r < p.reels; r++) if (!p.scReels.includes(r) && p.scatter && scHit(c.use[r], r).q > 0) warnings.push(`組合「${c.name || i + 1}」第 ${r + 1} 軸用到含 Scatter 的輪帶，但規格寫 Scatter 只在第 ${p.scReels.map((x) => x + 1).join('/')} 軸`);
      }
      const tot = m.combos.reduce((a, c) => a + c.weight, 0);
      if (!tot) return { ok: false, warnings: ['輪帶組合權重全為 0'] };
      let rtp = 0, scRtp = 0, hit = 0, trig = 0, tease = 0;
      const parts = m.combos.map((c) => {
        const share = c.weight / tot;
        const d = p.scatter ? scDist(c.use) : [1];
        const pr = (k) => d[k] || 0;
        let t = 0, sr = 0, se = 0;
        d.forEach((v, k) => {
          if (k >= p.trigger) t += v;
          sr += v * (scPay[k] || 0);
          if (k >= scEvent) se += v;
        });
        const cr = share ? comboRtp(c.use) : 0;
        const ch = share ? comboHit(c.use) : 0;
        const cTease = p.feature ? pr(p.trigger - 1) : 0;
        rtp += share * cr;
        scRtp += share * sr;
        hit += share * (ch + se - ch * se); // 連線中獎和 Scatter 事件近似獨立，取聯集
        trig += share * (p.feature ? t : 0);
        tease += share * cTease;
        return { name: c.name, share, rtp: cr, hit: ch, trigger: p.feature ? t : 0 };
      });
      if (p.feature && trig <= 0) warnings.push('沒有任何組合能湊到觸發顆數 → 永遠不會進玩法');
      return { ok: true, rtp, scatterRtp: scRtp, hit, trigger: trig, cycle: trig > 0 ? 1 / trig : Infinity, tease, teaseToHit: trig + tease > 0 ? trig / (trig + tease) : 0, parts, warnings: [...new Set(warnings)] };
    },

    // ---------- 玩法模組 ----------
    // 回傳 { def, fp, logic }：def＝Proto.features 裡登記的模組；logic 可被 game.js 的 spec.feature.logic 蓋掉（第三層專屬數學）
    feature(p) {
      if (!p.feature) return null;
      if (p.__feature) return p.__feature;
      const def = Proto.features[p.feature.type];
      if (!def) return null;
      const logic = { ...def.logic, ...(p.feature.logic || {}) };
      const fp = logic.prepare ? logic.prepare(p.feature, p) : p.feature;
      Object.defineProperty(p, '__feature', { value: { def, fp, logic }, enumerable: false, configurable: true });
      return p.__feature;
    },

    // 一次付費旋轉（含觸發的玩法），單位 × 總押注
    playOne(p, rng) {
      const g = Logic.spinGrid(p, 'base', rng);
      const ev = Logic.evaluate(p, g.grid);
      let fx = 0;
      let res = null;
      let draw = null;
      if (ev.trigger) {
        const F = Logic.feature(p);
        if (F) {
          draw = F.logic.draw(F.fp, p, rng, ev, g);
          res = F.logic.play(F.fp, p, rng, draw, ev, g, { record: false });
          fx = res.x;
        }
      }
      return { base: ev.x, feature: fx, total: ev.x + fx, triggered: ev.trigger, hit: ev.x > 0 || ev.trigger, draw, res };
    },

    newAccumulator() {
      const S = Proto.sim;
      return {
        spins: 0, all: new S.Stats(), baseWin: 0, featWin: 0, hits: 0, triggers: 0, featSession: new S.Stats(), featSpins: 0, groups: {},
        dist: new S.Histogram([1e-9, 1, 2, 5, 10, 20, 50, 100, 500, 1000], ['0（沒中）', '0～1 倍', '1～2 倍', '2～5 倍', '5～10 倍', '10～20 倍', '20～50 倍', '50～100 倍', '100～500 倍', '500～1000 倍', '1000 倍以上']),
      };
    },

    simulate(spec, n, rng, acc) {
      const p = Logic.prepare(spec);
      acc = acc || Logic.newAccumulator();
      for (let i = 0; i < n; i++) {
        const r = Logic.playOne(p, rng);
        acc.spins++;
        acc.all.add(r.total);
        acc.baseWin += r.base;
        acc.featWin += r.feature;
        if (r.hit) acc.hits++;
        if (r.triggered) {
          acc.triggers++;
          acc.featSession.add(r.feature);
          if (r.res && r.res.spinsPlayed) acc.featSpins += r.res.spinsPlayed;
          const gname = r.draw && r.draw.group;
          if (gname !== undefined) {
            const g = (acc.groups[gname] = acc.groups[gname] || { n: 0, sum: 0 });
            g.n++;
            g.sum += r.feature;
          }
        }
        acc.dist.add(r.total);
      }
      return acc;
    },

    // 找一組停輪，讓盤面符合條件（除錯「強制」用）
    search(p, mode, rng, predicate, opts = {}, tries = 300000) {
      for (let i = 0; i < tries; i++) {
        const g = Logic.spinGrid(p, mode, rng, opts);
        const ev = Logic.evaluate(p, g.grid);
        if (predicate(ev, g)) return g;
      }
      return null;
    },
  };
  Proto.slotLogic = Logic;

  // ==================== 內建玩法：一般免費旋轉 ====================
  // spec.freeSpins（舊寫法）或 spec.feature = { type: 'freeSpins', award: { 3: 10, 4: 15 }, multiplier: 2, retrigger: true, strips: 'fs' }
  Proto.features.freeSpins = {
    logic: {
      prepare(cfg) {
        return { award: cfg.award || { 3: 10 }, multiplier: cfg.multiplier || 1, retrigger: !!cfg.retrigger, mode: cfg.strips || cfg.mode || 'fs', max: cfg.maxSpins || 1000 };
      },
      draw(fp, p, rng, ev) {
        const keys = Object.keys(fp.award).map(Number).sort((a, b) => a - b);
        const k = keys.filter((x) => x <= ev.scatter.count).pop() ?? keys[0];
        return { spins: fp.award[k] };
      },
      play(fp, p, rng, draw, ev, g, { record } = {}) {
        let left = draw.spins;
        let played = 0;
        let x = 0;
        const list = [];
        while (left > 0 && played < fp.max) {
          left--;
          played++;
          const gg = Logic.spinGrid(p, fp.mode, rng);
          const e = Logic.evaluate(p, gg.grid, fp.multiplier);
          let add = 0;
          if (fp.retrigger && e.trigger) {
            add = this.draw(fp, p, rng, e).spins;
            left += add;
          }
          x += e.x;
          if (record) list.push({ g: gg, ev: e, add, left });
        }
        return { x, spinsPlayed: played, spins: list };
      },
    },
    // 演出：沿用主遊戲的轉輪
    Present: class {
      constructor(mod, fp) {
        this.mod = mod;
        this.fp = fp;
      }
      async run(res, draw, ctx) {
        const mod = this.mod;
        let shown = 0;
        mod.featureHud({ left: draw.spins, total: 0 });
        for (const s of res.spins) {
          mod.featureHud({ left: s.left + 1 - s.add, total: shown });
          await mod.waitSpinPress();
          await mod.spinReels(s.g, { fast: false });
          mod.featureHud({ left: s.left - s.add, total: shown });
          if (s.ev.x > 0) {
            await mod.showWins(s.ev, { cycle: false });
            shown += s.ev.x;
            mod.featureHud({ left: s.left - s.add, total: shown });
            await mod.countBox(shown * mod.bet, 0.6);
          }
          if (s.add) {
            await mod.app.timeline.play(mod.pres.fsRetrigger, { ...ctx, fsAward: s.add });
            mod.featureHud({ left: s.left, total: shown });
          }
          await Proto.wait(0.35 * mod.tf());
        }
        return res.x;
      }
    },
  };

})();
