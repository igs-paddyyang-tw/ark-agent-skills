// sheet.mjs 驗收（規格 AC-6）：拼圖 PNG／JSON 一致、每格非空白、PixiJS 讀得進；每項反證會紅。
// 需要 headless Chromium（findChrome）；PixiJS 解析另需 ARK_SVGA_PIXI=<pixi.min.js>。缺了就明說跳過。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { buildSheets, checkSheet, findChrome, layout, pixiParse, sheetJson } from '../sheet.mjs';
import { creature } from '../svg_anim.mjs';

const chrome = findChrome();

test('排版與 JSON：格數、animations、尺寸（不需瀏覽器）', () => {
  const { frames, meta } = creature({ name: 'SHARK', length: 80 });
  const lay = layout(frames, meta);
  const j = sheetJson('SHARK', lay, meta, 2);
  assert.equal(Object.keys(j.frames).length, 7);
  assert.deepEqual(Object.keys(j.animations), ['swim', 'catch']);
  assert.equal(j.meta.size.w, lay.width * 2);
  assert.equal(j.frames['SHARK/swim_1'].frame.x, (Math.ceil(meta.viewBox[0]) + 2) * 2, '格間隔 2px × scale');
});

test('拼圖：產出通過；尺寸不符／空白格必紅', { skip: chrome ? false : '找不到 headless Chromium —— 跳過（不是通過）' }, () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'svga-sheet-t-'));
  const r = buildSheets({ out: dir, names: ['SHARK', 'BOMB_CRAB'], length: 80, chrome });
  assert.deepEqual(r.built, ['SHARK', 'BOMB_CRAB']);
  assert.deepEqual(checkSheet(dir, 'SHARK'), []);
  const jp = path.join(dir, 'SHARK.json'), j = JSON.parse(readFileSync(jp, 'utf8'));
  writeFileSync(jp, JSON.stringify({ ...j, meta: { ...j.meta, size: { w: j.meta.size.w + 5, h: j.meta.size.h } } }));
  assert.ok(checkSheet(dir, 'SHARK').some((m) => m.includes('≠ JSON')), '尺寸不符要紅');
  const blank = structuredClone(j);
  blank.frames['SHARK/swim_0'].frame = { x: 0, y: 0, w: 1, h: 1 };
  writeFileSync(jp, JSON.stringify(blank));
  assert.ok(checkSheet(dir, 'SHARK').some((m) => m.includes('空白格')), '指到空白區域要紅');
});

const pixi = process.env.ARK_SVGA_PIXI;
test('PixiJS Spritesheet.parse：讀得進；壞 JSON 必紅', { skip: chrome && pixi ? false : '需要 Chromium 與 ARK_SVGA_PIXI=<pixi.min.js> —— 跳過（不是通過）' }, () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'svga-pixi-t-'));
  buildSheets({ out: dir, names: ['NEMO'], length: 60, chrome });
  assert.deepEqual(pixiParse(dir, ['NEMO'], pixi, chrome), []);
  const jp = path.join(dir, 'NEMO.json'), j = JSON.parse(readFileSync(jp, 'utf8'));
  j.animations.swim = j.animations.swim.slice(0, 2);       // JSON 說 swim 2 格，但 frames 還在 —— 比對 JSON 自己會過
  j.frames = { bogus: { frame: null } };                   // PixiJS 讀不懂 → 解析失敗
  writeFileSync(jp, JSON.stringify(j));
  assert.ok(pixiParse(dir, ['NEMO'], pixi, chrome).length > 0, '壞 JSON 要紅');
});
