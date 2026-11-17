// gamekit 0.10.0：aidev 回饋 §2 缺的 10 項 —— 空槽、參數守門、動畫接縫、一次性動畫；接縫檢查忽略色碼（反證：幾何跳動仍抓得到）。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { asset, assetPhase, KINDS } from '../gamekit.mjs';
import { checkSeam, checkFlat, verifyKit } from '../verify_svg.mjs';

const NEW = ['fg_intro', 'multiplier', 'fg_counter', 'info_bar', 'dialog', 'loading_bar', 'coin_burst', 'tide_banner', 'boss_warning', 'jp_marquee'];
const words = (svg) => (svg.match(/stroke-linejoin="bevel"/g) ?? []).length / 2;

test('10 個新 kind 都在，verifyKit（確定性、預算、flat、換 theme、接縫）全綠', () => {
  for (const k of NEW) assert.ok(KINDS[k], k);
  const r = verifyKit({ kinds: NEW });
  assert.equal(r.ok, true, r.problems.slice(0, 5).join('\n'));
});

test('空槽：數字預設不出字，給值才出字', () => {
  assert.equal(words(asset('fg_counter', {}).svg), 1);
  assert.equal(words(asset('fg_counter', { value: '12' }).svg), 2);
  assert.equal(words(asset('info_bar', {}).svg), 3);
  assert.equal(words(asset('info_bar', { values: ['1', '2', '3'] }).svg), 6);
  assert.equal(words(asset('dialog', { buttons: 2 }).svg), 0, '標題與按鈕字預設空');
  assert.equal(words(asset('fg_intro', {}).svg), 2, '主字＋SPINS，次數空槽');
  assert.equal(words(asset('fg_intro', { count: '10' }).svg), 3);
  assert.equal(words(asset('jp_marquee', {}).svg), 1, '只有級別字');
});

test('參數守門：錯的值報錯並說明', () => {
  assert.throws(() => asset('multiplier', { value: 'abc' }), /要是數字/);
  assert.throws(() => asset('multiplier', { value: 2, shape: 'heart' }), /burst／pill/);
  assert.throws(() => asset('info_bar', { labels: [] }), /1～5/);
  assert.throws(() => asset('dialog', { buttons: 3 }), /0／1／2/);
  assert.throws(() => asset('loading_bar', { value: 1.5 }), /0～1/);
  assert.throws(() => asset('loading_bar', { part: 'glow' }), /all／track／fill/);
  assert.throws(() => asset('coin_burst', { count: 99 }), /1～40/);
  assert.throws(() => asset('fg_intro', { mode: 'jackpot' }), /free／bonus/);
  assert.throws(() => asset('jp_marquee', { tier: 'Mega' }), /Grand/);
});

test('倍率：×2～×100 依倍率分色；value 可帶或不帶 ×', () => {
  assert.equal(asset('multiplier', { value: '×10' }).svg, asset('multiplier', { value: 10 }).svg);
  assert.notEqual(asset('multiplier', { value: 2 }).svg, asset('multiplier', { value: 100 }).svg);
  assert.equal(asset('multiplier', { value: 50 }).meta.alias, 'mult_x50');
});

test('金幣噴發：一次性、各格不同、同 seed 相同／不同 seed 不同；flat 合規', () => {
  const a = asset('coin_burst', { seed: 1 }), b = asset('coin_burst', { seed: 2 });
  assert.equal(a.meta.loop, false);
  assert.equal(new Set(a.frames).size, a.frames.length);
  assert.deepEqual(a.frames, asset('coin_burst', { seed: 1 }).frames);
  assert.notDeepEqual(a.frames, b.frames);
  for (const f of asset('coin_burst', { profile: 'flat' }).frames) assert.deepEqual(checkFlat(f), []);
});

test('接縫檢查忽略色碼：只換顏色的跑馬燈不誤報；幾何真的跳一下仍會紅', () => {
  const fr = asset('jp_marquee', { profile: 'flat' });
  assert.deepEqual(checkSeam(fr.frames, assetPhase('jp_marquee', { profile: 'flat' }, 1)), []);
  const W = (r, c) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 50 50" width="50" height="50"><circle cx="25" cy="25" r="${r}" style="fill:${c}"/></svg>`;
  assert.deepEqual(checkSeam([W(10, '#111111'), W(10, '#999999'), W(10, '#111111'), W(10, '#999999')], W(10, '#111111')), [], '只有顏色在變');
  assert.ok(checkSeam([W(10, '#111111'), W(11, '#111111'), W(12, '#111111'), W(13, '#111111')], W(20, '#111111')).length > 0, '半徑跳動要紅');
});
