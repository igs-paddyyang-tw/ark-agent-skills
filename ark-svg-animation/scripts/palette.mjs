#!/usr/bin/env node
// palette.mjs —— 參考圖 → 色票（0.11.0）。只取「顏色」：不描形、不輸出圖、不保留圖檔路徑以外的任何內容。
//
//   node palette.mjs --image ref.jpg [--k 8] [--json]
//   → { colors: ['#…' 依佔比排序], roles: { skyTop, skyBottom, glow, far, mid, near, ground, accent, particle, orb } }
// 用法：網路找的參考圖先下載到暫存資料夾 → 取色 → 刪圖；把 roles 傳給 gamekit 的 scene（palette 參數）。
// 需要 headless Chromium（同 sheet.mjs 的 findChrome）；支援瀏覽器能解碼的格式（png／jpg／webp／svg）。
import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { findChrome } from './sheet.mjs';
import { assignRoles } from './kit/scene.mjs';
import { mix } from './draw.mjs';

/** 參考圖 → 依佔比排序的 k 個代表色（k-means，初始中心依亮度分位數 → 確定性） */
export function extractPalette(image, { k = 8, chrome = findChrome() } = {}) {
  if (!chrome) throw new Error('找不到 headless Chromium（設 ARK_SVGA_CHROME 或安裝 playwright chromium）');
  if (!existsSync(image)) throw new Error(`找不到圖：${image}`);
  if (!(k >= 3 && k <= 16)) throw new Error('k 要在 3～16');
  const tmp = mkdtempSync(path.join(tmpdir(), 'svga-pal-'));
  const html = path.join(tmp, 'p.html');
  writeFileSync(html, `<!doctype html><html><body><pre id="r"></pre><script>
const img=new Image();img.onload=()=>{try{const c=document.createElement('canvas');c.width=c.height=64;const x=c.getContext('2d');x.drawImage(img,0,0,64,64);
const d=x.getImageData(0,0,64,64).data,px=[];for(let i=0;i<d.length;i+=4)if(d[i+3]>200)px.push([d[i],d[i+1],d[i+2]]);
const L=p=>0.2126*p[0]+0.7152*p[1]+0.0722*p[2],K=${k};const s=[...px].sort((a,b)=>L(a)-L(b));let C=Array.from({length:K},(_,j)=>s[Math.floor((j+0.5)*s.length/K)].slice());
let A=new Array(px.length).fill(0);for(let it=0;it<12;it++){for(let i=0;i<px.length;i++){let b=0,bd=1e9;for(let j=0;j<K;j++){const q=C[j],dd=(px[i][0]-q[0])**2+(px[i][1]-q[1])**2+(px[i][2]-q[2])**2;if(dd<bd){bd=dd;b=j}}A[i]=b}
C=C.map((q,j)=>{const m=px.filter((_,i)=>A[i]===j);return m.length?[0,1,2].map(t=>m.reduce((a,p)=>a+p[t],0)/m.length):q})}
const cnt=C.map((_,j)=>A.filter(a=>a===j).length);const out=C.map((q,j)=>({hex:'#'+q.map(v=>Math.round(v).toString(16).padStart(2,'0')).join(''),n:cnt[j]})).filter(o=>o.n>0).sort((a,b)=>b.n-a.n);
document.getElementById('r').textContent=JSON.stringify({px:px.length,colors:out.map(o=>o.hex),share:out.map(o=>+(o.n/px.length).toFixed(3))})}catch(e){document.getElementById('r').textContent=JSON.stringify({error:e.message})}};
img.onerror=()=>{document.getElementById('r').textContent=JSON.stringify({error:'瀏覽器無法解碼這張圖'})};img.src=${JSON.stringify('file://' + path.resolve(image))};
</script></body></html>`);
  const dom = execFileSync(chrome, ['--headless', '--no-sandbox', '--disable-gpu', '--allow-file-access-from-files', '--virtual-time-budget=15000', '--dump-dom', `file://${html}`],
    { encoding: 'utf8', timeout: 60000, maxBuffer: 16 * 1024 * 1024, stdio: ['ignore', 'pipe', 'ignore'] });
  const m = /<pre id="r">([^<]*)<\/pre>/.exec(dom);
  if (!m || !m[1].trim()) throw new Error('取色頁沒有結果（逾時或瀏覽器錯誤）');
  const r = JSON.parse(m[1].replace(/&quot;/g, '"').replace(/&amp;/g, '&'));
  if (r.error) throw new Error(r.error);
  if (!r.px) throw new Error('圖裡沒有不透明像素');
  // 色數太少（例：只有兩色的圖）→ 補中間混色，至少 3 色才能分派角色
  const pool = [...r.colors];
  while (new Set(pool).size < 3) pool.push(mix(pool[0], pool[pool.length - 1] === pool[0] ? '#ffffff' : pool[pool.length - 1], 0.5 / (pool.length - 1 || 1)));
  return { colors: r.colors, share: r.share, roles: assignRoles(pool) };
}

const isMain = process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href;
if (isMain) {
  const args = process.argv.slice(2), at = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : undefined; };
  if (!at('--image')) { console.error('用法：node palette.mjs --image <圖檔> [--k 8] [--json]'); process.exit(2); }
  try {
    const r = extractPalette(at('--image'), { k: Number(at('--k') ?? 8) });
    if (args.includes('--json')) console.log(JSON.stringify(r, null, 2));
    else { console.log('colors:', r.colors.map((c, i) => `${c}(${Math.round(r.share[i] * 100)}%)`).join(' ')); console.log('roles :', JSON.stringify(r.roles)); }
  } catch (e) { console.error('❌', e.message); process.exit(1); }
}
