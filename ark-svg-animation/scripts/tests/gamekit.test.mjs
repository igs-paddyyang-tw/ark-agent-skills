// gamekit／字形／theme／flat profile 測試（0.5.0，規格 AC-G1～G3）—— 每項守門都附反證：故意做壞必須紅。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { creature, renderPhase, SPECIES } from '../svg_anim.mjs';
import { asset, SAMPLES } from '../gamekit.mjs';
import { GLYPHS, layoutText, measure, unsupported } from '../glyphs.mjs';
import { theme, THEMES } from '../themes.mjs';
import { checkFlat, checkSecurity, verify, verifyKit, flatSamples } from '../verify_svg.mjs';
import { pixiFlatCheck } from '../pixi_check.mjs';
import { findChrome } from '../sheet.mjs';

test('重構不改輸出：texture 的 creature() 逐格與 0.4.0 逐位元組相同（快照）', () => {
  const c = createHash('sha256');
  for (const n of [...Object.keys(SPECIES), 'TWIST_NEMO', 'SINGLE_GURNARD']) for (const v of [[], ['gold'], ['boss'], ['twister']]) for (const f of ['up', 'right']) {
    const s = { name: n, length: 104, variants: v, facing: f };
    c.update(JSON.stringify(creature(s).frames)); c.update(renderPhase(s, 1));
  }
  // 造型或演算法有意改變時：升版號並更新這個值（規格 §4「造型改變就升 minor」）
  assert.equal(c.digest('hex'), 'e8f869425cdb50584e03f252b64b4f50e03f243f58d5c473f6e49fb2efb9a4ca');
});

test('字形：每個字都排得出來；未支援字元報錯並列出字元', () => {
  const all = Object.keys(GLYPHS).join('');
  const { strokes, width } = layoutText(all, { size: 60 });
  assert.ok(strokes.length > 60 && width > 0);
  assert.equal(measure('AB'), 4 + 4 + 2);
  assert.deepEqual(unsupported('Big 金 Win 金!'), ['金']);
  assert.throws(() => layoutText('中文', { size: 40 }), /「中」「文」/);
});

test('gamekit：輸出不含 <text>；塞 <text> 必紅（AC-G1）', () => {
  for (const [kind, list] of Object.entries(SAMPLES)) for (const s of list) for (const profile of ['texture', 'flat']) {
    assert.doesNotMatch(asset(kind, { ...s, profile }).svg, /<text\b/);
  }
  const bad = asset('label', { text: 'WIN' }).svg.replace('</svg>', '<text>WIN</text></svg>');
  assert.ok(checkSecurity(bad).some((m) => m.includes('<text>')));
});

test('theme：同參數逐位元組相同；換 theme 會變色；覆寫物件只改指定 token（AC-G2）', () => {
  const a = asset('plate', { shape: 'shield', theme: 'deep-sea' }).svg;
  assert.equal(a, asset('plate', { shape: 'shield', theme: 'deep-sea' }).svg);
  assert.notEqual(a, asset('plate', { shape: 'shield', theme: 'neon-night' }).svg);
  const t = theme({ base: 'deep-sea', primary: { main: '#123456' } });
  assert.equal(t.primary.main, '#123456');
  assert.equal(t.primary.dark, THEMES['deep-sea'].primary.dark);
  assert.throws(() => theme('nope'), /未知 theme/);
  assert.throws(() => asset('plate', { src: 'x.png' }), /外部圖片/);
});

test('flat：gamekit 與生物的 flat 輸出全部合規；texture 輸出必紅（AC-G3 靜態）', () => {
  for (const [kind, list] of Object.entries(SAMPLES)) for (const s of list) assert.deepEqual(checkFlat(asset(kind, { ...s, profile: 'flat' }).svg), [], `${kind}`);
  for (const name of ['NEMO', 'BOMB_CRAB', 'FIRE_DRAGON', 'GOLDEN_TURTLE']) {
    const f = creature({ name, length: 104, profile: 'flat', variants: ['boss', 'twister'], facing: 'right' }).frames;
    for (const svg of [...f.swim, ...f.catch]) assert.deepEqual(checkFlat(svg), [], name);
  }
  assert.ok(checkFlat(creature({ name: 'NEMO', length: 104 }).frames.swim[0]).length > 0, 'texture（漸層＋transform）要紅');
  const W = (b) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" width="10" height="10">${b}</svg>`;
  for (const [what, bad] of [
    ['polygon', W('<polygon points="1.5,1 9,1 5,9" style="fill:#000"/>')],
    ['transform', W('<path d="M0,0 L5,5" transform="rotate(9)" style="fill:none;stroke:#000;stroke-width:1"/>')],
    ['fill 屬性', W('<circle cx="5" cy="5" r="3" fill="#000" style="fill:#000"/>')],
    ['沒有 style', W('<circle cx="5" cy="5" r="3"/>')],
    ['<g>', W('<g><circle cx="5" cy="5" r="3" style="fill:#000"/></g>')],
    ['沒有 stroke-width', W('<path d="M0,0 L5,5" style="fill:none;stroke:#000"/>')],
  ]) assert.ok(checkFlat(bad).length > 0, `${what} 要紅`);
});

test('verifyKit：全綠；寫死顏色／非確定／沒樣本必紅', () => {
  assert.equal(verifyKit().ok, true, verifyKit().problems.slice(0, 3).join('\n'));
  const genFixed = (k, s) => (k === 'fixed' ? { svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" width="10" height="10"><circle cx="5" cy="5" r="4" style="fill:#ff0000"/></svg>`, meta: { category: 'symbol' } } : asset(k, s));
  assert.ok(verifyKit({ kinds: ['fixed'], samples: { fixed: [{}] }, gen: genFixed }).problems.some((p) => p.includes('換 theme')));
  const genRandom = (k, s) => { const o = asset(k, s); return { ...o, svg: o.svg.replace('</svg>', `<!--${Math.random()}--></svg>`) }; };
  assert.ok(verifyKit({ kinds: ['plate'], gen: genRandom }).problems.some((p) => p.includes('兩次輸出不同')));
  assert.ok(verifyKit({ kinds: ['plate'], samples: { plate: [] } }).problems.some((p) => p.includes('範圍是空的')));
});

test('verify：生物 flat 也在掃（flatFrames > 0）', () => {
  const r = verify(['NEMO', 'SHARK']);
  assert.equal(r.ok, true, r.problems.join('\n'));
  assert.ok(r.flatFrames >= 2 * 2 * 7);
});

const chrome = findChrome(), pixi = process.env.ARK_SVGA_PIXI;
test('PixiJS 實機：flat 樣本與瀏覽器形狀一致；texture／小數 polygon 必紅（AC-G3）', { skip: chrome && pixi ? false : '需要 Chromium 與 ARK_SVGA_PIXI=<pixi.min.js> —— 跳過（不是通過）' }, () => {
  const ok = pixiFlatCheck(flatSamples(), pixi);
  assert.deepEqual(ok.problems, []);
  assert.ok(ok.scores.length > 50);
  const bad = pixiFlatCheck([
    { name: 'texture', svg: creature({ name: 'NEMO', length: 104 }).frames.swim[0] },
    { name: 'decimal-polygon', svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100"><polygon points="10.5,10.5 90.5,10.5 50.5,90.5" style="fill:#0f0"/></svg>' },
  ], pixi);
  assert.ok(bad.problems.some((p) => p.startsWith('texture')), 'texture 要紅');
  assert.ok(bad.problems.some((p) => p.startsWith('decimal-polygon')), '小數 polygon 要紅');
});
