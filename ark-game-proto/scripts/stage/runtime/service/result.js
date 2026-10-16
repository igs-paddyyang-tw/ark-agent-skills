// ============================================================
//  [ark-game-proto stage] ResultBuilder：引擎輸出 → SpinResult（proto-stage-result/1）
//  ・只讀 Logic / 玩法 logic 的回傳值（含 record 劇本），不改任何數學
//  ・金額一律整數 credit：credits(x, bet) = floor(x × bet)（加 1e-6 吸收浮點誤差，例 0.7×240）
//  ・validate(r)：輕量驗證器（不依賴 ajv），欄位語意與 schema/spin-result.schema.json 一致
//  node / 瀏覽器 / Worker 共用；不碰 DOM
// ============================================================
(function () {
  'use strict';
  const root = typeof window !== 'undefined' ? window : globalThis;
  const Proto = root.Proto;
  const SCHEMA = 'proto-stage-result/1';
  // slot-bot M-16 門檻（倍數），與 ark-game-proto slot-core 相同
  const TIERS = [[100, 'GOLDEN'], [50, 'SUPER'], [25, 'MEGA'], [10, 'BIG'], [5, 'SMALL'], [1, 'LIGHT'], [0, 'NORMAL']];

  const credits = (x, bet) => Math.floor((Number(x) || 0) * bet + 1e-6);
  function winType(win, bet) {
    if (!win) return 'NO_WIN';
    const x = win / bet;
    for (const [t, n] of TIERS) if (x >= t) return n;
    return 'NORMAL';
  }

  // JSON 安全的深拷貝：去掉 strips（輪帶不下發）、函式、Set → 陣列；陣列上的附加屬性（例 grid.hp）不保留
  function clean(v, depth = 0) {
    if (v === null || v === undefined) return v === undefined ? undefined : null;
    if (depth > 40) return null;
    if (typeof v === 'function') return undefined;
    if (typeof v === 'number') return Number.isFinite(v) ? v : null;
    if (typeof v !== 'object') return v;
    if (v instanceof Set) return [...v].map((x) => clean(x, depth + 1));
    if (Array.isArray(v)) return v.map((x) => { const c = clean(x, depth + 1); return c === undefined ? null : c; });
    const o = {};
    for (const [k, x] of Object.entries(v)) {
      if (k === 'strips') continue;
      const c = clean(x, depth + 1);
      if (c !== undefined) o[k] = c;
    }
    return o;
  }

  const grid2d = (grid) => grid.map((col) => Array.from(col));

  // 主遊戲 ev 的玩法專屬欄位（例 HuffNPuff：feat、scCount、scCnt）原樣放 base.extra
  const EV_KEYS = new Set(['wins', 'scatter', 'x', 'trigger']);

  function build(o) {
    const { g, ev, bet } = o;
    const baseWin = credits(ev.x, bet);
    const extra = {};
    for (const [k, v] of Object.entries(ev)) if (!EV_KEYS.has(k)) extra[k] = clean(v);
    const base = {
      winX: ev.x,
      win: baseWin,
      ways: (ev.wins || []).map((w) => ({
        sym: w.symbol, len: w.count, ways: w.ways ?? null, line: w.line ?? null,
        winX: w.x, win: credits(w.x, bet), cells: clean(w.cells || []),
      })),
      scatter: ev.scatter ? clean(ev.scatter) : null,
      trigger: !!ev.trigger,
      extra,
    };
    let feature = null;
    if (o.res) {
      const script = {};
      for (const [k, v] of Object.entries(o.res)) if (k !== 'x') script[k] = v;
      feature = {
        type: o.featureType,
        draw: clean(o.draw) || {},
        group: o.draw && o.draw.group !== undefined ? String(o.draw.group) : null,
        winX: o.res.x,
        win: credits(o.res.x, bet),
        capped: !!o.res.capped,
        spinsPlayed: o.res.spinsPlayed ?? null,
        script: clean(script),
        awaitAction: null,
      };
    }
    const totalWin = baseWin + (feature ? feature.win : 0);
    const r = {
      schema: SCHEMA,
      roundId: o.roundId,
      requestId: o.requestId ?? null,
      round: o.round,
      seed: o.seed ?? null,
      bet,
      betIndex: o.betIndex ?? null,
      mode: 'base',
      reel: { combo: g.combo ?? 0, stops: g.stops.slice(), grid: grid2d(g.grid), view: g.view ? grid2d(g.view) : null },
      base,
      feature,
      totalX: ev.x + (feature ? feature.winX : 0),
      totalWin,
      capped: !!(feature && feature.capped),
      winType: winType(totalWin, bet),
      balanceBefore: o.balanceBefore,
      balanceAfter: o.balanceBefore - bet + totalWin,
      fx: o.fx >>> 0,
    };
    return r;
  }

  // ---------- 驗證 ----------
  const isInt = (v) => Number.isInteger(v);
  function validate(r) {
    const err = [];
    const need = (cond, msg) => { if (!cond) err.push(msg); };
    need(r && typeof r === 'object', '不是物件');
    if (err.length) return err;
    need(r.schema === SCHEMA, `schema 必須是 ${SCHEMA}`);
    need(typeof r.roundId === 'string' && r.roundId.length > 0, 'roundId 必填字串');
    for (const k of ['bet', 'totalWin', 'balanceBefore', 'balanceAfter', 'fx']) need(isInt(r[k]), `${k} 必須是整數 credit`);
    need(r.bet > 0, 'bet 必須 > 0');
    need(r.totalWin >= 0, 'totalWin 不可為負');
    need(typeof r.winType === 'string', 'winType 必填');
    need(r.reel && Array.isArray(r.reel.stops) && Array.isArray(r.reel.grid), 'reel.stops / reel.grid 必填');
    if (r.reel && Array.isArray(r.reel.grid)) need(r.reel.grid.every((c) => Array.isArray(c) && c.every((s) => typeof s === 'string')), 'reel.grid 必須是 [軸][列] 的符號字串');
    need(r.base && isInt(r.base.win) && r.base.win >= 0 && Array.isArray(r.base.ways), 'base.win（整數）與 base.ways 必填');
    if (r.base && Array.isArray(r.base.ways)) r.base.ways.forEach((w, i) => need(typeof w.sym === 'string' && isInt(w.len) && isInt(w.win), `base.ways[${i}] 需 sym / len / win（整數）`));
    if (r.feature !== null && r.feature !== undefined) {
      const f = r.feature;
      need(typeof f.type === 'string', 'feature.type 必填');
      need(isInt(f.win) && f.win >= 0, 'feature.win 必須是非負整數');
      need(f.script && typeof f.script === 'object', 'feature.script 必填（玩法劇本）');
      need(r.totalWin === r.base.win + f.win || !!f.awaitAction, 'totalWin ≠ base.win + feature.win');
    } else need(r.totalWin === (r.base ? r.base.win : -1), 'totalWin ≠ base.win（無玩法）');
    need(r.balanceAfter === r.balanceBefore - r.bet + r.totalWin, 'balanceAfter ≠ balanceBefore − bet + totalWin');
    return err;
  }

  Proto.stageResult = { SCHEMA, TIERS, credits, winType, clean, build, validate };
})();
