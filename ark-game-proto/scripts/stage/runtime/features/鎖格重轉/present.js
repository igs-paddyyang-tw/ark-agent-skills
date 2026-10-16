// ============================================================
//  [ark-game-proto stage] 玩法：鎖格重轉 — Pixi Presenter（features['鎖格重轉'].Stage）
//  只讀劇本（SpinResult.feature.script = logic.play(record:true)）：
//    start: [{ idx, face }]、hands: [{ left, landed: { idx: face }, reset }]、faces、hits、full、fullMult
//  格位 idx = row × reels + reel；面額 = values[face].v × multiplyFactor ^ hits（× 總押注）
//  遊戲包可設 spec.feature.present = { images: { coin, empty, jackpot: {…} }, valueColors: [[min,'#色'],…], sounds: { land, reset, full, tick }, perfs: { start, end } }
// ============================================================
(function () {
  'use strict';
  const Proto = window.Proto;

  class HoldWinStage {
    constructor(mod, fp) {
      this.mod = mod;
      this.fp = fp;
      this.pf = (mod.p.feature && mod.p.feature.present) || {};
      this.root = null;
    }

    build() {
      const mod = this.mod, v = mod.view, fp = this.fp;
      this.root = new PIXI.Container();
      this.root.position.set(v.box.x, v.box.y);
      mod.stage.layer('reels').addChild(this.root);
      this.root.addChild(new PIXI.Graphics().roundRect(-8, -8, v.box.w + 16, v.box.h + 16, 20).fill({ color: 0x07050f, alpha: 0.92 }));
      this.cells = [];
      for (let i = 0; i < fp.cells; i++) {
        const r = i % fp.reels, row = Math.floor(i / fp.reels);
        const c = new PIXI.Container();
        c.position.set(v.colX[r] + v.cellW / 2, (row + 0.5) * v.cellH);
        this.root.addChild(c);
        this.cells.push(c);
      }
      this.faces = new Array(fp.cells).fill(-1);
      this.hits = new Array(fp.cells).fill(0);
      this.left = 0;
      const st = mod.stage;
      this.hudText = new PIXI.Text({ text: '', style: { fontFamily: "'Arial Black','Microsoft JhengHei',sans-serif", fontSize: 46, fill: '#ffe57f', fontWeight: '900', stroke: { color: '#000', width: 6 } } });
      this.hudText.anchor.set(0.5, 1);
      this.hudText.position.set(v.box.x + v.box.w / 2, v.box.y - 20);
      st.layer('ui').addChild(this.hudText);
    }

    valueOf(i) { const f = this.faces[i]; return f < 0 ? 0 : this.fp.values[f].v * Math.pow(this.fp.multiplyFactor, this.hits[i]); }
    colorOf(v) { for (const [min, c] of this.pf.valueColors || [[50, '#FF5C6E'], [10, '#D48CFF'], [0, '#FFE57F']]) if (v >= min) return c; return '#fff'; }
    total() { let s = 0; for (let i = 0; i < this.faces.length; i++) s += this.valueOf(i); return s; }

    paint(i) {
      const c = this.cells[i], v = this.mod.view, I = this.pf.images || {};
      c.removeChildren().forEach((o) => o.destroy());
      const w = v.cellW - 14, hh = v.cellH - 14;
      if (this.faces[i] < 0) {
        const t = I.empty && this.mod.stage.texture(I.empty);
        if (t) { const s = new PIXI.Sprite(t); s.anchor.set(0.5); s.width = w; s.height = hh; c.addChild(s); }
        else c.addChild(new PIXI.Graphics().roundRect(-w / 2, -hh / 2, w, hh, 18).fill({ color: 0x1a1430 }).stroke({ width: 3, color: 0x3c3366 }));
        return;
      }
      const face = this.fp.values[this.faces[i]];
      const t = I.coin && this.mod.stage.texture(I.coin);
      if (t) { const s = new PIXI.Sprite(t); s.anchor.set(0.5); const k = Math.min(w / t.width, hh / t.height); s.scale.set(k); c.addChild(s); }
      else c.addChild(new PIXI.Graphics().circle(0, 0, Math.min(w, hh) / 2).fill({ color: 0xffb300 }).stroke({ width: 6, color: 0xfff3b0 }));
      const val = this.valueOf(i);
      const label = face.jackpot ? String(face.name || face.jackpot) : Proto.fmt.short(val * (this.pf.showCredits === false ? 1 : this.mod.bet));
      const tx = new PIXI.Text({ text: label, style: { fontFamily: "'Arial Black',sans-serif", fontSize: Math.min(w, hh) * (label.length > 4 ? 0.24 : 0.32), fill: this.colorOf(val), fontWeight: '900', stroke: { color: '#2a1300', width: 6, join: 'round' } } });
      tx.anchor.set(0.5);
      c.addChild(tx);
      if (this.hits[i]) { const m = new PIXI.Text({ text: `×${Math.pow(this.fp.multiplyFactor, this.hits[i])}`, style: { fontSize: 30, fill: '#fff', fontWeight: '900', stroke: { color: '#000', width: 4 } } }); m.anchor.set(1, 1); m.position.set(w / 2, hh / 2); c.addChild(m); }
    }
    paintAll() { for (let i = 0; i < this.cells.length; i++) this.paint(i); }
    hud() { this.hudText.text = `剩餘 ${this.left} 手　${this.faces.filter((f) => f >= 0).length}/${this.fp.cells}　${Proto.fmt.money(this.total() * this.mod.bet)}`; }
    snd(k) { const id = (this.pf.sounds || {})[k]; return id ? this.mod.playSound(id) : null; }
    perf(k, ctx) { const n = (this.pf.perfs || {})[k]; return n ? this.mod.app.timeline.play(n, ctx) : Promise.resolve(); }
    async pop(i) { const c = this.cells[i]; c.scale.set(0.2); await Proto.tween(c.scale, { x: 1, y: 1 }, 0.32 * this.mod.tf(), { ease: 'outBack' }); }

    // 一手：空格依軸逐列閃動，停入的格在該軸停下時才畫上
    async spinEmpties(landed) {
      const fp = this.fp, k = this.mod.tf();
      const empties = this.cells.map((c, i) => i).filter((i) => this.faces[i] < 0);
      const stops = [];
      for (const i of empties) { const c = this.cells[i]; c.alpha = 1; stops.push(Proto.tween.loop(c, { alpha: 0.45 }, 0.09)); }
      for (let r = 0; r < fp.reels; r++) {
        await Proto.wait(0.16 * k);
        for (const i of empties) if (i % fp.reels === r && landed[i] !== undefined) {
          this.faces[i] = landed[i];
          this.paint(i);
          this.pop(i);
          this.snd('land');
        }
      }
      stops.forEach((s) => s());
      for (const i of empties) this.cells[i].alpha = 1;
    }

    async run(res, draw, ctx) {
      const mod = this.mod, k = mod.tf();
      if (!this.root) this.build();
      this.root.visible = true; this.hudText.visible = true;
      this.faces.fill(-1); this.hits.fill(0);
      this.paintAll();
      this.left = draw.spins;
      this.hud();
      await this.perf('start', ctx);
      for (const s of res.start || []) { this.faces[s.idx] = s.face; this.paint(s.idx); this.pop(s.idx); await Proto.wait(0.08 * k); }
      this.hud();
      await Proto.wait(0.5 * k);
      for (const hd of res.hands || []) {
        await mod.waitSpinPress();
        this.left = Math.max(0, this.left - 1);
        this.hud();
        await this.spinEmpties(hd.landed || {});
        if (hd.reset) { this.left = hd.left; this.snd('reset'); mod.stage.flash('#ffe57f', 0.2); }
        else this.left = hd.left;
        this.hud();
        await Proto.wait(0.25 * k);
      }
      if (res.full) {
        this.snd('full');
        mod.stage.showText('hw-full', `FULL BOARD${res.fullMult ? `  ×${res.fullMult}` : ''}`, { layer: 'overlay', size: 110, color: '#ffe14a', anim: 'pop', y: mod.stage.height * 0.4 });
        await Proto.wait(1.4 * k);
        mod.stage.remove('hw-full', 0.3);
      }
      // 逐格累計
      let acc = 0;
      const order = this.cells.map((c, i) => i).filter((i) => this.faces[i] >= 0);
      for (const i of order) {
        acc += this.valueOf(i);
        Proto.tween(this.cells[i].scale, { x: 1.18, y: 1.18 }, 0.08, { yoyo: true, repeat: 1 });
        this.hudText.text = `合計 ${Proto.fmt.money(Math.round(acc * mod.bet))}`;
        this.snd('tick');
        await Proto.wait(0.07 * k);
      }
      await this.perf('end', ctx);
      await Proto.wait(0.6 * k);
    }

    exit() { if (this.root) { this.root.visible = false; this.hudText.visible = false; } }
    references() { const I = this.pf.images || {}; return { images: [I.coin, I.empty, ...Object.values(I.jackpot || {})].filter(Boolean), sounds: Object.values(this.pf.sounds || {}), perfs: Object.values(this.pf.perfs || {}) }; }
  }

  Proto.features['鎖格重轉'].Stage = HoldWinStage;
})();
