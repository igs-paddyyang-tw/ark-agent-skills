#!/usr/bin/env node
// 驗證台真瀏覽器驗收（node tests/browser_check.js <含 index.html 的資料夾> [選項]）
//
// 用系統已安裝的 Chrome / Edge 無頭模式 + DevTools 協定（Node 22 內建 WebSocket，零 npm 相依）：
//   載入 proto_build 產出的 index.html → 面板檢查（L1 / 缺口 / Go 對照）→ 每種玩法各找 seed 演一場並逐段截圖
//   → 單局分頁 → L2 蒙地卡羅 → 輸出 <out>/browser-check.json + *.png。
// 規格：docs/specs/2026-10-19-ark-game-proto-browser-check-spec.md
//
// 選項：--out <dir>（預設 <資料夾>/browser-check）  --browser <exe>（或環境變數 CHROME_PATH）
//       --turbo（快速演出）  --interval <ms>（截圖間隔，預設 2500）  --max-shots <n>（每場上限，預設 60）
//       --l2 <手數>（預設 200000；0 = 不跑）  --groups <a,b>（只驗這些玩法）
// exit：0 全過 / 1 有 FAIL / 2 環境不足（找不到瀏覽器或 index.html）
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');

const argv = process.argv.slice(2);
const opt = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const flag = (k) => argv.includes(k);
const dir = argv[0] && !argv[0].startsWith('--') ? path.resolve(argv[0]) : null;
const envFail = (msg) => { console.error('ENV ' + msg); process.exit(2); };
if (!dir || !fs.existsSync(path.join(dir, 'index.html'))) envFail('用法：node tests/browser_check.js <含 index.html 的資料夾>（proto_build --out 的輸出）');
if (typeof WebSocket === 'undefined') envFail('需要 Node 22+（內建 WebSocket）');
const OUT = path.resolve(opt('--out', path.join(dir, 'browser-check')));
const INTERVAL = +opt('--interval', 2500), MAX_SHOTS = +opt('--max-shots', 60), L2N = +opt('--l2', 200000);
const ONLY = opt('--groups', '') ? opt('--groups').split(',') : null;
fs.mkdirSync(OUT, { recursive: true });

// ── 找瀏覽器 ──
function findBrowser() {
  const given = opt('--browser') || process.env.CHROME_PATH;
  if (given) return fs.existsSync(given) ? given : envFail(`找不到瀏覽器 ${given}（--browser 或 CHROME_PATH 指向 chrome / msedge 執行檔）`);
  const pf = [process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA].filter(Boolean);
  const cands = [
    ...pf.flatMap((p) => [path.join(p, 'Google/Chrome/Application/chrome.exe'), path.join(p, 'Microsoft/Edge/Application/msedge.exe')]),
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/microsoft-edge',
  ];
  return cands.find((c) => fs.existsSync(c)) || envFail('找不到 Chrome / Edge / Chromium（用 --browser 或 CHROME_PATH 指定）');
}

// ── 靜態檔伺服器（隨機埠）──
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml' };
function serve() {
  const srv = http.createServer((req, res) => {
    const p = path.normalize(path.join(dir, decodeURIComponent(req.url.split('?')[0]))).replace(/[\\/]$/, '');
    const f = p === dir ? path.join(dir, 'index.html') : p;
    if (!f.startsWith(dir) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' });
    fs.createReadStream(f).pipe(res);
  });
  return new Promise((r) => srv.listen(0, '127.0.0.1', () => r(srv)));
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [], shots = [];
const check = (name, ok, detail) => { results.push({ name, ok: !!ok, ...(detail != null ? { detail } : {}) }); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail != null && !ok ? '：' + JSON.stringify(detail).slice(0, 300) : ''}`); };

(async () => {
  const exe = findBrowser();
  const srv = await serve();
  const url = `http://127.0.0.1:${srv.address().port}/index.html`;
  const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'proto-bc-'));
  const br = spawn(exe, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${prof}`, '--no-first-run', '--no-default-browser-check',
    '--window-size=1400,1000', '--enable-unsafe-swiftshader', 'about:blank'], { stdio: 'ignore' });
  const cleanup = () => { try { br.kill(); } catch {} srv.close(); setTimeout(() => { try { fs.rmSync(prof, { recursive: true, force: true }); } catch {} }, 800); };
  try {
    // DevTools 埠：Chrome 以 --remote-debugging-port=0 自選，寫在 profile/DevToolsActivePort
    let port = null;
    for (let i = 0; i < 60 && !port; i++) { await sleep(250); try { port = fs.readFileSync(path.join(prof, 'DevToolsActivePort'), 'utf8').split('\n')[0].trim(); } catch {} }
    if (!port) envFail(`瀏覽器沒有開出 DevTools 埠（${exe}）`);
    const ver = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
    const tgt = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
    const ws = new WebSocket(tgt.webSocketDebuggerUrl);
    await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
    let id = 0; const pend = {}, errs = [];
    ws.onmessage = (m) => {
      const d = JSON.parse(m.data);
      if (d.id && pend[d.id]) { pend[d.id](d); delete pend[d.id]; }
      if (d.method === 'Runtime.exceptionThrown') errs.push('exception: ' + (d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text));
      if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error') errs.push('console.error: ' + d.params.args.map((a) => a.value || a.description).join(' '));
      if (d.method === 'Network.loadingFailed' && !d.params.canceled && !/cdn\.jsdelivr/.test(d.params.errorText + (d.params.url || ''))) errs.push('loadingFailed: ' + d.params.errorText);
    };
    const send = (method, params = {}) => new Promise((r) => { const i = ++id; pend[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
    const ev = async (expr) => { const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true }); if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || 'evaluate 失敗'); return r.result?.result?.value; };
    const shot = async (name) => { const r = await send('Page.captureScreenshot', { format: 'png' }); const f = name + '.png'; fs.writeFileSync(path.join(OUT, f), Buffer.from(r.result.data, 'base64')); shots.push(f); };
    const tab = (t) => ev(`(document.querySelector('.tabs button[data-tab="${t}"]')||{click(){}}).click()`);
    await send('Runtime.enable'); await send('Page.enable'); await send('Network.enable');
    await send('Emulation.setDeviceMetricsOverride', { width: 1400, height: 1000, deviceScaleFactor: 1, mobile: false });
    await send('Page.navigate', { url });
    let up = false;
    for (let i = 0; i < 120 && !up; i++) { await sleep(500); try { up = await ev('!!(window.__proto && window.__proto.C)'); } catch {} }
    check('頁面載入、驗證台啟動（window.__proto）', up, up ? null : errs.slice(0, 3));
    if (!up) throw new Error('stop');
    await sleep(1200);
    await shot('00-load');
    const game = await ev('window.GAME_CONFIG.game + " · " + window.__proto.C.model');
    // 面板
    for (const p of ['l1', 'gaps', 'go']) {
      await tab(p); await sleep(250);
      const h = await ev(`document.querySelector('#pane-${p}').innerHTML`);
      check(`#pane-${p} 有內容且無 undefined / NaN`, h && h.length > 50 && !/undefined|NaN/.test(h));
      await shot(`01-${p}`);
    }
    const chip = await ev(`document.querySelector('#chipL1').innerText`);
    check('L1 總 RTP 判定不是 FAIL', !/FAIL/.test(chip), chip);
    if (flag('--turbo')) await ev(`document.querySelector('#btnTurbo').click()`);
    // 每種玩法各演一場
    const groups = (await ev('window.__proto.C.G')).filter((g) => !ONLY || ONLY.includes(g));
    const seeds = await ev(`(() => { const P = window.__proto, S = P.SlotCore, C = P.C, want = ${JSON.stringify(groups)}, out = { __none: null };
      want.forEach((g) => (out[g] = null));
      for (let s = 1; s < 4e6 && Object.values(out).some((v) => v == null); s++) { const r = S.spin(C, s), k = r.fg ? r.fg.group : '__none'; if (k in out && out[k] == null) out[k] = s; }
      return out; })()`);
    await tab('spin');
    for (const [g, seed] of Object.entries(seeds)) {
      const label = g === '__none' ? '主遊戲' : g;
      if (seed == null) { check(`找到 ${label} 的 seed`, false); continue; }
      const e0 = errs.length, t0 = Date.now();
      ev(`window.__proto.playSeed(${seed})`).catch((e) => errs.push('playSeed: ' + e.message));
      let k = 0, done = false;
      while (k < MAX_SHOTS) {
        await sleep(k < 1 ? 1200 : INTERVAL);
        await shot(`play-${g.replace(/[^\w-]/g, '_')}-${String(++k).padStart(2, '0')}`);
        if (!(await ev('window.__proto.busy'))) { done = true; break; }
      }
      const spinPane = await ev(`document.querySelector('#pane-spin').innerHTML`);
      check(`演一局 ${label}（seed ${seed}）：演完、無頁面錯誤、抽表軌跡無 undefined / NaN`,
        done && errs.length === e0 && spinPane.includes(`seed ${seed}`) && !/undefined|NaN/.test(spinPane),
        { seed, shots: k, sec: Math.round((Date.now() - t0) / 1000), errors: errs.slice(e0, e0 + 3) });
      while (await ev('window.__proto.busy')) await sleep(500);
    }
    await shot('90-spin-tab');
    // L2
    if (L2N > 0) {
      await tab('l2');
      await ev(`window.__proto.runL2(${L2N})`);
      let fin = false;
      for (let i = 0; i < 600 && !fin; i++) { await sleep(1000); fin = /完成/.test(await ev(`(document.querySelector('#l2status')||{}).textContent||''`)); }
      const row = await ev(`(() => { const t = document.querySelectorAll('#l2body table tr'); return t[1] ? t[1].innerHTML : ''; })()`);
      check(`L2 蒙地卡羅 ${L2N.toLocaleString('en-US')} 手完成，總 RTP 判定不是 FAIL`, fin && row.includes('總 RTP') && !row.includes('v fail'));
      await shot('91-l2');
    }
    check('整段頁面錯誤 0', errs.length === 0, errs.slice(0, 5));
    const rep = { schema: 'proto-browser-check/1', game, url: path.join(dir, 'index.html'), browser: ver.Browser, at: new Date().toISOString(),
      pass: results.every((r) => r.ok), results, seeds, errors: errs, shots };
    fs.writeFileSync(path.join(OUT, 'browser-check.json'), JSON.stringify(rep, null, 1) + '\n');
    console.log(`browser_check：${game}｜${ver.Browser}｜${results.filter((r) => r.ok).length}/${results.length} PASS｜截圖 ${shots.length} 張 → ${OUT}`);
    ws.close(); cleanup();
    process.exit(rep.pass ? 0 : 1);
  } catch (e) {
    if (e.message !== 'stop') check('執行', false, e.message);
    fs.writeFileSync(path.join(OUT, 'browser-check.json'), JSON.stringify({ schema: 'proto-browser-check/1', pass: false, results, shots }, null, 1) + '\n');
    cleanup();
    process.exit(1);
  }
})();
