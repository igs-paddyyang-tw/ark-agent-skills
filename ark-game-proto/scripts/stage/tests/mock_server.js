#!/usr/bin/env node
// slot-bot server 的 mock（HTTP 契約 API-101～105，設計文件 §4.3）：內部用 LocalService 出結果
//   node mock_server.js --game <game.js> [--port 8787] [--seed 123] [--balance 100000] [--dev]
//   瀏覽器：index.html?service=http&base=http://localhost:8787&game=<id>&dev=1
// 行為：session 以 Authorization: Bearer <token> 區分（沒給 = 'anon'）；requestId 冪等；
//       header X-Mock-Fail: <n> → 同一 requestId 前 n 次回 503（測重試）；X-Mock-Delay: <ms> → 延遲回應
'use strict';
const http = require('http');
const path = require('path');
const { load } = require('./load');

function createMock({ game, seed = 20261016, balance = 100000, dev = true }) {
  const P = load(path.resolve(game));
  const scenes = ((P.config.presentation || {}).stage || {}).scenes || [];
  const sessions = new Map();
  const fails = new Map();
  const sess = (token) => {
    if (!sessions.has(token)) sessions.set(token, new P.svc.LocalService(P.config.spec, { seed: (seed + sessions.size) >>> 0, balance }));
    return sessions.get(token);
  };
  const STATUS = { INVALID_BET: 400, INSUFFICIENT_BALANCE: 402, NOT_SUPPORTED: 400, NOT_FOUND: 404, SESSION_EXPIRED: 401 };
  async function handle(req, body) {
    const m = req.url.match(/^\/api\/slot\/([^/]+)\/(init|spin|action|balance|dev\/force)(\?.*)?$/);
    if (!m) return [404, { code: 'NOT_FOUND', message: req.url }];
    const op = m[2];
    const token = (req.headers.authorization || '').replace(/^Bearer\s+/, '') || 'anon';
    const svc = sess(token);
    const fk = body && body.requestId;
    const want = Number(req.headers['x-mock-fail'] || 0);
    if (want && fk) { const n = (fails.get(fk) || 0) + 1; fails.set(fk, n); if (n <= want) return [503, { code: 'SERVER_ERROR', message: 'mock 503' }]; }
    try {
      if (op === 'init') { const info = await svc.init(); delete info.seed; return [200, { ...info, service: 'http' }]; }
      if (op === 'balance') return [200, { balance: await svc.balance() }];
      if (op === 'spin') { const r = await svc.spin({ bet: body.bet, requestId: body.requestId }); return [200, { ...r, seed: null }]; }   // 不外洩數學 seed
      if (op === 'action') return [200, await svc.action(body)];
      if (op === 'dev/force') {
        if (!dev) return [404, { code: 'NOT_FOUND', message: 'dev 端點未開啟' }];
        let scene = body.scene;
        if (scene && scene.label) { const hit = scenes.find(([l]) => l === scene.label); if (!hit) return [404, { code: 'NOT_FOUND', message: `沒有情境 ${scene.label}` }]; scene = hit[1]; }
        const r = await svc.force(scene, { bet: body.bet, requestId: body.requestId });
        return [200, { ...r, seed: null }];
      }
    } catch (e) { return [STATUS[e.code] || 500, { code: e.code || 'SERVER_ERROR', message: e.message }]; }
    return [404, { code: 'NOT_FOUND' }];
  }
  const server = http.createServer((req, res) => {
    const cors = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Mock-Fail, X-Mock-Delay', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS' };
    if (req.method === 'OPTIONS') { res.writeHead(204, cors); return res.end(); }
    let raw = '';
    req.on('data', (c) => (raw += c));
    req.on('end', async () => {
      let body = {};
      try { body = raw ? JSON.parse(raw) : {}; } catch (e) { res.writeHead(400, { ...cors, 'Content-Type': 'application/json' }); return res.end(JSON.stringify({ code: 'BAD_REQUEST' })); }
      const delay = Number(req.headers['x-mock-delay'] || 0);
      if (delay) await new Promise((r) => setTimeout(r, delay));
      const [code, data] = await handle(req, body);
      res.writeHead(code, { ...cors, 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify(data));
    });
  });
  return { server, P, sessions };
}

if (require.main === module) {
  const a = process.argv.slice(2);
  const arg = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
  const game = arg('--game');
  if (!game) { console.error('需要 --game <game.js>'); process.exit(2); }
  const port = Number(arg('--port', 8787));
  const { server } = createMock({ game, seed: Number(arg('--seed', 20261016)), balance: Number(arg('--balance', 100000)), dev: a.includes('--dev') || true });
  server.listen(port, () => console.log(`mock slot-bot server：http://localhost:${port}/api/slot/<game>/…（game=${path.basename(path.dirname(game))}）`));
}
module.exports = { createMock };
