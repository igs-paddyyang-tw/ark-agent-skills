import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { ReplayService, type GameService } from '@pgp/game-service';
import { ServiceError, type SpinResult } from '@pgp/shared-types';
import { GameController, type View } from '../src/game/controller.js';
import { expectedEvents, type PresentEvent } from '../src/game/present-events.js';
import { ManualClock } from '../src/runtime/clock.js';

const TRACE = JSON.parse(readFileSync(new URL('./fixtures/trace.json', import.meta.url), 'utf8'));
const fakeView = (log: string[] = []): View => ({
  render: () => {}, spinStart: () => log.push('spinStart'), abortSpin: () => log.push('abort'),
  land: async () => { log.push('land'); }, showWins: async () => { log.push('wins'); }, countWin: async () => { log.push('count'); },
  feature: async () => { log.push('feature'); }, clearWins: () => {},
});

describe('GameController', () => {
  it('軌跡 42 局：present-events 與 expectedEvents 完全相同；餘額＝balanceAfter', async () => {
    const svc = new ReplayService(TRACE);
    const c = new GameController(svc, fakeView(), new ManualClock());
    const evs: PresentEvent[] = [];
    c.events.on('present', (e) => evs.push(e));
    await c.start(await svc.init());
    expect(c.hud.bet).toBe(240);
    for (const r of TRACE.results) {
      const got = await c.spin();
      expect(got?.roundId).toBe(r.roundId);
      expect(c.hud.balance).toBe(r.balanceAfter);
    }
    expect(evs).toEqual(TRACE.results.flatMap((r: SpinResult) => expectedEvents(r)));
    expect(evs.filter((e) => e.type === 'feature-start').length).toBe(TRACE.results.filter((r: SpinResult) => r.feature).length);
  });
  it('續玩：init 帶 pending → 先播、校正餘額、ack，之後才可 SPIN', async () => {
    const pend = TRACE.results[41];
    const acked: string[] = [];
    const svc = { kind: 'ws', debug: null, init: async () => ({}), balance: async () => 0, spin: async () => TRACE.results[0], action: async () => pend, ack: async (id: string) => { acked.push(id); return true; } } as unknown as GameService;
    const log: string[] = [];
    const c = new GameController(svc, fakeView(log), new ManualClock());
    const evs: PresentEvent[] = [];
    c.events.on('present', (e) => evs.push(e));
    expect(c.hud.busy).toBe(true);
    await c.start({ bets: [240], defaultBet: 240, balance: 1, pending: pend } as any);
    expect(acked).toEqual([pend.roundId]);
    expect(c.hud.balance).toBe(pend.balanceAfter);
    expect(c.hud.busy).toBe(false);
    expect(evs.map((e) => e.type)).toEqual(['round-start', 'reels-stop', 'feature-start', 'feature-end', 'round-end']);
    expect(log).toContain('feature');
  });
  it('spin 失敗 → 退回押注、停輪、送 error，不播放', async () => {
    const svc = { kind: 'ws', debug: null, init: async () => ({}), balance: async () => 0, spin: async () => { throw new ServiceError('NETWORK', 'down'); }, action: async () => null, ack: async () => true } as unknown as GameService;
    const log: string[] = [];
    const c = new GameController(svc, fakeView(log), new ManualClock());
    const errs: string[] = [];
    c.events.on('error', (e) => errs.push(e.code));
    await c.start({ bets: [240], defaultBet: 240, balance: 1000 } as any);
    expect(await c.spin()).toBeNull();
    expect(c.hud.balance).toBe(1000);
    expect(c.hud.busy).toBe(false);
    expect(errs).toEqual(['NETWORK']);
    expect(log).toEqual(['spinStart', 'abort']);
  });
  it('餘額不足不送出；押注只能選 bets 內的值', async () => {
    let calls = 0;
    const svc = { kind: 'ws', debug: null, spin: async () => { calls++; return TRACE.results[0]; }, ack: async () => true } as unknown as GameService;
    const c = new GameController(svc, fakeView(), new ManualClock());
    await c.start({ bets: [120, 240], defaultBet: 240, balance: 100 } as any);
    expect(await c.spin()).toBeNull();
    expect(calls).toBe(0);
    expect(c.hud.message).toBe('餘額不足');
    c.stepBet(-1); expect(c.hud.bet).toBe(120);
    c.setBet(999); expect(c.hud.bet).toBe(120);
  });
});
