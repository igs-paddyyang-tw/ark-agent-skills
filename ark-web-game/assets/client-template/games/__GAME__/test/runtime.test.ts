import { describe, expect, it } from 'vitest';
import { Boot } from '../src/runtime/boot.js';
import { ManualClock } from '../src/runtime/clock.js';
import { Emitter } from '../src/runtime/events.js';
import { Tweener } from '../src/runtime/tween.js';

describe('Tween／Clock', () => {
  it('to：時長內內插、到點精確、Promise 完成', async () => {
    const c = new ManualClock(), tw = new Tweener(c), o = { x: 0, s: { y: 10 } };
    let done = false;
    void tw.to(o, { x: 100, 's.y': 0 }, 1, { ease: 'linear' }).then(() => { done = true; });
    await c.tick(0.25);
    expect(o.x).toBeCloseTo(25); expect(o.s.y).toBeCloseTo(7.5);
    await c.tick(0.25, 3);
    expect(o.x).toBe(100); expect(o.s.y).toBe(0); expect(done).toBe(true);
  });
  it('delay、stop、dur 0', async () => {
    const c = new ManualClock(), tw = new Tweener(c), o = { x: 0 };
    const p = tw.to(o, { x: 10 }, 1, { delay: 0.5, ease: 'linear' });
    await c.tick(0.5); expect(o.x).toBe(0);
    await c.tick(0.5); expect(o.x).toBeCloseTo(5);
    p.stop(); await c.tick(1); expect(o.x).toBeCloseTo(5);
    await tw.to(o, { x: 3 }, 0); expect(o.x).toBe(3);
  });
  it('loop：來回、stop 還原', async () => {
    const c = new ManualClock(), tw = new Tweener(c), o = { a: 1 };
    const stop = tw.loop(o, { a: 2 }, 0.5);
    await c.tick(0.5); expect(o.a).toBeCloseTo(2);
    await c.tick(0.5); expect(o.a).toBeCloseTo(1);
    stop(); expect(o.a).toBe(1);
  });
  it('wait 依演出時間（speed 由 RealClock 乘進 dt）', async () => {
    const c = new ManualClock(); let n = 0;
    void c.wait(1).then(() => n++);
    await c.tick(0.5); expect(n).toBe(0);
    await c.tick(0.5); expect(n).toBe(1);
  });
});

describe('Boot', () => {
  it('依序到 playable，記 time_to_playable_ms 並回報遙測', async () => {
    let t = 0; const tel: any[] = [];
    const b = new Boot(() => t, (n, d) => tel.push([n, d]));
    const states: string[] = [];
    b.events.on('state', (s) => states.push(s.state));
    const ok = await b.run({ connect: async () => { t = 100; }, load: async () => { t = 400; }, build: async () => { t = 450; } });
    expect(ok).toBe(true);
    expect(states).toEqual(['connecting', 'loading', 'core_ready', 'playable']);
    expect(b.metrics).toEqual({ time_to_core_ready_ms: 400, time_to_playable_ms: 450 });
    expect(tel).toEqual([['boot', { time_to_core_ready_ms: 400, time_to_playable_ms: 450 }]]);
  });
  it('連線失敗 → error（帶錯誤碼），不會到 playable', async () => {
    const b = new Boot(() => 0);
    const ok = await b.run({ connect: async () => { throw Object.assign(new Error('協定不相容'), { code: 'PROTOCOL_MISMATCH' }); }, load: async () => {}, build: async () => {} });
    expect(ok).toBe(false);
    expect(b.state).toBe('error');
    expect(b.error).toEqual({ code: 'PROTOCOL_MISMATCH', message: '協定不相容' });
    expect(() => b.to('playable')).toThrow();
  });
  it('Emitter：handler 例外不影響其他', () => {
    const e = new Emitter<{ a: number }>(); const got: number[] = [];
    e.on('a', () => { throw new Error('x'); }); const off = e.on('a', (d) => got.push(d));
    const err = console.error; console.error = () => {};
    e.emit('a', 1); off(); e.emit('a', 2);
    console.error = err;
    expect(got).toEqual([1]);
  });
});
