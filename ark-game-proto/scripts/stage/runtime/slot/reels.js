// ============================================================
//  [ark-game-proto stage] ReelView（CMP-105 / DD-002）
//  每軸一條「帶面」：固定 rows + 2 個 Sprite 循環重用，以 offset（格）捲動；遮罩裁成盤面窗。
//  停輪：把結果盤面寫進帶面前方 → offset 以 outBack 補間落到目標（過衝 = 真機回彈）。
//  起轉不等結果（DD-001）：spinStart() 立刻轉，land(grid) 收到 SpinResult 才排停輪。
//  填充符號只用演出亂數（mod.fx），不影響結果。
//  版面：layout.reels = { x, y, w, h, cellW, colX:[各軸左緣偏移], cellH? }（舞台像素，左上角）
// ============================================================
(function () {
  'use strict';
  const Proto = window.Proto;

  class ReelView {
    constructor(mod) {
      this.mod = mod;
      this.stage = mod.app.stage;
      const L = mod.layout.reels || {};
      this.reels = mod.p.reels;
      this.rows = mod.p.rows;
      this.box = { x: L.x ?? 40, y: L.y ?? 700, w: L.w ?? 1000, h: L.h ?? 600 };
      this.cellH = L.cellH ?? this.box.h / this.rows;
      this.cellW = L.cellW ?? this.box.w / this.reels;
      this.colX = L.colX || Array.from({ length: this.reels }, (_, r) => (r * this.box.w) / this.reels);
      this.ids = mod.p.ids.filter((id) => !(mod.p.symbols[id] || {}).noFill);
      this.fillIds = this.ids.filter((id) => !mod.p.symbols[id].scatter && !mod.p.symbols[id].noReel);
      this.tex = new Map();
      this.root = new PIXI.Container();
      this.root.label = 'reels';
      this.root.position.set(this.box.x, this.box.y);
      this.stage.layer('reels').addChild(this.root);
      const mask = new PIXI.Graphics().rect(0, 0, this.box.w, this.box.h).fill(0xffffff);
      this.root.addChild(mask);
      this.strips = new PIXI.Container();
      this.strips.mask = mask;
      this.root.addChild(this.strips);
      this.fxLayer = new PIXI.Container();   // 連線框、聽牌框（不受遮罩）
      this.root.addChild(this.fxLayer);
      this.R = [];
      for (let r = 0; r < this.reels; r++) {
        const c = new PIXI.Container();
        c.x = this.colX[r];
        const blur = new PIXI.BlurFilter({ strength: 0, quality: 2 });
        blur.strengthX = 0; blur.strengthY = 0;
        c.filters = [blur];
        const cells = [];
        for (let i = 0; i < this.rows + 2; i++) { const s = new PIXI.Sprite(PIXI.Texture.EMPTY); s.anchor.set(0.5); s.x = this.cellW / 2; c.addChild(s); cells.push(s); }
        this.strips.addChild(c);
        this.R.push({ c, blur, cells, tape: new Map(), offset: 0, speed: 0, state: 'idle' });
      }
      this.offFrame = Proto.every((dt) => this.frame(dt));
      mod.app.events.on('assets-changed', () => { this.tex.clear(); this.redraw(); });
      mod.app.events.on('asset-swap', () => { this.tex.clear(); this.redraw(); });
    }

    // ---------- 貼圖 ----------
    symTex(id) {
      if (this.tex.has(id)) return this.tex.get(id);
      const sym = this.mod.p.symbols[id] || {};
      let t = this.stage.texture(sym.image || `sym_${id}`);
      if (!t) t = this.placeholderTex(id, sym);
      this.tex.set(id, t);
      return t;
    }
    placeholderTex(id, sym) {
      const w = this.cellW - 12, h = this.cellH - 12;
      const c = new PIXI.Container();
      const col = Proto.pixiColor(sym.color || '#607d8b');
      c.addChild(new PIXI.Graphics().roundRect(0, 0, w, h, 22).fill({ color: col }).stroke({ width: 5, color: 0xffffff, alpha: 0.55 }));
      c.addChild(new PIXI.Graphics().roundRect(8, 8, w - 16, h * 0.45, 16).fill({ color: 0xffffff, alpha: 0.16 }));
      const label = String(sym.name || id);
      const t = new PIXI.Text({ text: label, style: { fontFamily: "'Arial Black','Microsoft JhengHei',sans-serif", fontSize: Math.min(64, (w * 1.4) / Math.max(1, label.length)), fill: '#fff', fontWeight: '900', stroke: { color: '#000', width: 6, join: 'round' } } });
      t.anchor.set(0.5); t.position.set(w / 2, h / 2);
      c.addChild(t);
      const tex = this.stage.renderer.generateTexture({ target: c, resolution: 1 });
      c.destroy({ children: true });
      return tex;
    }
    fitSprite(s, id) {
      const t = this.symTex(id);
      if (s.texture !== t) s.texture = t;
      const sym = this.mod.p.symbols[id] || {};
      const k = Math.min(this.cellW / t.width, this.cellH / t.height) * (sym.scale ?? 0.96);
      s.scale.set(k);
      s.__sym = id;
    }

    // ---------- 帶面 ----------
    tapeAt(R, k) {
      if (!R.tape.has(k)) R.tape.set(k, this.fillIds[Math.floor(this.mod.fx() * this.fillIds.length)]);
      return R.tape.get(k);
    }
    place(R) {
      const base = Math.floor(R.offset) - 1;
      R.cells.forEach((s, i) => {
        const k = base + i;
        this.fitSprite(s, this.tapeAt(R, k));
        s.y = (k - R.offset) * this.cellH + this.cellH / 2;
        s.__k = k;
      });
    }
    redraw() { this.R.forEach((R) => this.place(R)); }

    setGrid(grid) {
      this.R.forEach((R, r) => {
        R.tape.clear();
        R.offset = 0;
        for (let row = 0; row < this.rows; row++) R.tape.set(row, grid[r][row]);
        this.place(R);
      });
      this.grid = grid.map((c) => c.slice());
    }

    frame(dt) {
      for (const R of this.R) {
        if (R.state === 'spin') R.offset -= R.speed * dt;
        if (R.state !== 'idle') {
          this.place(R);
          const b = Math.min(18, Math.abs(R.speed) * 0.9);
          R.blur.strengthY = R.state === 'spin' ? b : 0;
          // 帶面過長時回收（只保留目前附近）
          if (R.tape.size > 400) for (const k of [...R.tape.keys()]) if (k > R.offset + this.rows + 4) R.tape.delete(k);
        }
      }
    }

    feel() {
      const F = { startGap: 0.12, firstLand: 0.9, landGap: 0.23, tug: 0.08, tugAmount: 0.18, accel: 0.18, decel: 0.42, speed: 20, ...(this.mod.pres.reelFeel || {}) };
      const k = this.mod.tf();
      return { ...F, startGap: F.startGap * k, firstLand: F.firstLand * k, landGap: F.landGap * k, accel: F.accel * k, decel: F.decel * (this.mod.state.fast ? 0.7 : 1) };
    }

    // 起轉：先往上拉一點（tug），再加速到全速
    spinStart() {
      const F = this.feel();
      this.spinning = true;
      this.R.forEach((R, r) => {
        Proto.tween.kill(R);
        R.state = 'start';
        const o0 = R.offset;
        const go = async () => {
          if (F.tug > 0) await Proto.tween(R, { offset: o0 + F.tugAmount }, F.tug, { ease: 'outQuad' });
          R.state = 'spin';
          R.speed = 0;
          await Proto.tween(R, { speed: F.speed }, F.accel, { ease: 'inQuad' });
        };
        R.started = Proto.wait(F.startGap * r).then(go);
      });
    }

    // 停輪：grid = [軸][列]；opts.extend = { 軸: 額外秒數 }（聽牌延長，該軸與之後各軸順延）；opts.onTease(r, 秒)、opts.onLand(r)
    async land(grid, opts = {}) {
      const F = this.feel();
      const t0 = Proto.clock.now();
      await Promise.all(this.R.map((R) => R.started));
      const jobs = this.R.map(async (R, r) => {
        let at = F.firstLand + F.landGap * r;
        for (let j = 0; j <= r; j++) at += (opts.extend && opts.extend[j]) || 0;
        const elapsed = () => Proto.clock.now() - t0;
        const ext = (opts.extend && opts.extend[r]) || 0;
        if (ext && opts.onTease) { await Proto.wait(Math.max(0, at - ext - elapsed())); opts.onTease(r, ext); }
        await Proto.wait(Math.max(0, at - elapsed()));
        const target = Math.floor(R.offset) - (this.rows + 2);
        for (let row = 0; row < this.rows; row++) R.tape.set(target + row, grid[r][row]);
        R.state = 'stop';
        const sp = R.speed;
        R.speed = 0;
        const dur = Math.max(F.decel, (R.offset - target) / Math.max(1, sp) * 1.6);
        await Proto.tween(R, { offset: target }, dur, { ease: 'outBack' });
        R.offset = target;
        // 重新編號，讓 offset 回到 0 附近（避免長時間遊玩數值飄移）
        const tape = new Map();
        for (const [k, v] of R.tape) if (k >= target - 2 && k <= target + this.rows + 2) tape.set(k - target, v);
        R.tape = tape; R.offset = 0;
        R.state = 'idle';
        R.blur.strengthY = 0;
        this.place(R);
        if (opts.onLand) opts.onLand(r);
      });
      await Promise.all(jobs);
      this.spinning = false;
      this.grid = grid.map((c) => c.slice());
    }

    // ---------- 給演出用 ----------
    cell(r, row) { const R = this.R[r]; return R ? R.cells.find((s) => s.__k === row) || R.cells[row + 1] : null; }
    cellCenter(r, row) { return { x: this.box.x + this.colX[r] + this.cellW / 2, y: this.box.y + (row + 0.5) * this.cellH }; }
    allCells() { const out = []; for (let r = 0; r < this.reels; r++) for (let row = 0; row < this.rows; row++) out.push([r, row, this.cell(r, row)]); return out; }
    setSymbol(r, row, id) { const R = this.R[r]; R.tape.set(row, id); this.place(R); if (this.grid) this.grid[r][row] = id; }
  }

  Proto.ReelView = ReelView;
})();
