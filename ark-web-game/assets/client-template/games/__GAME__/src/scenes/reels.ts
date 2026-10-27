// ReelView：5×3 轉輪（符號用素材 sym_<代號>，沒有就佔位）；空轉 → 依 reel.grid 逐軸停輪（不自行決定結果）
import { Container, Graphics, Sprite } from 'pixi.js';
import { NO_ART, type Art } from './art.js';
import { GAME } from '../game.config.js';
import type { Clock } from '../runtime/clock.js';
import type { Tweener } from '../runtime/tween.js';
import { box, txt } from './ui.js';

/** 沒設定顏色的符號：依名稱雜湊給固定佔位色 */
export const symColor = (s: string) => { let h = 2166136261; for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619) >>> 0; return 0x404040 + (h & 0x7f7f7f); };

export class Cell extends Container {
  sym = '';
  private bg = new Graphics();
  private caption = txt('', 34, 0x111111);
  private pic = new Sprite();
  constructor(readonly w: number, readonly h: number, private art: Art = NO_ART) {
    super();
    this.caption.anchor.set(0.5);
    this.caption.position.set(w / 2, h / 2);
    this.pic.anchor.set(0.5);
    this.pic.position.set(w / 2, h / 2);
    this.pivot.set(w / 2, h / 2);
    this.addChild(this.bg, this.caption, this.pic);
  }
  set(sym: string) {
    if (sym === this.sym) return;
    this.sym = sym;
    const t = this.art.tex(`sym_${sym}`);
    if (t) {
      this.pic.texture = t;
      this.pic.width = this.w - 4; this.pic.height = this.h - 4;
      this.pic.visible = true; this.bg.visible = false; this.caption.visible = false;
      return;
    }
    this.pic.visible = false; this.bg.visible = true; this.caption.visible = true;
    const [name, color] = GAME.symbols[sym] ?? [sym, symColor(sym)];
    this.bg.clear().roundRect(6, 6, this.w - 12, this.h - 12, 18).fill(color);
    this.caption.text = name;
    this.caption.style.fontSize = name.length > 3 ? 24 : 34;
  }
}

export class ReelView extends Container {
  readonly cells: Cell[][] = [];                // [reel][row]（可見三格）
  private spare: Cell[] = [];                    // 每軸多一格在上方，空轉時補位（不會出現空洞）
  readonly fx = new Container();
  private cols: Container[] = [];
  private spinning: boolean[] = [];
  private offTick: (() => void) | null = null;
  private spinT0 = 0;
  private seq = 1;
  readonly symList: string[];
  constructor(private clock: Clock, private tw: Tweener, symbols?: string[], private art: Art = NO_ART) {
    super();
    const R = GAME.reels;
    this.symList = (symbols ?? Object.keys(GAME.symbols)).filter((s) => s !== 'KEY');
    const W = R.cols * R.cellW + (R.cols - 1) * R.gap;
    const bg = art.sprite('reel_bg', W, R.rows * R.cellH);
    if (bg) this.addChild(bg); else this.addChild(box(W + 24, R.rows * R.cellH + 24, 0x1c2233, 22, 0x3a4566)).position.set(-12, -12);
    for (let r = 0; r < R.cols; r++) {
      const col = new Container();
      col.x = r * (R.cellW + R.gap);
      const mask = new Graphics().rect(0, 0, R.cellW, R.rows * R.cellH).fill(0xffffff);
      col.addChild(mask);
      col.mask = mask;
      const list: Cell[] = [];
      for (let row = 0; row < R.rows; row++) {
        const c = new Cell(R.cellW, R.cellH, art);
        c.position.set(R.cellW / 2, row * R.cellH + R.cellH / 2);
        c.set(this.symList[(r * 3 + row * 5) % this.symList.length]!);
        col.addChild(c);
        list.push(c);
      }
      const sp = new Cell(R.cellW, R.cellH, art);
      sp.position.set(R.cellW / 2, -R.cellH / 2);
      sp.set(this.symList[(r * 7 + 3) % this.symList.length]!);
      col.addChild(sp);
      this.spare.push(sp);
      this.cells.push(list);
      this.cols.push(col);
      this.addChild(col);
      this.spinning.push(false);
    }
    this.addChild(this.fx);
  }
  cell(r: number, row: number): Cell | undefined { return this.cells[r]?.[row]; }
  cellCenter(r: number, row: number) { const R = GAME.reels; return { x: r * (R.cellW + R.gap) + R.cellW / 2, y: row * R.cellH + R.cellH / 2 }; }
  private nextSym() { this.seq = (this.seq * 1103515245 + 12345) >>> 0; return this.symList[(this.seq >>> 8) % this.symList.length]!; }

  /** 空轉（按下 SPIN 立刻開始，掩蓋網路延遲） */
  spin(fxSeed = 1) {
    this.seq = fxSeed >>> 0 || 1;
    this.spinT0 = this.clock.now();
    this.spinning = this.spinning.map(() => true);
    const R = GAME.reels, speed = R.cellH * 22;
    this.offTick?.();
    this.offTick = this.clock.onTick((dt) => {
      this.cells.forEach((list, r) => {
        if (!this.spinning[r]) return;
        for (const c of [...list, this.spare[r]!]) {
          c.y += speed * dt;
          if (c.y > R.rows * R.cellH + R.cellH / 2) { c.y -= (R.rows + 1) * R.cellH; c.set(this.nextSym()); }
        }
      });
    });
  }

  /** 拿不到結果：直接停在原格位 */
  stopNow() {
    const R = GAME.reels;
    this.spinning = this.spinning.map(() => false);
    this.offTick?.(); this.offTick = null;
    this.cells.forEach((_, r) => this.settle(r));
  }

  /** 依 grid 逐軸停輪；extend[r] = 聽牌延長秒數 */
  async land(grid: string[][], extend: Record<number, number> = {}, onLand?: (r: number) => void) {
    const R = GAME.reels, T = GAME.timing;
    const left = T.spinMin - (this.clock.now() - this.spinT0);
    if (left > 0) await this.clock.wait(left);
    for (let r = 0; r < R.cols; r++) {
      if (r > 0) await this.clock.wait(T.reelGap + (extend[r] ?? 0));
      this.spinning[r] = false;
      const list = this.settle(r);
      list.forEach((c, row) => { c.set(grid[r]?.[row] ?? c.sym); c.y = row * R.cellH + R.cellH / 2 - 26; });
      await Promise.all(list.map((c, row) => this.tw.to(c, { y: row * R.cellH + R.cellH / 2 }, T.land, { ease: 'back' })));
      onLand?.(r);
    }
    this.offTick?.(); this.offTick = null;
  }

  /** 依目前位置重排一軸：最上面那格當備用（放到框外上方），其餘三格依序為可見列 */
  private settle(r: number): Cell[] {
    const R = GAME.reels;
    const all = [...this.cells[r]!, this.spare[r]!].sort((a, b) => a.y - b.y);
    this.spare[r] = all[0]!;
    this.spare[r]!.y = -R.cellH / 2;
    const list = all.slice(1);
    list.forEach((c, row) => { c.y = row * R.cellH + R.cellH / 2; });
    this.cells[r] = list;
    return list;
  }

  allCells(): [number, number, Cell][] { return this.cells.flatMap((l, r) => l.map((c, row) => [r, row, c] as [number, number, Cell])); }
}
