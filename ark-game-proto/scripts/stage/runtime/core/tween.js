// ============================================================
//  [ark-game-proto stage] 補間（ADR-007）
//  ・所有動畫共用一個時鐘：Proto.tick(dtMs) 由 Pixi ticker（瀏覽器）或測試手動推進
//  ・服從 Proto.time：speed 倍速、paused 暫停、skip 跳過（立即到終值）；Token 取消 → reject Cancelled
//  ・props 支援點路徑：{ x: 10, 'scale.x': 1.2, alpha: 0 }
//  Proto.tween(target, props, sec, { ease, delay, token, onUpdate }) → Promise
//  Proto.every(fn) → 每格回呼（dtSec 已乘倍速），回傳取消函式
// ============================================================
(function () {
  'use strict';
  const root = typeof window !== 'undefined' ? window : globalThis;
  const Proto = root.Proto;

  const PI = Math.PI;
  const Ease = {
    linear: (t) => t,
    inQuad: (t) => t * t, outQuad: (t) => t * (2 - t), inOutQuad: (t) => (t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t),
    inCubic: (t) => t * t * t, outCubic: (t) => 1 - Math.pow(1 - t, 3), inOutCubic: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    outQuart: (t) => 1 - Math.pow(1 - t, 4),
    inBack: (t) => 2.70158 * t * t * t - 1.70158 * t * t,
    outBack: (t) => 1 + 2.70158 * Math.pow(t - 1, 3) + 1.70158 * Math.pow(t - 1, 2),
    outElastic: (t) => (t === 0 || t === 1 ? t : Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * ((2 * PI) / 3)) + 1),
    outBounce: (t) => {
      const n = 7.5625, d = 2.75;
      if (t < 1 / d) return n * t * t;
      if (t < 2 / d) return n * (t -= 1.5 / d) * t + 0.75;
      if (t < 2.5 / d) return n * (t -= 2.25 / d) * t + 0.9375;
      return n * (t -= 2.625 / d) * t + 0.984375;
    },
    sine: (t) => 0.5 - 0.5 * Math.cos(t * PI),
  };

  const get = (o, path) => path.split('.').reduce((a, k) => (a == null ? a : a[k]), o);
  const set = (o, path, v) => { const ks = path.split('.'); const last = ks.pop(); const t = ks.reduce((a, k) => a[k], o); t[last] = v; };

  const tweens = new Set();
  const hooks = new Set();

  // dtMs：真實經過毫秒；這裡換算倍速與暫停
  Proto.tick = function (dtMs) {
    if (Proto.time.paused) return;
    const dt = (dtMs / 1000) * (Proto.time.speed || 1);
    for (const f of [...hooks]) { try { f(dt); } catch (e) { console.error(e); } }
    for (const tw of [...tweens]) tw.step(dt);
  };

  Proto.every = function (fn) { hooks.add(fn); return () => hooks.delete(fn); };

  class Tween {
    constructor(target, props, sec, o) {
      this.target = target;
      this.to = props;
      this.sec = Math.max(0, sec || 0);
      this.ease = typeof o.ease === 'function' ? o.ease : Ease[o.ease || 'outQuad'] || Ease.outQuad;
      this.delay = o.delay || 0;
      this.onUpdate = o.onUpdate;
      this.yoyo = !!o.yoyo;
      this.repeat = o.repeat ?? 0;   // -1 = 無限
      this.t = 0;
      this.from = null;
      this.promise = new Promise((res, rej) => { this.res = res; this.rej = rej; });
      if (o.token) this.offCancel = o.token.onCancel(() => this.kill(true));
    }
    start() {
      this.from = {};
      for (const k of Object.keys(this.to)) this.from[k] = get(this.target, k);
    }
    apply(p) {
      const e = this.ease(p);
      for (const k of Object.keys(this.to)) set(this.target, k, this.from[k] + (this.to[k] - this.from[k]) * e);
      if (this.onUpdate) this.onUpdate(p, e);
    }
    step(dt) {
      if (this.target && this.target.destroyed) return this.kill(false);
      if (this.delay > 0) { this.delay -= dt; if (this.delay > 0) return; dt = -this.delay; this.delay = 0; }
      if (!this.from) this.start();
      if (Proto.time.skip && this.repeat === 0) { this.apply(1); return this.finish(); }
      this.t += dt;
      const p = this.sec > 0 ? Math.min(1, this.t / this.sec) : 1;
      this.apply(p);
      if (p >= 1) {
        if (this.repeat !== 0) {
          if (this.repeat > 0) this.repeat--;
          this.t = Math.max(0, this.t - this.sec);      // 保留溢出時間，迴圈不漂移
          if (this.yoyo) { const f = this.from; this.from = { ...this.to }; this.to = f; }
          this.apply(this.sec > 0 ? Math.min(1, this.t / this.sec) : 0);
          return;
        }
        this.finish();
      }
    }
    finish() { tweens.delete(this); if (this.offCancel) this.offCancel(); this.res(this.target); }
    kill(cancelled) {
      tweens.delete(this);
      if (this.offCancel) this.offCancel();
      if (cancelled) this.rej(new Proto.Cancelled()); else this.res(this.target);
    }
  }

  Proto.Ease = Ease;
  Proto.tween = function (target, props, sec, o = {}) {
    if (o.token && o.token.cancelled) return Promise.reject(new Proto.Cancelled());
    const tw = new Tween(target, props, sec, o);
    if ((Proto.time.skip && tw.repeat === 0) || (!(tw.sec > 0) && !(tw.delay > 0))) { tw.start(); tw.apply(1); return Promise.resolve(target); }
    tweens.add(tw);
    target.__tweens = target.__tweens || new Set();
    target.__tweens.add(tw);
    tw.promise.then(() => target.__tweens && target.__tweens.delete(tw), () => target.__tweens && target.__tweens.delete(tw));
    return tw.promise;
  };
  // 停掉某物件身上的所有補間（不 reject，直接結束在目前值）
  Proto.tween.kill = function (target) { for (const tw of [...(target.__tweens || [])]) tw.kill(false); };
  // 迴圈補間（脈動、呼吸）：回傳停止函式
  Proto.tween.loop = function (target, props, sec, o = {}) {
    const tw = new Tween(target, props, sec, { ...o, yoyo: o.yoyo !== false, repeat: -1 });
    tweens.add(tw);
    return () => tw.kill(false);
  };
  Proto.tween.count = () => tweens.size;
})();
