---
name: ark-svg-animation
description: |
  原創遊戲向量美術產生器（executor，零相依 ESM，瀏覽器與 node 共用）：① 生物逐格動畫 —— 依「體型＋物種名」產生游動、被捕動畫
  （SVG 字串陣列＋meta：viewBox、錨點、身體框、碰撞參考半徑）；② gamekit —— 魚機／slot 必要圖元素（0.10.0：描邊字、底板、撲克符號、WILD／SCATTER 徽章、12 種通用物件、符號框、轉輪底／框、面板、圓鈕、背景、JP 牌、Win 橫幅、FG 橫幅、FG／Bonus 進場、倍率標籤、FG 次數板、資訊列、彈窗、載入條、金幣（翻轉／噴發）、彩池跑馬燈；魚機砲台 1～5 級、子彈、網、寶珠、鎖定框、魚潮橫幅、Boss 警示；kit.json 產生器（ark-web-game wg_pack_assets 直接呼叫）；
  主題 theme、原創向量字形轉 path、flat profile 給 PixiJS Graphics.svg() 直接解析）。同參數逐位元組相同；verify_svg.mjs 守門
  （確定性、安全、體積、循環接縫、flat 規則），pixi_check.mjs 用真的 PixiJS 比對形狀。
  用途：遊戲素材缺圖補位、骨架（Spine）魚的替代、新遊戲的原創 UI／符號美術、素材管線未產出時的執行期補位。
  使用此 skill 當提及：SVG 動畫、向量動畫、SVG 魚、缺圖補位、素材補位、程式產生美術、生物動畫、魚種動畫、游動動畫、被捕動畫、
  原創向量圖、SVG 產生器、Spine 魚替代、骨架魚替代、spritesheet 補位、gamekit、slot 美術、slot 符號、魚機 UI、
  BIG WIN 橫幅、描邊字、向量字形、符號底板、JP 牌、PixiJS Graphics SVG、flat SVG。
  不適用於：像素點陣風格（→ ark-pixel-animation）、slot 驗證台的靜態佔位圖（→ ark-game-proto）、
  正式 Client 骨架與素材打包（→ ark-web-game）、一般網頁 UI 動效（→ ark-frontend-design）。
metadata:
  schema_version: "1.2"
  status: experimental
  author: paddyyang
  category: view
  form: executor
  domain: game
  version: "0.10.0"
  updated: 2026-11-17
  outputs:
    - { format: data, audience: ai }
    - { format: png, audience: human }
  render: none
---

# ark-svg-animation

> 規格／設計／計畫：kiro-cli `docs/specs/ark-svg-animation-spec.md`、`docs/designs/ark-svg-animation-design.md`、`docs/plans/ark-svg-animation-plan.md`。
> gamekit 升級計畫：kiro-cli `docs/plans/ark-svg-animation-gamekit-plan.md`（M5 字形／theme／flat ✅、M6 老虎機元素＋共用演出物 ✅、M7 魚機元素＋產生器 CLI ✅；M8 1.0.0）。
> 使用方怎麼接：`references/consumer-contract.md`；體型與參數：`references/archetypes.md`；新增物種：`references/species-registry.md`；**gamekit：`references/gamekit.md`**。

## 體型

| 體型 | 代表物種 | 動畫 |
|---|---|---|
| `fusiform` 紡錘魚 | 小丑魚、蝴蝶魚、獅子魚、旗魚、鮟鱇、鯒 | 擺尾＋胸鰭 |
| `shark` 鯊／鯨 | 鯊、鋸鯊、虎鯨 | 全身 S 形 |
| `ray` 魟 | 魟、光魟 | 雙翼波動 |
| `flat` 比目魚 | 比目魚 | 緣鰭行進波 |
| `puffer` 河豚 | 河豚、巨河豚 | 脹縮＋刺 |
| `crab` 蟹 | 炸彈／電磁／鑽頭／轉輪蟹 | 步足交替、螯開合、配件 |
| `lobster` 龍蝦 | 龍蝦 | 腹節擺、尾扇、觸角 |
| `cephalopod` 頭足 | 章魚 | 8 觸手行進波 |
| `jelly` 水母 | 小水母、電光水母（`arc`） | 傘體收縮、觸手拖曳、電弧 |
| `turtle` 海龜 | 海龜 | 前鰭划水 |
| `snail` 海螺 | 海螺魚 | 腹足波動、觸角 |
| `serpent` 分節長體 | 狂暴火龍（Spine 部件魚的替代） | 節鏈行進波 |
| `token` 角色徽章 | 野牛、金猴爺、孫悟空、貓魚 | 浮動＋耳／角擺 |

新增物種：在 `scripts/species.mjs` 加一行（`archetype`、`size`、可選 `params`／`palette`／`variants`／`accessory`），跑 `verify_svg.mjs --strict`。

## 規範

1. **只產原創向量圖**：不讀任何外部圖片、不臨摹公司素材（傳 `image`／`href`／`src` 參數直接拒絕）
2. **確定性**：同參數＋同版號 → 逐位元組相同；動畫只用相位函式（t＝i/n），不用 `Math.random`／時間／字型
3. **安全**：輸出只有圖元（`path`／`polygon`／`ellipse`／`circle`／`polyline`／`g`）與 `<defs>` 內的漸層、裁切；沒有 script、事件屬性、外部參照、文字
4. **id 不衝突**：漸層／裁切 id＝物種種子＋外觀雜湊（變體、尺寸、朝向、配色、參數）＋狀態格號；同頁內嵌多張圖時同 id 必為同定義（`verify_svg` 驗）
5. **profile**：`texture`（預設，轉貼圖用）／`flat`（PixiJS `Graphics.svg()` 直接解析：無漸層、裁切、transform、`<g>`，polygon 改 path，上色只寫 style）
6. 改 rig 或核心後跑 `verify_svg.mjs`（rc≠0 不提交）；造型改變就升版號（`meta.version`），使用方據此重建快取

## 用法

```js
import { creature } from './svg_anim.mjs';
import { asset } from './gamekit.mjs';
asset('label', { text: 'BIG WIN', size: 72, fill: 'gold', theme: 'royal-gold' });   // → { svg, meta }
asset('plate', { shape: 'shield', theme: 'deep-sea', profile: 'flat' });            // PixiJS new Graphics().svg(svg)
asset('royal', { letter: 'K' }); asset('icon', { name: 'chest', metal: 'silver' }); asset('button', { icon: 'spin' });
asset('win_banner', { tier: 'mega' });                                              // 動畫：{ svg, frames（6 格）, meta }
asset('cannon', { level: 3, profile: 'flat' });                                     // meta.anchor＝底座圓心（旋轉中心）
creature({ name: 'NEMO', length: 104, profile: 'flat' });
const { frames, meta } = creature({ name: 'SHARK', length: 160 });       // frames.swim（4 格）／frames.catch（3 格）
creature({ name: 'BOMB_CRAB', length: 104, facing: 'right', variants: ['gold'] });
```

```bash
S=.kiro/skills/ark-svg-animation/scripts
node $S/svg_anim.mjs list                                              # 登錄的物種
node $S/svg_anim.mjs frames SHARK --length 160 [--state swim|catch] [--facing up|right] [--variant gold,twister,boss] [--json]
node $S/svg_anim.mjs gen --out out/svg [--names A,B|all] [--length 100]  # 逐格 .svg＋manifest.json
node $S/svg_anim.mjs preview --out preview.html [--names all] [--base 90] # 單檔預覽（點一下看被捕）
node $S/sheet.mjs --out out/sheets [--names all] [--length 100] [--scale 2]  # PixiJS spritesheet（每種 PNG＋JSON＋index.json）
node $S/sheet.mjs --check out/sheets [--pixi node_modules/pixi.js/dist/pixi.min.js]   # 尺寸／空白格／真的 PixiJS 讀得進
node $S/verify_svg.mjs [--expect names.txt] [--strict] [--json]      # 守門（生物＋gamekit）；0 個物種＝失敗
node $S/gamekit.mjs --config kit.json --out art/ [--only a,b] [--list] [--profile flat]   # 產生器：<別名>.svg＋動畫格＋kit-manifest.json
node $S/gamekit.mjs list                                               # gamekit 的 kind 與 theme
node $S/gamekit.mjs preview --out kit.html [--profile texture|flat]    # 全部 kind × 4 theme
ARK_SVGA_PIXI=node_modules/pixi.js/dist/pixi.min.js node $S/pixi_check.mjs   # flat 輸出：PixiJS 與瀏覽器形狀比對
node --test $S/tests/*.test.mjs
```

| 參數 | 說明 |
|---|---|
| `name` | 必填；決定預設體型（`*_CRAB`→crab、`*SHARK`／`*WHALE`→shark、`TWIST_`→旋風變體、`SINGLE_`／`LINE_` 去前綴）與配色種子 |
| `length` | 長軸像素（預設 100） |
| `archetype`／`params`／`palette`／`accessory`／`seed` | 覆寫 |
| `facing` | `up`（預設，頭朝 −y 俯視）／`right`（側向） |
| `frames` | `{ swim, catch }` 格數（預設 4／3） |
| `variants` | `twister`（旋風外圈）、`gold`（金色）、`boss`（淡外圈）、`glow`（光暈：亮色淡出到透明） |

`meta`：`version`、`archetype`、`viewBox`、`anchor`（身體中心 0～1）、`bodyBox`、`hitRadius`（參考值）、`fallback`（未登錄、以預設體型代替）

## 守門 `verify_svg.mjs`

| 檢查 | 判定 |
|---|---|
| 確定性 | 同參數產兩次 sha256 相同 |
| 安全／結構 | 無 script、事件屬性、href、url(…)、style、text；`<svg>`／`<g>` 成對；開頭帶 viewBox |
| 體積 | 單格 ≤ 4 KB |
| 循環接縫 | ① 等速：每一步（含最後一格 → t＝1）≤ 步長中位數 × 1.5 ② 週期：t＝1 與第一格的排序後數字集合相同（容許對稱零件換位） |
| 涵蓋 | `--expect` 清單中未登錄的列警告（`--strict` 算失敗）；0 個物種算失敗 |
| flat 規則 | 無漸層／裁切／transform／`<g>`／polygon／polyline／rgba／fill 屬性；每個圖元自帶 style、描邊有 stroke-width |
| gamekit | 每個 kind 樣本 × 4 theme × 兩種 profile：確定性、禁 `<text>`、分類預算（符號 6 KB、UI／字 8 KB、演出 12 KB、背景 16 KB；flat 2 倍）、換 theme 必變色；動畫 kind 驗接縫 |
| 覆蓋率 | `COVERAGE`：aidev 兩款老虎機素材別名 → kind；非專屬別名必須全部產得出來（角色／Logo／題材物件列為專屬，不計缺漏） |
| PixiJS 實機（`pixi_check.mjs`） | 同一張 flat SVG：Pixi `Graphics.svg()` 與瀏覽器各畫一次，遮罩擴 1 px 後互相涵蓋率 ≥ 0.95 |

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 0.10.0 | 2026-11-17 | aidev 回饋缺的 10 項：`fg_intro`🎞️、`multiplier`、`fg_counter`、`info_bar`、`dialog`、`loading_bar`、`coin_burst`🎞️（一次性）、`jp_marquee`🎞️、`tide_banner`🎞️、`boss_warning`🎞️；數字一律可空槽；接縫檢查忽略色碼；共 30 種 kind；測試 53 項 |
| 0.9.0 | 2026-11-17 | aidev 回饋（字與 FG）：粗體字預設（`BOLD` 1.55、撲克字 1.85，實心可辨識）＋`weight` 參數，字距隨粗細加寬、`boldText` 精準縮進框內；FG 橫幅加高 760×280、徽冠、次數槽（`sub: ''`＝空槽）；測試 47 項 |
| 0.8.0 | 2026-11-17 | 對照 aidev 神燈寶藏並排補選項：寶箱 `metal` 改箱體（金／銀／木）、`royal` 的 `plate`／`plateColor`（整組符號同底板）、執行期文字空槽（`jp_plate` `value: ''`、`fg_banner` `text: ''`）；slot 範例改全 arch 底板＋JP 空槽；測試 43 項 |
| 0.7.0 | 2026-11-17 | gamekit M7：魚機 `cannon`（1～5 級）、`bullet`、`net`（一次性動畫）、`bead`、`lock`（循環）；產生器 CLI `--config kit.json`（wg_pack_assets 0.13.0 直接呼叫）＋ `assets/` 兩份範例；接縫一律比 flat；🔴 `badge` 參數 `kind` 改名 `type`；測試 40 項 |
| 0.6.0 | 2026-11-16 | gamekit M6：`royal`、`badge`、`icon`（12 種）、`frame`、`reel_bg`、`reel_frame`、`panel`、`button`、`bg`、`jp_plate`、`win_banner`（動畫）、`fg_banner`、`coin`（動畫）；`assetPhase`、`COVERAGE`（aidev 兩款非專屬 100%）；flat 光暈改多層同心；`g` 支援等比縮放；測試 34 項 |
| 0.5.0 | 2026-11-16 | gamekit M5：核心抽成 `draw.mjs`（生物 texture 輸出逐位元組不變，快照守門）、`flat` profile（PixiJS 8.6.6 `Graphics.svg()` 相容）、原創向量字形 `glyphs.mjs`（A–Z、0–9、符號）、`themes.mjs`（4 組原創配色）、`gamekit.mjs`（`label`、`plate`）、`pixi_check.mjs`；測試 29 項 |
| 0.4.0 | 2026-11-16 | 畫質：參考 fish-bot 作法（只取做法，不取其素材配色）—— 放射漸層立體感、三圓眼睛（眼白＋瞳孔＋反光）、紡錘魚貝茲身形＋尾鰭繞尾柄旋轉＋花紋裁切在身體內、`glow` 變體；id 含外觀雜湊、verify 驗同頁 id 定義不衝突；測試 21 項 |
| 0.3.0 | 2026-11-16 | M3：`sheet.mjs`（headless Chromium 一次截圖＝拼圖、TexturePacker hash JSON 含 anchor 與 animations、PNG 自解碼驗非空白、`--pixi` 用真的 PixiJS 解析）、references 三份；測試 17 項 |
| 0.2.0 | 2026-11-16 | M2：其餘 10 種體型、物種登錄表 33 種、`list`／`gen`／`preview`、boss 外圈調淡；測試 14 項 |
| 0.1.0 | 2026-11-16 | M1：核心（確定性、配色、變體、被捕曲線、facing）、3 種體型、守門與 10 項測試（每項反證會紅） |
