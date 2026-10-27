// mock ark-go WebSocket server（node 測試用；不需 Go、不需第三方套件）
//   最小 RFC 6455：握手、文字幀（client 有遮罩、server 無遮罩）、close；ark-go wire 封包（tests 用 Proto.wire 編解碼）
//   行為對齊 go-server internal/api/ws.go：auth（default system）、sys "slot"：init／balance／spin／ack／fetch／action／force；
//   結果超過 maxInline 字元時先推 n 段 "result" 再回 {chunks, chars}
//   測試旋鈕（opts）：maxInline、dropChunk（漏送第幾段）、protocol（支援清單）、onConn（取得連線以便模擬斷線）
'use strict';
const http = require('http');
const crypto = require('crypto');
const path = require('path');
const { load } = require('./load');

function createMockWs(opts = {}) {
  const P = load(opts.game || path.resolve(__dirname, '..', '..', '..', 'golden', 'stage-demo', 'game.js'));
  const spec = P.config.spec;
  const players = new Map();                                      // arkId → { svc, rounds: Map, pending }
  const supported = opts.supported || { result: ['proto-stage-result/1'], info: ['proto-stage-info/1'], wire: ['ark-wire/1'] };
  const stats = { conns: 0, spins: 0, settles: 0 };
  const player = (id) => {
    if (!players.has(id)) players.set(id, { svc: new P.svc.LocalService(spec, { seed: (opts.seed ?? 777) + players.size, balance: opts.balance ?? 1e9 }), rounds: new Map(), byReq: new Map(), pending: null });
    return players.get(id);
  };

  const server = http.createServer((_, res) => { res.writeHead(404); res.end(); });
  server.on('upgrade', (req, sock) => {
    const key = req.headers['sec-websocket-key'];
    const accept = crypto.createHash('sha1').update(key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
    sock.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
    stats.conns++;
    const c = { sock, authed: null, buf: Buffer.alloc(0), dec: P.wire.createDecoder() };
    const sendText = (s) => {
      const b = Buffer.from(s, 'utf8');
      const head = b.length < 126 ? Buffer.from([0x81, b.length]) : b.length < 65536 ? Buffer.from([0x81, 126, b.length >> 8, b.length & 255]) : Buffer.concat([Buffer.from([0x81, 127]), (() => { const x = Buffer.alloc(8); x.writeBigUInt64BE(BigInt(b.length)); return x; })()]);
      if (!sock.destroyed) sock.write(Buffer.concat([head, b]));
    };
    const send = (p) => sendText(P.wire.encode(p));
    c.kill = () => sock.destroy();
    if (opts.onConn) opts.onConn(c);
    sock.on('data', (chunk) => {
      c.buf = Buffer.concat([c.buf, chunk]);
      for (;;) {
        if (c.buf.length < 2) return;
        const op = c.buf[0] & 15; let len = c.buf[1] & 127, off = 2;
        if (len === 126) { if (c.buf.length < 4) return; len = c.buf.readUInt16BE(2); off = 4; } else if (len === 127) { if (c.buf.length < 10) return; len = Number(c.buf.readBigUInt64BE(2)); off = 10; }
        const masked = c.buf[1] & 128; const mask = masked ? c.buf.slice(off, off + 4) : null; if (masked) off += 4;
        if (c.buf.length < off + len) return;
        const data = Buffer.from(c.buf.slice(off, off + len)); c.buf = c.buf.slice(off + len);
        if (mask) for (let i = 0; i < data.length; i++) data[i] ^= mask[i & 3];
        if (op === 8) { sock.end(); return; }
        if (op !== 1) continue;
        for (const p of c.dec(data.toString('utf8'))) handle(p).catch((e) => console.error('mock_ws', e));
      }
    });
    sock.on('error', () => {});

    async function handle(p) {
      const reply = (data) => send({ ret: p.cmd, data, sn: p.sn, sys: p.sys });
      if (!p.sys) {
        if (p.cmd === 'auth') { const ok = p.data && p.data.ark_id && p.data.ark_token && p.data.ark_token !== 'bad'; if (ok) c.authed = p.data.ark_id; reply(ok ? { status: 0 } : { status: 1, msg: 'bad token' }); return; }
        if (p.cmd === 'alive') return;
        if (p.cmd === 'close') { reply('Bye'); sock.end(); return; }
        return;
      }
      if (!c.authed) { reply({ status: -999, msg: 'not authed' }); return; }
      const pl = player(c.authed);
      const d = p.data || {};
      const err = (status, code, message) => reply({ status, code, message });
      const deliver = (r) => {
        const body = P.wire.escapeNonASCII(JSON.stringify(r));
        if (body.length <= (opts.maxInline ?? 9743)) { reply({ status: 0, result: r }); return; }
        const n = Math.ceil(body.length / 4000);
        for (let i = 0; i < n; i++) if (opts.dropChunk !== i) send({ cmd: 'result', sys: 'slot', data: { roundId: r.roundId, i, n, part: body.slice(i * 4000, (i + 1) * 4000) } });
        reply({ status: 0, roundId: r.roundId, chunks: n, chars: body.length });
      };
      try {
        switch (p.cmd) {
          case 'init': {
            for (const [k, v] of Object.entries(d.protocol || {})) if (!(supported[k] || []).includes(v)) return err(426, 'PROTOCOL_MISMATCH', `協定不相容：${k}=${v}`);
            const info = await pl.svc.init();
            delete info.seed;
            const pend = pl.pending ? pl.rounds.get(pl.pending) : null;
            return reply({ status: 0, info: { ...info, service: 'go', pending: pend || null, supported } });
          }
          case 'balance': return reply({ status: 0, balance: await pl.svc.balance() });
          case 'spin': case 'force': {
            if (d.requestId && pl.byReq.has(d.requestId)) return deliver(pl.rounds.get(pl.byReq.get(d.requestId)));
            if (pl.pending) pl.pending = null;                     // 隱含 ack
            stats.spins++;
            const r = p.cmd === 'force' ? await pl.svc.force(d.scene || 'feature', { bet: d.bet, requestId: d.requestId }) : await pl.svc.spin({ bet: d.bet, requestId: d.requestId });
            r.seed = null;
            stats.settles++;
            pl.rounds.set(r.roundId, r); pl.byReq.set(d.requestId, r.roundId); pl.pending = r.roundId;
            if (opts.dropAfterSpin) { opts.dropAfterSpin--; sock.destroy(); return undefined; }
            return deliver(r);
          }
          case 'ack': if (!pl.rounds.has(d.roundId)) return err(404, 'NOT_FOUND', '沒有這一局'); if (pl.pending === d.roundId) pl.pending = null; return reply({ status: 0 });
          case 'fetch': { const r = pl.rounds.get(d.roundId); if (!r) return err(404, 'NOT_FOUND', '沒有這一局'); const save = opts.dropChunk; opts.dropChunk = undefined; deliver(r); opts.dropChunk = save; return undefined; }
          case 'action': return err(400, 'NOT_SUPPORTED', '此玩法沒有玩家選擇步驟');
          default: return err(404, 'NOT_FOUND', p.cmd);
        }
      } catch (e) { return err(e.code === 'INVALID_BET' ? 400 : e.code === 'INSUFFICIENT_BALANCE' ? 402 : 500, e.code || 'SERVER_ERROR', e.message); }
    }
  });
  return { server, P, stats, players };
}

module.exports = { createMockWs };

if (require.main === module) {
  const port = Number(process.argv[2] || 8788);
  createMockWs().server.listen(port, () => console.log(`mock ark-go ws on ws://127.0.0.1:${port}/ws`));
}
