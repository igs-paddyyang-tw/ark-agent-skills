// ark-svg-animation 驗收（規格 AC-2～AC-5、AC-8）：每個守門都正反各測一次。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { creature, classify, renderPhase, RIGS, SPECIES } from '../svg_anim.mjs';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import * as fusiform from '../rigs/fusiform.mjs';
import { checkSecurity, checkSize, checkSeam, checkDeterminism, checkWellFormed, checkIdsUnique, verify, SAMPLE } from '../verify_svg.mjs';

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


// ── M2：13 種體型、登錄表、gen／preview ─────────────────────────────────────
test('13 種體型都有 rig 且都被登錄表用到', () => {
  assert.equal(Object.keys(RIGS).length, 13);
  const used = new Set(Object.values(SPECIES).map((r) => r.archetype));
  for (const a of Object.keys(RIGS)) assert.ok(used.has(a), `體型 ${a} 沒有任何物種使用`);
  for (const [n, r] of Object.entries(SPECIES)) assert.ok(RIGS[r.archetype], `${n} 的體型 ${r.archetype} 不存在`);
});

test('登錄表：配色與參數生效；gold 變體蓋過登錄表配色；未登錄標 fallback', () => {
  const svg = creature({ name: 'NEMO' }).frames.swim[0];
  assert.match(svg, /#ff7a1a/, '小丑魚用登錄表的橘色');
  assert.doesNotMatch(creature({ name: 'NEMO', variants: ['gold'] }).frames.swim[0], /#ff7a1a/);
  assert.equal(creature({ name: 'FLASH_SHARK' }).meta.archetype, 'jelly', '電光水母：名字有 SHARK 但登錄為水母');
  assert.equal(creature({ name: 'NO_SUCH_FISH' }).meta.fallback, true);
  assert.equal(creature({ name: 'NO_SUCH_FISH' }, {}).meta.fallback, true);
  assert.equal(classify('LINE_PUFFER_FISH').archetype, 'puffer');
});

test('verify：登錄表全部物種 × 4 變體在 --strict 下全過', () => {
  const rep = verify(SAMPLE, { strict: true });
  assert.ok(rep.ok, rep.problems.slice(0, 5).join('\n'));
  assert.ok(rep.checked >= 33);
});

test('CLI gen／preview：產出檔案與 manifest；未知指令 rc=2', () => {
  const tmp = mkdtempSync(path.join(tmpdir(), 'svga-'));
  const cli = path.join(dir, 'svg_anim.mjs');
  execFileSync(process.execPath, [cli, 'gen', '--out', tmp, '--names', 'SHARK,BOMB_CRAB', '--length', '80']);
  const m = JSON.parse(readFileSync(path.join(tmp, 'manifest.json'), 'utf8'));
  assert.deepEqual(Object.keys(m.species).sort(), ['BOMB_CRAB', 'SHARK']);
  assert.ok(existsSync(path.join(tmp, m.species.SHARK.frames.catch[2])));
  execFileSync(process.execPath, [cli, 'preview', '--out', path.join(tmp, 'p.html'), '--names', 'NEMO']);
  assert.match(readFileSync(path.join(tmp, 'p.html'), 'utf8'), /NEMO/);
  assert.throws(() => execFileSync(process.execPath, [cli, 'nope'], { stdio: 'pipe' }), (e) => e.status === 2);
});

// ── 0.4.0：漸層、眼睛、裁切、光暈；同頁內嵌不撞 id ────────────────────────────
export function allIds(svgs) {
  return svgs.flatMap((s) => [...s.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]));
}

test('同一頁內嵌多張 SVG：所有 id 唯一（fish-bot D-285 踩過漸層互撞）', () => {
  const svgs = ['NEMO', 'SHARK', 'BOMB_CRAB', 'FIRE_DRAGON', 'GIANT_NEMO'].flatMap((n) => { const f = creature({ name: n, variants: ['glow'] }).frames; return [...f.swim, ...f.catch]; });
  const ids = allIds(svgs);
  assert.ok(ids.length > 20, `應該有漸層／裁切 id，實際 ${ids.length}`);
  assert.equal(new Set(ids).size, ids.length, '有重複 id');
  // 每個 url(#x) 都要在同一張圖內有定義
  for (const s of svgs) for (const [, ref] of s.matchAll(/url\(#([^)]+)\)/g)) assert.ok(s.includes(`id="${ref}"`), `懸空參照 ${ref}`);
});

test('同參數不同 params（體寬）：id 也要不同 —— 裁切依幾何而定', () => {
  const a = creature({ name: 'NEMO' }).frames.swim[0], b = creature({ name: 'NEMO', params: { bodyW: 0.6 } }).frames.swim[0];
  assert.deepEqual(checkIdsUnique([a, b]), []);
  assert.notDeepEqual(allIds([a]), allIds([b]));
});

test('新圖元：漸層填色、三圓眼睛、花紋裁切、光暈', () => {
  const nemo = creature({ name: 'NEMO' }).frames.swim[0];
  assert.match(nemo, /<radialGradient /);
  assert.match(nemo, /<clipPath /);
  assert.equal((nemo.match(/<circle /g) ?? []).length, 6, '兩隻眼睛 × 3 圓');
  assert.match(creature({ name: 'NEMO', variants: ['glow'] }).frames.swim[0], /stop-opacity="0"/);
  const caught = creature({ name: 'NEMO' }).frames.catch[0];
  assert.doesNotMatch(caught, /stop-color="#ff7a1a"/, '被捕閃白也要套到漸層色');
});

test('同種魚不同版本（變體／尺寸）同頁：id 不撞；verify 的唯一性檢查反證會紅', () => {
  const svgs = [creature({ name: 'NEMO' }), creature({ name: 'NEMO', variants: ['gold'] }), creature({ name: 'NEMO', length: 200 })].flatMap((g) => [...g.frames.swim, ...g.frames.catch]);
  assert.deepEqual(checkIdsUnique(svgs), []);
  const one = creature({ name: 'NEMO' }).frames.swim[0];
  assert.deepEqual(checkIdsUnique([one, one]), [], '同一張貼兩次：定義相同，不算衝突');
  // 反證：同 id、不同定義（把漸層顏色改掉）→ 必紅
  const forged = one.replace(/stop-color="#[0-9a-f]{6}"/, 'stop-color="#000000"');
  assert.notEqual(forged, one);
  assert.equal(checkIdsUnique([one, forged]).length, 1, '同 id 不同定義要紅');
});
