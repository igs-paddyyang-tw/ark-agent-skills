// ============================================================
//  引擎回放試玩（⑦-lite）通用遊戲包 — ark-game-proto 1.5.0
//  軌跡（proto-stage-trace/1）由 scripts/engine_trace.py 從該款 Go 快測引擎原樣跑出，stage.yaml `odds:` 注入 globalThis.HUFF_ODDS。
//  數學 = 快測引擎（不是規格書）；演出泛用：主遊戲盤面＋贏分，特色遊戲只顯示摘要（沒有玩法演出）。
//  符號名依 FastTest 範本代碼：1 WILD、2 SCATTER、3 BONUS、11～19 M1～M9、21～ A K Q J 10 9 8 7（其餘 S<代碼>）。
// ============================================================
(function () {
  'use strict';
  const root = typeof window !== 'undefined' ? window : globalThis;
  const Proto = root.Proto;
  // 精簡格式 proto-stage-trace-lite/1：rounds[i] = [總贏分, 主遊戲贏分, 有無特色, 盤面(代碼)] → 展開成 proto-stage-trace/1（與 engine_trace.expand_lite 同邏輯）
  const TIERS = [[100, 'GOLDEN'], [50, 'SUPER'], [25, 'MEGA'], [10, 'BIG'], [5, 'SMALL'], [1, 'LIGHT'], [0, 'NORMAL']];
  function expand(lt) {
    const bet = lt.info.defaultBet;
    let bal = lt.info.balance;
    const results = lt.rounds.map(([win, mg0, sg, grid], i) => {
      const mg = Math.min(mg0, win), fg = win - mg;
      const r = { schema: 'proto-stage-result/1', roundId: `T${i + 1}`, requestId: null, round: i + 1, seed: null, bet, betIndex: 0, mode: 'base',
        reel: { combo: 0, stops: grid.map(() => 0), grid: grid.map((col) => col.map((v) => `S${v}`)), view: null },
        base: { winX: mg / bet, win: mg, ways: [], scatter: null, trigger: !!sg, extra: {} },
        feature: sg || fg > 0 ? { type: '特色遊戲', draw: {}, group: null, winX: fg / bet, win: fg, capped: false, spinsPlayed: null, script: { engine: 'summary' }, awaitAction: null } : null,
        totalX: win / bet, totalWin: win, capped: false, winType: win ? TIERS.find(([t]) => win / bet >= t)[1] : 'NO_WIN',
        balanceBefore: bal, balanceAfter: bal - bet + win, fx: i };
      bal = r.balanceAfter;
      return r;
    });
    return { schema: 'proto-stage-trace/1', info: lt.info, results, meta: lt.meta, loop: lt.loop !== false };
  }
  const RAW = root.HUFF_ODDS;
  const TR = RAW && RAW.schema === 'proto-stage-trace-lite/1' ? expand(RAW) : RAW;
  if (!TR || TR.schema !== 'proto-stage-trace/1') throw new Error('引擎回放試玩需要 stage.yaml `odds:` 指到 engine_trace.py 產的 trace.json');
  const R0 = TR.results[0];
  const reels = R0.reel.grid.length, rows = R0.reel.grid[0].length;
  const LOW = ['A', 'K', 'Q', 'J', '10', '9', '8', '7', '6', '5'];
  const PAL = ['#e53935', '#8e24aa', '#1e88e5', '#43a047', '#fb8c00', '#6d4c41', '#00897b', '#3949ab', '#c0ca33'];
  const label = (n) => (n === 1 ? 'WILD' : n === 2 ? 'SCATTER' : n === 3 ? 'BONUS' : n >= 11 && n <= 19 ? `M${n - 10}` : n >= 21 && n <= 30 ? LOW[n - 21] : `S${n}`);
  const ids = [...new Set(TR.results.flatMap((r) => r.reel.grid.flat()))].sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)));
  const SYM = {};
  ids.forEach((id, i) => {
    const n = Number(id.slice(1));
    SYM[id] = { name: label(n), color: n === 1 ? '#2fbf71' : n === 2 ? '#8e5cff' : n === 3 ? '#ff4fd8' : n >= 21 ? '#00897b' : PAL[i % PAL.length], ...(n === 1 ? { wild: true } : {}), ...(n === 2 ? { scatter: true } : {}) };
  });
  const bet = TR.info.defaultBet;
  const W = 1080, cellW = Math.floor(1000 / reels) - 6, gap = Math.floor((1000 - cellW * reels) / Math.max(1, reels - 1));
  const H = Math.min(600, rows * (cellW + 6));
  const M = TR.meta || {};
  Proto.game({
    name: `${TR.info.name || 'Slot'}｜引擎回放試玩`,
    seed: null,
    stage: { width: W, height: 1920, background: '#14102a' },
    assets: { images: {}, videos: {}, sounds: {} },
    service: { kind: 'replay', trace: TR, loop: true },
    spec: {
      reels, rows, pays: 'ways', symbols: SYM, symbolOrder: ids,
      paytable: {}, bet: { base: bet, steps: [bet], default: bet },
      strips: { base: Array.from({ length: reels }, () => ids.join(' ')) },
    },
    layout: {
      decor: [
        { label: '背景', fill: 'radial-gradient(ellipse at 50% 35%,#33245e 0%,#170d36 60%,#090518 100%)', x: 0, y: 0, w: W, h: 1920, layer: 'bg' },
        { label: '盤面框', fill: 'linear-gradient(180deg,#d9c27a,#8a6a1c)', x: 28, y: 742, w: 1024, h: H + 36, layer: 'main' },
        { label: '盤面底', fill: 'linear-gradient(180deg,#1e1442,#0f0826)', x: 38, y: 752, w: 1004, h: H + 16, layer: 'main' },
      ],
      reels: { x: 40, y: 760, w: 1000, h: H, cellW, colX: Array.from({ length: reels }, (_, r) => r * (cellW + gap)) },
      hud: {
        balance: { x: 60, y: 1560, w: 420, h: 60, size: 40, align: 'left' },
        bet: { x: 60, y: 1660, w: 300, h: 60, size: 40 },
        win: { x: 380, y: 1440, w: 320, h: 80, size: 56 },
        buttons: { fast: { x: 610, y: 1660, w: 120, h: 90 }, auto: { x: 610, y: 1560, w: 120, h: 80 }, spin: { x: 800, y: 1560, w: 220, h: 220 }, info: { x: 40, y: 80, w: 110, h: 110 } },
      },
    },
    presentation: { startBalance: TR.info.balance, trigger: { wait: false },
      winTiers: { tiers: [{ name: 'BIG WIN', min: 10 }, { name: 'MEGA WIN', min: 25 }, { name: 'SUPER WIN', min: 50 }] } },
    performances: {},
    info: { langs: [['tw', '繁中']], default: 'tw', rows: [
      { t: 'h', tw: '引擎回放試玩' },
      { t: 'p', tw: `本試玩版逐局播放「${TR.info.name || ''}」Go 快測引擎原樣跑出的 ${TR.results.length.toLocaleString()} 局結果（循環播放）。數學 = 快測引擎（${M.engine || ''}），不是規格書；特色遊戲只顯示贏分摘要。` },
      { t: 'p', tw: `引擎 20 萬局樣本：總 RTP ${M.rtp ?? '—'}%、主遊戲 ${M.rtp_main ?? '—'}%、特色觸發 ${M.feature_rate ?? '—'}%。` },
    ] },
  });
})();
