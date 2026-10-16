// ============================================================
//  [ark-game-proto stage] 玩法：鎖格重轉 純邏輯
//  來源：Proto 試玩模板 玩法模組/鎖格重轉/holdwin.js（sha256 8b714f6853743bcc）
//  只保留純邏輯段（到 document 判斷為止），邏輯行一字未改；畫面段由 Stage 的 Pixi 版取代
// ============================================================
// ============================================================
//  玩法模組：鎖格重轉（Hold & Win）
//  主遊戲湊到觸發顆數 → 觸發的格子變成圖騰 → 每手空格依「停入率」轉出新圖騰，圖騰鎖住不動
//  → 手數用完或盤面填滿結束，所有圖騰面額加總（× 總押注）
//
//  分兩部分：
//    logic    純數學（Node 也能跑）。game.js 可以用 spec.feature.logic 整個或部分換掉（第三層專屬數學，例如八尺）
//    Present  演出：只負責把 logic 已經算好的「劇本」演出來，不會再抽任何亂數影響結果
//
//  劇本格式（logic.play 回傳，自訂 logic 也要照這個格式）：
//    { x: 總贏分（× 總押注）, spinsPlayed,
//      start: [{ idx, face }],                      起始圖騰（idx＝列×軸數＋軸，face＝values 的索引）
//      hands: [{ left,                              這手之後剩幾手
//                landed: { idx: face },             這手停入的圖騰
//                reset,                             這手有停入而重置手數
//                act, hit: [idx], marks: [idx],     表演名稱（第三層插槽）、被加倍的格、陪襯標記格
//                showAt, showImage }],              表演前先在某格亮一張圖（八尺：鬼手）
//      fullBoard: { picks: [idx] } 或 null,         滿盤後逐格加倍（八尺：剩餘手數 → 爪擊）
//      fullMult, capped }                          滿盤總分倍數、是否碰到 Max Win
//  格子面額 ＝ values[face].v × multiplyFactor ^ 被加倍次數
// ============================================================
(function () {
  'use strict';
  const root = typeof window !== 'undefined' ? window : globalThis;
  const Proto = root.Proto;
  const Logic = Proto.slotLogic;
  const pickW = Logic.pickW;
  const rnd = (rng, n) => Math.floor(rng() * n);

  const logic = {
    prepare(cfg, p) {
      const reels = cfg.reels ?? p.reels;
      const rows = cfg.rows ?? p.rows;
      const values = (cfg.values || [{ v: 1 }]).map((x) => (typeof x === 'number' ? { v: x } : x));
      const spinsOf = (s) => (typeof s === 'number' ? { value: [s], weight: [1] } : s);
      const groups = cfg.groups ? cfg.groups.map((g) => ({ ...g, spins: spinsOf(g.spins ?? cfg.spins ?? 3), valueWeight: g.valueWeight || values.map((x) => x.weight ?? 1) })) : null;
      const land = cfg.land ?? 0.05;
      return {
        ...cfg,
        reels, rows, cells: reels * rows, values, groups,
        spins: spinsOf(cfg.spins ?? 3),
        valueWeight: values.map((x) => x.weight ?? 1),
        land: Array.isArray(land) ? land : [land],
        reset: cfg.reset ?? null,
        multiplyFactor: cfg.multiplyFactor ?? 2,
        fullMult: cfg.fullBoard && cfg.fullBoard.multiplier ? cfg.fullBoard.multiplier : 1,
        maxWin: cfg.maxWin ?? p.maxWin ?? Infinity,
        startFromTrigger: cfg.startFromTrigger !== false,
      };
    },

    // 觸發當下就抽定：組別（有設定 groups 時）、起始手數
    draw(fp, p, rng) {
      let gi = null;
      let sp = fp.spins;
      if (fp.groups) {
        gi = pickW(rng, fp.groups.map((g) => g.weight ?? 1));
        sp = fp.groups[gi].spins;
      }
      const spins = sp.value[pickW(rng, sp.weight)];
      return { spins, gi, group: gi === null ? undefined : fp.groups[gi].name ?? gi };
    },

    // 一局完整結果。record：是否產生逐手劇本（模擬時關掉求速度，數學亂數順序不變）
    play(fp, p, rng, draw, ev, g, { record } = {}) {
      const N = fp.cells;
      const vw = draw.gi !== null && draw.gi !== undefined && fp.groups ? fp.groups[draw.gi].valueWeight : fp.valueWeight;
      const face = new Array(N).fill(-1);
      const hits = new Array(N).fill(0);
      let filled = 0;
      const start = [];
      const put = (i) => {
        const f = pickW(rng, vw);
        face[i] = f;
        filled++;
        return f;
      };
      if (fp.startFromTrigger && ev && ev.scatter) for (const [r, row] of ev.scatter.cells) {
        const i = row * fp.reels + r;
        if (face[i] < 0) start.push({ idx: i, face: put(i) });
      }
      let left = draw.spins;
      let played = 0;
      const hands = [];
      while (left > 0 && filled < N) {
        left--;
        played++;
        const rate = fp.land[Math.min(filled, fp.land.length - 1)];
        const landed = {};
        let any = false;
        for (let i = 0; i < N; i++) {
          if (face[i] >= 0) continue;
          if (rng() < rate) { landed[i] = put(i); any = true; }
        }
        const reset = any && fp.reset !== null && left < fp.reset;
        if (reset) left = fp.reset;
        if (record) hands.push({ left, landed, reset, act: null, hit: [], marks: [] });
      }
      const full = filled >= N;
      let x = 0;
      for (let i = 0; i < N; i++) if (face[i] >= 0) x += fp.values[face[i]].v * Math.pow(fp.multiplyFactor, hits[i]);
      if (full) x *= fp.fullMult;
      const capped = x > fp.maxWin;
      return { x: capped ? fp.maxWin : x, rawX: x, capped, spinsPlayed: played, full, fullMult: full && fp.fullMult !== 1 ? fp.fullMult : null, fullBoard: null, ...(record ? { start, hands, faces: face, hits } : {}) };
    },
  };

  // 模擬用：隨機產生一個觸發盤面（觸發顆數的 Scatter 落在不同的 Scatter 軸）
  function fakeTrigger(p, rng) {
    const reels = p.scReels.slice();
    const cells = [];
    for (let k = 0; k < p.trigger && reels.length; k++) cells.push([reels.splice(rnd(rng, reels.length), 1)[0], rnd(rng, p.rows)]);
    return { scatter: { count: cells.length, cells, x: 0 }, trigger: true };
  }

  const def = { logic, fakeTrigger };
  Proto.features['鎖格重轉'] = def;
})();
