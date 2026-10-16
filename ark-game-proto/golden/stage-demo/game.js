// ============================================================
//  stage-demo：ark-game-proto Stage 的無版權示範遊戲包（回歸測試基準）
//  5×3、243 Ways、W 從第 2 軸替代、金幣 C 為 Scatter；5 顆以上（每軸一顆）→ 鎖格重轉（Hold & Win）
//  美術：Stage 依符號代號產生佔位貼圖（assets 不給圖時）
// ============================================================
(function () {
  'use strict';
  const S = (a) => a.join(' ');
  const strips = [
    S(['H1','L1','L2','C','M1','L3','H2','L4','M2','L1','C','L2','H1','L3','M1','L4','W','L2','M2','L1','C','L3','H2','L4','M1','L2','L1','M2','L3','L4']),
    S(['L2','H2','W','L1','C','M2','L3','L4','H1','L2','M1','C','L1','L3','W','M2','L4','H2','L2','C','L1','M1','L3','L4','H1','W','L2','M2','L1','L3']),
    S(['M1','L3','C','L1','W','L2','H1','L4','M2','C','L3','L1','H2','W','L2','M1','L4','C','L3','L1','M2','L2','H1','W','L4','L3','C','L1','M1','L2']),
    S(['L4','M2','L1','W','C','L3','H2','L2','M1','L4','C','L1','W','H1','L3','M2','L2','C','L4','L1','M1','W','L3','H2','L2','C','L4','L1','M2','L3']),
    S(['H2','L1','C','L3','M1','W','L2','L4','C','H1','L3','M2','L1','W','L2','C','L4','M1','L3','H2','L1','W','L2','C','L4','M2','L3','L1','H1','L2']),
  ];
  const SYM = {
    W: { name: 'WILD', wild: true, color: '#ff4fd8' },
    C: { name: '金幣', scatter: true, color: '#ffc400' },
    H1: { name: '皇冠', color: '#e53935' }, H2: { name: '寶石', color: '#8e24aa' },
    M1: { name: '金鐘', color: '#1e88e5' }, M2: { name: '幸運草', color: '#43a047' },
    L1: { name: 'A', color: '#00897b' }, L2: { name: 'K', color: '#00897b' }, L3: { name: 'Q', color: '#00897b' }, L4: { name: 'J', color: '#00897b' },
  };
  Proto.game({
    name: 'Stage Demo（無版權示範）',
    seed: null,
    stage: { width: 1080, height: 1920, background: '#14102a' },
    assets: { images: {}, videos: {}, sounds: {} },
    spec: {
      reels: 5, rows: 3, pays: 'ways', maxWin: 5000,
      symbols: SYM,
      symbolOrder: ['W', 'C', 'H1', 'H2', 'M1', 'M2', 'L1', 'L2', 'L3', 'L4'],
      paytable: { H1: [20, 60, 250], H2: [15, 50, 200], M1: [10, 30, 100], M2: [8, 25, 80], L1: [5, 10, 40], L2: [5, 10, 40], L3: [4, 8, 30], L4: [4, 8, 30] },
      bet: { base: 50, steps: [50, 100, 250, 500, 1000], default: 50 },
      strips: { base: strips },
      scatter: { trigger: 5 },
      feature: {
        type: '鎖格重轉',
        values: [{ v: 1, weight: 40 }, { v: 2, weight: 25 }, { v: 5, weight: 12 }, { v: 10, weight: 5 }, { v: 25, weight: 2 }, { v: 100, weight: 1 }],
        spins: 3, reset: 3, land: [0.12, 0.1, 0.08, 0.06], multiplyFactor: 2, fullBoard: { multiplier: 2 },
      },
    },
    layout: {
      reels: { x: 40, y: 760, w: 1000, h: 600, cellW: 196, colX: [0, 201, 402, 603, 804] },
      hud: {
        balance: { x: 60, y: 1560, w: 420, h: 60, size: 40, align: 'left' },
        bet: { x: 60, y: 1660, w: 300, h: 60, size: 40 },
        win: { x: 380, y: 1440, w: 320, h: 80, size: 56 },
        buttons: { betDown: { x: 380, y: 1660, w: 90, h: 90 }, betUp: { x: 490, y: 1660, w: 90, h: 90 }, fast: { x: 610, y: 1660, w: 120, h: 90 }, auto: { x: 610, y: 1560, w: 120, h: 80 }, spin: { x: 800, y: 1560, w: 220, h: 220 }, info: { x: 40, y: 80, w: 110, h: 110 } },
      },
    },
    presentation: {
      startBalance: 100000,
      declare: { hold: 1.2 },
      winTiers: { tiers: [{ name: 'BIG WIN', min: 10 }, { name: 'MEGA WIN', min: 25 }, { name: 'SUPER WIN', min: 50 }] },
    },
    performances: {},
    info: { langs: [['tw', '繁中'], ['en', 'English']], default: 'tw', rows: [
      { t: 'h', tw: '遊戲規則', en: 'Rules' },
      { t: 'p', tw: '243 Ways；WILD 從第 2 軸開始替代。5 顆以上金幣觸發鎖格重轉。', en: '243 Ways; WILD substitutes from reel 2. 5+ coins trigger Hold & Win.' },
    ] },
  });
})();
