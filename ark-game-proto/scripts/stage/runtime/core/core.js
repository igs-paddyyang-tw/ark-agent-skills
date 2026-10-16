// ============================================================
//  核心：命名空間、時間控制、亂數、小工具
//  老虎機試玩模板（2026-10 從柏青「HTML共用模板」分出，只做老虎機）
//  所有檔案都掛在全域的 Proto 底下，不需要安裝或打包，雙擊 index.html 就能跑
// ============================================================
(function () {
  'use strict';
  const root = typeof window !== 'undefined' ? window : globalThis;
  const Proto = (root.Proto = root.Proto || {});

  // 核心檔案載入順序（index.html 的載入器會照這個順序載入）
  Proto.coreFiles = ['核心/assets.js', '核心/audio.js', '核心/stage.js', '核心/timeline.js', '核心/sim.js', '核心/ui.js', '核心/app.js'];
  Proto.coreStyles = ['核心/style.css'];
  // 遊戲類型 → 模組檔案
  Proto.moduleFiles = {
    slot: { scripts: ['老虎機模組/slot.js'], styles: ['老虎機模組/slot.css'] },
  };
  // 玩法模組（第二層，選配）：game.js 的 spec.feature.type 寫哪個就載哪個
  // 內建的 'freeSpins'（一般免費旋轉）寫在 slot.js 裡，不用另外載
  Proto.featureFiles = {
    '鎖格重轉': { scripts: ['玩法模組/鎖格重轉/holdwin.js'], styles: ['玩法模組/鎖格重轉/holdwin.css'] },
  };
  Proto.modules = Proto.modules || {};
  Proto.features = Proto.features || {};

  // 遊戲設定檔（game.js）呼叫這個函式登記設定；type 不寫就是 'slot'
  Proto.game = function (config) {
    if (!config.type) config.type = 'slot';
    Proto.config = config;
  };
  Proto.machine = Proto.game; // 舊名稱，柏青模板的 machine.js 也能用

  // ---------- 時間 ----------
  // speed：倍速；paused：暫停；skip：跳過演出（等待立即結束、不播影音）
  // clock.now() 是「換算回 1 倍速」的經過秒數，演出記錄用它，所以倍速測試時記下的時間點仍然正確
  Proto.time = { speed: 1, paused: false, skip: false };
  const clock = { acc: 0, last: nowReal() };
  function nowReal() {
    return typeof performance !== 'undefined' ? performance.now() : Date.now();
  }
  function flush() {
    const t = nowReal();
    if (!Proto.time.paused) clock.acc += (t - clock.last) * Proto.time.speed;
    clock.last = t;
  }
  Proto.clock = {
    now() {
      flush();
      return clock.acc / 1000;
    },
  };
  Proto.setSpeed = function (s) {
    flush();
    Proto.time.speed = s;
  };
  Proto.setPaused = function (p) {
    flush();
    Proto.time.paused = p;
  };

  // ---------- 取消 ----------
  class Cancelled extends Error {
    constructor() {
      super('cancelled');
      this.cancelled = true;
    }
  }
  class Token {
    constructor() {
      this.cancelled = false;
      this.listeners = new Set();
    }
    cancel() {
      if (this.cancelled) return;
      this.cancelled = true;
      for (const f of this.listeners) f();
      this.listeners.clear();
    }
    onCancel(f) {
      if (this.cancelled) {
        f();
        return () => {};
      }
      this.listeners.add(f);
      return () => this.listeners.delete(f);
    }
    check() {
      if (this.cancelled) throw new Cancelled();
    }
  }
  Proto.Cancelled = Cancelled;
  Proto.Token = Token;

  // 會受倍速、暫停、跳過、取消影響的等待（秒）
  Proto.wait = function (sec, token) {
    return new Promise((resolve, reject) => {
      if (token && token.cancelled) return reject(new Cancelled());
      if (Proto.time.skip || !(sec > 0)) return resolve();
      let remaining = sec * 1000;
      let last = nowReal();
      let timer = null;
      let off = null;
      const tick = () => {
        const t = nowReal();
        if (!Proto.time.paused) remaining -= (t - last) * Proto.time.speed;
        last = t;
        if (Proto.time.skip || remaining <= 0) {
          if (off) off();
          resolve();
        } else {
          timer = setTimeout(tick, Math.max(4, Math.min(50, remaining / Proto.time.speed)));
        }
      };
      if (token) {
        off = token.onCancel(() => {
          clearTimeout(timer);
          reject(new Cancelled());
        });
      }
      timer = setTimeout(tick, Math.max(4, Math.min(50, remaining / Proto.time.speed)));
    });
  };

  // ---------- 亂數 ----------
  // 可指定種子（seed），同樣的種子會得到同樣的結果，方便重現問題
  Proto.createRng = function (seed) {
    let a = (seed === undefined || seed === null || seed === '' ? Math.floor(Math.random() * 4294967296) : Number(seed)) >>> 0;
    const rnd = function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    rnd.int = (n) => Math.floor(rnd() * n);
    rnd.chance = (p) => rnd() < p;
    rnd.pick = (arr) => arr[Math.floor(rnd() * arr.length)];
    rnd.weighted = (list) => Proto.weighted(list, rnd);
    // 幾何分布：機率 p 的抽選第幾次會中（1 起算）
    rnd.geometric = (p) => {
      if (p >= 1) return 1;
      if (p <= 0) return Infinity;
      return Math.floor(Math.log(1 - rnd()) / Math.log(1 - p)) + 1;
    };
    return rnd;
  };

  // 依 weight 權重抽一個；沒寫 weight 視為 1
  Proto.weighted = function (list, rnd = Math.random) {
    let total = 0;
    for (const x of list) total += Math.max(0, x.weight ?? 1);
    if (total <= 0) return list[0];
    let r = rnd() * total;
    for (const x of list) {
      r -= Math.max(0, x.weight ?? 1);
      if (r < 0) return x;
    }
    return list[list.length - 1];
  };

  // ---------- 事件 ----------
  class Emitter {
    constructor() {
      this.map = new Map();
    }
    on(name, f) {
      if (!this.map.has(name)) this.map.set(name, new Set());
      this.map.get(name).add(f);
      return () => this.map.get(name).delete(f);
    }
    emit(name, ...args) {
      for (const f of this.map.get(name) || []) {
        try {
          f(...args);
        } catch (e) {
          console.error(e);
        }
      }
    }
  }
  Proto.Emitter = Emitter;

  // ---------- 格式化 ----------
  Proto.fmt = {
    int: (n) => (Number.isFinite(n) ? Math.round(n).toLocaleString('en-US') : String(n)),
    num: (n, d = 2) => (Number.isFinite(n) ? n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }) : String(n)),
    pct: (x, d = 2) => (Number.isFinite(x) ? `${(x * 100).toFixed(d)}%` : '—'),
    oneIn: (p, d = 1) => (p > 0 ? `1/${(1 / p).toFixed(d)}` : '—'),
    sec: (s) => (Number.isFinite(s) ? s.toFixed(2) : ''),
    // 格子裡放不下完整數字時用：一律不超過 4 個字元（八尺 美術規格 §6-3）
    //   1～9,999 原樣（小數留一位）／10K～999K／1M～999M／1B～
    // 門檻設 10,000 而不是 1,000：1,024 和 1,536 都寫成 1K 玩家會分不出來
    short: (v) => {
      if (!Number.isFinite(v)) return String(v);
      if (v < 10000) return v % 1 === 0 ? String(v) : String(Math.round(v * 10) / 10);
      if (v < 1e6) return Math.floor(v / 1e3) + 'K';
      if (v < 1e9) return Math.floor(v / 1e6) + 'M';
      return Math.floor(v / 1e9) + 'B';
    },
    // 金額：整數不帶小數，有小數時留兩位
    money: (n) => (Number.isFinite(n) ? (Math.abs(n - Math.round(n)) < 1e-9 ? Math.round(n).toLocaleString('en-US') : n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })) : String(n)),
  };

  // ---------- DOM 小工具 ----------
  // Proto.h('div', { class: 'x', onclick: fn }, '文字', 子元素...)
  Proto.h = function (tag, props, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
      else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
      else if (k === 'html') el.innerHTML = v;
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const c of children.flat()) {
      if (c === undefined || c === null || c === false) continue;
      el.appendChild(typeof c === 'object' ? c : document.createTextNode(String(c)));
    }
    return el;
  };
})();
