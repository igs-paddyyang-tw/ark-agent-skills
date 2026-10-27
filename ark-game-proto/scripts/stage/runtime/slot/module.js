// ============================================================
//  [ark-game-proto stage] 老虎機模組（Pixi 版，CMP-105 / CMP-108）
//  Flow：按 SPIN → 轉輪立刻起轉 → service.spin() 取得完整 SpinResult（含玩法劇本）→ 依 stops / grid 停輪
//        → afterReels 掛勾 → 連線 / 報獎 → 玩法 Presenter 依劇本播放 → 以 balanceAfter 更新 HUD
//  演出層不呼叫任何數學函式（Proto.slotLogic 只拿來讀 prepare 後的符號 / 賠付表做顯示）
//  與 Proto 試玩模板相容的演出 API（給玩法 Presenter / afterReels 用）：
//    tf() cell(r,row) cellEl(r,row) cellCenter(r,row) playSound(id) setInfoLine(t) symName(id) featureHud(o)
//    waitSpinPress() spinReels(g) showWins(ev) clearWins() countBox(v,dur) winLadder(v) declare(draw) setMode(m)
//    bet stage view tween app pres layout p state fx
//  遊戲包的 Pixi 版演出掛勾放 presentation.stage = { afterReels(mod, g, ev, result), tease(mod, result) }；
//  玩法的 Pixi Presenter 放 Proto.features[type].Stage（class，run(res, draw, ctx, ev, g, result)）
//  舊的 DOM 版 presentation.afterReels / features[type].Present 不會被呼叫（遷移時改寫成 Pixi，見 references/stage-game-pack.md）
// ============================================================
(function () {
  'use strict';
  const Proto = window.Proto;
  const h = (...a) => Proto.h(...a);
  const Logic = () => Proto.slotLogic;

  // CSS 漸層 → 2D canvas 貼圖（decor 的 fill 沿用 Proto 的 CSS 寫法）
  function splitArgs(s) { const out = []; let d = 0, cur = ''; for (const ch of s) { if (ch === '(') d++; if (ch === ')') d--; if (ch === ',' && d === 0) { out.push(cur.trim()); cur = ''; } else cur += ch; } if (cur.trim()) out.push(cur.trim()); return out; }
  function gradientTexture(fill, w, h) {
    const cv = document.createElement('canvas');
    cv.width = Math.max(1, Math.round(w)); cv.height = Math.max(1, Math.round(h));
    const g = cv.getContext('2d');
    const m = String(fill).match(/^(linear|radial)-gradient\((.*)\)$/s);
    if (!m) { g.fillStyle = fill; g.fillRect(0, 0, w, h); return PIXI.Texture.from(cv); }
    const args = splitArgs(m[2]);
    let grad;
    if (m[1] === 'linear') {
      let ang = 180;
      if (/deg$/.test(args[0])) ang = parseFloat(args.shift());
      else if (/^to /.test(args[0])) { const t = args.shift(); ang = { 'to top': 0, 'to right': 90, 'to bottom': 180, 'to left': 270 }[t] ?? 180; }
      const a = ((ang - 90) * Math.PI) / 180, L = Math.abs(w * Math.cos(a)) + Math.abs(h * Math.sin(a));
      const cx = w / 2, cy = h / 2, dx = (Math.cos(a) * L) / 2, dy = (Math.sin(a) * L) / 2;
      grad = g.createLinearGradient(cx - dx, cy - dy, cx + dx, cy + dy);
    } else {
      let px = 0.5, py = 0.5;
      if (/^(circle|ellipse)|at /.test(args[0])) { const at = args.shift().match(/at\s+([\d.]+)%\s+([\d.]+)%/); if (at) { px = at[1] / 100; py = at[2] / 100; } }
      grad = g.createRadialGradient(w * px, h * py, 0, w * px, h * py, Math.max(w, h) * 0.75);
    }
    args.forEach((stop, i) => {
      const mm = stop.match(/^(.*?)(?:\s+([\d.]+)%)?$/);
      const pos = mm[2] !== undefined ? mm[2] / 100 : args.length > 1 ? i / (args.length - 1) : 0;
      try { grad.addColorStop(Math.min(1, Math.max(0, pos)), mm[1].trim()); } catch (e) { /* 忽略無法解析的色票 */ }
    });
    g.fillStyle = grad; g.fillRect(0, 0, w, h);
    return PIXI.Texture.from(cv);
  }

  // SpinResult → Proto 試玩模板的 ev / g / res（讓既有 Presenter 寫法可沿用）
  function toLegacy(r) {
    const ev = { wins: r.base.ways.map((w) => ({ symbol: w.sym, count: w.len, ways: w.ways, line: w.line, x: w.winX, win: w.win, cells: w.cells })), scatter: r.base.scatter, x: r.base.winX, trigger: r.base.trigger, ...(r.base.extra || {}) };
    const g = { mode: r.mode, combo: r.reel.combo, stops: r.reel.stops, grid: r.reel.grid, view: r.reel.view };
    const res = r.feature ? { ...r.feature.script, x: r.feature.winX, capped: r.feature.capped, spinsPlayed: r.feature.spinsPlayed } : null;
    return { ev, g, res, draw: r.feature ? r.feature.draw : null };
  }

  class SlotModule {
    constructor(app) {
      this.app = app;
      this.spec = app.config.spec;
      this.pres = app.config.presentation || {};
      this.layout = app.config.layout || {};
      this.stage = app.stage;
      this.tween = Proto.tween;
      this.p = Logic().prepare(this.spec);            // 只讀：符號、賠付表、盤面尺寸（顯示用）
      const info = app.info || {};
      this.bets = info.bets || this.p.bet.steps;
      this.betIdx = Math.max(0, this.bets.indexOf(info.defaultBet ?? this.p.bet.def));
      this.state = { balance: info.balance ?? 0, bet: this.bets[this.betIdx], busy: false, auto: false, fast: false, mode: 'base', spins: 0, shownWin: 0, history: [] };
      this.fx = app.rng;                              // 演出亂數
      this.winFx = new PIXI.Container();
      this.lastResult = null;
    }
    get bet() { return this.state.bet; }
    tf() { return this.state.fast ? 0.35 : 1; }

    async init() {
      this.buildLayout();
      this.view = new Proto.ReelView(this);
      this.view.fxLayer.addChild(this.winFx);
      this.hud = new Proto.Hud(this);
      this.buildOverlays();
      if (this.app.config.info) this.buildInfo();
      const def = Proto.features[(this.p.feature || {}).type];
      this.featDef = def || null;
      this.present = def && def.Stage ? new def.Stage(this, Logic().feature(this.p) ? Logic().feature(this.p).fp : this.p.feature) : null;
      this.app.events.on('key', (e) => { if (e.code === 'Space' || e.key === ' ') { e.preventDefault(); this.onButton('spin'); } });
      this.app.events.on('service-changed', (info) => { this.state.balance = info.balance ?? this.state.balance; this.renderHud(); });
      this.app.events.on('assets-changed', () => this.refreshArt());
      const grid = Array.from({ length: this.p.reels }, () => Array.from({ length: this.p.rows }, () => this.view.fillIds[Math.floor(this.fx() * this.view.fillIds.length)]));
      this.view.setGrid(grid);
      this.renderHud();
    }

    start() { this.renderHud(); }

    // ---------- 版面 ----------
    buildLayout() {
      const st = this.stage;
      if (this.decor) this.decor.forEach((o) => o.destroy({ children: true }));
      this.decor = [];
      const bgId = (this.layout.background || {}).image;
      if (bgId) { const t = st.texture(bgId); if (t) { const s = new PIXI.Sprite(t); st.place(s, { full: true, fit: 'cover' }); st.layer('bg').addChild(s); this.decor.push(s); } }
      for (const d of this.layout.decor || []) {
        let o = null;
        if (d.image) { const t = st.texture(d.image); o = t ? new PIXI.Sprite(t) : null; if (o) { o.width = d.w; o.height = d.h; } }
        else if (d.fill) { o = new PIXI.Sprite(gradientTexture(d.fill, d.w, d.h)); }
        if (!o) continue;
        o.position.set(d.x || 0, d.y || 0);
        o.__modes = d.modes || null;
        o.label = d.label || '';
        st.layer(d.layer || 'main').addChild(o);
        this.decor.push(o);
      }
      this.jp = [];
      for (const j of this.layout.jackpots || []) {
        const c = new PIXI.Container();
        c.position.set(j.x, j.y);
        c.addChild(new PIXI.Graphics().roundRect(0, 0, j.w, j.h, 14).fill({ color: 0x000000, alpha: 0.55 }).stroke({ width: 3, color: Proto.pixiColor(j.color || '#ffd24a') }));
        const lab = new PIXI.Text({ text: j.label, style: { fontFamily: "'Arial Black',sans-serif", fontSize: Math.round((j.size || 34) * 0.55), fill: j.color || '#ffd24a', fontWeight: '900' } });
        lab.anchor.set(0.5, 0); lab.position.set(j.w / 2, 4);
        const val = new PIXI.Text({ text: '', style: { fontFamily: "'Arial Black',sans-serif", fontSize: j.size || 34, fill: '#ffffff', fontWeight: '900', stroke: { color: '#000', width: 4 } } });
        val.anchor.set(0.5, 1); val.position.set(j.w / 2, j.h - 4);
        c.addChild(lab, val);
        st.layer('main').addChild(c);
        this.jp.push({ j, val, c });
        this.decor.push(c);
      }
      this.updateJackpots();
      this.setMode(this.state.mode, { quiet: true });
    }
    updateJackpots() { for (const { j, val } of this.jp || []) { val.text = Proto.fmt.money(Math.round((j.mult || 0) * this.bet)); const mw = j.w - 16; val.scale.set(1); if (val.width > mw) val.scale.set(mw / val.width); } }
    refreshArt() { this.buildLayout(); this.view.tex.clear(); this.view.redraw(); }

    setMode(mode, { quiet } = {}) {
      this.state.mode = mode;
      for (const o of this.decor || []) if (o.__modes) o.visible = o.__modes.includes(mode === 'fs' ? 'fs' : 'base');
      if (!quiet) this.app.events.emit('mode', mode);
    }

    buildOverlays() {
      this.busyEl = h('div', { class: 'stage-busy', hidden: true }, '連線中…');
      this.stage.dom.appendChild(this.busyEl);
    }

    // ---------- HUD ----------
    renderHud() { this.hud.render({ ...this.state, bet: this.bet }); this.updateJackpots(); }
    setInfoLine(t) { this.hud.setInfo(t); }
    flashMessage(t) { this.setInfoLine(t); }
    symName(id) { return (this.p.symbols[id] || {}).name || id; }
    playSound(id) { return id ? this.app.audio.play(id) : null; }
    featureHud(o) { this.setInfoLine(`剩餘 ${o.left ?? '—'} 手｜累計 ${Proto.fmt.money(Math.round((o.total || 0) * this.bet))}`); }

    onButton(key) {
      const st = this.state;
      if (key === 'spin') { if (st.auto && st.busy) { st.auto = false; this.renderHud(); return; } if (this.pressResolve) { const r = this.pressResolve; this.pressResolve = null; r(); return; } this.spin(); return; }
      if (key === 'auto') { st.auto = !st.auto; this.renderHud(); if (st.auto && !st.busy) this.spin(); return; }
      if (key === 'fast') { st.fast = !st.fast; this.playSound((this.pres.sounds || {})[st.fast ? 'fastOn' : 'fastOff']); this.renderHud(); return; }
      if (key === 'info' || key === 'menu') { this.openInfo(); return; }
      if (st.busy) return;
      if (key === 'betUp') this.betIdx = Math.min(this.bets.length - 1, this.betIdx + 1);
      if (key === 'betDown') this.betIdx = Math.max(0, this.betIdx - 1);
      if (key === 'maxBet') this.betIdx = this.bets.length - 1;
      st.bet = this.bets[this.betIdx];
      this.renderHud();
    }

    // 玩法中「按一下轉下一手」：自動 / 跳過 / 快速 → 短暫停頓後自動繼續
    waitSpinPress() {
      if (this.state.auto || Proto.time.skip || this.pres.featureAutoSpin !== false) return Proto.wait(0.35 * this.tf());
      return new Promise((r) => { this.pressResolve = r; });
    }

    // ---------- 一局 ----------
    async spin() {
      const st = this.state;
      if (st.busy) return;
      if (st.balance < this.bet) { this.flashMessage('餘額不足'); st.auto = false; this.renderHud(); return; }
      st.busy = true;
      this.clearWins();
      st.shownWin = 0;
      st.balance -= this.bet;                          // 顯示用；結束時以 balanceAfter 校正
      this.renderHud();
      this.setInfoLine('');
      this.playSound((this.pres.sounds || {}).spin);
      this.view.spinStart();
      let result = null;
      const slow = setTimeout(() => (this.busyEl.hidden = false), 3000);
      try {
        result = await this.app.service.spin({ bet: this.bet });
      } catch (e) {
        clearTimeout(slow); this.busyEl.hidden = true;
        await this.view.land(this.view.grid);
        st.balance += this.bet;
        this.flashMessage(`無法取得結果：${e.code || ''} ${e.message || e}`);
        st.busy = false; st.auto = false; this.renderHud();
        return;
      }
      clearTimeout(slow); this.busyEl.hidden = true;
      const errs = Proto.stageResult.validate(result);
      if (errs.length) {
        await this.view.land(this.view.grid);
        st.balance = result && Number.isInteger(result.balanceBefore) ? result.balanceBefore : st.balance + this.bet;
        this.flashMessage(`結果格式錯誤（不播放）：${errs[0]}`);
        console.error('SpinResult 驗證失敗', errs, result);
        st.busy = false; st.auto = false; this.renderHud();
        return;
      }
      try { await this.play(result); } catch (e) { if (!e || !e.cancelled) console.error(e); }
      st.balance = result.balanceAfter;                 // 權威值
      st.busy = false;
      this.renderHud();
      if (this.app.service.ack) this.app.service.ack(result.roundId);   // 演完確認（Http／Ws；失敗不擋，下次 init 會再帶 pending）
      if (st.auto) setTimeout(() => st.auto && !st.busy && this.spin(), 350 / (Proto.time.speed || 1));
    }

    // 播放一份 SpinResult（Replay / Http / Local 都走這裡）
    async play(result) {
      const st = this.state, app = this.app;
      st.spins++;
      this.lastResult = result;
      const { ev, g, res, draw } = toLegacy(result);
      // 演出事件（present-events/1，1.5.0）：兩軌（Stage／正式 Client）同一份結果的事件序列必須相同；值只取自 SpinResult
      const pe = (type, data) => app.events.emit('present', { type, roundId: result.roundId, ...data });
      pe('round-start', { bet: result.bet });
      app.timeline.record('label', `局 ${result.roundId}｜停輪 ${result.reel.stops.join(',')}｜贏 ${result.totalWin}（${Proto.fmt.num(result.totalX, 2)}×）`);
      const ctx = { win: result.base.win, winX: result.base.winX, trigger: result.base.trigger, total: result.totalWin };
      if (this.pres.spin) app.timeline.play(this.pres.spin, ctx);
      const S = this.pres.stage || {};
      const extend = S.tease ? S.tease(this, result, ev) : this.defaultTease(result);
      await this.view.land(result.reel.grid, {
        extend,
        onTease: (r, sec) => this.showTenpai(r, sec),
        onLand: (r) => { this.playSound((this.pres.sounds || {}).reelStop); if (extend && extend[r]) this.hideTenpai(); },
      });
      pe('reels-stop', { stops: result.reel.stops.slice() });
      if (S.afterReels) await S.afterReels(this, g, ev, result);
      if (result.base.win > 0) {
        pe('base-win', { win: result.base.win, ways: result.base.ways.length });
        await this.showWins(ev);
        if (this.pres.smallWin) app.timeline.play(this.pres.smallWin, ctx);
        if (this.reachesLadder(result.base.winX)) await this.winLadder(result.base.win);
        else await this.countBox(result.base.win, 0.5);
      }
      if (result.feature) {
        pe('feature-start', { feature: result.feature.type, spinsPlayed: result.feature.spinsPlayed });
        await this.runFeature(result, ev, g, res, draw, ctx);
        pe('feature-end', { win: result.feature.win });
      }
      pe('round-end', { totalWin: result.totalWin, balanceAfter: result.balanceAfter });
      st.history.unshift({ round: result.roundId, stops: result.reel.stops.join(','), win: result.totalWin, x: result.totalX, feat: result.feature ? result.feature.type : '' });
      if (st.history.length > 200) st.history.pop();
    }

    // 預設聽牌：Scatter 型觸發，前面各軸湊到「差一顆」→ 後面各軸各延長
    defaultTease(result) {
      const p = this.p;
      if (!p.scatter || !p.trigger) return null;
      const ext = {};
      let n = 0;
      for (let r = 0; r < p.reels; r++) {
        if (n >= p.trigger - 1 && p.scReels.includes(r)) ext[r] = (this.pres.teaseTime ?? 1.4) * this.tf();
        n += result.reel.grid[r].filter((s) => s === p.scatter).length;
      }
      return Object.keys(ext).length ? ext : null;
    }
    showTenpai(r, sec) {
      this.hideTenpai();
      const v = this.view;
      const g = new PIXI.Graphics().roundRect(v.colX[r] - 4, -4, v.cellW + 8, v.box.h + 8, 18).stroke({ width: 10, color: 0xffe14a });
      v.fxLayer.addChild(g);
      this.tenpai = g;
      this.tenpaiStop = Proto.tween.loop(g, { alpha: 0.25 }, 0.18);
      if (this.pres.sounds && this.pres.sounds.tease) this.playSound(this.pres.sounds.tease);
    }
    hideTenpai() { if (this.tenpaiStop) this.tenpaiStop(); if (this.tenpai) this.tenpai.destroy(); this.tenpai = null; this.tenpaiStop = null; }

    // ---------- 連線 ----------
    clearWins() {
      if (this.cycleStop) this.cycleStop();
      this.cycleStop = null;
      for (const s of this.pulses || []) s();
      this.pulses = [];
      this.winFx.removeChildren().forEach((c) => c.destroy());
      for (const [, , s] of this.view.allCells()) if (s) { s.alpha = 1; s.tint = 0xffffff; }
    }
    highlight(cells, dim = true) {
      const v = this.view;
      const on = new Set(cells.map(([r, row]) => `${r},${row}`));
      for (const [r, row, s] of v.allCells()) if (s) s.alpha = !dim || on.has(`${r},${row}`) ? 1 : 0.32;
      this.winFx.removeChildren().forEach((c) => c.destroy());
      for (const [r, row] of cells) {
        const g = new PIXI.Graphics().roundRect(v.colX[r] + 4, row * v.cellH + 4, v.cellW - 8, v.cellH - 8, 16).stroke({ width: 6, color: 0xffe57f });
        this.winFx.addChild(g);
      }
    }
    async showWins(ev, { cycle = true } = {}) {
      const all = [];
      for (const w of ev.wins || []) for (const c of w.cells || []) all.push(c);
      if (ev.scatter && ev.scatter.x > 0) for (const c of ev.scatter.cells || []) all.push(c);
      if (!all.length) return;
      this.highlight(all);
      for (const [r, row] of all) {
        const s = this.view.cell(r, row);
        if (s) { const k = s.scale.x; this.pulses.push(Proto.tween.loop(s, { 'scale.x': k * 1.08, 'scale.y': k * 1.08 }, 0.32 * this.tf(), { ease: 'sine' })); }
      }
      const top = (ev.wins || []).slice().sort((a, b) => b.x - a.x)[0];
      if (top) this.setInfoLine(`${top.count} ${this.symName(top.symbol)}${top.ways > 1 ? ` × ${top.ways} ways` : ''} ＝ ${Proto.fmt.money(top.win ?? Math.floor(top.x * this.bet))}`);
      await Proto.wait(0.6 * this.tf());
      if (cycle && (ev.wins || []).length > 1) this.cycleLines(ev.wins);
    }
    cycleLines(list) {
      let alive = true;
      this.cycleStop = () => { alive = false; };
      (async () => {
        for (let round = 0; round < 3 && alive; round++) {
          for (const w of list) {
            if (!alive) return;
            this.highlight(w.cells || []);
            this.setInfoLine(`${w.count} ${this.symName(w.symbol)}${w.ways > 1 ? ` × ${w.ways} ways` : ''} ＝ ${Proto.fmt.money(w.win ?? Math.floor(w.x * this.bet))}`);
            await Proto.wait(0.65);
          }
        }
      })();
    }

    async countBox(target, dur = 0.5) {
      const st = this.state;
      const o = { v: st.shownWin || 0 };
      await Proto.tween(o, { v: target }, dur * this.tf(), { ease: 'outQuad', onUpdate: () => { st.shownWin = Math.round(o.v); this.hud.setText(this.hud.fields.win, Proto.fmt.money(st.shownWin)); } });
      st.shownWin = target;
      this.renderHud();
    }

    reachesLadder(x) {
      const W = this.pres.winTiers;
      if (Array.isArray(W)) return W.some((t) => x >= (t.min ?? 0) && (t.min ?? 0) > 0);
      return !!(W && W.tiers && W.tiers.some((t) => x >= t.min));
    }

    // 報獎階梯：計數越過門檻就換下一階（BIG → MEGA → SUPER …）
    async winLadder(amount) {
      const W = this.pres.winTiers || {};
      const tiers = (Array.isArray(W) ? W : W.tiers || []).filter((t) => t.min > 0).sort((a, b) => a.min - b.min);
      const st = this.stage;
      const x = amount / this.bet;
      const reach = tiers.filter((t) => x >= t.min);
      if (!reach.length) return this.countBox(amount, 0.5);
      const S = W.sounds || {};
      this.playSound(S.start);
      const ov = new PIXI.Container();
      ov.addChild(new PIXI.Graphics().rect(0, 0, st.width, st.height).fill({ color: 0x000000, alpha: 0.6 }));
      const title = new PIXI.Text({ text: reach[0].name, style: { fontFamily: "'Arial Black',sans-serif", fontSize: 140, fill: '#ffd24a', fontWeight: '900', stroke: { color: '#5a1a00', width: 12, join: 'round' }, dropShadow: { color: '#000', blur: 10, distance: 6, alpha: 0.7 } } });
      title.anchor.set(0.5); title.position.set(st.width / 2, st.height * 0.42);
      const N = W.number || {};
      const num = new PIXI.Text({ text: '0', style: { fontFamily: "'Arial Black',sans-serif", fontSize: N.size || 110, fill: N.color || '#ffe9b0', fontWeight: '900', stroke: { color: '#000', width: 10, join: 'round' } } });
      num.anchor.set(0.5); num.position.set(st.width / 2, st.height * (N.y || 0.56));
      ov.addChild(title, num);
      st.layer('overlay').addChild(ov);
      ov.alpha = 0;
      await Proto.tween(ov, { alpha: 1 }, (W.fade ?? 0.35) * this.tf());
      title.scale.set(0.3); Proto.tween(title.scale, { x: 1, y: 1 }, 0.35, { ease: 'outBack' });
      const per = (W.dwell ?? 2.2) * this.tf();
      let idx = 0;
      const o = { v: 0 };
      await Proto.tween(o, { v: amount }, per * reach.length, {
        ease: 'linear',
        onUpdate: () => {
          num.text = Proto.fmt.money(Math.round(o.v));
          while (idx + 1 < reach.length && o.v / this.bet >= reach[idx + 1].min) {
            idx++;
            title.text = reach[idx].name;
            title.scale.set(1.4); Proto.tween(title.scale, { x: 1, y: 1 }, (W.swap ?? 0.4), { ease: 'outBack' });
            this.stage.flash('#fff', 0.2);
          }
        },
      });
      num.text = Proto.fmt.money(amount);
      this.playSound(S.end);
      await Proto.wait((W.end ?? 1.6) * this.tf());
      await Proto.tween(ov, { alpha: 0 }, (W.fade ?? 0.35) * this.tf());
      ov.destroy({ children: true });
      this.state.shownWin = (this.state.shownWin || 0) + 0;
      await this.countBox(Math.max(amount, this.state.shownWin), 0.2);
    }

    // ---------- 玩法 ----------
    // 宣告面板：與 Proto 試玩模板相同，presentation.declare 有設定才顯示（{ hold }；玩法自己有標題的就不要設）
    async declare(draw) {
      const D = this.pres.declare;
      if (!D) return;
      const st = this.stage;
      const name = (draw && draw.group !== undefined ? draw.group : null) || (this.featDef && this.p.feature.type) || 'FEATURE';
      const box = new PIXI.Container();
      box.addChild(new PIXI.Graphics().rect(0, 0, st.width, st.height).fill({ color: 0x000000, alpha: 0.55 }));
      const t = new PIXI.Text({ text: String(name), style: { fontFamily: "'Arial Black','Microsoft JhengHei',sans-serif", fontSize: 110, fill: '#ffe14a', fontWeight: '900', stroke: { color: '#3a0a00', width: 12, join: 'round' }, align: 'center', wordWrap: true, wordWrapWidth: st.width - 120 } });
      t.anchor.set(0.5); t.position.set(st.width / 2, st.height * 0.44);
      box.addChild(t);
      if (draw && draw.spins) { const s = new PIXI.Text({ text: `${draw.spins} SPINS`, style: { fontFamily: "'Arial Black',sans-serif", fontSize: 72, fill: '#fff', fontWeight: '900', stroke: { color: '#000', width: 8 } } }); s.anchor.set(0.5); s.position.set(st.width / 2, st.height * 0.54); box.addChild(s); }
      st.layer('overlay').addChild(box);
      box.alpha = 0;
      await Proto.tween(box, { alpha: 1 }, 0.3);
      t.scale.set(0.4); await Proto.tween(t.scale, { x: 1, y: 1 }, 0.4, { ease: 'outBack' });
      await Proto.wait(((D && D.hold) ?? 1.4) * this.tf());
      await Proto.tween(box, { alpha: 0 }, 0.3);
      box.destroy({ children: true });
    }

    async runFeature(result, ev, g, res, draw, ctx) {
      const app = this.app, pres = this.pres;
      const trig = pres.trigger || {};
      if (trig.sound) { const hd = this.playSound(trig.sound); if (trig.wait !== false && hd) await Promise.race([hd.promise, Proto.wait(trig.maxWait ?? 4)]); }
      if (trig.perf) await app.timeline.play(trig.perf, ctx);
      const fctx = { ...ctx, spins: draw && draw.spins, fsAward: draw && draw.spins, group: draw && draw.group };
      app.timeline.record('label', `玩法 ${result.feature.type}｜${draw && draw.group !== undefined ? `組別 ${draw.group}｜` : ''}結果 ${result.feature.win}（${Proto.fmt.num(result.feature.winX, 2)}×）`);
      const intro = pres.featureIntro ?? pres.fsIntro;
      if (intro) await app.timeline.play(intro, fctx);
      await this.declare(draw);
      this.clearWins();
      this.setMode('fs');
      const base = this.state.shownWin || 0;
      if (this.present) await this.present.run(res, draw, fctx, ev, g, result);
      else await this.genericFeature(result);
      const win = result.feature.win;
      const outro = pres.featureOutro ?? pres.fsOutro;
      if (outro) await app.timeline.play(outro, { ...fctx, fsTotal: win, fsTotalX: result.feature.winX, fsPlayed: result.feature.spinsPlayed });
      if (this.reachesLadder(result.feature.winX)) await this.winLadder(win);
      await this.countBox(base + win, 0.4);
      this.setMode('base');
      if (this.present && this.present.exit) this.present.exit();
      this.view.setGrid(result.reel.grid);
    }

    // 沒有 Pixi Presenter 的玩法：顯示摘要（不中斷遊戲，OQ-005）
    async genericFeature(result) {
      const st = this.stage;
      const t = st.showText('stage-feat', `${result.feature.type}\n${result.feature.spinsPlayed ? `${result.feature.spinsPlayed} 手｜` : ''}贏 ${Proto.fmt.money(result.feature.win)}`, { layer: 'overlay', size: 80, color: '#ffe14a', anim: 'pop', y: st.height * 0.45 });
      await Proto.wait(1.8 * this.tf());
      st.remove('stage-feat', 0.3);
      return t;
    }

    // 給玩法用：用主遊戲轉輪轉一手（劇本裡的 g.grid）
    async spinReels(g) { this.clearWins(); this.view.spinStart(); await this.view.land(g.grid); }
    cell(r, row) { return this.view.cell(r, row); }
    cellEl(r, row) { return this.view.cell(r, row); }
    cellCenter(r, row) { return this.view.cellCenter(r, row); }

    // ---------- INFO（DOM 疊層，ADR-004）----------
    imgEl(id, cls) {
      const a = id && this.app.assets.images[id];
      if (!a || !a.ok || !a.el) return null;
      const img = a.el.cloneNode();
      if (cls) img.className = cls;
      return img;
    }
    buildInfo() {
      const st = this.stage;
      const I = this.app.config.info;
      this.infoLang = I.default || (I.langs && I.langs[0] && I.langs[0][0]) || 'tw';
      this.infoTitle = h('span', {});
      this.infoLangs = h('div', { class: 'if-langs' });
      this.infoBody = h('div', { class: 'if-body' });
      const close = h('button', { class: 'if-x', onclick: () => this.closeInfo() }, '✕');
      this.infoEl = h('div', { class: 'sl-info' }, h('div', { class: 'if-head' }, this.infoTitle, close), this.infoLangs, this.infoBody);
      Object.assign(this.infoEl.style, { position: 'absolute', left: '0', top: '0', width: '100%', height: '100%', fontSize: `${st.width / 33}px` });
      st.dom.appendChild(this.infoEl);
    }
    openInfo() {
      if (!this.infoEl) return;
      this.renderInfo();
      this.infoBody.scrollTop = 0;
      this.infoEl.classList.add('on');
      this.stage.pixi.stage.eventMode = 'none';      // 疊層開啟時 canvas 不接點擊
      this.playSound((this.pres.sounds || {}).info);
    }
    closeInfo() { this.infoEl.classList.remove('on'); this.stage.pixi.stage.eventMode = 'static'; }
    renderInfo() {
      const I = this.app.config.info;
      const lang = this.infoLang;
      const rows = I.rows || [];
      const pick = (r) => r[lang] ?? r.en ?? r.tw ?? '';
      const icon = (text) => {
        const frag = document.createDocumentFragment();
        String(text).split(/(\{[^}]+\})/).forEach((part) => {
          const m = part.match(/^\{([^}]+)\}$/);
          if (!m) return part && frag.append(part);
          const img = this.imgEl((I.icons || {})[m[1]], 'inl');
          frag.append(img || h('span', { class: 'inl-ph' }, `〔${m[1].replace(/圖$/, '')}〕`));
        });
        return frag;
      };
      this.infoTitle.textContent = rows[0] ? pick(rows[0]) : 'INFO';
      this.infoLangs.innerHTML = '';
      for (const [code, label] of I.langs || []) this.infoLangs.append(h('button', { class: code === lang ? 'on' : '', onclick: () => { this.infoLang = code; this.renderInfo(); } }, label));
      this.infoBody.innerHTML = '';
      rows.forEach((r, i) => {
        if (i === 0 && rows.length > 1) return;
        const t = pick(r);
        if (r.t === 'h') { this.infoBody.append(h('h4', {}, icon(t))); if (r.odds || r.en === 'ODDS TABLE') this.infoBody.append(this.oddsTable()); }
        else if (r.t === 's') this.infoBody.append(h('h5', {}, icon(t)));
        else this.infoBody.append(h('p', {}, icon(t)));
      });
    }
    oddsTable() {
      const p = this.p;
      return h('div', { class: 'if-odds' }, p.payIds.map((id) => {
        const counts = Object.keys(p.pay[id]).map(Number).sort((a, b) => b - a);
        return h('div', { class: 'if-oc' }, this.imgEl(p.symbols[id].image || `sym_${id}`) || h('div', { class: 'if-ph' }, this.symName(id)),
          h('div', { class: 'if-ol' }, counts.map((n) => h('div', {}, h('i', {}, n), p.pay[id][n]))));
      }));
    }

    // ---------- 設定檢查 / 除錯 ----------
    references() {
      const refs = { perfs: [], images: [], videos: [], sounds: [] };
      const pr = this.pres;
      for (const k of ['spin', 'smallWin', 'featureIntro', 'featureOutro', 'fsIntro', 'fsOutro']) if (typeof pr[k] === 'string') refs.perfs.push(pr[k]);
      if (pr.trigger && pr.trigger.perf) refs.perfs.push(pr.trigger.perf);
      for (const v of Object.values(pr.sounds || {})) if (v) refs.sounds.push(v);
      for (const d of this.layout.decor || []) if (d.image) refs.images.push(d.image);
      const F = this.featDef;
      if (F && F.references) { const r = F.references(this); for (const k of Object.keys(refs)) refs[k].push(...(r[k] || [])); }
      if (this.present && this.present.references) { const r = this.present.references(); for (const k of Object.keys(refs)) refs[k].push(...(r[k] || [])); }
      return refs;
    }
    validate() {
      const out = [];
      const F = this.featDef;
      if (this.p.feature && !this.present) out.push({ level: 'warn', text: `玩法「${this.p.feature.type}」沒有 Pixi Presenter（features[…].Stage），先用摘要畫面代替` });
      if (this.pres.afterReels && !(this.pres.stage && this.pres.stage.afterReels)) out.push({ level: 'info', text: 'presentation.afterReels 是 DOM 版，Stage 不會呼叫；請改寫到 presentation.stage.afterReels' });
      if (F && F.Present && !F.Stage) out.push({ level: 'info', text: `玩法「${this.p.feature.type}」只有 DOM 版 Present，需改寫成 Stage` });
      return out;
    }
    debugTabs() {
      const tabs = [{ title: '強制', render: (el) => this.renderForceTab(el) }, { title: '歷史', render: (el) => this.renderHistory(el), live: true }];
      const F = this.featDef;
      if (F && F.debugTabs) { try { tabs.push(...F.debugTabs(this)); } catch (e) { /* DOM 版除錯分頁可能依賴舊 API，略過 */ } }
      return tabs;
    }
    renderForceTab(el) {
      const svc = this.app.service;
      const go = async (scene, label) => {
        if (this.state.busy || !svc.debug) return;
        this.state.busy = true;
        this.clearWins(); this.state.shownWin = 0; this.renderHud();
        this.view.spinStart();
        try {
          const r = await svc.debug.force(typeof scene === 'function' && (svc.kind === 'http' || svc.kind === 'ws') ? { label } : scene, { bet: this.bet });   // 函式情境送到 Server 時改送名稱
          this.state.balance = r.balanceBefore - this.bet; this.renderHud();
          await this.play(r);
          this.state.balance = r.balanceAfter;
        } catch (e) { await this.view.land(this.view.grid); this.flashMessage(`${label}：${e.message || e}`); }
        this.state.busy = false; this.renderHud();
      };
      el.append(h('p', { class: 'proto-note' }, svc.debug ? '強制情境 = 沿數學流往後搜尋「自然轉出」的局（不是改結果），跳過的局不計帳。' : '目前的結果來源不支援強制情境（正式環境或重播）。'));
      const scenes = [['玩法局', 'feature'], ['贏 ≥ 10 倍', { minX: 10 }], ['贏 ≥ 50 倍', { minX: 50 }], ['玩法 ≥ 100 倍', { feature: true, minX: 100 }], ...((this.pres.stage && this.pres.stage.scenes) || [])];
      el.append(h('div', { class: 'proto-row' }, scenes.map(([label, sc]) => h('button', { onclick: () => go(sc, label) }, label))));
    }
    renderHistory(el) {
      el.append(Proto.table(['局', '停輪', '贏分', '倍數', '玩法'], this.state.history.slice(0, 60).map((x) => [x.round, x.stops, Proto.fmt.money(x.win), Proto.fmt.num(x.x, 2), x.feat])));
    }
  }

  Proto.modules.slot = SlotModule;
  Proto.gradientTexture = gradientTexture;
  Proto.stageLegacy = toLegacy;
})();
