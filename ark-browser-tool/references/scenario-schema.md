# 劇本格式 `browser-scenario/1`

> 劇本＝「要怎麼操作」＋「怎樣才算對」。AI 可以寫劇本、讀報告，但**判定只由 `browser_tool.py` 做**。

## 頂層欄位

| 欄位 | 必填 | 說明 |
|---|---|---|
| `schema` | ✅ | 固定 `browser-scenario/1` |
| `name` | | 報告與輸出資料夾名稱 |
| `base_url` | | `goto` 的相對路徑以此為基準；CLI `--base-url` 可覆蓋 |
| `viewport` | | `{width, height}`；與 `device` 擇一 |
| `device` | | Playwright 裝置名，如 `iPhone 13`、`Pixel 7`（含 UA、縮放、觸控）|
| `browser` | | `{gl: true}` Canvas／WebGL 用軟體 GL；`args: [...]`；`slow_mo: ms` |
| `allowed_origins` | | 預設＝`base_url` 的網域；主框架跳到清單外 → **BLOCK**（exit 3）|
| `vars` | | 初始變數；CLI `--var k=v` 可覆蓋 |
| `checks` | | `console_errors`／`page_errors`／`failed_requests`：`fail`（預設）／`warn`／`off` |
| `steps` | ✅ | 步驟清單 |

## 步驟

每一步**只能有一個動作**，另可加 `name`（報告顯示）、`timeout`（ms，預設 15000）、`optional: true`（失敗只記錄不中止）。
字串裡的 `${變數}` 會被替換；整串剛好是 `${x}` 時保留原型別（數字、物件）。JS 裡用 `v.變數` 取值。

| 動作 | 參數 | 說明 |
|---|---|---|
| `goto` | 路徑或網址 | HTTP ≥ 400 → 失敗 |
| `reload` | `true` | 重新整理 |
| `wait_for` | selector 或 `{selector, state}` | `state`：visible（預設）／attached／hidden／detached |
| `wait_until` | JS 或 `{js, interval}` | 反覆執行直到為真；Canvas 遊戲靠它等一局結束 |
| `wait_stable` | `{threshold, frames, interval}` | 連續截圖差異 ≤ threshold 達 frames 次（有 Pillow 用像素差，沒有就比雜湊）|
| `sleep` | ms | 盡量少用，優先 `wait_until` |
| `click` | selector 或 `{x, y}` | 座標以 viewport CSS 像素計 |
| `fill` | `{selector, value}` | 輸入框 |
| `press` | 鍵名 | 如 `Enter`、`Escape` |
| `read` | `{as, js}`／`{as, selector}`／`{as, selector, attr}`；可加 `number: true` | 讀值存變數；`number` 會去掉千分位轉數字 |
| `eval` | JS 或 `{js, as, body}` | 執行 JS（可等 Promise）；`body: true` 表示多行函式本體（自己 `return`）|
| `set` | `{k: v}` | 設變數 |
| `expect` | `{js 或 value, equals／gt／gte／lt／lte／contains／truthy, msg}` | 不寫比較子＝真值判定 |
| `expect_text` | `{selector, equals 或 contains}` | 比對元素文字 |
| `expect_visible` | selector | 元素可見 |
| `expect_url` | 片段 | 目前網址包含該片段 |
| `shot` | 名稱 | 截圖到 `shots/` |
| `offline` | `true`／`false` | 模擬斷網、恢復 |
| `repeat` | `{times, steps}` | 迴圈；內層可用 `v.i`（第幾輪）|

## 判定與輸出

| 結果 | exit | 條件 |
|---|---|---|
| PASS | 0 | 所有非 optional 步驟成功，且 `checks` 為 fail 的項目 0 筆 |
| FAIL | 1 | 任一步驟失敗（失敗即停、截圖 `fail-<步>`），或頁面錯誤／console error／失敗請求 |
| ENV | 2 | 沒有 playwright、劇本格式錯 |
| BLOCK | 3 | 離開允許網域等要人處理的狀況 |

輸出資料夾（預設 `artifacts/browser/<name>-<時間>/`）：

```
report.json   機器讀（browser-report/1：verdict、steps、vars、findings）
report.md     人讀（步驟表＋頁面健康）
shots/        截圖（含失敗當下）
trace.zip     python -m playwright show-trace trace.zip 重播（--no-trace 關閉）
console.jsonl 全部 console 訊息
video/        --video 時才有
```

## 寫劇本的原則

1. **先 `shot` 看畫面再寫座標**；座標綁 viewport，換尺寸要重量
2. **能讀狀態就不要看圖**：DOM 用 selector、Canvas 遊戲用頁面掛勾（如 `window.__pgp`）
3. **斷言要能證明錯誤**：寫完故意改一個期望值，確認會 FAIL
4. **只讀不改**：`eval` 只用來觸發 UI 也能做的事或讀值，不要直接改遊戲狀態造假
5. 不碰付費、刪除、送出不可逆表單；遇到就讓劇本停在那一步，由人處理
