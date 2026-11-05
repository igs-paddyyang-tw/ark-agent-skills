/*
 * ark-pixel-animation · Q 版角色產生器（sprite sheet 模式的唯一來源）
 *
 * 版型：112×96 = 3 列方向（下、上、右；左＝右的水平鏡像）× 7 格 × 16×32
 *       第 0–2 格走路、3–4 格打字、5–6 格閱讀（與 pixel-agents char_N.png 相容）
 * 外觀：名字 → FNV-1a 雜湊 → 髮色 × 衣服 × 配件（6×6×6＝216 種）；uniqueLooks() 保證同一組名字不重複
 * 規則：只用 CHIBI_PAL；背景 alpha=0、其餘 alpha=255（鐵律 3 的 sprite sheet 例外）；整數 fillRect；決定性
 *
 * 用法（不需建置）：
 *   瀏覽器   以 script 標籤載入 chibi.js → window.ArkChibi
 *   ES 模組  import './chibi.js'; const C = globalThis.ArkChibi;
 *   node     await import('./chibi.js'); globalThis.ArkChibi
 * 原創角色（鐵律 7）：造型是通用的 Q 版人物＋常見配件，不仿任何既有作品角色。
 */
(function (g) {
  'use strict';

  // 角色色盤（索引固定；manifest 的 palette 就是這份）
  const CHIBI_PAL = [
    '#0e0f16', // 0 外框／眼睛描邊
    '#3b4060', // 1 褲子
    '#5b5f74', // 2 深灰（預留）
    '#c9ccd6', // 3 紙張／銀髮
    '#f2f2f2', // 4 白（領口、毛帽邊）
    '#f5cfa8', // 5 膚色
    '#d9a17a', // 6 膚色陰影
    '#f08a8a', // 7 腮紅、蝴蝶結
    '#2a2233', // 8 眼睛／黑髮
    '#6b4430', // 9 棕髮
    '#e8d27a', // 10 金髮
    '#e5484d', // 11 紅
    '#b07ae0', // 12 紫
    '#4aa8ff', // 13 藍
    '#3fbf6a', // 14 綠
    '#f0b43c', // 15 琥珀
    '#a87c52', // 16 木色
    '#8a8fa3', // 17 中灰（預留）
  ];
  const HAIR = [9, 8, 10, 11, 12, 3];          // 棕、黑、金、紅、紫、銀
  const OUTFIT = [13, 14, 12, 11, 15, 16];     // 藍、綠、紫、紅、琥珀、木
  const ACCESSORY = ['none', 'glasses', 'cap', 'headband', 'bow', 'beanie'];
  const FW = 16, FH = 32, COLS = 7, ROWS = ['down', 'up', 'right'];
  const FRAMES = { walk: [0, 1, 2], type: [3, 4], read: [5, 6] };
  const OUT = 0, PANTS = 1, PAPER = 3, WHITE = 4, SKIN = 5, SKIN_D = 6, BLUSH = 7, EYE = 8, RED = 11;

  /** FNV-1a 32 位元。 */
  function strHash(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }

  /** 雜湊 → 外觀。 */
  function lookFor(h) {
    return { hair: HAIR[h % HAIR.length], outfit: OUTFIT[(h >>> 3) % OUTFIT.length], acc: ACCESSORY[(h >>> 6) % ACCESSORY.length] };
  }

  const lookKey = v => `${v % 6}-${(v >>> 3) % 6}-${(v >>> 6) % 6}`;

  /** 一組名字 → 各自的外觀雜湊，同組內不重複（依名稱排序、碰撞往下一個組合找；決定性）。 */
  function uniqueLooks(names) {
    const used = new Set(), out = {};
    for (const n of [...names].sort()) {
      let v = strHash(n);
      for (let i = 0; i < 216 && used.has(lookKey(v)); i++) v = (v + 1 + (i % 6 === 5 ? 8 : 0)) >>> 0;
      used.add(lookKey(v)); out[n] = v;
    }
    return out;
  }

  /**
   * 畫一格。R(x, y, w, h, colorIndex) 由呼叫端提供（已加上該格的原點）。
   * dir：0 下、1 上、2 右；f：0–6。
   */
  function drawFrame(R, dir, f, look) {
    const side = dir === 2, back = dir === 1;
    const { hair, outfit, acc } = look;
    // 腿（走路三格交替抬腳）
    const lift = f === 1 ? [1, 0] : f === 2 ? [0, 1] : [0, 0];
    if (side) {
      R(6, 28, 2, 3 - lift[0], PANTS); R(9, 28, 2, 3 - lift[1], PANTS);
      R(6, 31 - lift[0], 3, 1, OUT); R(9, 31 - lift[1], 3, 1, OUT);
    } else {
      R(5, 28, 2, 3 - lift[0], PANTS); R(9, 28, 2, 3 - lift[1], PANTS);
      R(5, 31 - lift[0], 2, 1, OUT); R(9, 31 - lift[1], 2, 1, OUT);
    }
    // 小身體
    R(3, 21, 10, 8, OUT); R(4, 22, 8, 6, outfit);
    if (!back) R(side ? 8 : 6, 22, side ? 2 : 4, 1, WHITE);
    // 手
    if (f === 3 || f === 4) {                                         // 打字：手在桌面高度、兩格交替
      const d = f === 3 ? 0 : 1;
      if (!side) { R(2, 21 + d, 2, 2, SKIN); R(12, 22 - d, 2, 2, SKIN); } else R(12, 21 + d, 2, 2, SKIN);
    } else if (f === 5 || f === 6) {                                  // 閱讀：雙手捧文件
      R(side ? 12 : 3, 22, 2, 2, SKIN); if (!side) R(11, 22, 2, 2, SKIN);   // 文件在畫完頭之後才畫（見函式尾端）
    } else {                                                          // 走路：手擺動
      const s = f === 1 ? 1 : f === 2 ? -1 : 0;
      if (!side) { R(2, 23 + s, 2, 3, SKIN); R(12, 23 - s, 2, 3, SKIN); } else R(7 + s, 23, 2, 3, SKIN);
    }
    // 大頭（14×14）
    R(1, 8, 14, 14, OUT); R(2, 9, 12, 12, SKIN); R(2, 20, 12, 1, SKIN_D);
    if (back) {
      R(2, 9, 12, 11, hair);
    } else if (side) {
      R(2, 9, 12, 4, hair); R(2, 13, 5, 6, hair);
      R(11, 15, 1, 2, EYE); R(12, 18, 1, 1, BLUSH); R(12, 19, 1, 1, SKIN_D);
    } else {
      R(2, 9, 12, 4, hair); R(2, 13, 2, 4, hair); R(12, 13, 2, 4, hair);
      R(5, 13, 1, 1, hair); R(9, 13, 1, 1, hair);
      R(5, 15, 1, 2, EYE); R(10, 15, 1, 2, EYE);
      R(4, 18, 1, 1, BLUSH); R(11, 18, 1, 1, BLUSH); R(7, 18, 2, 1, SKIN_D);
    }
    // 配件
    if (acc === 'glasses' && !back) {
      if (side) { R(10, 14, 3, 1, OUT); R(10, 17, 3, 1, OUT); R(12, 14, 1, 4, OUT); }
      else { R(4, 14, 3, 4, OUT); R(5, 15, 1, 2, EYE); R(9, 14, 3, 4, OUT); R(10, 15, 1, 2, EYE); R(7, 15, 2, 1, OUT); }
    } else if (acc === 'cap') {
      R(2, 6, 12, 4, OUT); R(3, 7, 10, 3, outfit);
      if (side) R(10, 9, 6, 2, OUT); else if (!back) R(2, 10, 12, 1, OUT);
    } else if (acc === 'headband') {
      R(2, 11, 12, 2, outfit); if (back || side) R(side ? 1 : 12, 12, 2, 3, outfit);
    } else if (acc === 'bow') {
      R(9, 5, 6, 4, OUT); R(10, 6, 2, 2, BLUSH); R(13, 6, 1, 2, BLUSH); R(12, 6, 1, 2, RED);
    } else if (acc === 'beanie') {
      R(2, 5, 12, 6, OUT); R(3, 6, 10, 4, outfit); R(2, 10, 12, 2, WHITE); R(7, 3, 2, 2, WHITE);
    }
    // 閱讀：文件捧在下巴前（最後畫，才不會被大頭擋住；背面看不到文件）
    if ((f === 5 || f === 6) && !back) {
      const d = f === 5 ? 0 : 1;
      if (side) { R(10, 17 + d, 5, 6, OUT); R(11, 18 + d, 3, 4, PAPER); R(11, 19 + d, 2, 1, OUT); }
      else { R(4, 17 + d, 8, 6, OUT); R(5, 18 + d, 6, 4, PAPER); R(6, 19 + d, 4, 1, OUT); R(6, 21 + d, 3, 1, OUT); }
    }
  }

  /** 在 ctx（至少 112×96、透明底）畫整張 sheet。 */
  function buildSheet(ctx, look) {
    for (let d = 0; d < ROWS.length; d++) {
      for (let f = 0; f < COLS; f++) {
        const ox = f * FW, oy = d * FH;
        drawFrame((x, y, w, h, c) => { ctx.fillStyle = CHIBI_PAL[c]; ctx.fillRect(ox + x, oy + y, w, h); }, d, f, look);
      }
    }
  }

  g.ArkChibi = { CHIBI_PAL, HAIR, OUTFIT, ACCESSORY, FW, FH, COLS, ROWS, FRAMES, strHash, lookFor, uniqueLooks, drawFrame, buildSheet };
})(typeof globalThis !== 'undefined' ? globalThis : window);
