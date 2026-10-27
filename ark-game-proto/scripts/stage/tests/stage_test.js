#!/usr/bin/env node
// ark-game-proto Stage 引擎層測試（P1）
//   node stage_test.js [--only logic|schema|result|service|parity|parity-src|replay] [--game <game.js> --orig <原 game.js>] [--n 100000]
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { load } = require('./load');

const SKILL = path.resolve(__dirname, '..', '..', '..');
const DEMO = path.join(SKILL, 'golden', 'stage-demo', 'game.js');
const argv = process.argv.slice(2);
const arg = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const ONLY = arg('--only', null);
const N = Number(arg('--n', 100000));
const GAMES = [DEMO];
const extraGame = arg('--game', process.env.STAGE_GAME || null);
if (extraGame) GAMES.push(path.resolve(extraGame));
const ORIG = arg('--orig', process.env.STAGE_ORIG || null);

let pass = 0, fail = 0;
function t(name, fn) {
  if (ONLY && !name.startsWith(ONLY + ':') && name !== ONLY) return;
  const t0 = Date.now();
  try { fn(); pass++; console.log(`✓ ${name} (${Date.now() - t0} ms)`); } catch (e) { fail++; console.log(`✗ ${name}\n    ${e && e.stack ? e.stack.split('\n').slice(0, 3).join('\n    ') : e}`); }
}
const eq = (a, b, m) => { if (a !== b) throw new Error(`${m || ''} 期望 ${b} 實得 ${a}`); };
const ok = (c, m) => { if (!c) throw new Error(m || 'assert'); };
const sync = (p) => { let v, e, done = false; p.then((x) => { v = x; done = true; }, (x) => { e = x; done = true; }); return () => { if (!done) throw new Error('not sync'); if (e) throw e; return v; }; };
// LocalService 的 async 方法內部全是同步運算 → 用微任務排空取值
async function run() {
  for (const G of GAMES) {
    const tag = path.basename(G) === 'game.js' ? path.basename(path.dirname(path.basename(path.dirname(G)) === 'stage' ? path.dirname(G) : G)) : path.basename(G);
    const P = load(G);
    const spec = P.config.spec;

    t(`logic:${tag}`, () => {
      const p = P.slotLogic.prepare(spec);
      const rng = P.createRng(1);
      for (let i = 0; i < 2000; i++) { const r = P.slotLogic.playOne(p, rng); ok(Number.isFinite(r.total)); }
    });

    await tA(`schema:${tag}`, async () => {
      const S = P.stageResult;
      const svc = new P.svc.LocalService(spec, { seed: 7 });
      const r = await svc.spin({ bet: P.slotLogic.prepare(spec).bet.def });
      eq(S.validate(r).length, 0, JSON.stringify(S.validate(r)));
      const bad1 = JSON.parse(JSON.stringify(r)); bad1.totalWin += 0.5; bad1.balanceAfter += 0.5;
      ok(S.validate(bad1).length > 0, '浮點金額應被拒');
      const bad2 = JSON.parse(JSON.stringify(r)); delete bad2.reel;
      ok(S.validate(bad2).length > 0, '缺 reel 應被拒');
      const bad3 = JSON.parse(JSON.stringify(r)); bad3.balanceAfter += 1;
      ok(S.validate(bad3).length > 0, '帳不平應被拒');
      // JSON 來回（模擬 Http 傳輸）仍合法
      eq(S.validate(JSON.parse(JSON.stringify(r))).length, 0);
    });

    await tA(`result:${tag}`, async () => {
      const S = P.stageResult;
      const p = P.slotLogic.prepare(spec);
      const svc = new P.svc.LocalService(spec, { seed: 99, balance: 1e12 });
      let feat = 0;
      for (let i = 0; i < 5000; i++) {
        const r = await svc.spin({ bet: p.bet.steps[i % p.bet.steps.length] });
        const e = S.validate(r);
        if (e.length) throw new Error(`第 ${i} 局：${e.join('；')}`);
        for (const k of ['bet', 'totalWin', 'balanceAfter']) ok(Number.isInteger(r[k]), k);
        if (r.feature) feat++;
      }
      // 情境搜尋一定拿到玩法局，且劇本可序列化
      const f = await svc.debug.force('feature');
      ok(f.feature && f.feature.script, '強制情境沒有玩法');
      JSON.stringify(f);
      console.log(`    5000 局含玩法 ${feat} 局；強制玩法局 ${f.feature.type} ${f.feature.winX}×`);
    });

    await tA(`service:${tag}`, async () => {
      const p = P.slotLogic.prepare(spec);
      const a = new P.svc.LocalService(spec, { seed: 20261016, balance: 1e12 });
      const b = new P.svc.LocalService(spec, { seed: 20261016, balance: 1e12 });
      for (let i = 0; i < 10000; i++) {
        const ra = await a.spin({ bet: p.bet.def }), rb = await b.spin({ bet: p.bet.def });
        if (JSON.stringify(ra.reel) !== JSON.stringify(rb.reel) || ra.totalWin !== rb.totalWin || ra.fx !== rb.fx) throw new Error(`第 ${i} 局不一致`);
      }
      // 冪等：同 requestId 不重複扣款
      const before = await a.balance();
      const r1 = await a.spin({ bet: p.bet.def, requestId: 'dup-1' });
      const r2 = await a.spin({ bet: p.bet.def, requestId: 'dup-1' });
      eq(r1, r2, '同 requestId 應回同一結果');
      eq(await a.balance(), before - p.bet.def + r1.totalWin, '只扣一次');
      // 錯誤碼
      let code = null; try { await a.spin({ bet: 7 }); } catch (e) { code = e.code; } eq(code, 'INVALID_BET');
      const poor = new P.svc.LocalService(spec, { seed: 1, balance: 0 });
      code = null; try { await poor.spin({ bet: p.bet.def }); } catch (e) { code = e.code; } eq(code, 'INSUFFICIENT_BALANCE');
    });

    // 結果一致：LocalService（record 劇本 + 演出流）vs 原 Proto Logic.playOne（record:false），同 seed 逐局 total 倍數相同
    await tA(`parity:${tag}`, async () => {
      const p = P.slotLogic.prepare(spec);
      const seed = 424242;
      const rng = P.createRng(seed);
      const svc = new P.svc.LocalService(spec, { seed, balance: 1e15 });
      let feats = 0, maxDiff = 0;
      for (let i = 0; i < N; i++) {
        const o = P.slotLogic.playOne(p, rng);
        const r = await svc.spin({ bet: p.bet.base });
        const d = Math.abs(o.total - r.totalX);
        if (d > 1e-9) throw new Error(`第 ${i} 局：Logic ${o.total} vs Service ${r.totalX}`);
        if (o.triggered !== !!r.feature) throw new Error(`第 ${i} 局觸發不一致`);
        if (r.feature) feats++;
        maxDiff = Math.max(maxDiff, d);
      }
      console.log(`    ${N} 局 0 差異（含玩法 ${feats} 局）`);
    });

    await tA(`replay:${tag}`, async () => {
      const p = P.slotLogic.prepare(spec);
      const rec = new P.svc.Recorder(new P.svc.LocalService(spec, { seed: 5, balance: 1e9 }));
      await rec.init();
      for (let i = 0; i < 100; i++) await rec.spin({ bet: p.bet.def });
      await rec.debug.force('feature');
      const tr = JSON.parse(JSON.stringify(rec.trace()));
      const rp = new P.svc.ReplayService(tr);
      await rp.init();
      for (let i = 0; i < tr.results.length; i++) {
        const r = await rp.spin({ bet: p.bet.def });
        eq(r.roundId, tr.results[i].roundId);
        eq(P.stageResult.validate(r).length, 0);
      }
      let code = null; try { await rp.spin({}); } catch (e) { code = e.code; } eq(code, 'END_OF_TRACE');
      eq(await rp.balance(), tr.results[tr.results.length - 1].balanceAfter);
    });
  }

  // ---------- P2：Tween（假時鐘）----------
  await tA('tween', async () => {
    const { load: ld } = require('./load');
    const P = ld(null, [path.join(__dirname, '..', 'runtime', 'core', 'tween.js')]);
    const o = { x: 0, s: { y: 0 } };
    let done = false;
    P.tween(o, { x: 10, 's.y': 4 }, 1, { ease: 'linear' }).then(() => (done = true));
    for (let i = 0; i < 5; i++) P.tick(100);            // 0.5 秒
    ok(Math.abs(o.x - 5) < 1e-9 && Math.abs(o.s.y - 2) < 1e-9, `1 倍速 0.5s 應到一半，實得 ${o.x}`);
    P.setSpeed(2); P.tick(250); P.setSpeed(1);          // 2 倍速 0.25s = 0.5s
    await Promise.resolve();
    ok(done && o.x === 10, '2 倍速應提早完成');
    const o2 = { a: 0 };
    P.time.skip = true; await P.tween(o2, { a: 1 }, 5); P.time.skip = false;
    eq(o2.a, 1, '跳過模式立即終值');
    const o3 = { a: 0 }; const tk = new P.Token();
    const pr = P.tween(o3, { a: 1 }, 1, { token: tk });
    P.setPaused(true); P.tick(5000); P.setPaused(false);
    eq(o3.a, 0, '暫停時不前進');
    tk.cancel();
    let cancelled = false; try { await pr; } catch (e) { cancelled = !!e.cancelled; }
    ok(cancelled, '取消應 reject Cancelled');
    const o4 = { a: 0 }; const stop = P.tween.loop(o4, { a: 1 }, 0.1, { ease: 'linear' });
    for (let i = 0; i < 25; i++) P.tick(10);
    ok(o4.a > 0.4 && o4.a < 0.6, `yoyo 迴圈 0.25s 應在回程中段，實得 ${o4.a}`); stop();
    eq(P.tween.count(), 0, '補間應全部回收');
  });

  // ---------- P2：Stage 公開方法與 Proto 試玩模板 stage.js 相同 ----------
  t('stage-api', () => {
    const PROTO_STAGE = ['fit', 'layer', 'place', 'placeholder', 'add', 'animateIn', 'showImage', 'showText', 'playVideo', 'setBgVideo', 'clearBgVideo', 'remove', 'clear', 'flash', 'shake', 'refresh'];
    const src = fs.readFileSync(path.join(__dirname, '..', 'runtime', 'core', 'stage.js'), 'utf8');
    const have = new Set([...src.matchAll(/^    (?:async )?([a-zA-Z]+)\(/gm)].map((m) => m[1]));
    const miss = PROTO_STAGE.filter((k) => !have.has(k));
    eq(miss.length, 0, `缺方法 ${miss.join(',')}`);
  });

  // ---------- P2：分層——演出層不呼叫數學（只允許 prepare / feature 讀設定）----------
  t('layering', () => {
    const files = ['slot/module.js', 'slot/reels.js', 'core/hud.js', 'core/stage.js', 'core/app.js', 'core/assets.js'];
    const bad = [];
    for (const f of files) {
      const s = fs.readFileSync(path.join(__dirname, '..', 'runtime', f), 'utf8');
      for (const m of s.matchAll(/(?:slotLogic|Logic\(\))\.(\w+)/g)) if (!['prepare', 'feature'].includes(m[1])) bad.push(`${f}: ${m[0]}`);
      if (/Math\.random\(\)/.test(s.replace(/\/\/.*$/gm, '')) && f !== 'core/stage.js' && f !== 'core/app.js') bad.push(`${f}: Math.random（演出亂數請用 mod.fx）`);
    }
    eq(bad.length, 0, bad.join('；'));
  });

  // ---------- P4：HttpService ⇄ mock slot-bot server ----------
  await tA('http', async () => {
    const { createMock } = require('./mock_server');
    const { server, P } = createMock({ game: DEMO, seed: 777, balance: 1e9 });
    await new Promise((r) => server.listen(0, r));
    const base = `http://127.0.0.1:${server.address().port}`;
    try {
      const spec = P.config.spec, bet = P.slotLogic.prepare(spec).bet.def;
      const http1 = new P.svc.HttpService({ base, gameId: 'stage-demo', token: 'A', fetch: (u, o) => fetch(u, o), dev: true });
      const local = new P.svc.LocalService(spec, { seed: 777, balance: 1e9 });
      const info = await http1.init();
      ok(info.seed === undefined && info.service === 'http', 'Http init 不外洩 seed');
      for (let i = 0; i < 300; i++) {
        const a = await http1.spin({ bet }), b = await local.spin({ bet });
        eq(P.stageResult.validate(a).length, 0, '回應通過 Schema');
        if (JSON.stringify(a.reel) !== JSON.stringify(b.reel) || a.totalWin !== b.totalWin || a.balanceAfter !== b.balanceAfter) throw new Error(`第 ${i} 局 Http ≠ Local`);
        ok(a.seed === null, 'Http 結果不帶數學 seed');
      }
      // 冪等：同 requestId 重送只扣一次
      const b0 = await http1.balance();
      const r1 = await http1.spin({ bet, requestId: 'same-1' });
      const r2 = await http1.spin({ bet, requestId: 'same-1' });
      eq(r1.roundId, r2.roundId); eq(await http1.balance(), b0 - bet + r1.totalWin, '只扣一次');
      // 5xx 重試沿用同 requestId（不重複扣款）
      const flaky = new P.svc.HttpService({ base, gameId: 'stage-demo', token: 'A', retries: 2, fetch: (u, o) => fetch(u, { ...o, headers: { ...o.headers, 'X-Mock-Fail': '2' } }) });
      const b1 = await http1.balance();
      const r3 = await flaky.spin({ bet, requestId: 'flaky-1' });
      eq(flaky.stats.retries, 2, '應重試 2 次');
      eq(await http1.balance(), b1 - bet + r3.totalWin, '重試不重複扣款');
      // 錯誤碼
      let code = null; try { await http1.spin({ bet: 3 }); } catch (e) { code = e.code; } eq(code, 'INVALID_BET');
      const poor = new P.svc.HttpService({ base, gameId: 'g', token: 'poor', fetch: (u, o) => fetch(u, o) });
      // 逾時
      const slow = new P.svc.HttpService({ base, gameId: 'g', token: 'S', timeout: 150, retries: 0, fetch: (u, o) => fetch(u, { ...o, headers: { ...o.headers, 'X-Mock-Delay': '600' } }) });
      code = null; try { await slow.spin({ bet }); } catch (e) { code = e.code; } eq(code, 'NETWORK', '逾時應回 NETWORK');
      // dev 強制情境
      const f = await http1.debug.force('feature', { bet });
      ok(f.feature && P.stageResult.validate(f).length === 0, 'dev/force 回玩法局');
      void poor;
    } finally { server.close(); }
  });

  // ---------- P4：Go math/rand Float64 數學流 ----------
  await tA('gorand', async () => {
    const P = load(DEMO);
    const g = P.GoRand.create(1);
    eq(String(g.int63()), '5577006791947779410', 'Go rand.NewSource(1).Int63() 第一個值');
    const f = P.svc.goFloatRng(1);
    // 黃金值 = Go 1.24 實跑 rand.New(rand.NewSource(seed)).Float64()（外部真值，不是自我比對）
    const GOLD = { 1: [0.60466028797961957, 0.94050908804501243, 0.66456005321849043], 42: [0.37302836104663262, 0.06600049679351791, 0.60409385155864204], 20261016: [0.21415471026081598, 0.34402538198128674, 0.77418565505817716] };
    eq(f(), GOLD[1][0], 'Float64 = float64(Int63()) / 2^63（Go 1 值流）');
    for (const [sd, vals] of Object.entries(GOLD)) { const r = P.svc.goFloatRng(Number(sd)); vals.forEach((v, i) => eq(r(), v, `seed ${sd} 第 ${i + 1} 個 Float64`)); }
    const svc = new P.svc.LocalService(P.config.spec, { seed: 42, rng: 'go', balance: 1e9 });
    eq((await svc.init()).rng, 'go');
    const svc2 = new P.svc.LocalService(P.config.spec, { seed: 42, rng: 'go', balance: 1e9 });
    for (let i = 0; i < 2000; i++) { const a = await svc.spin({}), b = await svc2.spin({}); if (a.totalWin !== b.totalWin || JSON.stringify(a.reel) !== JSON.stringify(b.reel)) throw new Error(`第 ${i} 局 go 流不一致`); }
  });

  // ---------- 1.5：三份契約 Schema（SpinResult、GameInfo、Release Manifest）----------
  await tA('schema:contract', async () => {
    const { validate } = require('./minischema');
    const P = load(DEMO);
    const svc = new P.svc.LocalService(P.config.spec, { seed: 3 });
    const info = await svc.init();
    eq(validate('game-info.schema.json', info).length, 0, JSON.stringify(validate('game-info.schema.json', info)));
    const r = await svc.spin({});
    eq(validate('spin-result.schema.json', r).length, 0, 'SpinResult');
    eq(validate('game-info.schema.json', { ...info, pending: r }).length, 0, 'pending = SpinResult');
    ok(validate('game-info.schema.json', { ...info, pending: { bad: 1 } }).length > 0, '壞 pending 應被拒');
    const h = 'a'.repeat(64);
    const rel = { schema: 'web-game-release/1', releaseId: 'huffnpuff-1.0.0+abc1234', gameId: 'huffnpuff-open-house', gameVersion: '1.0.0', runtimeApi: '^1.0.0',
      protocol: P.svc.PROTOCOL, manifestHash: null, status: 'candidate', unassigned: [],
      bundles: [{ name: 'boot', requiredForPlayable: true, hash: 'sha256:' + h, bytes: 3, files: [{ path: 'index.html', sha256: h, bytes: 3 }] }] };
    eq(validate('release-manifest.schema.json', rel).length, 0, JSON.stringify(validate('release-manifest.schema.json', rel)));
    const noHash = JSON.parse(JSON.stringify(rel)); delete noHash.bundles[0].hash;
    ok(validate('release-manifest.schema.json', noHash).length > 0, '缺 hash 應被拒');
    const badHash = JSON.parse(JSON.stringify(rel)); badHash.bundles[0].files[0].sha256 = 'xyz';
    ok(validate('release-manifest.schema.json', badHash).length > 0, '雜湊格式錯應被拒');
  });

  // ---------- 1.5：ark-go wire 編解碼與 Go 黃金封包逐字相同 ----------
  t('wire', () => {
    const P = load(DEMO);
    const G = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'wire-golden.json'), 'utf8'));
    for (const c of G.cases) eq(P.wire.encode(c.packet), c.frame, c.name);
    const dec = P.wire.createDecoder();
    const all = G.cases.map((c) => c.frame).join('');
    const got = [];
    for (let i = 0; i < all.length; i += 7) got.push(...dec(all.slice(i, i + 7)));     // 半包、黏包
    eq(got.length, G.cases.length, '切包數');
    got.forEach((p, i) => eq(JSON.stringify(p), JSON.stringify(G.cases[i].packet), `第 ${i} 包內容`));
    const pad = (n) => { const base = P.wire.encode({ cmd: 'x', data: '' }).length - 4; return { cmd: 'x', data: 'a'.repeat(n - base) }; };
    eq(P.wire.encode(pad(9999)).length, G.max9999.frameLen, '9,999 字元邊界');
    let code = null; try { P.wire.encode(pad(10000)); } catch (e) { code = e.code; }
    eq(code, 'WIRE_TOO_LARGE'); ok(G.tooLarge10000, 'Go 端同樣拒送');
    code = null; try { P.wire.createDecoder()('abcd{}'); } catch (e) { code = e.code; } eq(code, 'WIRE_BAD_HEADER');
  });

  // ---------- 1.5：ArkConn ⇄ mock ark-go（auth、sn、未認證、逾時、重連）----------
  await tA('arkconn', async () => {
    const { createMockWs } = require('./mock_ws');
    let conn0 = null;
    const m = createMockWs({ onConn: (c) => { conn0 = c; } });
    await new Promise((r) => m.server.listen(0, r));
    const url = `ws://127.0.0.1:${m.server.address().port}/ws`;
    const P = m.P;
    try {
      let code = null;
      const bad = new P.ArkConn({ url, auth: () => ({ ark_id: 'x', ark_token: 'bad' }) });
      try { await bad.open(); } catch (e) { code = e.code; } eq(code, 'SESSION_EXPIRED', 'auth 失敗');
      const c = new P.ArkConn({ url, auth: () => ({ ark_id: 'wolf', ark_token: 'dev' }), reconnect: { delays: [50, 50, 50] }, timeoutMs: 400 });
      await c.open();
      const a = await c.request('slot', 'balance'); eq(a.status, 0);
      const b = await c.request('slot', 'balance'); ok(c.sn >= 3, 'sn 遞增');
      void b;
      eq((await c.request('slot', 'nope')).status, 404, '未知指令回 404 資料而非例外');
      let rec = 0; c.on('', 'reconnected', () => rec++);
      conn0.kill();                                                        // 模擬斷線
      await new Promise((r) => setTimeout(r, 400));
      eq(c.state, 'authed', '自動重連並重新 auth'); eq(rec, 1);
      eq((await c.request('slot', 'balance')).status, 0, '重連後可用');
      c.close();
    } finally { m.server.close(); }
  });

  // ---------- 1.5：WsService（分段、缺段 fetch、426、重試同 requestId、ack／pending、與 Local 同結果）----------
  await tA('ws', async () => {
    const { createMockWs } = require('./mock_ws');
    let conn0 = null;
    const m = createMockWs({ seed: 777, maxInline: 600, onConn: (c) => { conn0 = c; } });
    await new Promise((r) => m.server.listen(0, r));
    const url = `ws://127.0.0.1:${m.server.address().port}/ws`;
    const P = m.P, spec = P.config.spec, bet = P.slotLogic.prepare(spec).bet.def;
    try {
      const ws = new P.svc.WsService({ url, arkId: 'A', token: 'dev', dev: true, reconnect: { delays: [30, 30] } });
      const local = new P.svc.LocalService(spec, { seed: 777, balance: 1e9 });
      const info = await ws.init();
      ok(info.seed === undefined && info.supported, 'init 不外洩 seed、帶 supported');
      for (let i = 0; i < 200; i++) {
        const a = await ws.spin({ bet }), b = await local.spin({ bet });
        if (JSON.stringify(a.reel) !== JSON.stringify(b.reel) || a.totalWin !== b.totalWin || a.balanceAfter !== b.balanceAfter) throw new Error(`第 ${i} 局 Ws ≠ Local`);
      }
      ok(ws.stats.chunked > 0, `應有分段局（maxInline 600），實得 ${ws.stats.chunked}`);
      // 缺段 → fetch 補拿
      const m2 = createMockWs({ seed: 1, maxInline: 300, dropChunk: 0 });
      await new Promise((r) => m2.server.listen(0, r));
      const ws2 = new P.svc.WsService({ url: `ws://127.0.0.1:${m2.server.address().port}/ws`, arkId: 'B', token: 'dev' });
      const r2 = await ws2.spin({ bet });
      ok(r2.roundId && ws2.stats.fetched === 1, '缺段應 fetch 一次');
      ws2.close(); m2.server.close();
      // 426
      const old = new P.svc.WsService({ url, arkId: 'C', token: 'dev', protocol: { result: 'proto-stage-result/2' } });
      let code = null; try { await old.init(); } catch (e) { code = e.code; } eq(code, 'PROTOCOL_MISMATCH');
      old.close();
      // pending：spin 後未 ack → init 帶 pending；ack 後清除
      const r3 = await ws.spin({ bet, requestId: 'p-1' });
      eq((await ws.init()).pending.roundId, r3.roundId, 'init 帶 pending');
      ok(await ws.ack(r3.roundId), 'ack'); eq((await ws.init()).pending, null, 'ack 後清除');
      // 斷線重試：Server 結算後斷線 → 同 requestId 重送拿回同一局、只結算一次
      const m3 = createMockWs({ seed: 5, dropAfterSpin: 1 });
      await new Promise((r) => m3.server.listen(0, r));
      const ws3 = new P.svc.WsService({ url: `ws://127.0.0.1:${m3.server.address().port}/ws`, arkId: 'D', token: 'dev', reconnect: { delays: [30, 30] }, retries: 2 });
      const r4 = await ws3.spin({ bet, requestId: 'same' });
      eq(m3.stats.settles, 1, '只結算一次'); ok(ws3.stats.retries >= 1, '應重試');
      ok(r4.roundId, '拿到結果'); ws3.close(); m3.server.close();
      // 錯誤碼
      code = null; try { await ws.spin({ bet: 3 }); } catch (e) { code = e.code; } eq(code, 'INVALID_BET');
      code = null; try { await ws.action({ roundId: r3.roundId }); } catch (e) { code = e.code; } eq(code, 'NOT_SUPPORTED');
      const f = await ws.debug.force('feature', { bet }); ok(f.feature, 'force');
      // Recorder 包 WsService：軌跡可給 ReplayService
      const rec = new P.svc.Recorder(ws); await rec.init(); await rec.spin({ bet });
      eq(rec.trace().results.length, 1); ok(await rec.ack(rec.trace().results[0].roundId), 'Recorder 轉送 ack');
      void conn0; ws.close();
    } finally { m.server.close(); }
  });

  // ---------- 1.5：pending 播放順序（app 規則：init 有 pending → 先播再開放 SPIN）----------
  await tA('pending', async () => {
    const P = load(DEMO);
    const spec = P.config.spec, bet = P.slotLogic.prepare(spec).bet.def;
    const local = new P.svc.LocalService(spec, { seed: 9, balance: 1e9 });
    const r = await local.spin({ bet });
    const fake = { kind: 'replay', init: async () => ({ balance: 1, pending: r }), ack: async (id) => { fake.acked = id; return true; } };
    const played = [];
    await P.playPending({ service: fake, info: await fake.init(), module: { play: async (x) => played.push(x.roundId), state: { balance: 0 }, renderHud() {} } });
    eq(played[0], r.roundId, '先播 pending'); eq(fake.acked, r.roundId, '播完 ack');
  });

  // 試點遊戲包的數值與玩法邏輯與原檔逐字相同（演出段除外）
  if (extraGame && ORIG) t('parity-src', () => {
    const seg = (f) => {
      const s = fs.readFileSync(f, 'utf8').replace(/\r\n/g, '\n');   // 換行符號不算差異（原檔 CRLF）
      const a = s.indexOf('const CFG'), b = s.indexOf('// ==================== 演出');
      ok(a > 0 && b > a, `${f} 找不到 CFG ～ 演出 區段`);
      const sim = s.slice(s.indexOf('function runSim'));
      return s.slice(a, b) + sim.slice(0, sim.indexOf('\n  }\n') + 4);
    };
    const h = (x) => crypto.createHash('sha256').update(x).digest('hex').slice(0, 16);
    const A = seg(path.resolve(extraGame)), B = seg(path.resolve(ORIG));
    eq(h(A), h(B), '數值 / 玩法邏輯區段雜湊');
    console.log(`    邏輯區段 ${A.split('\n').length} 行，sha ${h(A)} 與原檔相同`);
  });

  console.log(`\n${fail ? '❌' : '✅'} stage_test ${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
}
async function tA(name, fn) {
  if (ONLY && !name.startsWith(ONLY + ':') && name !== ONLY) return;
  const t0 = Date.now();
  try { await fn(); pass++; console.log(`✓ ${name} (${Date.now() - t0} ms)`); } catch (e) { fail++; console.log(`✗ ${name}\n    ${e && e.stack ? e.stack.split('\n').slice(0, 3).join('\n    ') : e}`); }
}
run();
