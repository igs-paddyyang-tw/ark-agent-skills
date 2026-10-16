// node 載入器：每款遊戲一個獨立 vm context（Proto 全域互不干擾），只載入引擎層（不需 DOM / Pixi）
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const RT = path.resolve(__dirname, '..', 'runtime');
const ENGINE = ['../../src/go-rand.js', 'core/core.js', 'core/sim.js', 'slot/logic.js', 'features/鎖格重轉/logic.js', 'service/result.js', 'service/service.js'];

function load(gameFile, extra = []) {
  const ctx = { console, setTimeout, clearTimeout, setInterval, clearInterval, performance, Math, Date, AbortController, fetch, URLSearchParams };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  for (const f of [...ENGINE.map((x) => path.join(RT, x)), ...extra, ...(gameFile ? [gameFile] : [])]) {
    vm.runInContext(fs.readFileSync(f, 'utf8'), ctx, { filename: f });
  }
  if (ctx.GoRand) ctx.Proto.GoRand = ctx.GoRand;
  return ctx.Proto;
}
module.exports = { load, RT, ENGINE };
