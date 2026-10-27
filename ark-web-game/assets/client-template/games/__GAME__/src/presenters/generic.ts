// 通用玩法 Presenter（沒有專屬 Presenter 時）：顯示玩法名稱與贏分。新遊戲先用這個，再依 feature.script 寫專屬 Presenter
import type { SpinResult } from '@pgp/shared-types';
import { Container } from 'pixi.js';
import { box, money, txt } from '../scenes/ui.js';
import type { Clock } from '../runtime/clock.js';
import type { Tweener } from '../runtime/tween.js';
import type { Art } from '../scenes/art.js';
import type { ReelView } from '../scenes/reels.js';

export interface PresenterCtx { clock: Clock; tw: Tweener; layer: Container; bet: number; setWin: (n: number) => void; art: Art; /** 玩法要在主轉輪上逐手停輪時用（例 神燈開箱） */ reels?: ReelView }
export type Presenter = (r: SpinResult, ctx: PresenterCtx) => Promise<void>;

export const playGeneric: Presenter = async (r, ctx) => {
  const c = new Container();
  c.addChild(box(660, 300, 0x0b0f19, 26, 0xffca28));
  const t = txt(String((r.feature as any)?.group ?? r.feature!.type), 40, 0xffe082);
  t.anchor.set(0.5); t.position.set(330, 90);
  const w = txt('', 48, 0xfff59d);
  w.anchor.set(0.5); w.position.set(330, 200);
  c.addChild(t, w);
  ctx.layer.addChild(c);
  try {
    const o = { v: 0 };
    const off = ctx.clock.onTick(() => { w.text = money(o.v); });
    await ctx.tw.to(o, { v: r.feature!.win }, 1);
    off();
    w.text = money(r.feature!.win);
    ctx.setWin(r.base.win + r.feature!.win);
    await ctx.clock.wait(0.6);
  } finally { c.destroy({ children: true }); }
};
