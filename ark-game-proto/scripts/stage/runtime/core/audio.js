// ============================================================
//  音效管理
//  頻道：bgm（同時只有一首）、se（音效）、voice（語音），各自有音量
//  跳過演出時 se／voice 不播放；倍速時播放速度跟著變
// ============================================================
(function () {
  'use strict';
  const Proto = window.Proto;

  class AudioManager {
    constructor(assets) {
      this.assets = assets;
      this.master = 1;
      this.channels = { bgm: 0.6, se: 1, voice: 1 };
      this.muted = false;
      this.active = new Set();
      this.bgm = null;
    }

    volumeOf(handle) {
      if (this.muted) return 0;
      const ch = this.channels[handle.channel] ?? 1;
      return Math.max(0, Math.min(1, this.master * ch * (handle.volume ?? 1) * (handle.gain ?? 1)));
    }

    // 回傳 handle：{ promise（播完時完成）, stop() }
    play(id, opts = {}) {
      const entry = this.assets.sounds[id];
      const channel = opts.channel || (entry && entry.channel) || 'se';
      const handle = { id, channel, volume: opts.volume ?? (entry && entry.volume) ?? 1, done: false, stop() {}, promise: Promise.resolve() };
      if (!entry || !entry.ok || (Proto.time.skip && channel !== 'bgm')) {
        handle.done = true;
        return handle;
      }
      const el = new Audio(entry.src);
      el.loop = opts.loop ?? entry.loop ?? channel === 'bgm';
      el.playbackRate = Proto.time.speed;
      handle.el = el;
      el.volume = this.volumeOf(handle);
      handle.promise = new Promise((resolve) => {
        const finish = () => {
          if (handle.done) return;
          handle.done = true;
          this.active.delete(handle);
          resolve();
        };
        el.addEventListener('ended', finish);
        el.addEventListener('error', finish);
        handle.stop = () => {
          el.pause();
          finish();
        };
      });
      this.active.add(handle);
      const p = el.play();
      if (p) p.catch(() => handle.stop());
      if (Proto.time.paused) el.pause();
      return handle;
    }

    playBgm(id) {
      if (!id) return this.stopBgm();
      const f = this.bgmFading;
      if (f && f.id === id && !f.done && (!this.bgm || this.bgm === f)) this.bgm = f;
      this.bgmFading = null;
      if (this.bgm && this.bgm.id === id && !this.bgm.done) {
        clearInterval(this.bgm.fadeTimer);
        this.bgm.gain = 1;
        if (this.bgm.el) this.bgm.el.volume = this.volumeOf(this.bgm);
        return;
      }
      this.stopBgm();
      this.bgm = this.play(id, { channel: 'bgm', loop: true });
    }

    stopBgm() {
      if (this.bgm) this.bgm.stop();
      this.bgm = null;
    }

    // 淡出後停止（秒）。BGM 收尾、聽牌聲提早結束都用這個
    fadeOut(handle, sec = 0.8) {
      if (!handle || handle.done) return Promise.resolve();
      if (!handle.el || !(sec > 0) || Proto.time.skip) {
        handle.stop();
        return Promise.resolve();
      }
      clearInterval(handle.fadeTimer);
      const g0 = handle.gain ?? 1;
      const t0 = Proto.clock.now();
      return new Promise((resolve) => {
        handle.fadeTimer = setInterval(() => {
          const k = Math.min(1, (Proto.clock.now() - t0) / sec);
          handle.gain = g0 * (1 - k);
          if (handle.el) handle.el.volume = this.volumeOf(handle);
          if (k >= 1 || handle.done) {
            clearInterval(handle.fadeTimer);
            handle.stop();
            resolve();
          }
        }, 40);
      });
    }

    // BGM 淡出；淡出中又呼叫 playBgm 同一首時會拉回原音量接著播
    fadeOutBgm(sec = 0.8) {
      const h = this.bgm;
      this.bgm = null;
      this.bgmFading = h;
      return this.fadeOut(h, sec);
    }

    stop(id) {
      for (const h of [...this.active]) if (h.id === id) h.stop();
    }

    stopAll({ keepBgm = false } = {}) {
      for (const h of [...this.active]) {
        if (keepBgm && h === this.bgm) continue;
        h.stop();
      }
      if (!keepBgm) this.bgm = null;
    }

    // 倍速、音量、暫停改變時呼叫
    refresh() {
      for (const h of this.active) {
        if (!h.el) continue;
        h.el.playbackRate = Proto.time.speed;
        h.el.volume = this.volumeOf(h);
        if (Proto.time.paused) h.el.pause();
        else if (h.el.paused && !h.done) h.el.play().catch(() => {});
      }
    }
  }

  Proto.AudioManager = AudioManager;
})();
