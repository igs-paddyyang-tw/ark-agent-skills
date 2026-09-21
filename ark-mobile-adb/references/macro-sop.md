# 按鍵精靈式腳本開發 SOP（aiqa_macro）

> 核心：**把「執行期的視覺分析」搬到「準備期」**。準備期用眼（截圖、錄製、建表、AI 幫看），執行期只做確定性的點座標 + 檢查點。
> 執行期零 LLM；AI 只在建表、驗證、與 aiqa_run 的 read / ask 出現。

## 0. 一支腳本的生命週期

```
探勘 ──▶ 建表 ──▶ 錄製 / 編寫 ──▶ lint ──▶ dry-run ──▶ 加檢查點 ──▶ 實跑量測 ──▶ 版本化
 (眼)     (眼)       (手)        (機)     (機)        (眼+機)        (機)         (機)
```

| 階段 | 做什麼 | 工具 | 產物 |
|---|---|---|---|
| 探勘 | 鎖 BlueStacks 解析度；截全圖；ui-dump 確認是 Unity（全螢幕節點 = 只能座標） | `doctor` `screen-size` `screenshot` `ui-dump` | 一組原始截圖（裝置尺寸） |
| 建表 | 把畫面 → 元素 → 座標寫進 gamepack：`screens`（錨點 region + 模板圖 + priority）、`buttons`（xy + 可選模板）、`rois`、`navigation` | `crop --rect --zoom 1`（裁模板）、`pixel --xy`（記找色點）、`aiqa_pack.py lint` | `gamepacks/<g>/[machines/<m>/]*.yaml` + `screens/*.png` |
| 錄製 | 人在 BlueStacks 上操作一次，CLI 錄 getevent → tap 序列（已換算成裝置座標） | `aiqa_macro.py record --game g --machine m --out m.yaml --duration 90` | macro 草稿（`tap: [x,y]` + 自動插入的 `wait_stable`） |
| 編寫 | 草稿的 `[x,y]` 換成 `btn:<name>`（改版只改 pack 一處）；固定 sleep 換成 `wait_stable` / `wait_pixel` / `wait_screen`；分支用 `if_screen` 關彈窗；重複用 `loop` | 編輯器 | macro.yaml |
| lint | 步驟合法、target 存在、解析度與 pack 一致、座標不超界（拿縮圖座標來點會被抓）、至少一個檢查點 | `aiqa_macro.py lint` | exit 0 / 3 |
| dry-run | 不點擊只走流程（locate / 截圖 / 檢查點）；或在 `--backend fake` 上跑 demo-slot 驗 DSL | `replay --dry-run` / `replay --backend fake` | summary.json |
| 加檢查點 | 每個「點下去之後應該變成什麼」的節點放 `checkpoint`（模板）或 `assert_pixel`（找色）；數值放 `ocr ... expect` | 看 dry-run 截圖決定 | 有檢查點的 macro |
| 實跑量測 | `replay --backend adb`；比對「視覺驅動 vs 座標重放」耗時（summary.elapsed_s / steps） | `replay` | summary.json、截圖 |
| 版本化 | macro 與 pack 同 commit；pack `resolution` / app 版本綁定；改版先跑 lint + dry-run | git | — |

## 1. DSL 一頁

```yaml
macro: <name>            # 檔名同
game: ghy                # 解析 btn: / roi: / screen: 用
machine: panda
resolution: {width: 720, height: 1280}   # 唯一座標基準 = wm size；不符拒跑
vars: {spins: 3}
steps:
  - tap: "btn:spin"                 # 或 tap: [x, y]（裝置座標）
  - swipe: {from: [x1,y1], to: [x2,y2], ms: 300}
  - key: BACK
  - sleep: 0.5                      # 只在動畫無法偵測時用；能用 wait_* 就不要 sleep
  - wait_stable: {timeout: 12, threshold: 0.004, strict: false}
  - wait_screen: {screen: main_game, timeout: 10}
  - wait_pixel: {xy: [x,y], rgb: [r,g,b], tol: 30, timeout: 10}
  - checkpoint: {screen: main_game}          # 不符 → FAIL 停
  - assert_pixel: {xy: [x,y], rgb: [r,g,b], tol: 30}
  - if_screen: {screen: popup_daily, then: [...], else: [...]}
  - loop: {times: "{spins}", steps: [...]}
  - ocr: {roi: "roi:bet", name: bet, digits: true, expect: 4000000}
  - shot: name
  - restart_app
  - net: disconnect | restore
  - note: 文字
```

## 2. 在 aiqa_run 裡怎麼用

checklist 的 action `{do: macro, name: enter-and-spin, vars: {spins: 2}}`：runner 執行 pack `macros/<name>.yaml`（machine 下同名優先），`ocr` 讀到的值併入 observations 給斷言用；macro 任一檢查點失敗 → 該項 BLOCK（附截圖）。
分工：**macro 管「走到那裡」，checklist 斷言管「對不對」**。

## 3. 三個常見錯法

1. **拿縮圖座標去點**：540x960 的 y=918 直接 tap → 點空三次。規則：縮圖只用 `thumb`（旁邊有 .meta.json 記 scale），要點就 `to-device` 或 `tap --basis 540x960`。lint 的 MC-COORD 會抓超界座標。
2. **一步一截圖給 AI 看**：每步 8–18 秒。規則：執行期不看，只在 checkpoint 看；看也是模板 / 找色，不是 LLM。
3. **固定 sleep**：短了截到過場、長了浪費。規則：`wait_stable`（動畫結束）、`wait_pixel`（按鈕亮起）、`wait_screen`（換頁）三選一。

## 4. 改版時

pack 座標失效 → `replay --dry-run` 立刻在第一個 checkpoint 停；只改 pack 的 `buttons` / `screens`，macro 不動（因為 macro 寫的是 `btn:<name>`）。模板圖用 `crop --zoom 1` 重裁；lint 綠再跑。
