// gamekit 0.8.0：對照 aidev 神燈寶藏補的選項 —— 寶箱材質、符號底板、執行期文字的空槽；每項附反證。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { asset } from '../gamekit.mjs';
import { checkFlat } from '../verify_svg.mjs';

const fills = (svg) => new Set([...svg.matchAll(/stop-color="(#[0-9a-f]{6})"/g)].map((m) => m[1]));

test('寶箱 metal 改箱體顏色（金／銀／木各不同）；不支援的材質報錯', () => {
  const [g, s, b, d] = ['gold', 'silver', 'bronze', undefined].map((metal) => asset('icon', { name: 'chest', metal }).svg);
  assert.equal(new Set([g, s, b, d]).size, 4);
  assert.ok(fills(g).has('#f5c542') || [...fills(g)].some((c) => c.startsWith('#f')), '金箱體要是金色系');
  assert.ok(!fills(d).has('#8a5a2b'), '預設不是木箱');
  assert.throws(() => asset('icon', { name: 'chest', metal: 'diamond' }), /gold／silver／bronze/);
});

test('royal plate：字放進底板（尺寸不變、多了底板圖形）；flat 合規', () => {
  const plain = asset('royal', { letter: 'K' }), boxed = asset('royal', { letter: 'K', plate: 'arch', plateColor: { light: '#ff8a8a', main: '#d6303f', dark: '#7a1020' } });
  assert.deepEqual([boxed.meta.w, boxed.meta.h], [plain.meta.w, plain.meta.h]);
  assert.match(boxed.svg, /#d6303f/);
  assert.doesNotMatch(plain.svg, /#d6303f/);
  assert.deepEqual(checkFlat(asset('royal', { letter: 'Q', plate: 'circle', profile: 'flat' }).svg), []);
});

test('空槽：jp_plate value:"" 只有級別＋空槽（沒有數字）；fg_banner text:"" 沒有字', () => {
  const blank = asset('jp_plate', { tier: 'Grand', value: '' }).svg, label = asset('jp_plate', { tier: 'Grand' }).svg;
  assert.notEqual(blank, label);
  const strokes = (svg) => (svg.match(/stroke-linejoin="bevel"/g) ?? []).length;   // 字＝兩層 bevel 筆畫
  assert.equal(strokes(blank), 2, '只有 GRAND 一組字');
  assert.equal(strokes(asset('jp_plate', { tier: 'Grand', value: '9.99' }).svg), 4, '有金額＝兩組字');
  assert.equal(strokes(asset('fg_banner', { text: '' }).svg), 0);
  assert.equal(strokes(asset('fg_banner', {}).svg), 2);
});
