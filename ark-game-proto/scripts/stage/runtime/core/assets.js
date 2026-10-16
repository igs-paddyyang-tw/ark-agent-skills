// ============================================================
//  [ark-game-proto stage] 素材載入（CMP-103）
//  清單格式與 Proto 試玩模板相同：
//    images: { 代號: '路徑' }；videos / sounds: { 代號: '路徑' 或 { src, loop, volume, channel } }
//  圖片：HTMLImageElement 載入 → PIXI.Texture.from(img)（a.tex）；保留 a.el 給 DOM 疊層（INFO、除錯）用
//  缺檔：記在 missing，演出時改用佔位；不中斷遊戲
//  熱替換：swap(id, url) → 發 'asset-swap' 事件（持有該 id 的 Sprite 會換貼圖，DD-008）
//  file:// 開非內嵌版：WebGL 無法讀本機圖檔（跨來源）→ fileProtocolBlocked = true，由 app 顯示指引（ADR-006）
// ============================================================
(function () {
  'use strict';
  const Proto = window.Proto;
  const normalize = (e) => (typeof e === 'string' ? { src: e } : { ...e });
  const isData = (s) => /^(data:|blob:)/.test(String(s));

  class Assets {
    constructor(manifest = {}, events) {
      this.events = events;
      this.images = {}; this.videos = {}; this.sounds = {};
      for (const [id, e] of Object.entries(manifest.images || {})) this.images[id] = { id, kind: 'image', ...normalize(e), ok: false };
      for (const [id, e] of Object.entries(manifest.videos || {})) this.videos[id] = { id, kind: 'video', ...normalize(e), ok: false };
      for (const [id, e] of Object.entries(manifest.sounds || {})) this.sounds[id] = { id, kind: 'sound', channel: 'se', ...normalize(e), ok: false };
      // window.__STAGE_INLINE：stage_build --inline-assets 產出的 { 原路徑: data URI }
      const inl = (typeof window !== 'undefined' && window.__STAGE_INLINE) || null;
      if (inl) for (const a of this.all()) if (inl[a.src]) a.src = inl[a.src];
      this.fileProtocolBlocked = typeof location !== 'undefined' && location.protocol === 'file:' && Object.values(this.images).some((a) => !isData(a.src));
    }
    all() { return [...Object.values(this.images), ...Object.values(this.videos), ...Object.values(this.sounds)]; }
    missing() { return this.all().filter((a) => !a.ok); }

    async load(onProgress) {
      const list = this.all();
      let done = 0;
      const tick = () => onProgress && onProgress(++done, list.length);
      const queue = list.slice();
      const worker = async () => {
        while (queue.length) {
          const a = queue.shift();
          try { if (a.kind === 'image') await this.loadImage(a); else await this.loadMedia(a); } catch (e) { a.ok = false; a.error = String(e && e.message || e); }
          tick();
        }
      };
      await Promise.all(Array.from({ length: 6 }, worker));
      if (!list.length && onProgress) onProgress(0, 0);
    }

    loadImage(a) {
      return new Promise((resolve) => {
        const img = new Image();
        if (!isData(a.src) && !/^file:/.test(location.href)) img.crossOrigin = 'anonymous';
        img.onload = () => {
          try {
            if (a.tex && a.tex.destroy) { /* 舊貼圖由持有者換掉後回收 */ }
            a.tex = PIXI.Texture.from(img);
            a.ok = true; a.el = img; a.width = img.naturalWidth; a.height = img.naturalHeight;
          } catch (e) { a.ok = false; a.error = 'WebGL 無法使用此圖（file:// 跨來源？）'; }
          resolve();
        };
        img.onerror = () => { a.ok = false; resolve(); };
        img.src = a.src;
      });
    }

    loadMedia(a) {
      return new Promise((resolve) => {
        const el = document.createElement(a.kind === 'video' ? 'video' : 'audio');
        let settled = false;
        const finish = (ok) => { if (settled) return; settled = true; a.ok = ok; if (ok && Number.isFinite(el.duration)) a.duration = el.duration; resolve(); };
        el.preload = 'metadata';
        el.onloadedmetadata = () => finish(true);
        el.onerror = () => finish(false);
        setTimeout(() => finish(!el.error && el.readyState > 0), 8000);
        el.src = a.src;
      });
    }

    async swap(id, url, label) {
      const a = this.images[id];
      if (!a) return false;
      if (!a.origSrc) a.origSrc = a.src;
      a.src = url; a.replacedBy = label || url;
      await this.loadImage(a);
      if (this.events) this.events.emit('asset-swap', [id]);
      return a.ok;
    }
  }

  Proto.Assets = Assets;
})();
