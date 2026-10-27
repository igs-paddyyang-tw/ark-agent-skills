// 系統瀏覽器驅動（零 npm 相依）：Chrome / Edge / Chromium 無頭模式 + DevTools 協定（Node 22 內建 WebSocket）。
// 提供 Playwright Page 的常用子集，讓測試在沒有 Playwright 的機器上也能跑真瀏覽器：
//   const { launch } = require('./cdp');
//   const b = await launch({ root: '<要服務的資料夾>' });      // root 給了就起內建靜態伺服器，b.url('index.html') 取網址
//   const p = await b.newPage({ viewport: { width, height } });
//   await p.goto(url); await p.evaluate(fn | 'expr', arg); await p.waitForFunction(fn, arg, { timeout });
//   await p.waitForSelector(sel); await p.click(sel); await p.screenshot({ path }); p.errors（例外 / console.error / 載入失敗）
//   await b.close();
// 找不到瀏覽器 → 拋 CdpEnvError（呼叫端據此 exit 2 / skip）。
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');

class CdpEnvError extends Error {}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function findBrowser(given) {
  given = given || process.env.CHROME_PATH;
  if (given) { if (fs.existsSync(given)) return given; throw new CdpEnvError(`找不到瀏覽器 ${given}（--browser 或 CHROME_PATH 指向 chrome / msedge 執行檔）`); }
  const pf = [process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA].filter(Boolean);
  const cands = [
    ...pf.flatMap((p) => [path.join(p, 'Google/Chrome/Application/chrome.exe'), path.join(p, 'Microsoft/Edge/Application/msedge.exe')]),
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/microsoft-edge',
  ];
  const hit = cands.find((c) => fs.existsSync(c));
  if (!hit) throw new CdpEnvError('找不到 Chrome / Edge / Chromium（用 --browser 或 CHROME_PATH 指定）');
  return hit;
}

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.css': 'text/css',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg', '.wav': 'audio/wav', '.woff2': 'font/woff2' };
function serve(root) {
  root = path.resolve(root);
  const srv = http.createServer((req, res) => {
    let f = path.normalize(path.join(root, decodeURIComponent(req.url.split('?')[0])));
    if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, 'index.html');
    if (!f.startsWith(root) || !fs.existsSync(f)) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' });
    fs.createReadStream(f).pipe(res);
  });
  return new Promise((r) => srv.listen(0, '127.0.0.1', () => r(srv)));
}

async function launch(opts = {}) {
  if (typeof WebSocket === 'undefined') throw new CdpEnvError('需要 Node 22+（內建 WebSocket）');
  const exe = findBrowser(opts.browser);
  const srv = opts.root ? await serve(opts.root) : null;
  const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'proto-cdp-'));
  const br = spawn(exe, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${prof}`, '--no-first-run', '--no-default-browser-check',
    '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--autoplay-policy=no-user-gesture-required',
    ...(process.getuid && process.getuid() === 0 ? ['--no-sandbox'] : []), 'about:blank'], { stdio: 'ignore' });   // Linux root（容器／CI）需 --no-sandbox 才開得起來
  let port = null;
  for (let i = 0; i < 80 && !port; i++) { await sleep(250); try { port = fs.readFileSync(path.join(prof, 'DevToolsActivePort'), 'utf8').split('\n')[0].trim(); } catch {} }
  if (!port) { try { br.kill(); } catch {} throw new CdpEnvError(`瀏覽器沒有開出 DevTools 埠（${exe}）`); }
  const base = `http://127.0.0.1:${port}`;
  const version = (await (await fetch(`${base}/json/version`)).json()).Browser;
  const sockets = [];
  return {
    version, exe,
    url: (p = 'index.html') => (srv ? `http://127.0.0.1:${srv.address().port}/${p.replace(/^\/+/, '')}` : null),
    async newPage(o = {}) { const p = await newPage(base, o); sockets.push(p._ws); return p; },
    async close() {
      sockets.forEach((w) => { try { w.close(); } catch {} });
      try { br.kill(); } catch {}
      if (srv) srv.close();
      await sleep(600);
      try { fs.rmSync(prof, { recursive: true, force: true }); } catch {}
    },
  };
}

async function newPage(base, o) {
  const t = await (await fetch(`${base}/json/new?about:blank`, { method: 'PUT' })).json();
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  let id = 0; const pend = {}, errors = [], loads = [], reqUrl = {};
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && pend[d.id]) { pend[d.id](d); delete pend[d.id]; }
    if (d.method === 'Page.loadEventFired') loads.splice(0).forEach((f) => f());
    if (d.method === 'Runtime.exceptionThrown') errors.push('pageerror ' + (d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text));
    if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error') errors.push('console ' + d.params.args.map((a) => a.value ?? a.description).join(' '));
    if (d.method === 'Network.requestWillBeSent') reqUrl[d.params.requestId] = d.params.request.url;
    // CDN 失敗會由頁面退回本地 vendor/（離線常見），不算錯
    if (d.method === 'Network.loadingFailed' && !d.params.canceled && !/ERR_ABORTED/.test(d.params.errorText) && !/cdn\.jsdelivr|unpkg|cdnjs/.test(reqUrl[d.params.requestId] || '')) errors.push(`loadingFailed ${d.params.errorText} ${reqUrl[d.params.requestId] || ''}`);
  };
  const send = (method, params = {}) => new Promise((r) => { const i = ++id; pend[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
  const toExpr = (fn, arg) => (typeof fn === 'function' ? `(${fn})(${arg === undefined ? '' : JSON.stringify(arg)})` : String(fn));
  const evaluate = async (fn, arg) => {
    const r = await send('Runtime.evaluate', { expression: toExpr(fn, arg), awaitPromise: true, returnByValue: true, userGesture: true });
    if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text);
    return r.result?.result?.value;
  };
  const waitForFunction = async (fn, arg, opt = {}) => {
    const end = Date.now() + (opt.timeout ?? 30000);
    for (;;) { try { if (await evaluate(fn, arg)) return; } catch {} if (Date.now() > end) throw new Error('waitForFunction 逾時'); await sleep(opt.polling ?? 150); }
  };
  await send('Runtime.enable'); await send('Page.enable'); await send('Network.enable');
  const vp = o.viewport || { width: 1280, height: 900 };
  await send('Emulation.setDeviceMetricsOverride', { width: vp.width, height: vp.height, deviceScaleFactor: 1, mobile: false });
  return {
    _ws: ws, errors, send, evaluate, waitForFunction,
    async goto(url) { const done = new Promise((r) => loads.push(r)); await send('Page.navigate', { url }); await Promise.race([done, sleep(30000)]); },
    waitForSelector: (sel, opt) => waitForFunction((s) => !!document.querySelector(s), sel, opt),
    waitForTimeout: sleep,
    async click(sel) {
      const box = await evaluate((s) => { const e = document.querySelector(s); if (!e) return null; e.scrollIntoView({ block: 'center' }); const b = e.getBoundingClientRect(); return { x: b.x + b.width / 2, y: b.y + b.height / 2 }; }, sel);
      if (!box) throw new Error('click：找不到 ' + sel);
      for (const type of ['mousePressed', 'mouseReleased']) await send('Input.dispatchMouseEvent', { type, x: box.x, y: box.y, button: 'left', clickCount: 1 });
    },
    async screenshot(opt = {}) { const r = await send('Page.captureScreenshot', { format: 'png' }); const buf = Buffer.from(r.result.data, 'base64'); if (opt.path) fs.writeFileSync(opt.path, buf); return buf; },
  };
}

module.exports = { launch, CdpEnvError, findBrowser, serve };
