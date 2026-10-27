// Tween（Stage Proto.tween 的 TS 版）：屬性路徑（'scale.x'）、緩動、loop；時間來自 Clock
import type { Clock } from './clock.js';

export type Ease = 'linear' | 'quad' | 'cubic' | 'back' | 'sine';
const EASE: Record<Ease, (t: number) => number> = {
  linear: (t) => t,
  quad: (t) => 1 - (1 - t) * (1 - t),
  cubic: (t) => 1 - (1 - t) ** 3,
  back: (t) => { const c = 1.70158; return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2; },
  sine: (t) => -(Math.cos(Math.PI * t) - 1) / 2,
};
const get = (o: any, p: string) => p.split('.').reduce((x, k) => x?.[k], o);
const set = (o: any, p: string, v: number) => { const ks = p.split('.'); const last = ks.pop()!; const t = ks.reduce((x, k) => x[k], o); t[last] = v; };

export class Tweener {
  constructor(readonly clock: Clock) {}
  /** 動到 props，dur 演出秒；回傳 Promise（完成）＋ stop() */
  to(target: object, props: Record<string, number>, dur: number, o: { ease?: Ease; delay?: number } = {}): Promise<void> & { stop(): void } {
    const from: Record<string, number> = {};
    for (const k of Object.keys(props)) from[k] = Number(get(target, k));
    let t = -(o.delay ?? 0), off = () => {}, done = () => {};
    const p = new Promise<void>((resolve) => {
      done = resolve;
      if (dur <= 0 && !o.delay) { for (const [k, v] of Object.entries(props)) set(target, k, v); resolve(); return; }
      off = this.clock.onTick((dt) => {
        t += dt;
        if (t < 0) return;
        const k = Math.min(1, t / dur), e = EASE[o.ease ?? 'quad'](k);
        for (const [key, v] of Object.entries(props)) set(target, key, from[key]! + (v - from[key]!) * e);
        if (k >= 1) { off(); resolve(); }
      });
    }) as Promise<void> & { stop(): void };
    p.stop = () => { off(); done(); };
    return p;
  }
  /** 來回循環（脈動）；回傳 stop（回到原值） */
  loop(target: object, props: Record<string, number>, half: number, o: { ease?: Ease } = {}): () => void {
    const from: Record<string, number> = {};
    for (const k of Object.keys(props)) from[k] = Number(get(target, k));
    let t = 0;
    const off = this.clock.onTick((dt) => {
      t += dt;
      const ph = (t / half) % 2, k = EASE[o.ease ?? 'sine'](ph < 1 ? ph : 2 - ph);
      for (const [key, v] of Object.entries(props)) set(target, key, from[key]! + (v - from[key]!) * k);
    });
    return () => { off(); for (const [k, v] of Object.entries(from)) set(target, k, v); };
  }
}
