#!/usr/bin/env node
// Stage 冒煙測試（真瀏覽器）：開頁 → 開始 → 一般局 → 各強制情境 → 截圖、收頁面錯誤、帳務檢查、量 FPS
//   node smoke.js --html <index.html 或其資料夾> [--out shots/] [--scenes '["feature",{"label":"Open House"}]' | all] [--speed 6] [--spins 3]
//                 [--backend auto|playwright|cdp] [--browser <chrome/msedge>] [--mid 2500] [--query 'seed=7&rng=go']
// 後端：auto = 有 Playwright 用 Playwright，否則用系統 Chrome / Edge（../../tests/cdp.js，DevTools 協定、零相依）。
//   兩者都沒有 → 印 SKIP、exit 0（加 --strict 改 exit 2）。頁面一律經內建靜態伺服器載入（資料夾版需要 http）。
// --scenes all = 內建情境「玩法局」＋ 遊戲包 presentation.stage.scenes 全部（函式情境在頁內依名稱取用）。
// 每個情境檢查：演完不逾時、0 頁面錯誤、帳務（餘額 = 結果 balanceAfter）、{feat} 情境的玩法種類相符。exit 0 全過 / 1 有 FAIL。
'use strict';
const path = require('path');
const fs = require('fs');
const cdp = require('../../tests/cdp.js');

const a = process.argv.slice(2);
const arg = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
let html = path.resolve(arg('--html', ''));
if (fs.existsSync(html) && fs.statSync(html).isDirectory()) html = path.join(html, 'index.html');
if (!fs.existsSync(html)) { console.error('需要 --html <index.html>'); process.exit(2); }
const out = path.resolve(arg('--out', path.join(path.dirname(html), 'smoke-shots')));
const scenesArg = arg('--scenes', '["feature"]');
const speed = Number(arg('--speed', 6));
const spins = Number(arg('--spins', 3));
const mid = Number(arg('--mid', 2500));
const backend = arg('--backend', 'auto');
const strict = a.includes('--strict');
const query = arg('--query', '');
fs.mkdirSync(out, { recursive: true });

async function open() {
  if (backend !== 'cdp') {
    try {
      const { chromium } = require('playwright');
      const srv = await cdp.serve(path.dirname(html));
      const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
      const p = await b.newPage({ viewport: { width: 720, height: 1100 } });
      const errors = [];
      p.on('pageerror', (e) => errors.push(`pageerror ${e.message}`));
      p.on('console', (m) => { if (m.type() === 'error') errors.push(`console ${m.text()}`); });
      p.errors = errors;
      return { kind: 'playwright', version: b.version(), p, url: `http://127.0.0.1:${srv.address().port}/${path.basename(html)}`, close: async () => { await b.close(); srv.close(); } };
    } catch (e) { if (backend === 'playwright') throw e; }
  }
  const b = await cdp.launch({ root: path.dirname(html), browser: arg('--browser') });
  const p = await b.newPage({ viewport: { width: 720, height: 1100 } });
  return { kind: 'cdp', version: b.version, p, url: b.url(path.basename(html)), close: () => b.close() };
}

(async () => {
  let B;
  try { B = await open(); } catch (e) {
    if (e instanceof cdp.CdpEnvError || /Cannot find module 'playwright'/.test(e.message)) { console.log(`SKIP：沒有可用瀏覽器（${e.message}）`); process.exit(strict ? 2 : 0); }
    throw e;
  }
  const p = B.p, errs = p.errors, checks = [];
  const check = (name, ok, detail) => { checks.push({ name, ok: !!ok, ...(detail ? { detail } : {}) }); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${!ok && detail ? '：' + JSON.stringify(detail).slice(0, 300) : ''}`); };
  await p.goto(B.url + (query ? '?' + query.replace(/^\?/, '') : ''));
  await p.waitForSelector('.proto-start', { timeout: 60000 });
  await p.click('.proto-start');
  await p.waitForFunction(() => !!(window.Proto && Proto.app && Proto.app.module && Proto.app.module.state), null, { timeout: 60000 });
  await p.evaluate((s) => Proto.setSpeed(s), speed);
  const game = await p.evaluate(() => `${Proto.app.config.name || Proto.app.config.slug} · ${Proto.app.service.kind}`);
  for (let i = 0; i < spins; i++) {
    await p.evaluate(() => Proto.app.module.spin());
    await p.waitForFunction(() => !Proto.app.module.state.busy, null, { timeout: 120000 });
  }
  check(`一般局 ${spins} 局`, errs.length === 0, errs.length ? { errors: errs.slice(0, 3) } : null);
  await p.screenshot({ path: path.join(out, '00-base.png') });
  const scenes = scenesArg === 'all'
    ? ['feature', ...(await p.evaluate(() => ((Proto.app.module.pres.stage && Proto.app.module.pres.stage.scenes) || []).map(([l]) => l))).map((label) => ({ label }))]
    : JSON.parse(scenesArg);
  const res = [];
  for (const [i, sc] of scenes.entries()) {
    const tag = String(i + 1).padStart(2, '0'), e0 = errs.length, t0 = Date.now();
    let r;
    try {
      r = await p.evaluate((sc) => {
        const m = Proto.app.module;
        const cfg = (m.pres.stage && m.pres.stage.scenes) || [];
        const hit = sc && sc.label ? cfg.find(([l]) => l === sc.label) : null;
        if (sc && sc.label && !hit) throw new Error('遊戲包沒有情境 ' + sc.label);
        const scene = hit ? hit[1] : sc;
        return m.app.service.debug.force(scene, { bet: m.bet }).then((r) => {
          m.state.busy = true; m.clearWins(); m.state.shownWin = 0; m.view.spinStart();
          window.__done = m.play(r).then(() => { m.state.busy = false; m.state.balance = r.balanceAfter; m.renderHud(); });
          const want = scene && typeof scene === 'object' ? scene.feat : null;
          const f = r.feature || null;
          return { roundId: r.roundId, totalWin: r.totalWin, balanceAfter: r.balanceAfter, feature: f && (f.draw ? f.draw.type : f.type), group: f && f.group, want };
        });
      }, sc);
      await p.waitForTimeout(mid);
      await p.screenshot({ path: path.join(out, `${tag}-mid.png`) });
      await p.waitForFunction(() => !Proto.app.module.state.busy, null, { timeout: 300000 });
      await p.evaluate(() => window.__done);
      await p.screenshot({ path: path.join(out, `${tag}-end.png`) });
      const bal = await p.evaluate(() => Proto.app.module.state.balance);
      const name = sc && sc.label ? sc.label : JSON.stringify(sc);
      check(`情境 ${name}：演完、0 頁面錯誤、餘額 = balanceAfter${r.want ? `、玩法 = ${r.want}` : ''}`,
        errs.length === e0 && bal === r.balanceAfter && (!r.want || r.feature === r.want),
        { sec: Math.round((Date.now() - t0) / 1000), feature: r.feature, balance: bal, balanceAfter: r.balanceAfter, errors: errs.slice(e0, e0 + 3) });
      res.push({ scene: sc, ...r, balance: bal, sec: Math.round((Date.now() - t0) / 1000) });
    } catch (e) {
      check(`情境 ${JSON.stringify(sc)}`, false, { error: e.message });
    }
  }
  const fps = await p.evaluate(() => Proto.app.stage.fps());
  const rep = { schema: 'proto-stage-smoke/2', game, html, backend: B.kind, browser: B.version, pass: checks.every((c) => c.ok), checks, scenes: res, fps: Math.round(fps * 10) / 10, errors: errs };
  fs.writeFileSync(path.join(out, 'smoke.json'), JSON.stringify(rep, null, 1));
  await B.close();
  console.log(`${rep.pass ? '✅' : '❌'} smoke：${game}｜${B.kind} ${B.version}｜${checks.filter((c) => c.ok).length}/${checks.length} PASS｜FPS ${rep.fps}｜截圖 → ${out}`);
  process.exit(rep.pass ? 0 : 1);
})().catch((e) => { console.error(e); process.exit(1); });
