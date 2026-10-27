import { afterEach, describe, expect, it } from 'vitest';
import { ServiceError, validateSpinResult } from '@pgp/shared-types';
import { WsService } from '../src/index.js';
import { huffMock } from './helpers.js';

let mock: any; const svcs: WsService[] = [];
afterEach(async () => { for (const s of svcs.splice(0)) s.close(); await mock?.close(); });
const mk = async (mo: any = {}, so: any = {}) => {
  mock ??= huffMock(mo);
  const url = mock.server.listening ? `ws://127.0.0.1:${mock.server.address().port}/ws` : await mock.listen();
  const s = new WsService({ url, arkId: 'p1', dev: true, backoffMs: 20, reconnect: { delays: [20, 20, 20] }, timeout: 2000, ...so });
  svcs.push(s);
  return s;
};

describe('WsService', () => {
  it('init 協商、40 局都合契約、餘額連續', async () => {
    mock = undefined; const s = await mk();
    const info = await s.init();
    expect(info.supported?.wire).toContain('ark-wire/1');
    let bal = info.balance as number;
    for (let i = 0; i < 40; i++) {
      const r = await s.spin({ bet: 240 });
      expect(validateSpinResult(r)).toEqual([]);
      expect(r.balanceBefore).toBe(bal);
      bal = r.balanceAfter;
    }
    expect(await s.balance()).toBe(bal);
  });
  it('協定不相容 → PROTOCOL_MISMATCH（426，不重試）', async () => {
    mock = undefined; const s = await mk({}, { protocol: { result: 'proto-stage-result/2', info: 'proto-stage-info/1', wire: 'ark-wire/1' } });
    await expect(s.init()).rejects.toMatchObject({ code: 'PROTOCOL_MISMATCH' });
    expect(s.stats.retries).toBe(0);
  });
  it('結果分段 → 組回；缺段 → fetch 補拿', async () => {
    mock = undefined; const s = await mk({ maxInline: 800 });
    await s.init();
    const f = await s.debug!.force('feature', { bet: 240 });
    expect(f.feature).toBeTruthy();
    expect(s.stats.chunked).toBe(1);
    mock.server.close(); await mock.close(); mock = undefined;
    const s2 = await mk({ maxInline: 800, dropChunk: 0 });
    await s2.init();
    const g = await s2.debug!.force('feature', { bet: 240 });
    expect(validateSpinResult(g)).toEqual([]);
    expect(s2.stats.fetched).toBe(1);
  });
  it('結算後斷線 → 自動重連、同 requestId 重試，不重複扣款', async () => {
    mock = undefined; const s = await mk({ dropAfterSpin: 1 });
    const info = await s.init();
    const r = await s.spin({ bet: 240, requestId: 'q-fixed' });
    expect(mock.stats.spins).toBe(1);
    expect(r.requestId).toBe('q-fixed');
    expect(r.balanceBefore).toBe(info.balance);
    expect(s.stats.retries).toBeGreaterThan(0);
    expect(mock.stats.conns).toBe(2);
  });
  it('未 ack 的局 → 下次 init 帶回 pending；ack 後清掉', async () => {
    mock = undefined; const a = await mk();
    await a.init();
    const r = await a.spin({ bet: 240 });
    a.close();
    const b = await mk();
    const info = await b.init();
    expect(info.pending?.roundId).toBe(r.roundId);
    expect(await b.ack(r.roundId)).toBe(true);
    expect((await b.init()).pending).toBeNull();
    expect(await b.ack('R-none')).toBe(false);
  });
  it('餘額不足 → INSUFFICIENT_BALANCE（不重試）；非 dev 沒有 debug', async () => {
    mock = undefined; const s = await mk({ balance: 100 }, { dev: false });
    await s.init();
    const e = await s.spin({ bet: 240 }).catch((x) => x);
    expect(e).toBeInstanceOf(ServiceError);
    expect(e.code).toBe('INSUFFICIENT_BALANCE');
    expect(e.retryable).toBe(false);
    expect(s.debug).toBeNull();
  });
});
