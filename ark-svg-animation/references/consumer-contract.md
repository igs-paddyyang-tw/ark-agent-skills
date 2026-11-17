# 使用方契約（函式庫 API、輸出格式、版號）

## 引用方式

前端打包不能依賴 `.kiro/skills/…` 路徑 → **複製 `scripts/` 整個目錄**進專案（例：`pixi-client/packages/svg-anim/`），
在專案的來源清單（例：`VENDORED.json`）記上游 repo、commit、`VERSION`、sha256。更新時重新複製並比對 `VERSION`。
`scripts/` 只依賴自己（零相依）；`sheet.mjs`／`verify_svg.mjs` 只在 node 用，可不打包。

## 函式庫

```js
import { creature, renderPhase, classify, SPECIES, RIGS, VERSION } from './svg_anim.mjs';
const { frames, meta } = creature({ name, length, facing, variants, palette, params, frames: { swim: 4, catch: 3 } }, registry?);
```

| 回傳 | 說明 |
|---|---|
| `frames.swim`／`frames.catch` | SVG 字串陣列；同一狀態每格 viewBox 相同（錨點不跳） |
| `meta.viewBox` | `[寬, 高]` 像素 |
| `meta.anchor` | 身體中心（0～1），直接給 PixiJS `sprite.anchor` |
| `meta.bodyBox`／`meta.hitRadius` | 身體框與碰撞參考半徑（像素）；使用方可沿用自己的判定 |
| `meta.version` | 造型或演算法版號 —— 快取鍵請包含它 |
| `meta.fallback` | `true`＝名字未登錄、以預設體型代替（畫面不會空白，但該補登錄） |

`registry` 省略＝內建 `SPECIES`；傳 `{}` 只用關鍵字規則；傳自己的表可覆寫或新增物種（同欄位格式，見 `species-registry.md`）。

## 執行期（瀏覽器）補位

```ts
const { frames, meta } = creature({ name: fish.name, length: tierLength(fish.odds) });
const textures = frames.swim.map((svg) => /* Graphics.svg(svg) → renderer.generateTexture(...) 或 Texture.from(dataURL) */);
// 第一次用到才產生並快取（以 name＋length＋VERSION 為鍵）
```

## 建置期 spritesheet（`sheet.mjs`）

每種一組 `<NAME>.png`＋`<NAME>.json`（TexturePacker hash 格式），外加 `index.json`：

```json
{ "frames": { "SHARK/swim_0": { "frame": {"x":0,"y":0,"w":104,"h":117}, "anchor": {"x":0.5,"y":0.45}, ... } },
  "animations": { "swim": ["SHARK/swim_0", ...], "catch": [...] },
  "meta": { "image": "SHARK.png", "size": {"w":..,"h":..}, "scale": "1", "version": "0.3.0", "creature": { ...meta } } }
```

PixiJS：`const sheet = await Assets.load('SHARK.json'); new AnimatedSprite(sheet.animations.swim)`。
驗收：`sheet.mjs --check <dir> [--pixi <pixi.min.js>]`（PNG 尺寸＝JSON、每格非空白、真的 PixiJS 讀得進）。

## PixiJS Graphics 直接解析（0.5.0 起）

不轉貼圖、想用 `new Graphics().svg(svg)` 的專案（例：aidev 魚機）傳 `profile: 'flat'`：

```js
creature({ name: 'NEMO', length: 104, profile: 'flat' });
asset('plate', { shape: 'circle', profile: 'flat' });
```

flat 沒有漸層、裁切花紋與 transform（Pixi 8.6.6 不支援）；限制與驗證方式見 `references/gamekit.md`。

## 建置期整套產出（0.7.0 起）

寫一份 `kit.json`（範例 `assets/kit.slot.example.json`／`kit.fish.example.json`），兩種接法：

1. 直接跑：`node gamekit.mjs --config kit.json --out art/`
2. ark-web-game：`assets.yaml` 的 `sources.art.generator: art/kit.json` → `wg_pack_assets` 自動呼叫並轉 WebP（需要 ark-web-game ≥ 0.13.0）
