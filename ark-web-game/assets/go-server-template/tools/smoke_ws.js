#!/usr/bin/env node
// pixi-client（Stage）⇄ Go Server：ark-go WebSocket 端到端冒煙（Playwright + Chromium SwiftShader）
//   自己起 Server、建置資料夾版、起靜態服務，跑完全部收掉：
//   node tools/smoke_ws.js [--skill <aidev>/.kiro/skills/ark-game-proto] [--game ../pixi-client/game.js] [--odds ../../quicktest/odds/odds_1.0.0.json]
//        [--server-dir .] [--server-odds <Server 設定檔>] [--engine huff] [--scenes '["feature",{"feat":"OH"},{"label":"Open House 到宮殿"}]'] [--out <dir>] [--spins 3]
// 檢查（ark-web-game 計畫 AC-022）：
//   1. 啟動指標 time_to_playable_ms 已記錄；init 帶 supported、不帶 seed
//   2. 一般局 N 局＋各強制情境：0 console error、HUD 餘額 = balanceAfter = Server 餘額
//   3. 至少一局走分段（chunked ≥ 1；Open House 劇本超過 wire 單包）
//   4. 斷線續玩：spin 後不 ack、重新整理頁面 → init 帶 pending → 先播 pending、ack 後清除、不重複扣款
//   5. 連線中斷後自動重連，下一局正常
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const http = require('http');
const { spawn, execFileSync } = require('child_process');
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { console.log('SKIP：未安裝 playwright'); process.exit(0); }

const a = process.argv.slice(2);
const arg = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
const HERE = __dirname;
const skill = path.resolve(arg('--skill', path.join(HERE, '..', '..', '..', '..', '..', '..', '.kiro', 'skills', 'ark-game-proto')));
const game = path.resolve(arg('--game', path.join(HERE, '..', '..', 'pixi-client', 'game.js')));
const oddsArg = arg('--odds', path.join(HERE, '..', '..', '..', 'quicktest', 'odds', 'odds_1.0.0.json'));
const odds = oddsArg === 'none' ? null : path.resolve(oddsArg);
const serverDir = path.resolve(arg('--server-dir', path.join(HERE, '..')));
const serverOdds = arg('--server-odds') ? path.resolve(arg('--server-odds')) : odds;   // Server 設定檔與用戶端 odds 不同時（例 stage-demo：configs/stagedemo.json）
const engine = arg('--engine', 'huff');
const scenes = JSON.parse(arg('--scenes', '["feature",{"feat":"OH"},{"label":"Open House 到宮殿"}]'));
const spins = Number(arg('--spins', 3));
const out = path.resolve(arg('--out', path.join(os.tmpdir(), 'smoke-ws')));
const PY = process.env.PYTHON || 'python3';
fs.mkdirSync(out, { recursive: true });
const cdp = require(path.join(skill, 'scripts', 'tests', 'cdp.js'));
const checks = [];
const check = (name, ok, detail) => { checks.push({ name, ok: !!ok, ...(detail ? { detail } : {}) }); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${!ok && detail ? '：' + JSON.stringify(detail).slice(0, 400) : ''}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function freePort() { return new Promise((r) => { const s = http.createServer().listen(0, () => { const p = s.address().port; s.close(() => r(p)); }); }); }

(async () => {
  // 1. Server
  const port = await freePort();
  const bin = path.join(os.tmpdir(), `game-server-${process.pid}`);
  execFileSync('go', ['build', '-o', bin, './cmd/server'], { cwd: serverDir, stdio: 'inherit' });
  // -ws-max-inline 3000：正式 odds 下 6 萬局最長結果 7,551 字元、沒有超過單包上限，調小門檻以確實走到分段路徑
  const srvArgs = ['-dev', '-seed', '20261016', '-addr', `127.0.0.1:${port}`, '-engine', engine, '-balance', '1000000', '-ws-max-inline', arg('--ws-max-inline', '3000')];
  if (serverOdds) srvArgs.push('-odds', serverOdds);
  const srv = spawn(bin, srvArgs, { cwd: serverDir, stdio: ['ignore', 'ignore', 'pipe'] });
  let srvLog = '';
  srv.stderr.on('data', (d) => { srvLog += d; });
  for (let i = 0; i < 100; i++) { try { await new Promise((ok, no) => http.get(`http://127.0.0.1:${port}/healthz`, (r) => (r.statusCode === 200 ? ok() : no())).on('error', no)); break; } catch (_) { await sleep(100); } }
  // 2. Client（資料夾版）
  const dist = fs.mkdtempSync(path.join(os.tmpdir(), 'smoke-ws-dist-'));
  const bargs = [path.join(skill, 'scripts', 'stage', 'stage_build.py'), '--game', game, '--out', dist, '--service', JSON.stringify({ kind: 'ws' })];
  if (odds) bargs.push('--odds', odds);
  execFileSync(PY, bargs, { stdio: 'ignore' });
  const stat = await cdp.serve(dist);
  const arkId = `smoke-${Date.now().toString(36)}`;
  const url = `http://127.0.0.1:${stat.address().port}/index.html?service=ws&url=ws://127.0.0.1:${port}/ws&dev=1&ark_id=${arkId}`;
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 720, height: 1100 } });
  const errs = [];
  let missing404 = 0;                                   // 素材不在本機（試玩素材在 assets_base 外）→ 404，另計、不算錯誤
  p.on('pageerror', (e) => errs.push(`pageerror ${e.message}`));
  p.on('console', (m) => { if (m.type() !== 'error') return; if (/Failed to load resource: .*404/.test(m.text())) { missing404++; return; } errs.push(`console ${m.text()}`); });
  const start = async () => {
    await p.goto(url);
    await p.waitForSelector('.proto-start', { timeout: 60000 });
    await p.click('.proto-start');
    await p.waitForFunction(() => !!(window.Proto && Proto.app && Proto.app.module && Proto.app.module.state), null, { timeout: 60000 });
    await p.evaluate(() => Proto.setSpeed(8));
  };
  const serverBal = () => p.evaluate(() => Proto.app.service.balance());
  try {
    await start();
    const info = await p.evaluate(() => ({ kind: Proto.app.service.kind, seed: Proto.app.info.seed, supported: Proto.app.info.supported, metrics: Proto.app.metrics }));
    check('WsService 連線、init 帶 supported、不帶 seed', info.kind === 'ws' && info.seed === undefined && info.supported && info.supported.wire, info);
    check(`啟動指標 time_to_playable_ms = ${info.metrics && info.metrics.time_to_playable_ms}`, info.metrics && info.metrics.time_to_playable_ms > 0, info.metrics);
    for (let i = 0; i < spins; i++) {
      await p.evaluate(() => Proto.app.module.spin());
      await p.waitForFunction(() => !Proto.app.module.state.busy, null, { timeout: 120000 });
    }
    const hud = await p.evaluate(() => Proto.app.module.state.balance);
    check(`一般局 ${spins} 局：0 error、HUD 餘額 = Server 餘額`, errs.length === 0 && hud === (await serverBal()), { hud, errs: errs.slice(0, 3) });
    await p.screenshot({ path: path.join(out, '00-base.png') });
    for (const [i, sc] of scenes.entries()) {
      const e0 = errs.length;
      const r = await p.evaluate((sc) => {
        const m = Proto.app.module;
        return m.app.service.debug.force(sc, { bet: m.bet }).then((r) => {
          m.state.busy = true; m.clearWins(); m.state.shownWin = 0; m.view.spinStart();
          window.__done = m.play(r).then(() => { m.state.busy = false; m.state.balance = r.balanceAfter; m.renderHud(); return m.app.service.ack(r.roundId); });
          return { roundId: r.roundId, type: r.feature && r.feature.draw && r.feature.draw.type, balanceAfter: r.balanceAfter };
        });
      }, sc);
      await p.waitForTimeout(1500);
      await p.screenshot({ path: path.join(out, `${String(i + 1).padStart(2, '0')}-mid.png`) });
      await p.evaluate(() => { Proto.time.skip = true; });
      await p.evaluate(() => window.__done);
      await p.evaluate(() => { Proto.time.skip = false; });
      const hb = await p.evaluate(() => Proto.app.module.state.balance);
      check(`情境 ${JSON.stringify(sc)}：玩法 ${r.type}、0 error、HUD = balanceAfter = Server`, errs.length === e0 && hb === r.balanceAfter && hb === (await serverBal()) && (!sc.feat || r.type === sc.feat), { ...r, hb, errs: errs.slice(e0, e0 + 3) });
    }
    const st = await p.evaluate(() => Proto.app.service.svc.stats);
    check(`分段組回（chunked ${st.chunked}、fetched ${st.fetched}）`, st.chunked >= 1, st);
    // 4. 斷線續玩：直接向 Service 要一局（不演出、不 ack）→ 重新整理
    const pend = await p.evaluate(async () => { const r = await Proto.app.service.svc.spin({ bet: Proto.app.module.bet }); return { roundId: r.roundId, balanceAfter: r.balanceAfter }; });
    await start();
    await p.waitForFunction(() => Proto.app.info && Proto.app.module && !Proto.app.module.state.busy, null, { timeout: 120000 });
    await p.waitForTimeout(500);
    const after = await p.evaluate(async () => ({ pending: Proto.app.info.pending && Proto.app.info.pending.roundId, hud: Proto.app.module.state.balance, again: (await Proto.app.service.svc.init()).pending }));
    check('斷線續玩：init 帶 pending → 先播、HUD = balanceAfter、ack 後清除', after.pending === pend.roundId && after.hud === pend.balanceAfter && after.again === null && after.hud === (await serverBal()), { pend, after });
    // 5. 連線中斷 → 自動重連
    await p.evaluate(() => Proto.app.service.svc.conn.ws.close());
    await p.waitForTimeout(300);
    await p.evaluate(() => Proto.app.module.spin());
    await p.waitForFunction(() => !Proto.app.module.state.busy, null, { timeout: 120000 });
    const rc = await p.evaluate(() => ({ state: Proto.app.service.svc.conn.state, reconnects: Proto.app.service.svc.conn.stats.reconnects, hud: Proto.app.module.state.balance }));
    check('連線中斷後自動重連、下一局正常', rc.state === 'authed' && rc.reconnects >= 1 && rc.hud === (await serverBal()) && errs.filter((e) => !/WebSocket/.test(e)).length === 0, rc);
  } catch (e) {
    check('執行', false, { error: String(e && e.stack || e).slice(0, 500) });
  } finally {
    const rep = { schema: 'web-game-smoke-ws/1', game, odds, engine, pass: checks.every((c) => c.ok), checks, errors: errs, missingAssets404: missing404 };
    fs.writeFileSync(path.join(out, 'smoke-ws.json'), JSON.stringify(rep, null, 1) + '\n');
    await b.close(); stat.close(); srv.kill();
    try { fs.unlinkSync(bin); } catch (_) { /* */ }
    if (!rep.pass && srvLog) console.log('server log:\n' + srvLog.slice(-1500));
    console.log(`${rep.pass ? '✅' : '❌'} smoke_ws：${checks.filter((c) => c.ok).length}/${checks.length} PASS → ${path.join(out, 'smoke-ws.json')}`);
    process.exit(rep.pass ? 0 : 1);
  }
})().catch((e) => { console.error(e); process.exit(1); });
