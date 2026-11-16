// draw.mjs —— 圖元 → SVG（0.5.0 由 svg_anim.mjs 抽出；生物與 gamekit 共用）。
//
// 兩種 profile：
//   texture（預設）：給瀏覽器 Image／wg_pack_assets／sheet 轉貼圖 —— 可用漸層、裁切、transform。
//                    0.4.0 的 creature() 輸出逐位元組不變（tests 有快照守門）。
//   flat：給 PixiJS GraphicsContext.svg() 直接解析（8.6.6 原始碼實讀）——
//     · <polygon>／<polyline> 的 points 用 /\d+/g 解析（小數、負號會壞）→ 一律改 <path>
//     · 只認 style 上色（有 style 就忽略 fill／stroke 屬性）、子元素關不掉繼承的填色 → 每個元素自帶完整 style、不在 <g> 上色
//     · 不支援漸層、裁切、transform、<text> → 漸層取平均色、略過裁切花紋、變換烘焙進座標
//
// 圖元（座標 × ctx.L；生物 L＝身長、gamekit L＝1 即像素）：
//   ellipse circle polygon polyline path eye clip g text
//   fill／stroke：'#hex'｜'none'｜'grad'（配色放射漸層）｜'glow'｜{ lg:[[offset,color,alpha?]…], x1,y1,x2,y2 }｜{ rg:[…], cx,cy,r }
import { GLYPHS, layoutText } from './glyphs.mjs';

/** FNV-1a 32 位元（名字 → 種子；漸層內容 → id） */
export function fnv1a(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
}

/** 數字輸出：小數 1 位、去掉多餘的 0 與 -0 —— 逐位元組穩定 */
export function num(n) {
  const r = Math.round(n * 10) / 10;
  return Object.is(r, -0) || r === 0 ? '0' : String(r);
}
const n2 = (n) => { const r = Math.round(n * 100) / 100; return Object.is(r, -0) || r === 0 ? '0' : String(r); };

/** 兩個 #rrggbb 依比例混色（被捕閃白用） */
export function mix(hex, toHex, k) {
  const p = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const a = p(hex), b = p(toHex);
  return '#' + a.map((v, i) => Math.round(v + (b[i] - v) * k).toString(16).padStart(2, '0')).join('');
}
function avgColor(list) {
  const p = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const s = list.map(p).reduce((a, b) => a.map((v, i) => v + b[i]), [0, 0, 0]);
  return '#' + s.map((v) => Math.round(v / list.length).toString(16).padStart(2, '0')).join('');
}

// ── 仿射矩陣 [a b c d e f]：(x, y) → (a·x + c·y + e, b·x + d·y + f) ──────────────
export const I = [1, 0, 0, 1, 0, 0];
export const mul = (m, n) => [m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1], m[0] * n[2] + m[2] * n[3], m[1] * n[2] + m[3] * n[3], m[0] * n[4] + m[2] * n[5] + m[4], m[1] * n[4] + m[3] * n[5] + m[5]];
export const translate = (x, y) => [1, 0, 0, 1, x, y];
export const scale = (k) => [k, 0, 0, k, 0, 0];
export const rotate = (deg, cx = 0, cy = 0) => {
  const r = (deg * Math.PI) / 180, c = Math.cos(r), s = Math.sin(r);
  return mul(translate(cx, cy), mul([c, s, -s, c, 0, 0], translate(-cx, -cy)));
};
const ap = (m, x, y) => [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]];
const scaleOf = (m) => Math.sqrt(Math.abs(m[0] * m[3] - m[1] * m[2]));
const isRotated = (m) => Math.abs(m[1]) > 1e-9 || Math.abs(m[2]) > 1e-9;

// ── 上色 ─────────────────────────────────────────────────────────────────────
const flash = (v, ctx) => (v && ctx.k ? mix(v, ctx.pal.white ?? '#ffffff', ctx.k) : v);

/** 漸層物件 → defs；id＝前綴＋定義內容雜湊 → 同 id 必同定義（同頁多張不會互撞） */
function gradObj(g, ctx) {
  const tag = g.lg ? 'linearGradient' : 'radialGradient';
  const stops = (g.lg ?? g.rg).map(([o, c, a]) => `<stop offset="${n2(o)}" stop-color="${flash(c, ctx)}"${a !== undefined && a !== 1 ? ` stop-opacity="${n2(a)}"` : ''}/>`).join('');
  const attrs = g.lg ? `x1="${n2(g.x1 ?? 0)}" y1="${n2(g.y1 ?? 0)}" x2="${n2(g.x2 ?? 0)}" y2="${n2(g.y2 ?? 1)}"` : `cx="${n2(g.cx ?? 0.5)}" cy="${n2(g.cy ?? 0.5)}" r="${n2(g.r ?? 0.5)}"`;
  const body = ` ${attrs}>${stops}</${tag}>`;
  const id = `${ctx.gid ?? 'g'}${fnv1a(tag + body).toString(36)}`;
  ctx.defs.set(id, `<${tag} id="${id}"${body}`);
  return id;
}

function fillOf(v, ctx) {
  if (v === 'none') return 'none';
  if (v === 'grad' || v === 'glow') return `url(#${grad(v, ctx)})`;
  if (v && typeof v === 'object') return `url(#${gradObj(v, ctx)})`;
  return v && ctx.k ? mix(v, ctx.pal.white, ctx.k) : v;
}

function grad(kind, ctx) {
  const id = `${ctx.id}${kind[0]}`;
  if (!ctx.defs.has(id)) {
    const c = (v) => (ctx.k ? mix(v, ctx.pal.white, ctx.k) : v);
    ctx.defs.set(id, kind === 'grad'
      ? `<radialGradient id="${id}" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="${c(ctx.pal.light)}"/><stop offset=".5" stop-color="${c(ctx.pal.main)}"/><stop offset="1" stop-color="${c(ctx.pal.dark)}"/></radialGradient>`
      : `<radialGradient id="${id}"><stop offset="0" stop-color="${c(ctx.pal.light)}" stop-opacity=".7"/><stop offset="1" stop-color="${c(ctx.pal.light)}" stop-opacity="0"/></radialGradient>`);
  }
  return id;
}

/** 樣式（texture）：筆寬、虛線一律是正規化單位（× L），透明度 0～1 */
function paint(o, ctx) {
  const { L } = ctx;
  let s = '';
  if (o.fill !== undefined) s += ` fill="${fillOf(o.fill, ctx)}"`;
  if (o.stroke) s += ` stroke="${fillOf(o.stroke, ctx)}" stroke-width="${num(Math.max(0.6, (o.sw ?? 0.015) * L))}"`;
  if (o.cap) s += ` stroke-linecap="${o.cap}"`;
  if (o.join) s += ` stroke-linejoin="${o.join}"`;
  if (o.op !== undefined && o.op !== 1) s += ` opacity="${num(o.op)}"`;
  if (o.dash) s += ` stroke-dasharray="${o.dash.map((d) => num(d * L)).join(' ')}"`;
  return s;
}

/** flat：顏色＋透明度（漸層取平均色；glow＝亮色 35%） */
function flatColor(v, ctx) {
  if (v === undefined || v === 'none') return null;
  if (v === 'grad') return { c: flash(ctx.pal.main, ctx), a: 1 };
  if (v === 'glow') return { c: flash(ctx.pal.light, ctx), a: 0.35 };
  if (typeof v === 'object') {
    const st = v.lg ?? v.rg;
    return { c: flash(avgColor(st.map((s) => s[1])), ctx), a: st.reduce((x, s) => x + (s[2] ?? 1), 0) / st.length };
  }
  return { c: flash(v, ctx), a: 1 };
}

/** flat 樣式：Pixi 只讀 style 的 fill／fill-opacity／stroke／stroke-width／stroke-opacity／opacity */
function flatStyle(o, ctx, m) {
  const f = flatColor(o.fill, ctx), s = o.stroke ? flatColor(o.stroke, ctx) : null;
  const op = (o.op ?? 1) * (ctx.op ?? 1);
  const out = [f ? `fill:${f.c}` : 'fill:none'];
  if (f && f.a * op < 0.995) out.push(`fill-opacity:${n2(f.a * op)}`);
  if (s) {
    out.push(`stroke:${s.c}`, `stroke-width:${num(Math.max(0.6, (o.sw ?? 0.015) * ctx.L) * scaleOf(m))}`);
    if (s.a * op < 0.995) out.push(`stroke-opacity:${n2(s.a * op)}`);
  }
  return ` style="${out.join(';')}"`;
}

/** path 指令（正規化座標）：['M',x,y] ['L',x,y] ['Q',x1,y1,x,y] ['C',x1,y1,x2,y2,x,y] ['Z'] */
function pathD(d, L) {
  return d.map(([c, ...v]) => c + v.map((n) => num(n * L)).join(',')).join(' ');
}
function pathDm(d, L, m) {
  return d.map(([c, ...v]) => {
    const pts = [];
    for (let i = 0; i < v.length; i += 2) pts.push(ap(m, v[i] * L, v[i + 1] * L).map(num).join(','));
    return c + pts.join(' ');
  }).join(' ');
}

/** 橢圓（可旋轉）→ 4 段三次貝茲（flat 用：Pixi 的 ellipse 不能旋轉） */
function ellipseD(cx, cy, rx, ry, rot, L, m) {
  const k = 0.5523, R = rotate(rot ?? 0), M = mul(m, mul(translate(cx * L, cy * L), R));
  const P = (x, y) => ap(M, x, y).map(num).join(',');
  const a = rx * L, b = ry * L;
  return `M${P(a, 0)} C${P(a, k * b)} ${P(k * a, b)} ${P(0, b)} C${P(-k * a, b)} ${P(-a, k * b)} ${P(-a, 0)} C${P(-a, -k * b)} ${P(-k * a, -b)} ${P(0, -b)} C${P(k * a, -b)} ${P(a, -k * b)} ${P(a, 0)} Z`;
}

// ── 文字（原創筆畫字，glyphs.mjs）─────────────────────────────────────────────
// texture：兩層 stroke path（外層 ink 粗筆、內層填色筆），linejoin bevel、linecap square
// flat：  同一幾何轉成填色多邊形（每段一個四邊形＋轉角斜接三角形），逆時針一致 → 非零規則下重疊處是聯集
function textShape(o, ctx, m) {
  const { strokes } = layoutText(o.str, o);
  const L = ctx.L, w = o.size / 6;                 // 1 格線單位＝字高 / 6
  const layers = [
    { color: o.ink ?? '#000000', width: w * (o.weight ?? 1) + 2 * (o.outline ?? w * 0.45) },
    { color: o.fill ?? '#ffffff', width: w * (o.weight ?? 1) },
  ].filter((l) => l.color !== 'none');
  if (ctx.profile !== 'flat') {
    const d = strokes.map((s) => 'M' + s.pts.map(([x, y]) => `${num(x * L)},${num(y * L)}`).join(' L') + (s.closed ? ' Z' : '')).join(' ');
    return layers.map((l) => `<path d="${d}" fill="none" stroke="${fillOf(l.color, ctx)}" stroke-width="${num(l.width * L)}" stroke-linejoin="bevel" stroke-linecap="square"${o.op !== undefined && o.op !== 1 ? ` opacity="${num(o.op)}"` : ''}/>`).join('');
  }
  return layers.map((l) => {
    const d = strokes.map((s) => strokePolys(s.pts.map(([x, y]) => ap(m, x * L, y * L)), s.closed, (l.width * L * scaleOf(m)) / 2)).join(' ');
    return `<path d="${d}"${flatStyle({ fill: l.color, op: o.op }, ctx, m)}/>`;
  }).join('');
}

/** 一條筆畫 → 多邊形 path 子路徑（square cap、bevel join） */
function strokePolys(pts, closed, h) {
  const P = (p) => `${Math.round(p[0])},${Math.round(p[1])}`;   // 整數像素：字的多邊形量大，小數 1 位會讓 flat 字體積翻倍（0.5 px 誤差看不出來）
  const poly = (ps) => {
    let a = 0;
    for (let i = 0; i < ps.length; i++) { const p = ps[i], q = ps[(i + 1) % ps.length]; a += p[0] * q[1] - q[0] * p[1]; }
    if (a < 0) ps = [...ps].reverse();
    return 'M' + ps.map(P).join(' L') + ' Z';
  };
  const segs = [], n = pts.length;
  const segCount = closed ? n : n - 1;
  const nrm = [];
  for (let i = 0; i < segCount; i++) {
    const p = pts[i], q = pts[(i + 1) % n];
    const dx = q[0] - p[0], dy = q[1] - p[1], len = Math.hypot(dx, dy) || 1;
    const ux = dx / len, uy = dy / len, nx = -uy * h, ny = ux * h;
    nrm.push([nx, ny]);
    const e0 = !closed && i === 0 ? h : 0, e1 = !closed && i === segCount - 1 ? h : 0;  // square cap
    const a = [p[0] - ux * e0, p[1] - uy * e0], b = [q[0] + ux * e1, q[1] + uy * e1];
    segs.push(poly([[a[0] + nx, a[1] + ny], [b[0] + nx, b[1] + ny], [b[0] - nx, b[1] - ny], [a[0] - nx, a[1] - ny]]));
  }
  const joints = closed ? n : n - 2;
  for (let j = 0; j < joints; j++) {
    const i = closed ? j : j + 1;                    // 頂點 i：進入段 i-1、離開段 i
    const v = pts[i], n1 = nrm[(i - 1 + segCount) % segCount], n2_ = nrm[i % segCount];
    const cross = n1[0] * n2_[1] - n1[1] * n2_[0];
    if (Math.abs(cross) < 1e-9) continue;            // 直線延續，不必補角
    segs.push(poly([v, [v[0] + n1[0], v[1] + n1[1]], [v[0] + n2_[0], v[1] + n2_[1]]]));
    segs.push(poly([v, [v[0] - n1[0], v[1] - n1[1]], [v[0] - n2_[0], v[1] - n2_[1]]]));
  }
  return segs.join(' ');
}

// ── 圖元 → SVG ──────────────────────────────────────────────────────────────
// ctx：{ L, pal, k 閃白比例, id 本格唯一前綴, defs Map, profile, m 矩陣（flat）, op 累積透明度（flat） }
export function shape(o, ctx) {
  return ctx.profile === 'flat' ? flatShape(o, ctx, ctx.m ?? I) : texShape(o, ctx);
}

function texShape(o, ctx) {
  const { L } = ctx, X = (v) => num(v * L), P = (pts) => pts.map(([x, y]) => `${X(x)},${X(y)}`).join(' ');
  switch (o.k) {
    case 'ellipse': return `<ellipse cx="${X(o.cx)}" cy="${X(o.cy)}" rx="${X(o.rx)}" ry="${X(o.ry)}"${o.rot !== undefined ? ` transform="rotate(${num(o.rot)} ${X(o.cx)} ${X(o.cy)})"` : ''}${paint(o, ctx)}/>`;
    case 'circle': return `<circle cx="${X(o.cx)}" cy="${X(o.cy)}" r="${X(o.r)}"${paint(o, ctx)}/>`;
    case 'polygon': return `<polygon points="${P(o.pts)}"${paint(o, ctx)}/>`;
    case 'polyline': return `<polyline points="${P(o.pts)}" fill="none"${paint({ ...o, fill: undefined }, ctx)}/>`;
    case 'path': return `<path d="${pathD(o.d, L)}"${paint(o, ctx)}/>`;
    // 眼睛：眼白＋瞳孔＋反光點（一個圖元展開成三個圓）
    case 'eye': return eyeParts(o, ctx).map((c) => texShape(c, ctx)).join('');
    // 裁切：花紋只畫在 shape 範圍內（不溢出身體輪廓）
    case 'clip': {
      const id = `${ctx.id}c${ctx.clip = (ctx.clip ?? 0) + 1}`;
      ctx.defs.set(id, `<clipPath id="${id}">${texShape({ ...o.shape, fill: undefined, stroke: undefined, op: undefined }, ctx)}</clipPath>`);
      return `<g clip-path="url(#${id})">${o.children.map((c) => texShape(c, ctx)).join('')}</g>`;
    }
    // 群組：可繞 (ox, oy) 旋轉 rot 度；rot 有給就一律輸出（含 0°）—— 各格結構一致，接縫檢查才比得起來
    case 'g': {
      // s：繞 (ox, oy) 等比縮放（0.6.0；gamekit 圖示放進底板用）—— 沒給 s 時輸出與 0.4.0 相同
      let tf = o.rot !== undefined ? `rotate(${num(o.rot)} ${X(o.ox ?? 0)} ${X(o.oy ?? 0)})` : '';
      if (o.s !== undefined) tf += `${tf ? ' ' : ''}translate(${X(o.ox ?? 0)} ${X(o.oy ?? 0)}) scale(${n2(o.s)}) translate(${X(-(o.ox ?? 0))} ${X(-(o.oy ?? 0))})`;
      return `<g${tf ? ` transform="${tf}"` : ''}${o.op !== undefined && o.op !== 1 ? ` opacity="${num(o.op)}"` : ''}>${o.children.map((c) => texShape(c, ctx)).join('')}</g>`;
    }
    case 'text': return textShape(o, ctx, I);
    default: throw new Error(`未知圖元 ${o.k}`);
  }
}

function eyeParts(o, ctx) {
  return [{ k: 'circle', cx: o.cx, cy: o.cy, r: o.r, fill: ctx.pal.white }, { k: 'circle', cx: o.cx, cy: o.cy - o.r * 0.15, r: o.r * 0.6, fill: ctx.pal.eye }, { k: 'circle', cx: o.cx - o.r * 0.25, cy: o.cy - o.r * 0.4, r: o.r * 0.22, fill: ctx.pal.white }];
}

/**
 * flat 的放射淡出（光暈）：Pixi 沒有漸層 → 疊 K 層同心形狀，每層透明度＝該半徑區間的落差，疊起來近似原本的淡出。
 * 只處理以中心為原點的放射漸層（cx＝cy＝0.5、r＝0.5，即 glowFill 的預設），其他照平均色。
 */
const GLOW_LAYERS = 6;
function radialLayers(o) {
  const g = o.fill;
  if (!g || typeof g !== 'object' || !g.rg || (g.cx ?? 0.5) !== 0.5 || (g.cy ?? 0.5) !== 0.5 || (g.r ?? 0.5) !== 0.5) return null;
  const st = g.rg, alphas = st.map((x) => x[2] ?? 1);
  if (Math.max(...alphas) - Math.min(...alphas) < 0.05) return null;
  const at = (f) => {                                   // f：0 中心 → 1 邊緣
    for (let i = 1; i < st.length; i++) if (f <= st[i][0]) { const a = st[i - 1], b = st[i], u = (f - a[0]) / ((b[0] - a[0]) || 1); return (a[2] ?? 1) + ((b[2] ?? 1) - (a[2] ?? 1)) * u; }
    return st[st.length - 1][2] ?? 1;
  };
  const color = avgColor(st.map((x) => x[1])), out = [];
  for (let j = GLOW_LAYERS; j >= 1; j--) {
    const f = j / GLOW_LAYERS, a = Math.max(0, at(f - 1 / GLOW_LAYERS) - at(f));
    if (a > 0.004) out.push({ f, fill: color, op: (o.op ?? 1) * a });
  }
  return out;
}

function flatShape(o, ctx, m) {
  const { L } = ctx, sc = scaleOf(m);
  if ((o.k === 'circle' || o.k === 'ellipse') && !o.stroke) {
    const layers = radialLayers(o);
    if (layers) return layers.map((l) => flatShape(o.k === 'circle' ? { ...o, r: o.r * l.f, fill: l.fill, op: l.op } : { ...o, rx: o.rx * l.f, ry: o.ry * l.f, fill: l.fill, op: l.op }, ctx, m)).join('');
  }
  const pt = (x, y) => ap(m, x * L, y * L).map(num).join(',');
  switch (o.k) {
    case 'circle': { const [x, y] = ap(m, o.cx * L, o.cy * L); return `<circle cx="${num(x)}" cy="${num(y)}" r="${num(o.r * L * sc)}"${flatStyle(o, ctx, m)}/>`; }
    case 'ellipse':
      if (o.rot || isRotated(m)) return `<path d="${ellipseD(o.cx, o.cy, o.rx, o.ry, o.rot, L, m)}"${flatStyle(o, ctx, m)}/>`;
      { const [x, y] = ap(m, o.cx * L, o.cy * L); return `<ellipse cx="${num(x)}" cy="${num(y)}" rx="${num(o.rx * L * sc)}" ry="${num(o.ry * L * sc)}"${flatStyle(o, ctx, m)}/>`; }
    case 'polygon': return `<path d="M${o.pts.map(([x, y]) => pt(x, y)).join(' L')} Z"${flatStyle(o, ctx, m)}/>`;
    case 'polyline': return `<path d="M${o.pts.map(([x, y]) => pt(x, y)).join(' L')}"${flatStyle({ ...o, fill: 'none' }, ctx, m)}/>`;
    case 'path': return `<path d="${pathDm(o.d, L, m)}"${flatStyle(o, ctx, m)}/>`;
    case 'eye': return eyeParts(o, ctx).map((c) => flatShape(c, ctx, m)).join('');
    case 'clip': return '';                          // Graphics 不支援裁切：略過花紋（寧缺不溢出輪廓）
    case 'g': {
      let m2 = o.rot ? mul(m, rotate(o.rot, (o.ox ?? 0) * L, (o.oy ?? 0) * L)) : m;
      if (o.s !== undefined) { const ox = (o.ox ?? 0) * L, oy = (o.oy ?? 0) * L; m2 = mul(m2, mul(translate(ox, oy), mul(scale(Math.round(o.s * 100) / 100), translate(-ox, -oy)))); }
      const sub = { ...ctx, op: (ctx.op ?? 1) * (o.op ?? 1) };
      return o.children.map((c) => flatShape(c, sub, m2)).join('');
    }
    case 'text': return textShape(o, ctx, m);
    default: throw new Error(`未知圖元 ${o.k}`);
  }
}

/** 一組圖元 → { body, defs }（defs 已包好 <defs>…</defs>，沒有就是空字串） */
export function draw(parts, ctx) {
  ctx.defs ??= new Map();
  const body = parts.map((o) => shape(o, ctx)).join('');
  return { body, defs: ctx.defs.size ? `<defs>${[...ctx.defs.values()].join('')}</defs>` : '' };
}

export { GLYPHS };
