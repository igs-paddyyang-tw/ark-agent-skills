import { describe, expect, it } from 'vitest';
import { HttpService, Recorder, ReplayService } from '../src/index.js';
import { TRACE } from './helpers.js';

const resp = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('HttpService', () => {
  it('路徑、Bearer、5xx 重試同 requestId、4xx 不重試', async () => {
    const calls: any[] = [];
    let n = 0;
    const f = (async (url: string, init: any) => {
      calls.push({ url, init });
      if (url.endsWith('/spin')) return ++n < 2 ? resp(500, { code: 'SERVER_ERROR' }) : resp(200, { ...TRACE.results[0] });
      if (url.endsWith('/action')) return resp(400, { code: 'NOT_SUPPORTED', message: 'x' });
      return resp(200, { status: 0, balance: 5 });
    }) as unknown as typeof fetch;
    const s = new HttpService({ base: 'http://h/', gameId: 'huff', token: 't', fetch: f });
    const r = await s.spin({ bet: 240 });
    expect(r.roundId).toBe(TRACE.results[0].roundId);
    expect(calls[0].url).toBe('http://h/api/slot/huff/spin');
    expect(calls[0].init.headers.Authorization).toBe('Bearer t');
    expect(JSON.parse(calls[0].init.body).requestId).toBe(JSON.parse(calls[1].init.body).requestId);
    await expect(s.action({ roundId: 'x', choice: 1 })).rejects.toMatchObject({ code: 'NOT_SUPPORTED' });
    expect(s.stats.retries).toBe(1);
    expect(await s.balance()).toBe(5);
  });
  it('逾時 → TIMEOUT', async () => {
    const f = ((_: string, init: any) => new Promise((_r, rej) => init.signal.addEventListener('abort', () => rej(Object.assign(new Error('aborted'), { name: 'AbortError' }))))) as unknown as typeof fetch;
    const s = new HttpService({ base: '', gameId: 'g', fetch: f, timeout: 30, retries: 0 });
    await expect(s.balance()).rejects.toMatchObject({ code: 'TIMEOUT' });
  });
});

describe('Replay／Recorder', () => {
  it('錄下的軌跡可原樣重播（與 Stage trace 同格式）', async () => {
    const rec = new Recorder(new ReplayService(TRACE));
    await rec.init();
    for (let i = 0; i < 5; i++) await rec.spin({ bet: 240 });
    const t = rec.trace();
    expect(t.schema).toBe('proto-stage-trace/1');
    const rp = new ReplayService(t);
    for (let i = 0; i < 5; i++) expect((await rp.spin({ bet: 240 })).roundId).toBe(TRACE.results[i].roundId);
    await expect(rp.spin({ bet: 240 })).rejects.toMatchObject({ code: 'END_OF_TRACE' });
    expect(await rp.balance()).toBe(TRACE.results[4].balanceAfter);
  });
  it('押注不符軌跡 → INVALID_BET', async () => {
    await expect(new ReplayService(TRACE).spin({ bet: 1 })).rejects.toMatchObject({ code: 'INVALID_BET' });
  });
});
