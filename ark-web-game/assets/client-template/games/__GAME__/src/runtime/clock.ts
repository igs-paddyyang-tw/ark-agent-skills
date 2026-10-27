// 可控時鐘：所有演出等待與 Tween 都走這裡 → speed 可加速（e2e、試玩快轉）、測試可手動推進（ManualClock）
export interface Clock {
  speed: number;
  /** 演出時間（秒，已乘 speed） */
  now(): number;
  /** 等 sec 演出秒 */
  wait(sec: number): Promise<void>;
  /** 每幀回呼（dt = 演出秒）；回傳取消 */
  onTick(fn: (dt: number) => void): () => void;
}

/** 真實時鐘：requestAnimationFrame（瀏覽器）或 setTimeout 16ms（node） */
export class RealClock implements Clock {
  speed = 1;
  private t = 0;
  private last = performance.now();
  private subs = new Set<(dt: number) => void>();
  private timers: { at: number; resolve: () => void }[] = [];
  private running = false;
  now() { return this.t; }
  private loop = () => {
    const n = performance.now();
    const dt = Math.min(0.1, (n - this.last) / 1000) * this.speed;
    this.last = n;
    this.advance(dt);
    if (this.subs.size || this.timers.length) this.schedule(); else this.running = false;
  };
  private schedule() { this.running = true; (globalThis.requestAnimationFrame ?? ((f: () => void) => setTimeout(f, 16)))(this.loop); }
  private kick() { if (!this.running) { this.last = performance.now(); this.schedule(); } }
  advance(dt: number) {
    this.t += dt;
    for (const fn of [...this.subs]) fn(dt);
    const due = this.timers.filter((x) => x.at <= this.t);
    this.timers = this.timers.filter((x) => x.at > this.t);
    for (const x of due) x.resolve();
  }
  wait(sec: number) { if (sec <= 0) return Promise.resolve(); return new Promise<void>((resolve) => { this.timers.push({ at: this.t + sec, resolve }); this.kick(); }); }
  onTick(fn: (dt: number) => void) { this.subs.add(fn); this.kick(); return () => { this.subs.delete(fn); }; }
}

/** 測試用：只有呼叫 tick() 才前進 */
export class ManualClock implements Clock {
  speed = 1;
  private t = 0;
  private subs = new Set<(dt: number) => void>();
  private timers: { at: number; resolve: () => void }[] = [];
  now() { return this.t; }
  wait(sec: number) { return new Promise<void>((resolve) => { this.timers.push({ at: this.t + sec, resolve }); }); }
  onTick(fn: (dt: number) => void) { this.subs.add(fn); return () => { this.subs.delete(fn); }; }
  async tick(dt: number, steps = 1) {
    for (let i = 0; i < steps; i++) {
      this.t += dt;
      for (const fn of [...this.subs]) fn(dt);
      const due = this.timers.filter((x) => x.at <= this.t + 1e-9);
      this.timers = this.timers.filter((x) => x.at > this.t + 1e-9);
      for (const x of due) x.resolve();
      await Promise.resolve(); await Promise.resolve();
    }
  }
}
