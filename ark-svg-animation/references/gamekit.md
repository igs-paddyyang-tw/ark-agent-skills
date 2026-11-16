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

## kind（0.6.0）

| kind | 參數 | 分類（預算） |
|---|---|---|
| `label` | `text`（必填）、`size` 字高 px（64）、`fill`（`'gold'｜'silver'｜'bronze'`＝金屬漸層，或色碼）、`ink`、`outline`、`spacing` | text（8 KB） |
| `plate` | `shape`：`arch`／`circle`／`shield`／`diamond`；`color`：`'primary'｜'accent'｜{ main, dark, light }`；`rim`；`size`（256） | symbol（6 KB） |
| `royal` | `letter`：A／K／Q／J／10／9（字色固定、描邊與寶石跟 theme）；`color` 覆寫；`size` | symbol |
| `badge` | `kind`：wild／scatter／free／bonus；`text` 覆寫字；`shape`／`color` 覆寫底板 | symbol |
| `icon` | `name`：crown／gem／chest／coin／key／bell／trophy／star／seven／goldbar／clover／heart；`metal`（chest 的金屬）；`plate`（放進底板） | symbol |
| `frame` | `level` 1～3（銅／銀／金；2 級角釘、3 級寶石）；`metal` 覆寫 | symbol |
| `reel_bg` | `cols`、`rows`（1～8）、`cell`（120）、`gap`（6） | ui（8 KB） |
| `reel_frame` | 同上＋`border`（28）、`metal`；四條邊分開畫（Pixi 不支援挖洞路徑） | ui |
| `panel` | `w`、`h`、`r` | ui |
| `button` | `icon`：spin／auto／plus／minus／turbo／stop；`size`（spin 200、其他 120） | ui |
| `bg` | `motif`：rays／stars／sea；`w`、`h`（720×1280） | bg（16 KB） |
| `jp_plate` | `tier`：Grand／Major／Minor／Mini（色取 theme.jp）；`value`（有給就兩行：級別＋金額） | ui |
| `win_banner` | 🎞️ `tier`：big／mega／super；`text` 覆寫；6 格（放射光一循環轉 30°＋閃光） | fx（12 KB／格） |
| `fg_banner` | `text`（FREE GAMES）、`sub`（例 `×10`） | fx |
| `coin` | 🎞️ `size`（64）；6 格翻轉 | fx |

🎞️ 動畫 kind：`asset()` 回 `{ svg（第 0 格）, frames, meta.frames }`；`frames` 參數改格數；`assetPhase(kind, spec, t)` 取任意相位。
後續（M7）：`cannon`、`bullet`、`net`、`bead`、`lock`、海底背景。

## 覆蓋率（`COVERAGE`）

aidev 兩款老虎機的素材別名對照 kind（`verify_svg` 每次都跑）：

| 遊戲 | 別名數 | kit 產得出 | 專屬（不收） |
|---|---|---|---|
| 神燈寶藏 magic-lamp | 34 | 31 | 3：Logo、魔毯、彎刀 |
| 豬來蓋福 huffnpuff | 45 | 27 | 18：Logo、三隻豬角色、狼演出、房屋／房間、磚木稻草、工具箱、捲尺 |

**專屬的原則**：角色、Logo、題材物件留在各專案（換一款遊戲就不通用）；kit 只收「每款老虎機都有」的東西。

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
| 放射漸層的光暈 | 疊 6 層同心形狀近似淡出（有階梯感，比整片實心圓好）；縱向漸層仍取平均色 |
| 挖洞路徑（外框） | 框類拆成四條邊各自填色 |

驗證：`verify_svg` 的 `checkFlat`（靜態規則）＋ `pixi_check.mjs`（Pixi 與瀏覽器各畫一次，遮罩擴 1 px 互相涵蓋率 ≥ 0.95）。

## 新增 kind 的步驟

1. `gamekit.mjs` 的 `KINDS` 加 `{ category, build(spec, theme) → { w, h, L?, parts, alias, anchor? } }` —— 顏色一律取自 theme token
2. `SAMPLES` 加涵蓋所有選項的樣本（沒有樣本＝verify 紅）
3. 動畫 kind：`anim: { frames }`，`build(spec, theme, t)` 只用相位 t，t＝1 必須回到 t＝0（旋轉零件轉到對稱角；🔴 不要先壓扁再旋轉 —— 壓扁的放射光轉 30° 就不再對稱）
4. `node verify_svg.mjs`、`ARK_SVGA_PIXI=… node pixi_check.mjs`、`node --test tests/*.test.mjs` 全綠；`gamekit.mjs preview` 目視
5. 造型改變升 minor
