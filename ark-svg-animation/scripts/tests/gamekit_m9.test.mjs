// gamekit 0.9.0：aidev 回饋的字與 FG 橫幅 —— 粗體字距、字不超框、撲克字實心、FG 份量；每項附反證。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { asset } from '../gamekit.mjs';
import { measure, layoutText } from '../glyphs.mjs';
import { boldText, BOLD, ROYAL_WEIGHT } from '../kit/util.mjs';

test('加粗時字距跟著加：measure／layoutText 吃 weight（不吃就會黏字）', () => {
  assert.equal(measure('AB'), 10);
  assert.equal(measure('AB', { weight: 2 }), 11);
  const a = layoutText('AB', { size: 60, weight: 2 }), b = layoutText('AB', { size: 60 });
  const gap = (l) => Math.min(...l.strokes.filter((s) => s.pts[0][0] > 0).map((s) => Math.min(...s.pts.map((p) => p[0]))));
  assert.ok(a.width > b.width, '加粗後總寬要變大');
  assert.ok(gap(a) > gap(b), '第二個字要往右挪');
});

test('boldText 一定縮進 maxW（含筆畫與外框）；空字串回 null（空槽）', () => {
  for (const str of ['BIG WIN', 'SUPER WIN', '12,345,678.00', 'X', '10']) {
    const t = boldText(str, { x: 100, y: 50, maxSize: 200, maxW: 180 });
    const u = t.size / 6, w = measure(str, { weight: t.weight }) * u + t.weight * u + 2 * t.outline;
    assert.ok(w <= 180 + 0.5, `${str} 實際 ${w.toFixed(1)} > 180`);
  }
  assert.equal(boldText('', { maxSize: 10, maxW: 10 }), null);
  assert.equal(boldText('A', { maxSize: 10, maxW: 99 }).weight, BOLD);
});

test('撲克字用加粗筆畫（盤面縮小仍是實心字）；徽章／彩池牌／AUTO 也是粗體', () => {
  const sw = (svg) => Math.max(...[...svg.matchAll(/stroke-width="([\d.]+)" stroke-linejoin="bevel"/g)].map((m) => Number(m[1])));
  const k = asset('royal', { letter: 'K' }).svg;
  assert.ok(sw(k) >= (150 / 6) * ROYAL_WEIGHT * 0.8, `撲克字內層筆寬 ${sw(k)} 太細`);
  for (const [kind, spec] of [['jp_plate', { tier: 'Grand' }], ['button', { icon: 'auto' }], ['badge', { type: 'wild' }]]) {
    const svg = asset(kind, spec).svg, sizes = [...svg.matchAll(/stroke-width="([\d.]+)" stroke-linejoin="bevel"/g)].map((m) => Number(m[1]));
    assert.ok(sizes.length >= 2, `${kind} 要有字`);
  }
});

test('FG 橫幅：預設 760×280、有徽冠；sub:"" 只留空槽不出字；text:"" 不出主字', () => {
  const d = asset('fg_banner', {});
  assert.deepEqual([d.meta.w, d.meta.h], [760, 280]);
  const words = (svg) => (svg.match(/stroke-linejoin="bevel"/g) ?? []).length / 2;
  assert.equal(words(d.svg), 1);
  assert.equal(words(asset('fg_banner', { sub: '×10' }).svg), 2);
  assert.equal(words(asset('fg_banner', { sub: '' }).svg), 1, '空次數槽不該有字');
  assert.equal(words(asset('fg_banner', { text: '' }).svg), 0);
  assert.notEqual(asset('fg_banner', { sub: '' }).svg, d.svg, '空槽要畫出槽位');
});
