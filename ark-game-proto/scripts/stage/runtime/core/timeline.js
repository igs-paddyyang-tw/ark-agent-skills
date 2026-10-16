// ============================================================
//  演出播放器
//  machine.js 的 performances 區塊裡，每個演出是一串「步驟」，由上往下依序執行。
//  步驟一覽（詳細說明見 說明.md）：
//    { wait: 1.5 }                                等待秒數
//    { sound: '代號', wait: true }                 播音效（wait: true 表示等它播完）
//    { bgm: '代號' } / { bgm: null }               切換／停止背景音樂
//    { stopSound: '代號' } / { stopSound: 'all' }  停止音效
//    { video: '代號', wait: true, duration: 3 }    播影片（預設等播完；duration 是缺檔時的佔位秒數）
//    { image: '代號', id, x, y, w, h, duration }   顯示圖片（有 duration 會自動消失）
//    { text: '文字', id, size, color, duration }   顯示文字
//    { hide: 'id' 或 ['id', ...], fadeOut }       移除畫面上的元素
//    { clear: '圖層名' 或 'all' }                  清空圖層
//    { flash: '#fff', duration: 0.3 }             畫面閃光
//    { shake: 0.5, power: 12 }                    畫面震動
//    { parallel: [ [步驟...], [步驟...] ] }        同時執行好幾串，全部結束才往下
//    { timeline: [ { at: 0, ... }, { at: 1.2, ... } ] }  依絕對時間點執行
//    { random: [ { weight: 3, steps: [...] }, ... ] }    依權重隨機選一串
//    { if: 'hit', then: [...], else: [...] }      條件分支（hit、!hit、mode=rush 等）
//    { call: '演出名稱' } 或直接寫 '演出名稱'       呼叫另一個演出
//    { emit: '事件名稱' }                          發出事件給遊戲模組
//    { log: '標記文字' }                            在演出記錄裡加一個標記
//  遊戲模組會再加自己的步驟，例如柏青哥的 { reels: 'stop', reel: 'L' }
// ============================================================
(function () {
  'use strict';
  const Proto = window.Proto;

  // 判斷順序：前面的是主要動作，wait 放最後（因為 sound/video 也會用 wait 當選項）
  const CORE_KEYS = ['parallel', 'timeline', 'random', 'if', 'call', 'sound', 'bgm', 'stopSound', 'video', 'image', 'text', 'hide', 'clear', 'flash', 'shake', 'emit', 'log'];

  class Timeline {
    constructor(app) {
      this.app = app;
      this.handlers = {};
      this.moduleKeys = [];
      this.log = [];
      this.stack = [];
      this.token = new Proto.Token();
      this.keySeq = 0;
      this.registerCore();
    }

    // 遊戲模組用這個加自己的步驟
    register(key, fn) {
      this.handlers[key] = fn;
      if (!CORE_KEYS.includes(key)) this.moduleKeys.push(key);
    }

    record(type, name, extra = {}) {
      this.log.push({ t: Proto.clock.now(), perf: this.stack.join(' › '), type, name, ...extra });
      if (this.log.length > 20000) this.log.splice(0, 5000);
      this.app.events.emit('timeline-log');
    }

    // 播放一個演出（名稱或步驟陣列）。被 cancelAll 中斷時不會丟出錯誤
    async play(perf, ctx = {}) {
      if (perf === undefined || perf === null) return;
      const token = this.token;
      try {
        await this.runPerf(perf, ctx, token);
      } catch (e) {
        if (!e || !e.cancelled) throw e;
      }
    }

    cancelAll() {
      this.token.cancel();
      this.token = new Proto.Token();
      this.stack = [];
    }

    async runPerf(perf, ctx, token) {
      if (typeof perf !== 'string') return this.runSteps(perf, ctx, token);
      const steps = (this.app.config.performances || {})[perf];
      if (!steps) {
        this.record('missing', perf, { note: '找不到這個演出' });
        return;
      }
      this.stack.push(perf);
      this.record('perf', perf, { note: '開始' });
      try {
        await this.runSteps(steps, ctx, token);
      } finally {
        this.record('perf-end', perf, { note: '結束' });
        this.stack.pop();
      }
    }

    async runSteps(steps, ctx, token) {
      if (!Array.isArray(steps)) steps = [steps];
      for (const step of steps) {
        token.check();
        await this.runStep(step, ctx, token);
      }
    }

    async runStep(step, ctx, token) {
      if (step === null || step === undefined) return;
      if (typeof step === 'string') return this.runPerf(step, ctx, token);
      if (typeof step === 'function') return step(ctx, this.app, token);
      for (const key of [...CORE_KEYS, ...this.moduleKeys]) {
        if (key in step && this.handlers[key]) return this.handlers[key](step, ctx, token);
      }
      if (typeof step.wait === 'number') return Proto.wait(step.wait, token);
      this.record('unknown', JSON.stringify(step), { note: '看不懂的步驟' });
    }

    // 條件：'hit'、'!hit'、'mode=rush'、'reach'，或函式 (ctx) => boolean
    test(cond, ctx) {
      if (typeof cond === 'function') return !!cond(ctx);
      if (typeof cond !== 'string') return !!cond;
      const s = cond.trim();
      if (s.startsWith('!')) return !this.test(s.slice(1), ctx);
      const m = s.match(/^([^=!<>]+)(==|=|!=|>=|<=|>|<)(.+)$/);
      if (!m) return !!ctx[s];
      const [, k, op, raw] = m;
      const a = ctx[k.trim()];
      const b = raw.trim();
      const na = Number(a);
      const nb = Number(b);
      const numeric = b !== '' && !Number.isNaN(nb) && !Number.isNaN(na);
      switch (op) {
        case '=':
        case '==': return String(a) === b;
        case '!=': return String(a) !== b;
        case '>': return numeric && na > nb;
        case '<': return numeric && na < nb;
        case '>=': return numeric && na >= nb;
        case '<=': return numeric && na <= nb;
      }
      return false;
    }

    autoKey(prefix) {
      return `${prefix}-${++this.keySeq}`;
    }

    registerCore() {
      const app = this.app;
      const self = this;

      this.register('parallel', (step, ctx, token) => Promise.all(step.parallel.map((branch) => self.runSteps(branch, ctx, token))));

      this.register('timeline', (step, ctx, token) => {
        const start = Proto.clock.now();
        return Promise.all(step.timeline.map(async (item) => {
          const { at = 0, ...rest } = item;
          await Proto.wait(at - (Proto.clock.now() - start), token);
          await self.runStep(rest, ctx, token);
        }));
      });

      this.register('random', (step, ctx, token) => {
        const choice = Proto.weighted(step.random, app.rng);
        self.record('random', choice.label || `選中第 ${step.random.indexOf(choice) + 1} 項`);
        return self.runSteps(choice.steps || [], ctx, token);
      });

      this.register('if', (step, ctx, token) => self.runSteps(self.test(step.if, ctx) ? step.then || [] : step.else || [], ctx, token));

      this.register('call', (step, ctx, token) => self.runPerf(step.call, ctx, token));

      this.register('sound', async (step, ctx, token) => {
        const entry = app.assets.sounds[step.sound];
        self.record('sound', step.sound, { len: entry && entry.duration, note: entry && entry.ok ? '' : '缺檔（靜音）' });
        const handle = app.audio.play(step.sound, step);
        if (step.wait) {
          const off = token.onCancel(() => handle.stop());
          await handle.promise;
          off();
          token.check();
        }
      });

      this.register('bgm', (step) => {
        self.record('bgm', step.bgm || '（停止）');
        app.audio.playBgm(step.bgm);
      });

      this.register('stopSound', (step) => {
        self.record('stopSound', step.stopSound);
        if (step.stopSound === 'all') app.audio.stopAll({ keepBgm: true });
        else app.audio.stop(step.stopSound);
      });

      this.register('video', async (step, ctx, token) => {
        const key = step.id || self.autoKey('video');
        const v = app.stage.playVideo(key, step.video, step, token);
        self.record('video', step.video, { len: v.duration, note: v.missing ? '缺檔（佔位）' : '' });
        const finish = () => {
          if (!step.keep) app.stage.remove(key, step.fadeOut || 0);
        };
        if (step.wait === false) {
          v.promise.then(finish, finish);
          return;
        }
        const off = token.onCancel(() => v.stop());
        try {
          await v.promise;
        } finally {
          off();
          finish();
        }
        token.check();
      });

      const timed = async (key, step, token) => {
        if (step.duration === undefined) return;
        const run = Proto.wait(step.duration, token).then(() => app.stage.remove(key, step.fadeOut || 0), () => app.stage.remove(key));
        if (step.wait) await run;
      };

      this.register('image', (step, ctx, token) => {
        const key = step.id || self.autoKey('image');
        const a = app.assets.images[step.image];
        self.record('image', step.image, { len: step.duration, note: a && a.ok ? '' : '缺檔（佔位）' });
        app.stage.showImage(key, step.image, step);
        return timed(key, step, token);
      });

      this.register('text', (step, ctx, token) => {
        const key = step.id || self.autoKey('text');
        const show = (v) => (typeof v === 'number' ? (Number.isInteger(v) ? Proto.fmt.int(v) : Proto.fmt.num(v, 1)) : v);
        const text = String(step.text).replace(/\{(\w+)\}/g, (_, k) => (ctx[k] !== undefined ? show(ctx[k]) : `{${k}}`));
        self.record('text', text, { len: step.duration });
        app.stage.showText(key, text, step);
        return timed(key, step, token);
      });

      this.register('hide', (step) => {
        for (const key of [].concat(step.hide)) app.stage.remove(key, step.fadeOut || 0);
      });

      this.register('clear', (step) => app.stage.clear(step.clear));

      this.register('flash', (step) => {
        self.record('flash', typeof step.flash === 'string' ? step.flash : '#fff', { len: step.duration });
        app.stage.flash(typeof step.flash === 'string' ? step.flash : '#fff', step.duration ?? 0.25);
      });

      this.register('shake', (step) => {
        self.record('shake', '', { len: step.shake });
        app.stage.shake(step.shake, step.power);
      });

      this.register('emit', (step, ctx) => {
        self.record('emit', step.emit);
        app.events.emit(step.emit, ctx, step);
      });

      this.register('log', (step) => self.record('label', step.log));
    }
  }

  // 找出演出裡用到的素材與演出名稱（設定檢查用）
  Timeline.collectRefs = function (steps, refs = { perfs: new Set(), images: new Set(), videos: new Set(), sounds: new Set() }) {
    const walk = (s) => {
      if (!s) return;
      if (typeof s === 'string') return refs.perfs.add(s);
      if (Array.isArray(s)) return s.forEach(walk);
      if (typeof s !== 'object') return;
      if (s.call) refs.perfs.add(s.call);
      if (s.sound) refs.sounds.add(s.sound);
      if (s.bgm) refs.sounds.add(s.bgm);
      if (s.video) refs.videos.add(s.video);
      if (s.image) refs.images.add(s.image);
      if (s.parallel) s.parallel.forEach(walk);
      if (s.timeline) s.timeline.forEach(walk);
      if (s.random) s.random.forEach((r) => walk(r.steps));
      if (s.then) walk(s.then);
      if (s.else) walk(s.else);
    };
    walk(steps);
    return refs;
  };

  Proto.Timeline = Timeline;
})();
