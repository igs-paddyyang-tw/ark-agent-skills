#!/usr/bin/env node
// Stage 冒煙測試（Playwright + Chromium，WebGL 用 SwiftShader）：開頁 → 開始 → 一般局 → 各強制情境 → 截圖、收 console error、量 FPS
//   node smoke.js --html <index.html> [--out shots/] [--scenes '["feature",{"minX":10}]'] [--speed 6] [--spins 3]
//   沒有 Playwright 時 exit 0 並註明 skip（CI 以外的機器不強制）
'use strict';
const path = require('path');
const fs = require('fs');
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { console.log('SKIP：未安裝 playwright（npm i -g playwright）'); process.exit(0); }
const a = process.argv.slice(2);
const arg = (k, d) => { const i = a.indexOf(k); return i >= 0 ? a[i + 1] : d; };
const html = path.resolve(arg('--html', ''));
const out = path.resolve(arg('--out', 'smoke-shots'));
const scenes = JSON.parse(arg('--scenes', '["feature"]'));
const speed = Number(arg('--speed', 6));
const spins = Number(arg('--spins', 3));
fs.mkdirSync(out, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 720, height: 1100 } });
  const errs = [];
  p.on('pageerror', (e) => errs.push(`pageerror ${e.message}`));
  p.on('console', (m) => { if (m.type() === 'error') errs.push(`console ${m.text()}`); });
  await p.goto((html.startsWith('http') ? '' : 'file://') + html);
  await p.waitForSelector('.proto-start', { timeout: 60000 });
  await p.click('.proto-start');
  await p.evaluate((s) => Proto.setSpeed(s), speed);
  const res = [];
  for (let i = 0; i < spins; i++) {
    await p.evaluate(() => Proto.app.module.spin());
    await p.waitForFunction(() => !Proto.app.module.state.busy, null, { timeout: 120000 });
  }
  await p.screenshot({ path: path.join(out, '00-base.png') });
  for (const [i, sc] of scenes.entries()) {
    const r = await p.evaluate((sc) => {
      const m = Proto.app.module;
      const scenesCfg = (m.pres.stage && m.pres.stage.scenes) || [];
      const hit = sc && sc.label ? scenesCfg.find(([l]) => l === sc.label) : null;
      return m.app.service.debug.force(hit ? hit[1] : sc, { bet: m.bet }).then((r) => {
        m.state.busy = true; m.clearWins(); m.state.shownWin = 0; m.view.spinStart();
        window.__done = m.play(r).then(() => { m.state.busy = false; m.state.balance = r.balanceAfter; m.renderHud(); });
        return { roundId: r.roundId, totalWin: r.totalWin, feature: r.feature && r.feature.type, group: r.feature && r.feature.group };
      });
    }, sc);
    await p.waitForTimeout(2500);
    await p.screenshot({ path: path.join(out, `${String(i + 1).padStart(2, '0')}-mid.png`) });
    await p.evaluate(() => window.__done);
    await p.screenshot({ path: path.join(out, `${String(i + 1).padStart(2, '0')}-end.png`) });
    const bal = await p.evaluate(() => Proto.app.module.state.balance);
    res.push({ scene: sc, ...r, balance: bal });
  }
  const fps = await p.evaluate(() => Proto.app.stage.fps());
  const rep = { html, scenes: res, fps: Math.round(fps * 10) / 10, errors: errs };
  fs.writeFileSync(path.join(out, 'smoke.json'), JSON.stringify(rep, null, 1));
  console.log(JSON.stringify(rep, null, 1));
  await b.close();
  console.log(errs.length ? `❌ smoke：${errs.length} 個 console error` : `✅ smoke：${res.length} 個情境，0 error`);
  process.exit(errs.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
