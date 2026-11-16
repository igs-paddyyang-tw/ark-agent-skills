#!/usr/bin/env node
// pixi_check.mjs —— flat profile 的實機守門（規格 AC-G3）：同一張 SVG，PixiJS GraphicsContext.svg() 畫出來的
// 形狀要和瀏覽器原生畫的一致：兩邊遮罩各自擴 1 px（3×3）後互相涵蓋的比例取小者 ≥ 門檻
// （Pixi 不開抗鋸齒、瀏覽器有，細線與小圓邊緣差 1 px 不算錯；解析錯誤會整塊跑位，照樣抓得到）。抓得到 Pixi 解析器的坑：polygon 小數被拆、樣式繼承、開放線段連筆。
//
//   node pixi_check.mjs --pixi <pixi.min.js> [--min 0.9]        # 內建樣本：gamekit 全部 kind × theme＋每種體型
// 需要 headless Chromium（同 sheet.mjs 的 findChrome）＋ WebGL（swiftshader 軟體繪製）。缺了就明說跳過。
import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { findChrome } from './sheet.mjs';

export const MIN_IOU = 0.95;

/**
 * @param {{ name:string, svg:string }[]} items  flat profile 的 SVG（viewBox 0 0 w h、width／height 為整數像素）
 * @returns {{ problems:string[], scores:{ name:string, iou:number, pixi:number, native:number }[], skipped?:string }}
 */
export function pixiFlatCheck(items, pixiPath, { chrome = findChrome(), min = MIN_IOU } = {}) {
  if (!chrome) return { problems: [], scores: [], skipped: '找不到 headless Chromium —— 跳過 PixiJS 實機比對（不是通過）' };
  if (!pixiPath) return { problems: [], scores: [], skipped: '沒給 pixi.min.js —— 跳過 PixiJS 實機比對（不是通過）' };
  if (!items.length) return { problems: ['掃到 0 張 SVG —— 範圍是空的，不是通過'], scores: [] };
  const tmp = mkdtempSync(path.join(tmpdir(), 'svga-flat-'));
  writeFileSync(path.join(tmp, 'data.js'), `window.ITEMS=${JSON.stringify(items)};`);
  writeFileSync(path.join(tmp, 'h.html'), `<!doctype html><html><head><meta charset="utf-8"><script src="file://${path.resolve(pixiPath)}"></script><script src="data.js"></script></head><body><pre id="r"></pre><script>
(async()=>{const out=[];try{
const app=new PIXI.Application();await app.init({width:64,height:64,backgroundAlpha:0,preference:'webgl',antialias:false});
for(const it of ITEMS){const m=/viewBox="0 0 ([\\d.]+) ([\\d.]+)"/.exec(it.svg);const w=Math.ceil(+m[1]),h=Math.ceil(+m[2]);
let px;try{app.renderer.resize(w,h);const g=new PIXI.Graphics().svg(it.svg);app.stage.removeChildren();app.stage.addChild(g);app.render();
px=app.renderer.extract.pixels({target:app.stage,frame:new PIXI.Rectangle(0,0,w,h)}).pixels;g.destroy();}catch(e){out.push({name:it.name,err:'Pixi：'+e.message});continue;}
const img=new Image();img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(it.svg);await img.decode();
const c=document.createElement('canvas');c.width=w;c.height=h;const x=c.getContext('2d');x.drawImage(img,0,0,w,h);const nv=x.getImageData(0,0,w,h).data;
const P=new Uint8Array(w*h),N=new Uint8Array(w*h);for(let i=0;i<w*h;i++){P[i]=(px[i*4+3]|0)>40;N[i]=nv[i*4+3]>40;}
const near=(M,i)=>{const x=i%w,y=(i/w)|0;for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){const X=x+dx,Y=y+dy;if(X>=0&&Y>=0&&X<w&&Y<h&&M[Y*w+X])return 1;}return 0;};
let a=0,b=0,pa=0,nb=0;for(let i=0;i<w*h;i++){if(P[i]){a++;pa+=near(N,i);}if(N[i]){b++;nb+=near(P,i);}}
out.push({name:it.name,pixi:a,native:b,iou:+Math.min(pa/(a||1),nb/(b||1)).toFixed(3)});}
}catch(e){out.push({err:e.message})}document.getElementById('r').textContent=JSON.stringify(out);})();</script></body></html>`);
  const dom = execFileSync(chrome, ['--headless', '--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--virtual-time-budget=60000',
    '--allow-file-access-from-files', '--dump-dom', `file://${path.join(tmp, 'h.html')}`],
  { encoding: 'utf8', timeout: 180000, maxBuffer: 64 * 1024 * 1024, stdio: ['ignore', 'pipe', 'ignore'] });
  const m = /<pre id="r">([^<]*)<\/pre>/.exec(dom);
  if (!m || !m[1].trim()) return { problems: ['PixiJS 比對頁沒有產出結果（腳本錯誤、逾時或沒有 WebGL）→ 確認 --pixi 是瀏覽器版 pixi.min.js'], scores: [] };
  const rows = JSON.parse(m[1].replace(/&quot;/g, '"').replace(/&amp;/g, '&'));
  const problems = [];
  for (const r of rows) {
    if (r.err) problems.push(`${r.name ?? '頁面'}：${r.err}`);
    else if (r.native === 0) problems.push(`${r.name}：瀏覽器畫出來是空的 → SVG 本身沒有可見形狀`);
    else if (r.iou < min) problems.push(`${r.name}：PixiJS 與瀏覽器形狀不一致（涵蓋率 ${r.iou} < ${min}；Pixi ${r.pixi} px、原生 ${r.native} px）→ 確認用了 flat profile（polygon／polyline／transform／漸層都要先轉掉）`);
  }
  if (rows.filter((r) => !r.err).length !== items.length) problems.push(`只比對到 ${rows.filter((r) => !r.err).length}／${items.length} 張`);
  return { problems, scores: rows.filter((r) => !r.err) };
}

const isMain = process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href;
if (isMain) {
  const args = process.argv.slice(2);
  const at = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : undefined; };
  const { flatSamples } = await import('./verify_svg.mjs');
  const items = flatSamples();
  const rep = pixiFlatCheck(items, at('--pixi') ?? process.env.ARK_SVGA_PIXI, { min: Number(at('--min') ?? MIN_IOU) });
  if (rep.skipped) { console.log('⏭️', rep.skipped); process.exit(0); }
  const worst = [...rep.scores].sort((a, b) => a.iou - b.iou).slice(0, 5);
  console.log(`PixiJS flat 比對：${rep.scores.length} 張｜最低涵蓋率 ${worst.map((w) => `${w.name} ${w.iou}`).join('、')}`);
  for (const p of rep.problems) console.log('❌', p);
  if (!rep.problems.length) console.log('✅ 通過');
  process.exit(rep.problems.length ? 1 : 0);
}
