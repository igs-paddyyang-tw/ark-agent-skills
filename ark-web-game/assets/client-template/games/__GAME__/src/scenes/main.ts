// 主畫面（實作 controller 的 View）：背景、Logo、轉輪（含框）、連線、贏分、HUD、玩法 Presenter、音效
//   版面：直式 720×1280，等比縮放置中；素材別名見 assets.yaml，沒有素材時退回佔位圖形
import { Application, Container, Graphics, Text } from 'pixi.js';
import type { SpinResult } from '@pgp/shared-types';
import { GAME } from '../game.config.js';
import type { GameController, HudState, View } from '../game/controller.js';
import type { Clock } from '../runtime/clock.js';
import type { Tweener } from '../runtime/tween.js';
import type { PresenterCtx } from '../presenters/generic.js';
import { pickPresenter } from '../presenters/index.js';
import { NO_ART, type Art } from './art.js';
import { ReelView } from './reels.js';
import { box, Button, money, otxt } from './ui.js';

export class MainScene extends Container implements View {
  readonly reels: ReelView;
  private winFx = new Container();
  private featLayer = new Container();
  private bannerLayer = new Container();
  private winText: Text = otxt('', 60, 0xfff176, 0x3a2116, 8);
  private tierText: Text = otxt('', 72, 0xff8a65, 0x3a2116, 8);
  private infoLine: Text = otxt('', 26, 0xffffff, 0x3a2116, 5);
  private msg: Text = otxt('', 26, 0xff8a80, 0x3a2116, 5);
  private balText: Text = otxt('', 30, 0xffffff, 0x000000, 4);
  private betText: Text = otxt('', 30, 0xffffff, 0x000000, 4);
  private spinBtn!: Button;
  private autoBtn!: Button;
  private betDown!: Button;
  private betUp!: Button;
  private pulses: (() => void)[] = [];
  ctrl: GameController | null = null;

  constructor(private app: Application, private clock: Clock, private tw: Tweener, symbols?: string[], private art: Art = NO_ART) {
    super();
    const D = GAME.design, R = GAME.reels;
    const W = R.cols * R.cellW + (R.cols - 1) * R.gap, H = R.rows * R.cellH;
    const ox = (D.w - W) / 2;
    // 背景與 Logo
    const bg = art.sprite('bg_main', D.w, D.h);
    this.addChild(bg ?? new Graphics().rect(0, 0, D.w, D.h).fill(0x141a2a));
    const logo = art.sprite('logo', 456, 190);
    if (logo) { logo.anchor.set(0.5, 0); logo.position.set(D.w / 2, 46); this.addChild(logo); }
    else { const t = otxt(GAME.name, 44, 0xffe082, 0x3a2116, 8); t.anchor.set(0.5); t.position.set(D.w / 2, 120); this.addChild(t); }
    // 轉輪＋框
    this.reels = new ReelView(clock, tw, symbols, art);
    this.reels.position.set(ox, R.y);
    this.winFx.position.set(ox, R.y);
    this.featLayer.position.set(ox, R.y);
    this.addChild(this.reels);
    const frame = art.sprite('reel_frame', W + 60, H + 60);
    if (frame) { frame.position.set(ox - 30, R.y - 30); this.addChild(frame); }
    this.addChild(this.winFx);
    this.winText.anchor.set(0.5); this.winText.position.set(D.w / 2, R.y + H + 80);
    this.infoLine.anchor.set(0.5); this.infoLine.position.set(D.w / 2, R.y + H + 134);
    this.tierText.anchor.set(0.5); this.tierText.position.set(D.w / 2, R.y + H / 2);
    this.addChild(this.winText, this.infoLine, this.tierText, this.featLayer, this.bannerLayer);
    // HUD
    const hudY = 960;
    const panel = art.sprite('ui_panel', D.w - 40, 260);
    this.addChild(panel ?? box(D.w - 40, 260, 0x0e1320, 24, 0x2f3a58)).position.set(20, hudY);
    const lb = otxt('餘額', 20, 0xffe082, 0x000000, 3), rb = otxt('押注', 20, 0xffe082, 0x000000, 3);
    lb.anchor.set(0.5); lb.position.set(173, hudY + 34);
    rb.anchor.set(0.5); rb.position.set(D.w - 173, hudY + 34);
    this.balText.anchor.set(0.5); this.balText.position.set(173, hudY + 64);
    this.betText.anchor.set(0.5); this.betText.position.set(D.w - 173, hudY + 64);
    this.addChild(lb, rb, this.balText, this.betText);
    this.betDown = new Button('－', 76, 76, 0x90caf9, () => { art.sfx('sfx_fast_off'); this.ctrl?.stepBet(-1); }, 40, art.tex('ui_minus'));
    this.betUp = new Button('＋', 76, 76, 0x90caf9, () => { art.sfx('sfx_fast_on'); this.ctrl?.stepBet(1); }, 40, art.tex('ui_plus'));
    this.betDown.position.set(D.w - 226, hudY + 160);
    this.betUp.position.set(D.w - 92, hudY + 160);
    this.spinBtn = new Button(art.tex('ui_spin') ? '' : 'SPIN', 172, 172, 0x66bb6a, () => void this.ctrl?.spin(), 40, art.tex('ui_spin'));
    this.spinBtn.position.set(D.w / 2, hudY + 150);
    this.spinBtn.label = 'spin';
    this.autoBtn = new Button(art.tex('ui_auto') ? '' : 'AUTO', 96, 96, 0xffcc80, () => {
      if (!this.ctrl) return;
      this.ctrl.hud.auto = !this.ctrl.hud.auto; this.render(this.ctrl.hud);
      if (this.ctrl.hud.auto) void this.ctrl.spin();
    }, 26, art.tex('ui_auto'));
    this.autoBtn.position.set(110, hudY + 165);
    this.msg.anchor.set(0.5); this.msg.position.set(D.w / 2, hudY - 26);
    this.addChild(this.betDown, this.betUp, this.spinBtn, this.autoBtn, this.msg);
    this.fit();
    app.renderer.on('resize', () => this.fit());
  }

  /** 等比縮放置中（直式設計 720×1280） */
  fit() {
    const { width, height } = this.app.screen, D = GAME.design;
    const k = Math.min(width / D.w, height / D.h);
    this.scale.set(k);
    this.position.set((width - D.w * k) / 2, (height - D.h * k) / 2);
  }

  render(h: HudState) {
    this.balText.text = money(h.balance);
    this.betText.text = money(h.bet);
    this.spinBtn.enabled = !h.busy;
    this.betDown.enabled = !h.busy; this.betUp.enabled = !h.busy;
    this.autoBtn.alpha = h.auto ? 1 : 0.85;
    this.autoBtn.setText(h.auto ? 'STOP' : this.art.tex('ui_auto') ? '' : 'AUTO');
    this.msg.text = h.message;
    this.winText.text = h.win > 0 ? `贏 ${money(h.win)}` : '';
  }

  spinStart() {
    this.tierText.text = ''; this.infoLine.text = '';
    this.bannerLayer.removeChildren().forEach((c) => c.destroy());
    this.art.sfx('sfx_spin', { volume: 0.6 });
    this.reels.spin(Math.floor(Math.random() * 2 ** 31));
  }
  abortSpin() { this.reels.stopNow(); }

  async land(r: SpinResult) {
    // 聽牌：game.config tease.symbols 前面各軸累計 ≥ tease.need → 後面各軸延長（只在觸發局）
    const ext: Record<number, number> = {};
    const T = GAME.tease;
    let n = 0;
    r.reel.grid.forEach((col, i) => { if (T.symbols.length && n >= T.need && i > 0) ext[i] = T.sec; n += (col as string[]).filter((s) => T.symbols.includes(s)).length; });
    await this.reels.land(r.reel.grid as string[][], r.base.trigger ? ext : {}, () => this.art.sfx('sfx_stop', { volume: 0.8 }));
  }

  clearWins() {
    for (const s of this.pulses) s();
    this.pulses = [];
    this.winFx.removeChildren().forEach((c) => c.destroy());
    for (const [, , c] of this.reels.allCells()) c.alpha = 1;
  }

  async showWins(r: SpinResult) {
    const cells = new Set<string>();
    for (const w of r.base.ways) for (const c of (w as any).cells ?? []) cells.add(`${c[0]},${c[1]}`);
    if (!cells.size) return;
    const R = GAME.reels;
    for (const [rr, row, c] of this.reels.allCells()) {
      if (cells.has(`${rr},${row}`)) {
        const p = this.reels.cellCenter(rr, row);
        this.winFx.addChild(new Graphics().roundRect(p.x - R.cellW / 2 + 3, p.y - R.cellH / 2 + 3, R.cellW - 6, R.cellH - 6, 18).stroke({ width: 7, color: 0xffe57f }));
        this.pulses.push(this.tw.loop(c, { 'scale.x': 1.08, 'scale.y': 1.08 }, 0.32));
      } else c.alpha = 0.35;
    }
    const top = r.base.ways.slice().sort((a: any, b: any) => b.win - a.win)[0] as any;
    if (top) this.infoLine.text = `${top.len} ${GAME.symbols[top.sym]?.[0] ?? top.sym}${top.ways > 1 ? ` × ${top.ways} ways` : ''} ＝ ${money(top.win)}`;
    await this.clock.wait(GAME.timing.winShow);
  }

  async countWin(win: number, bet: number) {
    const o = { v: 0 };
    const tier = GAME.winTiers.filter(([x]) => win >= x * bet).pop();
    if (tier) {
      this.art.sfx('sfx_prewin');
      const b = this.art.sprite(`win_${tier[1].toLowerCase()}`, 560, 192);
      if (b) {
        const D = GAME.design, R = GAME.reels;
        b.anchor.set(0.5); b.position.set(D.w / 2, R.y + R.rows * R.cellH / 2); b.scale.set(0.2);
        this.bannerLayer.addChild(b);
        void this.tw.to(b, { 'scale.x': 560 / b.texture.width, 'scale.y': 192 / b.texture.height }, 0.35, { ease: 'back' });
      } else this.tierText.text = tier[1] + ' WIN';
    }
    const off = this.clock.onTick(() => { this.winText.text = `贏 ${money(o.v)}`; });
    await this.tw.to(o, { v: win }, GAME.timing.countUp * (tier ? 3 : 1));
    off();
    this.winText.text = `贏 ${money(win)}`;
  }

  async feature(r: SpinResult) {
    this.clearWins();
    this.art.sfx('sfx_alarm');
    await this.art.ensureFor(GAME.featureArt);                 // 背景還沒載完 → 優先載玩法素材（失敗用佔位）
    this.art.sfx('sfx_board_start');
    const ctx: PresenterCtx = { clock: this.clock, tw: this.tw, layer: this.featLayer, bet: r.bet, art: this.art, reels: this.reels, setWin: (n) => { this.winText.text = `贏 ${money(n)}`; } };
    this.infoLine.text = GAME.featureNames[(r.feature!.script as any)?.type] ?? (r.feature as any).group ?? r.feature!.type;
    this.winText.visible = false; this.infoLine.visible = false;          // 玩法盤面自己顯示累計
    try { await pickPresenter(r)(r, ctx); } finally {
      this.art.sfx('sfx_board_end');
      this.winText.visible = true; this.infoLine.visible = true;
    }
  }
}
