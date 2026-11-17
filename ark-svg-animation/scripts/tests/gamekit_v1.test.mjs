// 1.0.0：aidev 複驗的 3 個建議 —— 撲克字自動對比、color 錯誤訊息、金幣噴發留在框內、跑馬燈級別字放大。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { asset } from '../gamekit.mjs';

const RED = { light: '#ff8a8a', main: '#d6303f', dark: '#7a1020' };

test('撲克字放進同色系底板 → 自動改金字；指定 color 時照指定；不同色系不改', () => {
  const a = asset('royal', { letter: 'A', plate: 'arch', plateColor: RED }).svg;
  assert.doesNotMatch(a, /#e8424f/, 'A 的紅字在紅底上要換掉');
  assert.match(asset('royal', { letter: 'A', plate: 'arch', plateColor: RED, color: '#e8424f' }).svg, /#e8424f/, '使用者指定就照用');
  assert.match(asset('royal', { letter: 'K', plate: 'arch', plateColor: RED }).svg, /#3f6fe0/, '藍字配紅底不用換');
});

test('royal color 給錯型別 → 看得懂的訊息（原本 h.slice is not a function）', () => {
  assert.throws(() => asset('royal', { letter: 'A', color: { main: '#ff0000' } }), /color 要給色碼字串/);
  assert.throws(() => asset('royal', { letter: 'A', color: 'red' }), /color 要給色碼字串/);
});

test('金幣噴發：每一格每枚金幣都在畫框內；往四周散開（不是擠在中間）', () => {
  for (const seed of [0, 1, 2, 3]) for (const count of [14, 20, 40]) {
    const a = asset('coin_burst', { seed, count }), L = a.meta.w / 256;
    for (const f of a.frames) for (const m of f.matchAll(/<ellipse cx="([\d.-]+)" cy="([\d.-]+)" rx="[\d.]+" ry="([\d.]+)"/g)) {
      const x = +m[1] / L, y = +m[2] / L, r = +m[3] / L;
      assert.ok(x - r >= -0.5 && y - r >= -0.5 && x + r <= 256.5 && y + r <= 256.5, `seed ${seed} count ${count}：(${x.toFixed(0)},${y.toFixed(0)}) r${r.toFixed(0)} 出框`);
    }
    const last = a.frames.at(-1), xs = [...last.matchAll(/<ellipse cx="([\d.-]+)" cy="[\d.-]+" rx="[\d.]+" ry="1\d|<ellipse cx="([\d.-]+)"/g)].map((m) => +(m[1] ?? m[2]) / L);
    assert.ok(Math.max(...xs) - Math.min(...xs) > 120, `散開寬度 ${(Math.max(...xs) - Math.min(...xs)).toFixed(0)} 太窄`);
  }
});

test('跑馬燈：級別字放大（預設字高 ≥ 框高 20%）；labelSize 可調', () => {
  const size = (svg) => Math.max(...[...svg.matchAll(/stroke-width="([\d.]+)" stroke-linejoin="bevel"/g)].map((m) => +m[1]));
  const big = asset('jp_marquee', {}), small = asset('jp_marquee', { labelSize: 14 });
  // 只有級別字（數字槽空）→ 內層筆寬＝字高/6 × 1.55
  assert.ok(size(big.svg) / 1.55 * 6 >= big.meta.h * 0.2 * 0.9, '級別字太小');
  assert.ok(size(small.svg) < size(big.svg));
});
