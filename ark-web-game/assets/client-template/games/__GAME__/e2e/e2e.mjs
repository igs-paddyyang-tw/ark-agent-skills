#!/usr/bin/env node
// 正式 Client 端到端（Playwright）：dist/ ⇄ 真 Go Server（-dev）。遊戲差異全在 e2e.config.json（ark-web-game client-template 通用）
//   node e2e/e2e.mjs [--config e2e/e2e.config.json] [--grep main|features|pending|protocol|trace-parity] [--server-dir <go-server>] [--server-bin <已建置執行檔>]
//        [--aidev <aidev 根>（trace-parity 用 Stage）] [--spins 50] [--speed 30] [--out <報告.json>] [--shots <截圖資料夾>]
//   e2e.config.json：game、arkIdPrefix、serverDir（相對 aidev 根）、serverArgs、scenes[{scene, expect（feature.script.type）}]、expectChunked、stage{game, odds}
//   dist 要用素材建置：PGP_ASSETS_DIR=<wg_pack_assets 的 --out> pnpm --filter <game> build（各情境另檢查素材 0 個 4xx、背景載入完成）
//   情境：
//     main          連線、50 局、餘額＝最後 balanceAfter＝Server 餘額、0 頁面錯誤、time_to_playable_ms
//     features      依 config.scenes 逐一強制情境，經真 Server（expectChunked 時檢查結果分段組回）
//     pending       結算後未 ack 就關頁 → 重開同帳號：先播 pending、ack，Server 不再帶 pending
//     protocol      協定不相容 → 啟動停在 error（PROTOCOL_MISMATCH）
//     trace-parity  同一份軌跡（main＋features 錄下）在 Stage 與正式 Client 重播，present-events 完全相同
//   exit：0 全過；1 有失敗；2 環境不足（沒有 playwright／Go Server／dist）
import { spawn, execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const here = path.dirname(fileURLToPath(import.meta.url));
const a = process.argv.slice(2);
const arg = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
const grep = arg('--grep', '');
const spins = Number(arg('--spins', 50));
const speed = Number(arg('--speed', 30));
const dist = path.resolve(arg('--dist', path.join(here, '..', 'dist')));
const CFG = JSON.parse(fs.readFileSync(path.resolve(arg('--config', path.join(here, 'e2e.config.json'))), 'utf8'));
const aidev = arg('--aidev', process.env.AIDEV_ROOT || '');
const serverDir = arg('--server-dir', process.env.PGP_SERVER_DIR || (aidev && CFG.serverDir ? path.join(aidev, CFG.serverDir) : ''));
const ID = (s) => `${CFG.arkIdPrefix || 'e2e'}-${s}`;
let chromium;
try { ({ chromium } = require('playwright')); } catch { console.log('SKIP：沒有 playwright'); process.exit(2); }
if (!fs.existsSync(path.join(dist, 'index.html'))) { console.error(`找不到 ${dist}/index.html（先 pnpm --filter ${CFG.game} build）`); process.exit(2); }

const results = [];
const check = (name, ok, detail) => { results.push({ name, ok: !!ok, detail }); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : '  ' + JSON.stringify(detail).slice(0, 400)}`); };
const want = (n) => !grep || grep.split('|').includes(n);
const freePort = () => new Promise((r) => { const s = http.createServer(); s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => r(p)); }); });
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json', '.map': 'application/json', '.png': 'image/png', '.webp': 'image/webp', '.css': 'text/css', '.mp3': 'audio/mpeg' };
function staticServer(root, extra = {}) {
  const s = http.createServer((req, res) => {
    const u = decodeURIComponent(req.url.split('?')[0]);
    if (extra[u]) { res.writeHead(200, { 'content-type': 'application/json' }); res.end(extra[u]); return; }
    const f = path.join(root, u.endsWith('/') ? u + 'index.html' : u);
    if (!f.startsWith(root) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'content-type': MIME[path.extname(f)] || 'application/octet-stream' });
    fs.createReadStream(f).pipe(res);
  });
  return new Promise((r) => s.listen(0, '127.0.0.1', () => r({ s, url: `http://127.0.0.1:${s.address().port}` })));
}
async function goServer(port, extraArgs = []) {
  let bin = arg('--server-bin', '');
  if (!bin) {
    if (!serverDir || !fs.existsSync(serverDir)) { console.error(`需要 --server-dir 或 --server-bin（${CFG.game} 的 Go Server）`); process.exit(2); }
    bin = path.join(os.tmpdir(), `${CFG.game}-e2e-srv${process.platform === 'win32' ? '.exe' : ''}`);
    execFileSync('go', ['build', '-o', bin, './cmd/server'], { cwd: serverDir, stdio: 'inherit' });
  }
  const p = spawn(bin, [...(CFG.serverArgs || ['-dev']), '-addr', `127.0.0.1:${port}`, ...extraArgs], { cwd: serverDir || path.dirname(bin), stdio: ['ignore', 'ignore', 'pipe'] });
  let err = '';
  p.stderr.on('data', (d) => { err += d; });
  for (let i = 0; i < 100; i++) {
    const ok = await new Promise((r) => { const q = http.get(`http://127.0.0.1:${port}/healthz`, (res) => { res.resume(); r(true); }); q.on('error', () => r(false)); });
    if (ok) return p;
    await new Promise((r) => setTimeout(r, 100));
  }
  p.kill();
  throw new Error(`Go Server 啟動失敗：${err.slice(-500)}`);
}

const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const port = await freePort();
const srv = await goServer(port);
const web = await staticServer(dist);
const wsUrl = `ws://127.0.0.1:${port}/ws`;
const open = async (query, opts = {}) => {
  const page = await browser.newPage({ viewport: { width: 540, height: 960 } });
  const errs = [];
  page.on('response', (r) => { if (r.status() >= 400) errs.push(`HTTP ${r.status()} ${r.url()}`); });
  page.on('pageerror', (e) => errs.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  await page.goto(`${opts.base || web.url}/?${query}`);
  await page.waitForFunction(() => window.__pgp && ['playable', 'error'].includes(window.__pgp.boot.state), null, { timeout: 60000 });
  return { page, errs };
};
const report = { schema: 'pgp-e2e/1', game: CFG.game, at: new Date().toISOString(), server: { port, flags: (CFG.serverArgs || []).join(' ') }, metrics: {} };
let trace = null;

try {
  if (want('main') || want('features') || want('trace-parity')) {
    const { page, errs } = await open(`service=ws&url=${encodeURIComponent(wsUrl)}&arkId=${ID('main')}&dev&speed=${speed}`);
    check('main：啟動到 playable', await page.evaluate(() => window.__pgp.boot.state) === 'playable', await page.evaluate(() => window.__pgp.boot.error));
    const m = await page.evaluate(() => window.__pgp.boot.metrics);
    report.metrics = m;
    check(`main：time_to_playable_ms = ${m.time_to_playable_ms}`, m.time_to_playable_ms > 0, m);
    if (want('main') || want('trace-parity')) {
      const out = await page.evaluate(async (n) => {
        const P = window.__pgp, rs = [];
        for (let i = 0; i < n; i++) { const r = await P.spin(); rs.push(r && { roundId: r.roundId, bal: r.balanceAfter, feat: r.feature && r.feature.script.type }); }
        return { rs, hud: P.hud.balance, server: await P.service.balance(), events: P.presentLog.length };
      }, spins);
      const last = out.rs[out.rs.length - 1];
      check(`main：${spins} 局都有結果`, out.rs.every(Boolean), out.rs.filter((x) => !x).length);
      check('main：HUD 餘額＝最後 balanceAfter＝Server 餘額', last && out.hud === last.bal && out.server === last.bal, { hud: out.hud, last: last && last.bal, server: out.server });
      check('main：每局 present-events 以 round-start 開始、round-end 結束', out.events >= spins * 3, out.events);
      report.main = { spins, features: out.rs.filter((x) => x && x.feat).length, events: out.events };
    }
    if (want('features') || want('trace-parity')) {
      for (const sc of CFG.scenes || []) {
        const r = await page.evaluate(async (s) => { const x = await window.__pgp.force(s); return { type: x.feature && x.feature.script && x.feature.script.type, win: x.feature && x.feature.win, bal: x.balanceAfter, hud: window.__pgp.hud.balance, ev: window.__pgp.presentLog.slice(-5).map((e) => e.type) }; }, sc.scene);
        check(`features：強制 ${JSON.stringify(sc.scene)} → 玩法 ${r.type}、餘額 ${r.hud}`, (sc.expect === undefined || r.type === sc.expect) && r.hud === r.bal && r.ev.includes('feature-start') && r.ev.includes('feature-end'), r);
      }
      const st = await page.evaluate(() => window.__pgp.service.stats);
      if (CFG.expectChunked) check(`features：真 Server 分段結果組回（chunked ${st.chunked}、fetched ${st.fetched}）`, st.chunked > 0, st);
      report.features = { stats: st };
      if (arg('--shots')) await page.screenshot({ path: path.join(arg('--shots'), 'e2e-main.png') });
    }
    const tel = await page.evaluate(() => window.__pgp.telemetry);
    const am = (tel.find((t) => t.name === 'assets') || {}).data;
    report.assets = am;
    check(`main：素材必要包 ${am?.core_bundle_ms} ms、背景載完 ${am?.background_done_ms} ms、音效失敗 ${am?.audio_failed}`, am && am.asset_fail === undefined && am.audio_failed === 0, am);
    check('main：0 頁面錯誤、素材 0 個 4xx', errs.length === 0, errs.slice(0, 5));
    trace = await page.evaluate(() => window.__pgp.trace());
    await page.close();
  }

  if (want('pending')) {
    const q = `service=ws&url=${encodeURIComponent(wsUrl)}&arkId=${ID('pend')}&dev&speed=${speed}`;
    const A = await open(q);
    const rid = await A.page.evaluate(async () => (await window.__pgp.service.spin({ bet: window.__pgp.hud.bet })).roundId);   // 結算但未播放、未 ack
    await A.page.close();
    const B = await open(q);
    await B.page.waitForFunction(() => window.__pgp.boot.state === 'playable');
    const r = await B.page.evaluate(async () => ({ first: window.__pgp.presentLog[0], end: window.__pgp.presentLog.find((e) => e.type === 'round-end'), info: window.__pgp.info.pending && window.__pgp.info.pending.roundId, again: (await window.__pgp.service.init()).pending, hud: window.__pgp.hud.balance }));
    check('pending：重開先播上一局（round-start 局號相同）', r.first && r.first.roundId === rid && r.info === rid, { rid, r });
    check('pending：餘額＝該局 balanceAfter；ack 後 Server 不再帶 pending', r.end && r.hud === r.end.balanceAfter && r.again === null, r);
    check('pending：0 頁面錯誤', A.errs.length + B.errs.length === 0, [...A.errs, ...B.errs]);
    await B.page.close();
  }

  if (want('protocol')) {
    const { page } = await open(`service=ws&url=${encodeURIComponent(wsUrl)}&arkId=${ID('proto')}&proto_result=proto-stage-result/9`);
    const b = await page.evaluate(() => ({ state: window.__pgp.boot.state, error: window.__pgp.boot.error, text: document.getElementById('boot').textContent }));
    check('protocol：協定不相容 → 停在 error（PROTOCOL_MISMATCH），畫面有說明', b.state === 'error' && b.error.code === 'PROTOCOL_MISMATCH' && b.text.includes('PROTOCOL_MISMATCH'), b);
    await page.close();
  }

  if (want('trace-parity')) {
    if (!trace) throw new Error('trace-parity 需要先跑 main／features 錄軌跡');
    const tr = JSON.stringify(trace);
    report.traceRounds = trace.results.length;
    // 正式 Client：ReplayService 播同一份軌跡
    const web2 = await staticServer(dist, { '/trace.json': tr });
    const P = await open(`service=replay&trace=/trace.json&speed=${speed}`, { base: web2.url });
    const prod = await P.page.evaluate(async (n) => { for (let i = 0; i < n; i++) await window.__pgp.spin(); return window.__pgp.presentLog; }, trace.results.length);
    await P.page.close(); web2.s.close();
    // Stage：用 config.stage 的遊戲包建資料夾版（素材不在本機時只缺圖，不影響事件），逐局呼叫 module.play
    let stage = null;
    if (aidev && CFG.stage) {
      const tmp = fs.mkdtempSync(path.join(os.tmpdir(), `${CFG.game}-stage-`));
      execFileSync(process.env.PYTHON || 'python3', [path.join(aidev, '.kiro/skills/ark-game-proto/scripts/stage/stage_build.py'), '--game', path.join(aidev, CFG.stage.game), ...(CFG.stage.odds ? ['--odds', path.join(aidev, CFG.stage.odds)] : []), '--out', tmp], { stdio: 'ignore' });
      const sw = await staticServer(tmp);
      const page = await browser.newPage({ viewport: { width: 540, height: 960 } });
      await page.goto(`${sw.url}/index.html`);
      await page.waitForSelector('.proto-start', { timeout: 60000 });
      await page.click('.proto-start');
      await page.waitForFunction(() => !!(window.Proto && Proto.app && Proto.app.module && Proto.app.module.state && !Proto.app.module.state.busy), null, { timeout: 60000 });
      stage = await page.evaluate(async ({ results, s }) => {
        Proto.setSpeed(s);
        const log = [];
        Proto.app.events.on('present', (e) => log.push(e));
        for (const r of results) { Proto.app.module.clearWins(); await Proto.app.module.play(r); }   // 同 module.spin()：先清連線再播
        return log;
      }, { results: trace.results, s: speed });
      await page.close(); sw.s.close();
    }
    const same = stage && JSON.stringify(stage) === JSON.stringify(prod);
    let firstDiff = null;
    if (stage && !same) for (let i = 0; i < Math.max(stage.length, prod.length); i++) if (JSON.stringify(stage[i]) !== JSON.stringify(prod[i])) { firstDiff = { i, stage: stage[i], prod: prod[i] }; break; }
    check(`trace-parity：${trace.results.length} 局 present-events Stage ${stage ? stage.length : '—'} 筆 ＝ 正式 Client ${prod.length} 筆`, same, stage ? firstDiff : '需要 --aidev 與 config.stage（Stage 遊戲包）');
    report.traceParity = { rounds: trace.results.length, events: prod.length, same: !!same };
  }
} catch (e) {
  check('執行', false, String(e && e.stack || e));
} finally {
  await browser.close();
  srv.kill();
  web.s.close();
}
report.results = results;
report.ok = results.every((r) => r.ok);
if (arg('--out')) fs.writeFileSync(arg('--out'), JSON.stringify(report, null, 1));
console.log(`${report.ok ? 'OK' : 'FAIL'}：${results.filter((r) => r.ok).length}/${results.length}`);
process.exit(report.ok ? 0 : 1);
