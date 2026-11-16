---
name: ark-svg-animation
description: |
  原創向量生物逐格動畫產生器（executor，零相依 ESM，瀏覽器與 node 共用）：依「體型＋物種名」產生俯視或側視的游動、被捕動畫
  （SVG 字串陣列＋meta：viewBox、錨點、身體框、碰撞參考半徑），同參數逐位元組相同；verify_svg.mjs 守門（確定性、安全、體積、循環接縫）。
  用途：遊戲素材缺圖補位、骨架（Spine）魚沒有骨架資料時的替代、素材管線未產出時的執行期補位；像素圖退場後的預設備援美術。
  使用此 skill 當提及：SVG 動畫、向量動畫、SVG 魚、缺圖補位、素材補位、程式產生美術、生物動畫、魚種動畫、游動動畫、被捕動畫、
  原創向量圖、SVG 產生器、Spine 魚替代、骨架魚替代、spritesheet 補位。
  不適用於：像素點陣風格（→ ark-pixel-animation）、slot 驗證台的靜態佔位圖（→ ark-game-proto）、
  正式 Client 骨架與素材打包（→ ark-web-game）、一般網頁 UI 動效（→ ark-frontend-design）。
metadata:
  schema_version: "1.2"
  status: experimental
  author: paddyyang
  category: view
  form: executor
  domain: game
  version: "0.1.0"
  updated: 2026-11-16
  outputs:
    - { format: data, audience: ai }
  render: none
---

# ark-svg-animation

> 規格／設計／計畫：kiro-cli `docs/specs/ark-svg-animation-spec.md`、`docs/designs/ark-svg-animation-design.md`、`docs/plans/ark-svg-animation-plan.md`。
> **0.1.0（M1）**：體型 `fusiform`（紡錘魚）、`shark`（鯊／鯨）、`crab`（蟹，配件 bomb／electrode／drill／wheel）；
> 其餘 10 種體型、物種登錄表（`assets/species.json`）、`gen`／`preview`／`sheet` 子命令在 M2～M3。

## 規範

1. **只產原創向量圖**：不讀任何外部圖片、不臨摹公司素材（傳 `image`／`href`／`src` 參數直接拒絕）
2. **確定性**：同參數＋同版號 → 逐位元組相同；動畫只用相位函式（t＝i/n），不用 `Math.random`／時間／字型
3. **安全**：輸出只有圖元（`polygon`／`ellipse`／`circle`／`polyline`／`g`），沒有 script、事件屬性、外部參照、文字
4. 改 rig 或核心後跑 `verify_svg.mjs`（rc≠0 不提交）；造型改變就升版號（`meta.version`），使用方據此重建快取

## 用法

```js
import { creature } from './svg_anim.mjs';
const { frames, meta } = creature({ name: 'SHARK', length: 160 });       // frames.swim（4 格）／frames.catch（3 格）
creature({ name: 'BOMB_CRAB', length: 104, facing: 'right', variants: ['gold'] });
```

```bash
S=.kiro/skills/ark-svg-animation/scripts
node $S/svg_anim.mjs frames SHARK --length 160 [--state swim|catch] [--facing up|right] [--variant gold,twister,boss] [--json]
node $S/verify_svg.mjs [--expect names.txt] [--strict] [--json]      # 守門；0 個物種＝失敗
node --test $S/tests/*.test.mjs
```

| 參數 | 說明 |
|---|---|
| `name` | 必填；決定預設體型（`*_CRAB`→crab、`*SHARK`／`*WHALE`→shark、`TWIST_`→旋風變體、`SINGLE_`／`LINE_` 去前綴）與配色種子 |
| `length` | 長軸像素（預設 100） |
| `archetype`／`params`／`palette`／`accessory`／`seed` | 覆寫 |
| `facing` | `up`（預設，頭朝 −y 俯視）／`right`（側向） |
| `frames` | `{ swim, catch }` 格數（預設 4／3） |
| `variants` | `twister`（旋風外圈）、`gold`（金色）、`boss`（外光） |

`meta`：`version`、`archetype`、`viewBox`、`anchor`（身體中心 0～1）、`bodyBox`、`hitRadius`（參考值）、`fallback`（未登錄、以預設體型代替）

## 守門 `verify_svg.mjs`

| 檢查 | 判定 |
|---|---|
| 確定性 | 同參數產兩次 sha256 相同 |
| 安全／結構 | 無 script、事件屬性、href、url(…)、style、text；`<svg>`／`<g>` 成對；開頭帶 viewBox |
| 體積 | 單格 ≤ 4 KB |
| 循環接縫 | ① 等速：每一步（含最後一格 → t＝1）≤ 步長中位數 × 1.5 ② 週期：t＝1 與第一格的排序後數字集合相同（容許對稱零件換位） |
| 涵蓋 | `--expect` 清單中未登錄的列警告（`--strict` 算失敗）；0 個物種算失敗 |

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 0.1.0 | 2026-11-16 | M1：核心（確定性、配色、變體、被捕曲線、facing）、3 種體型、守門與 10 項測試（每項反證會紅） |
