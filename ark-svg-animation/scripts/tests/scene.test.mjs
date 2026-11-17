// scene（0.11.0）：關鍵字 → 原創背景、色票覆寫、參考圖取色 —— 每項附反證。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { asset } from '../gamekit.mjs';
import { parseKeywords, assignRoles, SCENE_ELEMENTS } from '../kit/scene.mjs';
import { verifyKit } from '../verify_svg.mjs';
import { extractPalette } from '../palette.mjs';
import { findChrome } from '../sheet.mjs';

test('關鍵字解析：氛圍＋元素；單字誤中（金字塔→塔、火山→山）不再發生；不認得的詞列出來', () => {
  const a = parseKeywords('沙漠 宮殿 夜晚 神燈');
  assert.equal(a.mood, 'night');
  assert.ok(['dunes', 'palace', 'moon', 'stars'].every((e) => a.elements.includes(e)));
  assert.ok(!parseKeywords('埃及 金字塔').elements.includes('pagoda'), '金字塔不該觸發寶塔');
  assert.ok(!parseKeywords('火山 熔岩').elements.includes('mountains'), '火山不該觸發山脈');
  assert.equal(parseKeywords('深海 珊瑚').mood, 'underwater');
  assert.equal(parseKeywords('tropical beach palm sunset').mood, 'dusk');
  assert.deepEqual(parseKeywords('城堡 獨角獸').unknown, ['獨角獸']);
  assert.ok(parseKeywords('城堡 雪').elements.includes('pines') && !parseKeywords('城堡 雪').elements.includes('trees'), '雪景的樹要是松樹');
  assert.throws(() => parseKeywords(''), /keywords 必填/);
});

test('scene：確定性、seed 改變粒子、meta.recipe 帶解析結果；未知元素報錯', () => {
  const a = asset('scene', { keywords: '賭城 夜' });
  assert.equal(a.svg, asset('scene', { keywords: '賭城 夜' }).svg);
  assert.notEqual(a.svg, asset('scene', { keywords: '賭城 夜', seed: 9 }).svg);
  assert.equal(a.meta.recipe.mood, 'night');
  assert.ok(a.meta.recipe.landmarks.includes('city'));
  assert.equal(asset('scene', { keywords: 'x', w: 1280, h: 720 }).meta.w, 1280);
  assert.throws(() => asset('scene', { keywords: '夜', elements: ['dragon'] }), /未知元素 dragon/);
  assert.ok(SCENE_ELEMENTS.includes('palace'));
});

test('色票：物件覆寫指定角色、色碼陣列依亮度分派；少於 3 色報錯', () => {
  const base = asset('scene', { keywords: '深海' }).svg;
  assert.match(asset('scene', { keywords: '深海', palette: { accent: '#00ff00' } }).svg, /#00ff00/);
  assert.notEqual(asset('scene', { keywords: '深海', palette: ['#000000', '#555555', '#ff0000', '#ffffff'] }).svg, base);
  const r = assignRoles(['#ffffff', '#000000', '#ff0000', '#777777']);
  assert.equal(r.near, '#000000'); assert.equal(r.particle, '#ffffff'); assert.equal(r.accent, '#ff0000');
  assert.throws(() => assignRoles(['#000000', '#ffffff']), /至少要 3/);
});

test('verifyKit：11 組 scene 樣本 × 4 theme × 兩種 profile 全綠（預算、flat、確定性）', () => {
  const r = verifyKit({ kinds: ['scene'] });
  assert.equal(r.ok, true, r.problems.slice(0, 3).join('\n'));
});

const chrome = findChrome();
test('參考圖取色：上下兩色的圖取得出兩色；不存在的檔報錯', { skip: chrome ? false : '需要 headless Chromium —— 跳過（不是通過）' }, () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'svga-pal-t-')), img = path.join(dir, 'ref.svg');
  writeFileSync(img, '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="32" fill="#102060"/><rect y="32" width="64" height="32" fill="#e0a040"/></svg>');
  const r = extractPalette(img, { k: 4 });
  const near = (hex, target) => [1, 3, 5].every((i) => Math.abs(parseInt(hex.slice(i, i + 2), 16) - parseInt(target.slice(i, i + 2), 16)) <= 8);
  assert.ok(r.colors.some((c) => near(c, '#102060')) && r.colors.some((c) => near(c, '#e0a040')), r.colors.join(','));
  assert.throws(() => extractPalette(path.join(dir, 'nope.png')), /找不到圖/);
});
