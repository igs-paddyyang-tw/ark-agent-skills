# gamekit —— 魚機／老虎機必要圖元素（0.5.0 起）

> 規格 kiro-cli `docs/specs/ark-svg-animation-spec.md` §7；計畫 `docs/plans/ark-svg-animation-gamekit-plan.md`。
> 原則：**通用元素收進 kit，遊戲專屬角色留在各專案**（豬、狼、神燈、貓等角色不進上游；生物走 `creature()`）。

## 介面

```js
import { asset, KINDS, SAMPLES, THEMES } from './gamekit.mjs';
const { svg, meta } = asset('label', { text: 'MEGA WIN', size: 72, fill: 'gold', theme: 'neon-night' });
// meta：{ version, kind, alias, category, w, h, anchor, theme, profile }
```

| 共同參數 | 說明 |
|---|---|
| `theme` | `royal-gold`（預設）／`jade-jungle`／`deep-sea`／`neon-night`，或覆寫物件 `{ base: 'deep-sea', primary: { main: '#123456' } }` |
| `profile` | `texture`（預設：轉貼圖、wg_pack_assets → WebP）／`flat`（PixiJS `new Graphics().svg(svg)` 直接用） |
| `alias` | 輸出別名（對應 `assets.yaml` 的圖名）；不給就用 kind 預設 |

## kind（0.5.0）

| kind | 參數 | 分類（預算） |
|---|---|---|
| `label` | `text`（必填）、`size` 字高 px（64）、`fill`（`'gold'｜'silver'｜'bronze'`＝金屬漸層，或色碼）、`ink` 外框色、`outline`、`spacing` | text（8 KB） |
| `plate` | `shape`：`arch`／`circle`／`shield`／`diamond`；`color`：`'primary'｜'accent'｜{ main, dark, light }`；`rim`：金屬；`size`（256） | symbol（6 KB） |

後續（計畫 M6／M7）：`royal`、`badge`、`icon`、`frame`、`reel_bg`、`reel_frame`、`panel`、`button`、`bg`、`jp_plate`、`win_banner`、`fg_banner`、`coin`、`cannon`、`bullet`、`net`、`bead`、`lock`。

## 字形（`glyphs.mjs`）

- 原創切角筆畫字：A–Z、0–9、空白與 `+ - × . , ! ? : / % $ ¥ #`；小寫自動轉大寫
- 格線 寬 0..4 × 高 0..6，筆畫是中心線；`layoutText(str, { x, y, size, align, spacing })` 回筆畫座標，`measure(str)` 回字寬
- 未支援字元直接丟錯並列出字元 —— **中日文不內建**：使用方自備 path，或在自己的專案用字型（承擔換機器字型不同的風險）
- texture：兩層 stroke path（`stroke-linejoin=bevel`、`stroke-linecap=square`）；flat：同幾何轉成填色多邊形（整數像素）

## flat profile（PixiJS 8.6.6 `GraphicsContext.svg()`）

讀 Pixi 原始碼（`scene/graphics/shared/svg/SVGParser`）確認的限制與對策：

| Pixi 行為 | flat 對策 |
|---|---|
| `<polygon>`／`<polyline>` 的 points 用 `/\d+/g` 解析 —— 小數與負號被拆開 | 一律輸出 `<path>` |
| 有 `style` 就忽略 `fill`／`stroke` 屬性；子元素關不掉繼承的填色 | 每個圖元自帶完整 style（含 `fill:none`）、不輸出 `<g>` |
| 不支援漸層（`url(#…)` 直接丟錯）、裁切、transform、`<text>` | 漸層取平均色、略過被裁切的花紋、仿射矩陣烘焙進座標 |
| 不讀 `stroke-linecap`／`stroke-linejoin`／`stroke-dasharray` | 字改多邊形；虛線略過 |
| 可旋轉的橢圓不支援 | 轉 4 段貝茲 path |

驗證：`verify_svg` 的 `checkFlat`（靜態規則）＋ `pixi_check.mjs`（Pixi 與瀏覽器各畫一次，遮罩擴 1 px 互相涵蓋率 ≥ 0.95）。

## 新增 kind 的步驟

1. `gamekit.mjs` 的 `KINDS` 加 `{ category, build(spec, theme) → { w, h, L?, parts, alias, anchor? } }` —— 顏色一律取自 theme token
2. `SAMPLES` 加涵蓋所有選項的樣本（沒有樣本＝verify 紅）
3. `node verify_svg.mjs`、`ARK_SVGA_PIXI=… node pixi_check.mjs`、`node --test tests/*.test.mjs` 全綠；`gamekit.mjs preview` 目視
4. 造型改變升 minor
