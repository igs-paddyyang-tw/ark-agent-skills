// 驗證台 UI 無頭冒煙測試（node tests/ui_smoke.js <game-config.json> [--plays N]）
//
// 沒有瀏覽器時的替代：以 DOM / PixiJS / Worker 替身在 Node 跑完整 app.js ——
// L1 精算面板、規格缺口、Go 對照、L2（Worker 替身同步跑 simulate）、單局抽表軌跡、每種玩法各演一場（含特色遊戲演出）。
// 判定：流程不丟例外、各面板有內容、HTML 不含 undefined / NaN。不驗畫面像素（那要真瀏覽器）。
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const a = process.argv.slice(2);
const cfgPath = a[0];
const plays = a.includes('--plays') ? +a[a.indexOf('--plays') + 1] : 1;
if (!cfgPath) { console.error('用法：node tests/ui_smoke.js <game-config.json> [--plays N]'); process.exit(2); }
const SRC = path.join(__dirname, '..', 'src');
const read = (n) => fs.readFileSync(path.join(SRC, n), 'utf8');
const cfg = JSON.parse(fs.readFileSync(path.resolve(cfgPath), 'utf8'));

// ── 萬用替身：任何屬性 / 呼叫 / new 都回替身；數值情境轉成 0；不可 await（then = undefined）
function stub() {
  const t = function () {};
  return new Proxy(t, {
    get(o, k) {
      if (k === 'then') return undefined;
      if (k === Symbol.toPrimitive) return () => 0;
      if (k === Symbol.iterator) return function* () {};
      if (!(k in o)) o[k] = stub();
      return o[k];
    },
    set(o, k, v) { o[k] = v; return true; },
    apply() { return stub(); },
    construct() { return stub(); },
  });
}
const els = {};
function el(sel) {
  if (!els[sel]) {
    els[sel] = { sel, innerHTML: '', textContent: '', value: '', style: {}, disabled: false, dataset: {},
      classList: { toggle() {}, add() {}, remove() {} }, appendChild() {}, setAttribute() {}, getBoundingClientRect: () => ({ left: 0, top: 0, width: 1, height: 1 }) };
  }
  return els[sel];
}
const document = {
  querySelector: el, querySelectorAll: () => [], getElementById: (id) => (id === 'core-src' ? { textContent: read('slot-core.js') } : el('#' + id)),
  createElement: () => ({ textContent: '', onclick: null }),
};
const ticker = { add(fn) { fn({ deltaMS: 1e9 }); }, remove() {} };       // 補間一步到位
const PIXI = new Proxy({}, {
  get(o, k) {
    if (k === 'Application') return function () { const s = stub(); s.init = async () => {}; s.ticker = ticker; return s; };
    return function () { return stub(); };
  },
});
let errors = [];
const ctx = {
  console, Math, JSON, Date, Promise, Number, String, Array, Object, Set, Map, Symbol, Int8Array, Uint8Array, Uint32Array, Float64Array, Error, isFinite, BigInt,
  setTimeout: (f) => setImmediate(f), clearTimeout() {}, setImmediate,
  performance: { now: () => Date.now() }, requestAnimationFrame: () => 0, navigator: { hardwareConcurrency: 2 },
  crypto: { getRandomValues: (u) => { u[0] = 1 + Math.floor(Math.random() * 4e9); return u; } },
  URL: { createObjectURL: () => 'blob:x' }, Blob: function () {}, addEventListener() {},
  document, PIXI, devicePixelRatio: 1,
  Worker: class {
    postMessage(m) {
      setImmediate(() => {
        try { const C = ctx.SlotCore.compile(m.cfg); const st = ctx.SlotCore.simulate(C, m.seed0, m.n); this.onmessage({ data: { st, done: m.n, final: true } }); }
        catch (e) { errors.push('worker: ' + e.message); }
      });
    }
    terminate() {}
  },
};
ctx.window = ctx; ctx.self = ctx; ctx.globalThis = ctx;
ctx.window.GAME_CONFIG = cfg;
vm.createContext(ctx);
vm.runInContext(read('slot-core.js'), ctx, { filename: 'slot-core.js' });
vm.runInContext(read('art.js'), ctx, { filename: 'art.js' });
ctx.SlotArt.load = async () => new Proxy({}, { get: (o, k) => (k === 'then' ? undefined : stub()) });

let fail = 0;
const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fail++; };
const bad = (h) => /undefined|NaN/.test(h);
const until = async (pred, ms = 120000) => { const t0 = Date.now(); while (!pred()) { if (Date.now() - t0 > ms) return false; await new Promise((r) => setImmediate(r)); } return true; };

(async () => {
  try { await vm.runInContext(read('app.js'), ctx, { filename: 'app.js' }); } catch (e) { errors.push('app: ' + e.stack); }
  const P = ctx.window.__proto;
  ok(!!P && !errors.length, 'app.js 啟動（L1 / 缺口 / Go 對照 / L2 外殼 / Pixi 場景）' + (errors.length ? '：' + errors[0] : ''));
  if (!P) process.exit(1);
  for (const id of ['#pane-l1', '#pane-gaps', '#pane-go']) ok(el(id).innerHTML.length > 50 && !bad(el(id).innerHTML), `${id} 有內容且無 undefined / NaN`);
  // L2：Worker 替身同步跑
  P.runL2(200000);
  ok(await until(() => /贏分分級/.test(el('#l2body').innerHTML)), 'L2 蒙地卡羅 20 萬手完成並出表');
  ok(!bad(el('#l2body').innerHTML), '#l2body 無 undefined / NaN');
  // 每種玩法各找 seed 演一場（含主遊戲無玩法）
  const C = P.C, S = P.SlotCore, want = new Map([['__none', null]]);
  for (const g of C.G) want.set(g, null);
  for (let s = 1; s < 3e6 && [...want.values()].some((v) => v == null || v.length < plays); s++) {
    const r = S.spin(C, s), k = r.fg ? r.fg.group : '__none';
    if (!want.has(k)) continue;
    const v = want.get(k) || []; if (v.length < plays) v.push(s); want.set(k, v);
  }
  for (const [g, seeds] of want) {
    if (!seeds) { ok(false, `找不到 ${g} 的 seed`); continue; }
    for (const s of seeds) {
      try { await P.playSeed(s); } catch (e) { errors.push(`play ${g}#${s}: ${e.stack}`); }
      const h = el('#pane-spin').innerHTML;
      ok(!errors.length && h.includes(`seed ${s}`) && !bad(h), `演一局 ${g === '__none' ? '主遊戲' : g}（seed ${s}）：演出流程跑完、抽表軌跡無 undefined / NaN` + (errors.length ? '\n  ' + errors.pop() : ''));
    }
  }
  process.exit(fail ? 1 : 0);
})();
