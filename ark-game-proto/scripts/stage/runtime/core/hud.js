// ============================================================
//  [ark-game-proto stage] HUD（Pixi，ADR-004 / CMP-106）
//  座標沿用遊戲包 layout.hud（舞台像素、左上角）：
//    balance / bet / betSub / win：{ x, y, w, h, size, color, align, bg }
//    buttons：{ spin, betUp, betDown, maxBet, fast, auto, info, menu }：{ x, y, w, h, label? }
//  按鈕兩種畫法：layout.hud.art = true（底圖已畫好按鈕，HuffNPuff 的 Bar_直.png）→ 透明熱區 + 按下亮框；
//               否則畫預設按鈕。觸控 / 滑鼠 pointertap；空白鍵 SPIN 由模組處理。
//  數值只顯示模組給的值（餘額 = GameService 回傳，HUD 不自行加總）
// ============================================================
(function () {
  'use strict';
  const Proto = window.Proto;
  const FONT = "'Arial Black','Microsoft JhengHei','PingFang TC',sans-serif";
  const LABEL = { spin: 'SPIN', betUp: '+', betDown: '−', maxBet: 'MAX', fast: '⚡', auto: 'AUTO', info: 'i', menu: '≡' };

  class Hud {
    constructor(mod) {
      this.mod = mod;
      this.stage = mod.app.stage;
      const L = (this.L = mod.layout.hud || {});
      this.art = L.art ?? (mod.layout.decor || []).some((d) => d.image && /bar/i.test(d.image + (d.label || '')));
      this.root = new PIXI.Container();
      this.root.label = 'hud';
      this.stage.layer('ui').addChild(this.root);
      this.fields = {};
      for (const k of ['balance', 'bet', 'betSub', 'win']) if (L[k]) this.fields[k] = this.field(L[k], k);
      this.btn = {};
      for (const [k, b] of Object.entries(L.buttons || {})) this.btn[k] = this.button(k, b);
      this.infoLine = null;
      if (L.infoLine || mod.layout.reels) {
        const r = mod.layout.reels || {};
        const b = L.infoLine || { x: r.x ?? 40, y: (r.y ?? 700) - 70, w: r.w ?? 1000, h: 56, size: 34 };
        this.infoLine = this.field({ ...b, color: b.color || '#fff6d0' }, 'info');
      }
    }

    field(b, key) {
      const c = new PIXI.Container();
      c.position.set(b.x || 0, b.y || 0);
      if (b.bg) {
        // bg 可寫 CSS 漸層（沿用 Proto 版面）：蓋住底圖上的示意數字
        const t = typeof b.bg === 'string' && Proto.gradientTexture ? Proto.gradientTexture(b.bg, b.w, b.h) : null;
        if (t) { const s = new PIXI.Sprite(t); const mk = new PIXI.Graphics().roundRect(0, 0, b.w, b.h, Math.min(16, b.h / 3)).fill(0xffffff); s.mask = mk; c.addChild(mk, s); }
        else c.addChild(new PIXI.Graphics().roundRect(0, 0, b.w, b.h, Math.min(16, b.h / 3)).fill({ color: 0x000000, alpha: 0.85 }));
      }
      const t = new PIXI.Text({ text: '', style: { fontFamily: FONT, fontSize: b.size || 32, fill: b.color || '#ffffff', fontWeight: '900', stroke: { color: '#000', width: 4, join: 'round' } } });
      t.anchor.set(b.align === 'left' ? 0 : b.align === 'right' ? 1 : 0.5, 0.5);
      t.position.set(b.align === 'left' ? 12 : b.align === 'right' ? b.w - 12 : b.w / 2, b.h / 2);
      c.addChild(t);
      this.root.addChild(c);
      return { c, t, b, key };
    }

    setText(f, s) {
      if (!f) return;
      f.t.text = s;
      const maxW = f.b.w - 16;
      f.t.scale.set(1);
      if (f.t.width > maxW && maxW > 0) f.t.scale.set(maxW / f.t.width);
    }

    button(key, b) {
      const c = new PIXI.Container();
      c.position.set(b.x, b.y);
      c.eventMode = 'static';
      c.cursor = 'pointer';
      c.hitArea = new PIXI.Rectangle(0, 0, b.w, b.h);
      const g = new PIXI.Graphics();
      const glow = new PIXI.Graphics().roundRect(0, 0, b.w, b.h, Math.min(b.w, b.h) / 2.2).stroke({ width: 6, color: 0xfff1a8, alpha: 0.95 });
      glow.alpha = 0;
      if (!this.art || b.draw) {
        const round = key === 'spin' ? Math.min(b.w, b.h) / 2 : Math.min(18, b.h / 3);
        g.roundRect(0, 0, b.w, b.h, round).fill({ color: key === 'spin' ? 0x2e9d3c : 0x2a2a38 }).stroke({ width: 4, color: key === 'spin' ? 0xbaff9a : 0x8a8aa8 });
        const t = new PIXI.Text({ text: b.label || LABEL[key] || key, style: { fontFamily: FONT, fontSize: b.size || Math.min(b.h * 0.42, 48), fill: '#fff', fontWeight: '900' } });
        t.anchor.set(0.5); t.position.set(b.w / 2, b.h / 2);
        c.addChild(g, t);
        c.__label = t;
      } else {
        g.rect(0, 0, b.w, b.h).fill({ color: 0xffffff, alpha: 0.001 });
        c.addChild(g);
      }
      c.addChild(glow);
      c.on('pointerdown', () => { glow.alpha = 1; Proto.tween(c, { 'scale.x': 0.96, 'scale.y': 0.96 }, 0.06); });
      const up = () => { Proto.tween(glow, { alpha: 0 }, 0.25); Proto.tween(c, { 'scale.x': 1, 'scale.y': 1 }, 0.1); };
      c.on('pointerup', up); c.on('pointerupoutside', up);
      c.on('pointertap', () => { if (c.__enabled !== false) this.mod.onButton(key); });
      // 以中心縮放
      c.pivot.set(b.w / 2, b.h / 2); c.position.set(b.x + b.w / 2, b.y + b.h / 2);
      this.root.addChild(c);
      return { c, b, glow, set on(v) { glow.alpha = v ? 0.8 : 0; } };
    }

    enable(key, on) {
      const B = this.btn[key];
      if (!B) return;
      B.c.__enabled = on;
      B.c.alpha = on ? 1 : 0.45;
    }
    toggle(key, on) { const B = this.btn[key]; if (B) { B.glow.alpha = on ? 0.85 : 0; if (B.c.__label) B.c.__label.style.fill = on ? '#ffe57f' : '#fff'; } }

    render(st) {
      const m = Proto.fmt.money;
      this.setText(this.fields.balance, m(st.balance));
      this.setText(this.fields.bet, m(st.bet));
      if (this.fields.betSub) this.setText(this.fields.betSub, st.betSub || '');
      this.setText(this.fields.win, st.shownWin ? m(st.shownWin) : '');
      for (const k of ['betUp', 'betDown', 'maxBet']) this.enable(k, !st.busy);
      this.enable('spin', !st.busy || st.auto);
      this.toggle('fast', st.fast);
      this.toggle('auto', st.auto);
      if (this.btn.spin && this.btn.spin.c.__label) this.btn.spin.c.__label.text = st.auto ? 'STOP' : (this.btn.spin.b.label || 'SPIN');
    }

    setInfo(text) { if (this.infoLine) this.setText(this.infoLine, text || ''); }
  }

  Proto.Hud = Hud;
})();
