// ArkConn 對 mock ark-go Server：auth、sn 遞增、ret 對應、錯誤、推播、斷線自動重連、ready() 不重複開連線
import { afterEach, describe, expect, it } from 'vitest';
import { ArkConn, ConnError } from '../src/arkconn.js';
import { createMockArk } from './mock-ark.mjs';

let mock: any; let conn: ArkConn | null = null;
afterEach(async () => { conn?.close(); conn = null; await mock?.close(); });
const mk = async (o: any = {}, token = 'dev') => {
  mock = createMockArk(o);
  const url = await mock.listen();
  conn = new ArkConn({ url, auth: () => ({ ark_id: 'u1', ark_token: token }), reconnect: { delays: [50, 50, 50] }, timeoutMs: 2000 });
  return conn;
};

describe('ArkConn', () => {
  it('auth 成功、sn 遞增、回應以 ret＋sn 對應', async () => {
    const c = await mk();
    await c.open();
    expect(c.state).toBe('authed');
    const [a, b] = await Promise.all([c.request('slot', 'balance'), c.request('slot', 'init', { protocol: { wire: 'ark-wire/1' } })]);
    expect(a.status).toBe(0);
    expect(b.info.supported.wire).toContain('ark-wire/1');
    expect(c.sn).toBe(3);
  });
  it('auth 失敗 → SESSION_EXPIRED', async () => {
    const c = await mk({}, 'bad');
    await expect(c.open()).rejects.toMatchObject({ code: 'SESSION_EXPIRED' });
  });
  it('連不到 → NETWORK（不會卡住）', async () => {
    conn = new ArkConn({ url: 'ws://127.0.0.1:1/ws', auth: () => ({ ark_id: 'u', ark_token: 't' }) });
    await expect(conn.open()).rejects.toBeInstanceOf(ConnError);
  });
  it('錯誤碼放在 data（404 未知指令）', async () => {
    const c = await mk(); await c.open();
    const r = await c.request('slot', 'nope');
    expect(r).toMatchObject({ status: 404, code: 'NOT_FOUND' });
  });
  it('推播：spin 結果超過門檻 → 先收 n 段 result', async () => {
    const c = await mk({ maxInline: 100 }); await c.open();
    const parts: any[] = [];
    c.on('slot', 'result', (d) => parts.push(d));
    const r = await c.request('slot', 'spin', { bet: 240, requestId: 'q1' });
    expect(r.chunks).toBeGreaterThan(0);
    expect(parts.length).toBe(r.chunks);
    expect(JSON.parse(parts.map((p) => p.part).join('').replace(/\\u([0-9a-f]{4})/g, (_, h) => String.fromCharCode(parseInt(h, 16)))).roundId).toBe(r.roundId);
  });
  it('Server 斷線 → 自動重連；ready() 等待重連，不另開連線', async () => {
    const c = await mk(); await c.open();
    const evts: string[] = [];
    c.on('', 'reconnected', () => evts.push('re'));
    mock.conns[0].kill();
    await new Promise((r) => setTimeout(r, 5));
    await c.ready();
    await c.ready();
    expect(c.state).toBe('authed');
    expect(mock.stats.conns).toBe(2);
    expect(evts).toEqual(['re']);
    expect((await c.request('slot', 'balance')).status).toBe(0);
  });
});
