// ============================================================
//  [ark-game-proto stage] 舞台（PixiJS 8）
//  公開方法與 Proto 試玩模板 stage.js 同名同參數（ADR-001 / CMP-101），Timeline 與遊戲包不用改：
//    layer / place / placeholder / add / animateIn / showImage / showText / playVideo / setBgVideo / clearBgVideo
//    remove / clear / flash / shake / refresh / fit
//  圖層由下往上：bg → video → main → reels → effect → ui → overlay（7 個 Container）
//  位置參數（舞台像素，原點左上）：x, y 中心點（預設畫面中央）、w / h（只給一個時等比）、full + fit（cover|contain）、
//    anchor（'center' | 'topleft'）、opacity、fadeIn、anim（pop zoom slideLeft slideRight slideTop slideBottom blink）
//  另提供 this.dom：疊在 canvas 上、套同一縮放的 DOM 容器（INFO / 除錯疊層用，ADR-004）
// ============================================================
(function () {
  'use strict';
  const Proto = window.Proto;
  const h = (...a) => Proto.h(...a);
  const LAYERS = ['bg', 'video', 'main', 'reels', 'effect', 'ui', 'overlay'];
  const color = (c, d = 0xffffff) => { try { return new PIXI.Color(c ?? d).toNumber(); } catch (e) { return d; } };

  class Stage {
    constructor(container, opts = {}) {
      this.width = opts.width || 1080;
      this.height = opts.height || 1920;
      this.background = opts.background || '#000';
      this.container = container;
      this.items = new Map();
      this.videos = new Set();
      this.frame = h('div', { class: 'proto-stage-frame', style: { position: 'relative', overflow: 'hidden' } });
      this.dom = h('div', { class: 'proto-stage-dom', style: { position: 'absolute', left: '0', top: '0', width: `${this.width}px`, height: `${this.height}px`, transformOrigin: '0 0', pointerEvents: 'none' } });
      container.appendChild(this.frame);
    }

    // Pixi Application 需要非同步建立
    async init() {
      const app = (this.pixi = new PIXI.Application());
      const res = Math.min(window.devicePixelRatio || 1, 2);
      try {
        await app.init({ width: this.width, height: this.height, background: this.background, antialias: true, resolution: res, autoDensity: true, preference: 'webgl' });
      } catch (e) {
        await app.init({ width: this.width, height: this.height, background: this.background, antialias: false, resolution: 1, preference: 'webgl' });
      }
      this.renderer = app.renderer;
      this.canvas = app.canvas;
      this.canvas.style.display = 'block';
      this.frame.append(this.canvas, this.dom);
      this.root = new PIXI.Container();
      this.shaker = new PIXI.Container();
      this.root.addChild(this.shaker);
      app.stage.addChild(this.root);
      this.layers = {};
      for (const name of LAYERS) { const c = new PIXI.Container(); c.label = name; this.layers[name] = c; this.shaker.addChild(c); }
      app.stage.eventMode = 'static';
      app.ticker.add((t) => Proto.tick(t.deltaMS));
      this.fps = () => app.ticker.FPS;
      this.fit();
      if (typeof ResizeObserver !== 'undefined') new ResizeObserver(() => this.fit()).observe(this.container);
      window.addEventListener('resize', () => this.fit());
      return this;
    }

    fit() {
      if (!this.pixi) return;
      const cs = getComputedStyle(this.container);
      const cw = this.container.clientWidth - (parseFloat(cs.paddingLeft) || 0) - (parseFloat(cs.paddingRight) || 0);
      const ch = this.container.clientHeight - (parseFloat(cs.paddingTop) || 0) - (parseFloat(cs.paddingBottom) || 0);
      if (!(cw > 0) || !(ch > 0)) return;
      this.scale = Math.min(cw / this.width, ch / this.height);
      const W = Math.round(this.width * this.scale), H = Math.round(this.height * this.scale);
      this.canvas.style.width = `${W}px`;
      this.canvas.style.height = `${H}px`;
      this.frame.style.width = `${W}px`;
      this.frame.style.height = `${H}px`;
      this.dom.style.transform = `scale(${this.scale})`;
    }

    layer(name) { return this.layers[name] || this.layers.main; }

    // 物件尺寸：Sprite 以貼圖原始尺寸換算 scale；其他物件直接設 width / height
    place(obj, o = {}) {
      const W = this.width, H = this.height;
      const base = obj.__base || (obj.__base = { w: obj.texture ? obj.texture.width : obj.width, h: obj.texture ? obj.texture.height : obj.height });
      if (obj.anchor && obj.anchor.set) obj.anchor.set(o.anchor === 'topleft' && !o.full ? 0 : 0.5);
      if (o.full) {
        const sx = W / (base.w || 1), sy = H / (base.h || 1);
        const s = (o.fit || 'cover') === 'contain' ? Math.min(sx, sy) : Math.max(sx, sy);
        obj.scale.set(s);
        if (obj.anchor) obj.position.set(W / 2, H / 2);
        else obj.position.set((W - base.w * s) / 2, (H - base.h * s) / 2);
      } else {
        let sx = 1, sy = 1;
        if (o.w !== undefined && o.h !== undefined) { sx = o.w / (base.w || 1); sy = o.h / (base.h || 1); }
        else if (o.w !== undefined) sx = sy = o.w / (base.w || 1);
        else if (o.h !== undefined) sx = sy = o.h / (base.h || 1);
        obj.scale.set(sx, sy);
        const x = o.x ?? W / 2, y = o.y ?? H / 2;
        if (obj.anchor || o.anchor === 'topleft') obj.position.set(x, y);
        else obj.position.set(x - (base.w * sx) / 2, y - (base.h * sy) / 2);   // 無 anchor 的容器：以中心定位
      }
      if (o.opacity !== undefined) obj.alpha = o.opacity;
      if (o.z !== undefined) obj.zIndex = o.z;
      if (o.rotation !== undefined) obj.rotation = o.rotation;
      obj.__place = { ...o };
      return obj;
    }

    placeholder(label, o = {}) {
      const w = o.full ? this.width : o.w ?? 360, hh = o.full ? this.height : o.h ?? 200;
      const c = new PIXI.Container();
      c.addChild(new PIXI.Graphics().rect(0, 0, w, hh).fill({ color: 0x333333, alpha: 0.85 }).stroke({ width: 3, color: 0x888888 }));
      const t = new PIXI.Text({ text: label, style: { fontSize: Math.max(18, Math.min(40, w / 10)), fill: '#ddd', align: 'center', wordWrap: true, wordWrapWidth: w - 20 } });
      t.anchor.set(0.5); t.position.set(w / 2, hh / 2);
      c.addChild(t);
      c.__base = { w, h: hh };
      c.__label = t;
      return c;
    }

    add(key, obj, o = {}) {
      if (key) this.remove(key);
      this.place(obj, o);
      this.layer(o.layer).addChild(obj);
      if (key) { this.items.set(key, obj); obj.__key = key; }
      this.animateIn(obj, o);
      return obj;
    }

    animateIn(obj, o) {
      if (Proto.time.skip) return;
      if (o.fadeIn > 0) { const a = obj.alpha; obj.alpha = 0; Proto.tween(obj, { alpha: a }, o.fadeIn, { ease: 'linear' }); }
      if (!o.anim) return;
      const d = o.animTime ?? 0.35;
      const sx = obj.scale.x, sy = obj.scale.y, x = obj.x, y = obj.y;
      switch (o.anim) {
        case 'pop': obj.scale.set(sx * 0.3, sy * 0.3); Proto.tween(obj, { 'scale.x': sx, 'scale.y': sy }, d, { ease: 'outBack' }); break;
        case 'zoom': obj.scale.set(sx * 2.2, sy * 2.2); obj.alpha = 0; Proto.tween(obj, { 'scale.x': sx, 'scale.y': sy, alpha: 1 }, d, { ease: 'outCubic' }); break;
        case 'slideLeft': obj.x = x + this.width; Proto.tween(obj, { x }, d, { ease: 'outCubic' }); break;
        case 'slideRight': obj.x = x - this.width; Proto.tween(obj, { x }, d, { ease: 'outCubic' }); break;
        case 'slideTop': obj.y = y - this.height; Proto.tween(obj, { y }, d, { ease: 'outCubic' }); break;
        case 'slideBottom': obj.y = y + this.height; Proto.tween(obj, { y }, d, { ease: 'outCubic' }); break;
        case 'blink': Proto.tween(obj, { alpha: 0.15 }, d / 3, { ease: 'linear', yoyo: true, repeat: 5 }); break;
        default: break;
      }
    }

    texture(assetId) {
      const a = this.assets && this.assets.images[assetId];
      return a && a.ok ? a.tex : null;
    }

    showImage(key, assetId, o = {}) {
      const tex = this.texture(assetId);
      const obj = tex ? new PIXI.Sprite(tex) : this.placeholder(`圖片：${assetId}`, o);
      if (tex) obj.__assetId = assetId;
      return this.add(key, obj, { layer: 'main', ...o });
    }

    showText(key, text, o = {}) {
      const size = o.size ?? 48;
      const style = { fontFamily: o.font || "'Microsoft JhengHei','PingFang TC','Noto Sans TC','Arial Black',sans-serif", fontSize: size, fill: o.color ?? '#fff', fontWeight: String(o.weight ?? 900), align: o.align || 'center' };
      if (o.stroke !== false) style.stroke = { color: o.stroke ?? '#000', width: o.strokeWidth ?? Math.max(2, size / 12), join: 'round' };
      if (o.shadow !== false) style.dropShadow = { color: '#000', alpha: 0.6, blur: 6, distance: 4, angle: Math.PI / 2 };
      if (o.wrap) { style.wordWrap = true; style.wordWrapWidth = o.wrap; }
      const t = new PIXI.Text({ text: String(text), style });
      return this.add(key, t, { layer: 'effect', ...o });
    }

    // 影片：用 HTMLVideoElement 當貼圖來源；回傳 { promise, stop() }
    playVideo(key, assetId, o = {}, token) {
      const a = this.assets && this.assets.videos[assetId];
      const opts = { layer: 'effect', full: o.x === undefined && o.w === undefined, ...o };
      if (!a || !a.ok) {
        const dur = o.duration ?? 3;
        const ph = this.add(key, this.placeholder(`影片：${assetId}（缺檔，佔位 ${dur} 秒）`, opts), opts);
        return { promise: Proto.wait(dur, token).finally(() => this.items.get(key) === ph && this.remove(key)), stop() {}, duration: dur, missing: true };
      }
      if (Proto.time.skip) return { promise: Promise.resolve(), stop() {}, duration: a.duration };
      const el = this.videoEl(a, o);
      const sp = new PIXI.Sprite(PIXI.Texture.from(el));
      sp.__base = { w: el.videoWidth || this.width, h: el.videoHeight || this.height };
      this.add(key, sp, opts);
      this.videos.add(el);
      let done;
      const promise = new Promise((r) => { done = r; el.addEventListener('ended', r); el.addEventListener('error', r); })
        .finally(() => { this.videos.delete(el); el.pause(); });
      el.play().catch(() => done());
      if (token) token.onCancel(() => done());
      return { promise, el, duration: a.duration, stop: () => done() };
    }

    videoEl(a, o) {
      const el = document.createElement('video');
      el.src = a.src; el.playsInline = true; el.crossOrigin = 'anonymous';
      el.loop = o.loop ?? a.loop ?? false;
      el.muted = o.muted ?? false;
      el.volume = Math.max(0, Math.min(1, (o.volume ?? a.volume ?? 1) * (this.audio ? this.audio.master : 1) * (this.audio && this.audio.muted ? 0 : 1)));
      el.playbackRate = o.rate ?? Proto.time.speed;
      return el;
    }

    setBgVideo(assetId, o = {}) {
      if (!assetId) return this.clearBgVideo();
      if (this.bgVideoId === assetId && this.bgVideo) return this.bgVideo;
      this.clearBgVideo();
      this.bgVideoId = assetId;
      const a = this.assets && this.assets.videos[assetId];
      if (!a || !a.ok) return null;
      const el = this.videoEl(a, { loop: o.loop !== false, muted: o.muted !== false, rate: o.rate ?? 1, volume: o.volume });
      el.dataset.protoBg = '1';
      const sp = new PIXI.Sprite(PIXI.Texture.from(el));
      sp.__base = { w: el.videoWidth || this.width, h: el.videoHeight || this.height };
      el.addEventListener('loadedmetadata', () => { sp.__base = { w: el.videoWidth, h: el.videoHeight }; this.place(sp, { full: true, fit: o.fit || 'cover', opacity: o.opacity }); });
      this.place(sp, { full: true, fit: o.fit || 'cover', opacity: o.opacity });
      this.layers.video.addChild(sp);
      this.animateIn(sp, { fadeIn: o.fadeIn });
      this.videos.add(el);
      this.bgVideo = sp; this.bgVideoEl = el;
      el.play().catch(() => {});
      return sp;
    }

    clearBgVideo(fadeOut = 0) {
      const sp = this.bgVideo, el = this.bgVideoEl;
      this.bgVideoId = null; this.bgVideo = null; this.bgVideoEl = null;
      if (!sp) return null;
      this.videos.delete(el); el.pause();
      this.destroyLater(sp, fadeOut);
      return null;
    }

    destroyLater(obj, fadeOut) {
      Proto.tween.kill(obj);
      if (fadeOut > 0 && !Proto.time.skip) Proto.tween(obj, { alpha: 0 }, fadeOut, { ease: 'linear' }).then(() => obj.destroy({ children: true }));
      else obj.destroy({ children: true });
    }

    remove(key, fadeOut = 0) {
      const obj = this.items.get(key);
      if (!obj) return;
      this.items.delete(key);
      if (obj.destroyed) return;
      this.destroyLater(obj, fadeOut);
    }

    clear(layer) {
      for (const [key, obj] of [...this.items]) if (!layer || layer === 'all' || obj.parent === this.layers[layer]) this.remove(key);
    }

    flash(colorV = '#fff', duration = 0.25) {
      if (Proto.time.skip) return;
      const g = new PIXI.Graphics().rect(0, 0, this.width, this.height).fill({ color: color(colorV) });
      this.layers.overlay.addChild(g);
      Proto.tween(g, { alpha: 0 }, duration, { ease: 'outQuad' }).then(() => g.destroy());
    }

    shake(duration = 0.5, power = 12) {
      if (Proto.time.skip) return;
      if (this.offShake) this.offShake();
      let left = duration;
      const s = this.shaker;
      this.offShake = Proto.every((dt) => {
        left -= dt;
        if (left <= 0) { s.position.set(0, 0); this.offShake(); this.offShake = null; return; }
        const k = power * Math.min(1, left / Math.max(0.05, duration) + 0.3);
        s.position.set((Math.random() * 2 - 1) * k, (Math.random() * 2 - 1) * k);   // 純演出亂數
      });
    }

    refresh() {
      for (const v of this.videos) {
        if (!v.dataset.protoBg) v.playbackRate = Proto.time.speed;
        if (Proto.time.paused) v.pause(); else if (v.paused && !v.ended) v.play().catch(() => {});
      }
    }
  }

  Proto.Stage = Stage;
  Proto.pixiColor = color;
})();
