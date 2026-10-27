// mock ark-go WebSocket Server（測試用；不需 Go、不需第三方套件）
//   最小 RFC 6455（握手、文字幀、close）＋ ark-go wire（4 位數字元數前綴、非 ASCII \uXXXX）
//   行為對齊 go-server internal/api/ws.go（與 Stage tests/mock_ws.js 同一套）：
//     default system：auth／alive／close；sys "slot"：init／balance／spin／force／ack／fetch／action
//     結果超過 maxInline 字元 → 先推 n 段 cmd "result"，再回 {roundId, chunks, chars}
//   結果來源：opts.play({ bet, scene, requestId, n }) → SpinResult（未給時用內建最小結果）
//   測試旋鈕：maxInline、dropChunk（漏送第幾段）、dropAfterSpin（結算後斷線幾次）、supported、onConn
import http from 'node:http';
import crypto from 'node:crypto';

const esc = (s) => s.replace(/[\u0080-￿]/g, (c) => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0'));
export function encodePacket(p) {
  const parts = [];
  if (p.cmd) parts.push(`"cmd":${JSON.stringify(p.cmd)}`);
  if (p.ret) parts.push(`"ret":${JSON.stringify(p.ret)}`);
  if (p.data !== undefined && p.data !== null) parts.push(`"data":${JSON.stringify(p.data)}`);
  if (p.sn !== undefined && p.sn !== null) parts.push(`"sn":${JSON.stringify(p.sn)}`);
  if (p.sys) parts.push(`"sys":${JSON.stringify(p.sys)}`);
  const b = esc(`{${parts.join(',')}}`);
  return String(b.length).padStart(4, '0') + b;
}
function decoder() {
  let buf = '';
  return (s) => {
    buf += s;
    const out = [];
    while (buf.length >= 4) {
      const n = Number(buf.slice(0, 4));
      if (buf.length < 4 + n) break;
      out.push(JSON.parse(buf.slice(4, 4 + n)));
      buf = buf.slice(4 + n);
    }
    return out;
  };
}

let seq = 0;
export function minimalResult({ bet, scene, requestId }) {
  seq++;
  const feat = scene === 'feature';
  const win = feat ? bet * 5 : seq % 3 === 0 ? bet : 0;
  return {
    schema: 'proto-stage-result/1', roundId: `R${seq.toString(36)}-${'0'.repeat(15)}${seq % 10}`, requestId, seed: null,
    bet, grid: [[1, 2, 3], [4, 5, 6], [7, 8, 9], [1, 2, 3], [4, 5, 6]], wins: win && !feat ? [{ sym: 1, ways: 1, count: 3, pay: win, cells: [[0, 0], [1, 0], [2, 0]] }] : [],
    baseWin: feat ? 0 : win, feature: feat ? { type: 'demo', win, script: { steps: [{ kind: 'demo', win }] } } : null,
    totalWin: win, winType: win >= bet * 5 ? 'big' : win ? 'normal' : 'none', balanceBefore: 0, balanceAfter: 0,
    note: '中文備註',
  };
}

export function createMockArk(opts = {}) {
  const supported = opts.supported || { result: ['proto-stage-result/1'], info: ['proto-stage-info/1'], wire: ['ark-wire/1'] };
  const play = opts.play || minimalResult;
  const players = new Map();
  const stats = { conns: 0, spins: 0, packets: 0, auths: 0 };
  const conns = [];
  const player = (id) => {
    if (!players.has(id)) players.set(id, { balance: opts.balance ?? 1e9, rounds: new Map(), byReq: new Map(), pending: null, n: 0 });
    return players.get(id);
  };

  const server = http.createServer((_, res) => { res.writeHead(404); res.end(); });
  server.on('upgrade', (req, sock) => {
    const accept = crypto.createHash('sha1').update(req.headers['sec-websocket-key'] + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
    sock.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
    stats.conns++;
    const c = { sock, authed: null, buf: Buffer.alloc(0), dec: decoder() };
    conns.push(c);
    const sendText = (s) => {
      const b = Buffer.from(s, 'utf8');
      const head = b.length < 126 ? Buffer.from([0x81, b.length]) : b.length < 65536 ? Buffer.from([0x81, 126, b.length >> 8, b.length & 255]) : (() => { const x = Buffer.alloc(10); x[0] = 0x81; x[1] = 127; x.writeBigUInt64BE(BigInt(b.length), 2); return x; })();
      if (!sock.destroyed) sock.write(Buffer.concat([head, b]));
    };
    c.send = (p) => sendText(encodePacket(p));
    c.sendRaw = sendText;
    c.kill = () => sock.destroy();
    opts.onConn?.(c);
    sock.on('data', (chunk) => {
      c.buf = Buffer.concat([c.buf, chunk]);
      for (;;) {
        if (c.buf.length < 2) return;
        const op = c.buf[0] & 15; let len = c.buf[1] & 127, off = 2;
        if (len === 126) { if (c.buf.length < 4) return; len = c.buf.readUInt16BE(2); off = 4; } else if (len === 127) { if (c.buf.length < 10) return; len = Number(c.buf.readBigUInt64BE(2)); off = 10; }
        const masked = c.buf[1] & 128; const mask = masked ? c.buf.subarray(off, off + 4) : null; if (masked) off += 4;
        if (c.buf.length < off + len) return;
        const data = Buffer.from(c.buf.subarray(off, off + len)); c.buf = c.buf.subarray(off + len);
        if (mask) for (let i = 0; i < data.length; i++) data[i] ^= mask[i & 3];
        if (op === 8) { sock.end(); return; }
        if (op !== 1) continue;
        for (const p of c.dec(data.toString('utf8'))) { stats.packets++; handle(c, p); }
      }
    });
    sock.on('error', () => {});
  });

  function handle(c, p) {
    const reply = (data) => c.send({ ret: p.cmd, data, sn: p.sn, sys: p.sys });
    if (!p.sys) {
      if (p.cmd === 'auth') { stats.auths++; const ok = p.data?.ark_id && p.data?.ark_token && p.data.ark_token !== 'bad'; if (ok) c.authed = p.data.ark_id; reply(ok ? { status: 0 } : { status: 1, msg: 'bad token' }); }
      else if (p.cmd === 'close') { reply('Bye'); c.sock.end(); }
      return;
    }
    if (!c.authed) { reply({ status: -999, msg: 'not authed' }); return; }
    const pl = player(c.authed);
    const d = p.data || {};
    const err = (status, code, message) => reply({ status, code, message });
    const deliver = (r, drop) => {
      const body = esc(JSON.stringify(r));
      if (body.length <= (opts.maxInline ?? 9743)) { reply({ status: 0, result: r }); return; }
      const n = Math.ceil(body.length / 4000);
      for (let i = 0; i < n; i++) if (drop !== i) c.send({ cmd: 'result', sys: 'slot', data: { roundId: r.roundId, i, n, part: body.slice(i * 4000, (i + 1) * 4000) } });
      reply({ status: 0, roundId: r.roundId, chunks: n, chars: body.length });
    };
    switch (p.cmd) {
      case 'init': {
        for (const [k, v] of Object.entries(d.protocol || {})) if (!(supported[k] || []).includes(v)) return err(426, 'PROTOCOL_MISMATCH', `協定不相容：${k}=${v}`);
        const pend = pl.pending ? pl.rounds.get(pl.pending) : null;
        return reply({ status: 0, info: { schema: 'proto-stage-info/1', name: 'mock', service: 'go', bet: { def: 240, list: [240, 480] }, balance: pl.balance, pending: pend || null, supported } });
      }
      case 'balance': return reply({ status: 0, balance: pl.balance });
      case 'spin': case 'force': {
        if (d.requestId && pl.byReq.has(d.requestId)) return deliver(pl.rounds.get(pl.byReq.get(d.requestId)));
        if (!Number.isFinite(d.bet) || d.bet <= 0) return err(400, 'INVALID_BET', '押注不合法');
        if (d.bet > pl.balance) return err(402, 'INSUFFICIENT_BALANCE', '餘額不足');
        pl.pending = null;                                        // 隱含 ack（DR-1）
        stats.spins++;
        const r = { ...play({ bet: d.bet, scene: p.cmd === 'force' ? (d.scene || 'feature') : null, requestId: d.requestId, n: pl.n++ }) };
        r.requestId = d.requestId; r.seed = null;
        r.balanceBefore = pl.balance; pl.balance += r.totalWin - d.bet; r.balanceAfter = pl.balance;
        pl.rounds.set(r.roundId, r); if (d.requestId) pl.byReq.set(d.requestId, r.roundId); pl.pending = r.roundId;
        if (opts.dropAfterSpin) { opts.dropAfterSpin--; c.sock.destroy(); return undefined; }
        return deliver(r, opts.dropChunk);
      }
      case 'ack': if (!pl.rounds.has(d.roundId)) return err(404, 'NOT_FOUND', '沒有這一局'); if (pl.pending === d.roundId) pl.pending = null; return reply({ status: 0 });
      case 'fetch': { const r = pl.rounds.get(d.roundId); if (!r) return err(404, 'NOT_FOUND', '沒有這一局'); return deliver(r); }
      case 'action': return err(400, 'NOT_SUPPORTED', '此玩法沒有玩家選擇步驟');
      default: return err(404, 'NOT_FOUND', p.cmd);
    }
  }

  return {
    server, stats, players, conns,
    listen: () => new Promise((res) => server.listen(0, '127.0.0.1', () => res(`ws://127.0.0.1:${server.address().port}/ws`))),
    close: () => new Promise((res) => { for (const c of conns) c.sock.destroy(); server.close(() => res()); }),
  };
}
