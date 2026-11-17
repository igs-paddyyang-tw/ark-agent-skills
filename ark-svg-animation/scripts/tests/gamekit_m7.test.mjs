// gamekit M7（0.7.0）：魚機元素、一次性動畫、產生器 CLI、接縫只比 flat —— 每項附反證。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { asset, assetPhase, COVERAGE } from '../gamekit.mjs';
import { draw } from '../draw.mjs';
import { verifyKit, verifyCoverage, checkSeam } from '../verify_svg.mjs';

const KIT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'gamekit.mjs');

test('砲台：1～5 級、錨點在底座圓心、全部圖形在畫布內；6 級報錯', () => {
  for (let lv = 1; lv <= 5; lv++) {
    const a = asset('cannon', { level: lv });
    assert.deepEqual(a.meta.anchor, [0.5, 0.7]);
    const bottom = Math.max(...[...a.svg.matchAll(/cy="([\d.]+)" r="([\d.]+)"/g)].map((m) => Number(m[1]) + Number(m[2])));
    assert.ok(bottom <= a.meta.h + 0.5, `level ${lv} 底部 ${bottom} 超出 ${a.meta.h}`);
  }
  assert.notEqual(asset('cannon', { level: 1 }).svg, asset('cannon', { level: 3 }).svg);
  assert.throws(() => asset('cannon', { level: 6 }), /1～5/);
});

test('一次性動畫（網）：最後一格＝t＝1、各格都不同；循環動畫（鎖定框）接縫過', () => {
  const n = asset('net', {});
  assert.equal(n.meta.loop, false);
  assert.equal(n.frames.at(-1), assetPhase('net', {}, 1));
  assert.equal(new Set(n.frames).size, n.frames.length);
  const l = asset('lock', { profile: 'flat' });
  assert.equal(l.meta.loop, true);
  assert.deepEqual(checkSeam(l.frames, assetPhase('lock', { profile: 'flat' }, 1)), []);
});

test('接縫只比 flat：對稱旋轉（鎖定框轉 90°）不誤判；壓扁再旋轉的放射光必紅', () => {
  // 鎖定框 texture 版的 transform 只差一個 90 —— 舊作法（比 texture 數字）會誤判，現在要全綠
  assert.deepEqual(verifyKit({ kinds: ['lock'] }).problems, []);
  // 反證：壓扁（y×0.5）再轉 30° 的 12 道光 —— 幾何上不對稱，flat 必須抓到
  const W = 200, cx = 100, cy = 100;
  const rays = Array.from({ length: 12 }, (_, i) => { const a = (i * Math.PI) / 6, b = a + 0.16; return { k: 'polygon', pts: [[cx, cy], [cx + 90 * Math.cos(a), cy + 45 * Math.sin(a)], [cx + 90 * Math.cos(b), cy + 45 * Math.sin(b)]], fill: '#ffffff' }; });
  const frame = (t, profile) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${W}" width="${W}" height="${W}">${draw([{ k: 'g', rot: t * 30, ox: cx, oy: cy, children: rays }], { L: 1, pal: { white: '#ffffff' }, k: 0, id: 'x', profile }).body}</svg>`;
  const gen = (k, s) => { const frames = [0, 1, 2, 3, 4, 5].map((i) => frame(i / 6, s.profile)); return { svg: frames[0], frames, meta: { category: 'fx', loop: true } }; };
  const phase = (k, s, t) => frame(t, s.profile);
  const probs = verifyKit({ kinds: ['squash'], samples: { squash: [{}] }, themes: ['royal-gold'], gen, phase }).problems;
  assert.ok(probs.some((p) => p.includes('/flat]') && p.includes('週期')), probs.join('\n'));
  assert.ok(!probs.some((p) => p.includes('/texture]')), 'texture 不比接縫（transform 看不出幾何）');
});

test('覆蓋率含 aidev 魚機：cannon／bullet／net／bead／bg 都產得出；魚種標記走 creature()', () => {
  const r = verifyCoverage();
  assert.equal(r.ok, true, r.problems.join('\n'));
  const fish = COVERAGE.filter((x) => x.game === 'fish' || x.game === 'cat-fish');
  assert.ok(fish.some((x) => x.kind === 'cannon') && fish.some((x) => x.kind === 'bead'));
  assert.ok(fish.filter((x) => x.kind === null).some((x) => x.reason.includes('creature')));
});

test('產生器 CLI：--config 產 <別名>.svg＋動畫格＋manifest；--list；壞設定必紅且說明', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'gk-cli-'));
  const cfg = path.join(dir, 'kit.json');
  writeFileSync(cfg, JSON.stringify({ theme: 'neon-night', assets: { sym_AA: { kind: 'royal', letter: 'A' }, win_big: { kind: 'win_banner', tier: 'big' }, cannon_1: { kind: 'cannon', level: 1 } } }));
  const out = path.join(dir, 'out');
  execFileSync('node', [KIT, '--config', cfg, '--out', out], { encoding: 'utf8' });
  for (const f of ['sym_AA.svg', 'win_big.svg', 'win_big_0.svg', 'win_big_5.svg', 'cannon_1.svg', 'kit-manifest.json']) assert.ok(existsSync(path.join(out, f)), f);
  const man = JSON.parse(readFileSync(path.join(out, 'kit-manifest.json'), 'utf8'));
  assert.equal(man.assets.win_big.frames, 6);
  assert.equal(man.assets.cannon_1.anchor[1], 0.7);
  assert.equal(readFileSync(path.join(out, 'sym_AA.svg'), 'utf8'), asset('royal', { letter: 'A', theme: 'neon-night', alias: 'sym_AA' }).svg);
  const list = execFileSync('node', [KIT, '--config', cfg, '--list'], { encoding: 'utf8' });
  assert.match(list, /^sym_AA 256x256$/m);
  assert.match(list, /^win_big 640x240 ×6$/m);
  const flat = path.join(dir, 'flat');
  execFileSync('node', [KIT, '--config', cfg, '--out', flat, '--only', 'sym_AA', '--profile', 'flat'], { encoding: 'utf8' });
  assert.ok(!existsSync(path.join(flat, 'win_big.svg')), '--only 只產指定別名');
  assert.doesNotMatch(readFileSync(path.join(flat, 'sym_AA.svg'), 'utf8'), /Gradient|transform=/);
  // 反證
  const bad = (assets, extra = []) => { writeFileSync(cfg, JSON.stringify({ assets })); return spawnSync('node', [KIT, '--config', cfg, '--out', out, ...extra], { encoding: 'utf8' }); };
  let r = bad({});
  assert.equal(r.status, 2); assert.match(r.stderr, /範圍是空的/);
  r = bad({ x: { kind: 'dragon' } });
  assert.equal(r.status, 2); assert.match(r.stderr, /x（dragon）.*未知 kind/);
  r = bad({ x: { kind: 'royal', letter: 'Z' } });
  assert.equal(r.status, 2); assert.match(r.stderr, /A／K／Q／J／10／9/);
  r = bad({ x: { kind: 'royal' } }, ['--only', 'y']);
  assert.equal(r.status, 2); assert.match(r.stderr, /--only 的別名不在設定裡：y/);
});

test('範例 kit 設定（assets/）能整份產出', () => {
  for (const f of ['kit.slot.example.json', 'kit.fish.example.json']) {
    const p = path.join(path.dirname(KIT), '..', 'assets', f);
    const out = execFileSync('node', [KIT, '--config', p, '--list'], { encoding: 'utf8' });
    assert.ok(out.trim().split('\n').length >= 8, `${f} 至少 8 個別名`);
  }
});
