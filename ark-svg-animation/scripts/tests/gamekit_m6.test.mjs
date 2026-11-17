// gamekit M6（0.6.0）：老虎機符號、UI、共用演出物 —— 覆蓋率、動畫接縫、參數守門、flat 光暈；每項附反證。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { asset, assetPhase, KINDS, COVERAGE } from '../gamekit.mjs';
import { verifyCoverage, verifyKit, checkFlat, checkSeam } from '../verify_svg.mjs';

test('覆蓋率：aidev 兩款非專屬別名 100% 產得出來；kind 不存在／對照表空必紅（AC-G4）', () => {
  const r = verifyCoverage();
  assert.equal(r.ok, true, r.problems.join('\n'));
  for (const game of ['magic-lamp', 'huffnpuff']) {
    const rows = COVERAGE.filter((x) => x.game === game);
    assert.ok(rows.length >= 30 && rows.some((x) => x.kind === null), `${game} 要有專屬列（角色／Logo 不進 kit）`);
  }
  assert.ok(verifyCoverage([...COVERAGE, { game: 'x', alias: 'sym_Z', kind: 'nope', spec: {} }]).problems.some((p) => p.includes('sym_Z')));
  assert.ok(verifyCoverage([]).problems.some((p) => p.includes('範圍是空的')));
});

test('動畫 kind：格數、各格同尺寸、texture／flat 接縫都過；相位不回原點必紅（AC-G5）', () => {
  for (const kind of ['win_banner', 'coin']) {
    assert.ok(KINDS[kind].anim, `${kind} 要是動畫 kind`);
    for (const profile of ['texture', 'flat']) {
      const out = asset(kind, { profile });
      assert.equal(out.frames.length, KINDS[kind].anim.frames);
      assert.equal(out.meta.frames, out.frames.length);
      assert.deepEqual(checkSeam(out.frames, assetPhase(kind, { profile }, 1)), [], `${kind}/${profile}`);
    }
  }
  assert.equal(asset('coin', { frames: 8 }).frames.length, 8);
  const drift = (k, s, t) => assetPhase(k, s, t * 0.5 + 0.25);     // t＝1 停在半圈 → 不是週期
  assert.ok(verifyKit({ kinds: ['coin'], phase: drift }).problems.some((p) => p.includes('週期') || p.includes('接縫')));
});

test('參數守門：未知選項報錯並列出可用值', () => {
  assert.throws(() => asset('royal', { letter: 'Z' }), /A／K／Q／J／10／9/);
  assert.throws(() => asset('badge', { type: 'mystery' }), /wild/);
  assert.throws(() => asset('icon', { name: 'sword' }), /crown/);
  assert.throws(() => asset('frame', { level: 4 }), /1／2／3/);
  assert.throws(() => asset('button', { icon: 'menu' }), /spin/);
  assert.throws(() => asset('bg', { motif: 'lava' }), /rays/);
  assert.throws(() => asset('reel_bg', { cols: 9 }), /1～8/);
  assert.throws(() => asset('jp_plate', { tier: 'Mega' }), /Grand/);
  assert.throws(() => asset('win_banner', { tier: 'ultra' }), /big/);
});

test('flat 光暈：放射淡出改疊多層同心圓（不是一整片實心圓）；換成單層必被看出來', () => {
  const svg = asset('bg', { motif: 'stars', profile: 'flat' }).svg;
  assert.deepEqual(checkFlat(svg), []);
  const big = (svg.match(/<circle[^>]*r="(\d+(?:\.\d+)?)"[^>]*fill-opacity/g) ?? []).filter((c) => Number(/r="([\d.]+)"/.exec(c)[1]) > 100);
  assert.ok(big.length >= 4, `光暈要有多層（實得 ${big.length}）`);
  const tex = asset('bg', { motif: 'stars' }).svg;
  assert.match(tex, /<radialGradient/);                            // texture 仍用真的漸層
});

test('符號類全部 256 基準可縮放：size 改變 → 尺寸跟著變、內容等比', () => {
  for (const [kind, spec] of [['royal', { letter: 'K' }], ['badge', { type: 'wild' }], ['icon', { name: 'bell' }], ['frame', { level: 3 }], ['button', { icon: 'plus' }]]) {
    const a = asset(kind, { ...spec, size: 128 });
    assert.deepEqual([a.meta.w, a.meta.h], [128, 128], kind);
    assert.match(a.svg, /viewBox="0 0 128 128"/);
  }
});
