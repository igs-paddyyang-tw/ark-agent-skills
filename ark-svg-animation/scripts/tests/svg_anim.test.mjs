// ark-svg-animation 驗收（規格 AC-2～AC-5、AC-8）：每個守門都正反各測一次。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { creature, classify, renderPhase, RIGS } from '../svg_anim.mjs';
import * as fusiform from '../rigs/fusiform.mjs';
import { checkSecurity, checkSize, checkSeam, checkDeterminism, checkWellFormed, verify, SAMPLE } from '../verify_svg.mjs';

const dir = fileURLToPath(new URL('..', import.meta.url));

test('確定性：同參數逐位元組相同；不同名字配色不同', () => {
  assert.deepEqual(creature({ name: 'SHARK', length: 160 }), creature({ name: 'SHARK', length: 160 }));
  const fill = (n) => /fill="(#[0-9a-f]{6})"/.exec(creature({ name: n }).frames.swim[0])[1];
  assert.notEqual(fill('NEMO'), fill('GURNARD'));
});

test('每種體型：swim 4 格、catch 3 格；同狀態 viewBox 一致；facing right 長寬對調', () => {
  for (const name of ['NEMO', 'SHARK', 'BOMB_CRAB']) {
    const { frames, meta } = creature({ name, length: 120 });
    assert.equal(frames.swim.length, 4);
    assert.equal(frames.catch.length, 3);
    assert.equal(new Set(frames.swim.map((s) => /viewBox="([^"]+)"/.exec(s)[1])).size, 1, name);
    const r = creature({ name, length: 120, facing: 'right' }).meta;
    assert.deepEqual(r.viewBox, [meta.viewBox[1], meta.viewBox[0]]);
  }
});

test('AC-8 原創：不接受外部圖片參數', () => {
  assert.throws(() => creature({ name: 'NEMO', image: 'x.png' }), /不接受外部圖片/);
});

test('名稱解析：前綴、旋風、蟹配件、鯊', () => {
  assert.equal(classify('SINGLE_GURNARD').base, 'GURNARD');
  assert.deepEqual(classify('TWIST_NEMO').variants, ['twister']);
  assert.equal(classify('SERIAL_DRILL_CRAB').accessory, 'drill');
  assert.equal(classify('BOMB_CRAB').accessory, 'bomb');
  assert.equal(classify('KILLER_WHALE').archetype, 'shark');
  assert.equal(classify('X', { X: { archetype: 'crab' } }).archetype, 'crab', '登錄表優先');
});

test('AC-4 安全：乾淨輸出通過；注入 <script>／href／事件屬性必紅', () => {
  const svg = creature({ name: 'NEMO' }).frames.swim[0];
  assert.deepEqual(checkSecurity(svg), []);
  assert.equal(checkSecurity(svg.replace('</svg>', '<script>x</script></svg>')).length, 1);
  assert.equal(checkSecurity(svg.replace('<g', '<g onload="x()"')).length, 1);
  assert.equal(checkSecurity(svg.replace('<g', '<image href="http://x/a.png"/><g')).length, 2);
  assert.deepEqual(checkWellFormed(svg), []);
  assert.equal(checkWellFormed(svg.replace('</g></g>', '</g>')).length, 1, '少關一個 g 必紅');
});

test('AC-5 體積：≤ 4 KB 通過；塞大必紅', () => {
  const svg = creature({ name: 'BOMB_CRAB', length: 200 }).frames.swim[0];
  assert.deepEqual(checkSize(svg), []);
  assert.equal(checkSize(svg + ' '.repeat(5000)).length, 1);
});

test('AC-3 接縫：現有三種體型通過；不是週期／不等速必紅', () => {
  for (const name of ['NEMO', 'SHARK', 'WHEEL_CRAB']) {
    const f = creature({ name }).frames.swim;
    assert.deepEqual(checkSeam(f, renderPhase({ name }, 1)), [], name);
  }
  // 反證 1：轉輪一個循環轉 90°（3 根輪輻每 60° 對稱 → t＝1 不等於 t＝0）
  RIGS.badwheel = { ...fusiform, parts: (t, p, c) => [{ k: 'polyline', pts: [[Math.cos(t * Math.PI / 2) * 0.3, 0.5 + Math.sin(t * Math.PI / 2) * 0.3], [0, 0.5]], stroke: c.dark }] };
  try {
    const bad = creature({ name: 'X', archetype: 'badwheel' }).frames.swim;
    assert.ok(checkSeam(bad, renderPhase({ name: 'X', archetype: 'badwheel' }, 1)).some((m) => m.includes('不是週期')));
  } finally { delete RIGS.badwheel; }
  // 合成數列分開驗兩段：週期且等速 → 過；最後一段跳（連續性）→ 紅；t＝1 ≠ 第一格（週期性）→ 紅
  const f = ['<a 10>', '<a 0>', '<a -10>', '<a 0>'];
  assert.deepEqual(checkSeam(f, '<a 10>'), []);
  assert.ok(checkSeam(['<a 0>', '<a 10>', '<a 20>', '<a 30>'], '<a 0>').some((m) => m.includes('循環接縫')), '最後一格 → 下一循環跳一大步');
  const tri = ['<a 0>', '<a 10>', '<a 20>', '<a 30>', '<a 20>', '<a 10>'];
  assert.deepEqual(checkSeam(tri, '<a 0>'), [], '等速三角波要過');
  assert.ok(checkSeam(tri.map((x, i) => (i === 3 ? '<a 45>' : x)), '<a 0>').some((m) => m.includes('不等速')), '循環中間抖一格也要紅');
  assert.ok(checkSeam(f, '<a 3>').some((m) => m.includes('不是週期')));
});

test('AC-2 確定性守門：偷用 Math.random 必紅', () => {
  assert.deepEqual(checkDeterminism((s) => creature(s), { name: 'NEMO' }), []);
  assert.equal(checkDeterminism((s) => ({ ...creature(s), x: Math.random() }), { name: 'NEMO' }).length, 1);
});

test('原始碼不用 Math.random／Date（動畫只靠相位函式）', () => {
  const files = ['svg_anim.mjs', ...readdirSync(`${dir}/rigs`).map((f) => `rigs/${f}`)];
  const code = (f) => readFileSync(`${dir}/${f}`, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, ''); // 去掉註解再掃
  for (const f of files) assert.doesNotMatch(code(f), /Math\.random|Date\.now|new Date\(/, f);
});

test('verify：樣本全過；0 個物種不算通過', () => {
  const rep = verify(SAMPLE);
  assert.ok(rep.ok, rep.problems.join('\n'));
  assert.equal(verify([]).ok, false);
});
