---
name: ark-browser-tool
description: |
  獨立的網頁操作與測試工具（executor 型，捆綁 Playwright 腳本，不需要任何 LLM／API key）。
  browser_tool.py 三個子命令：doctor（環境檢查）、shot（開頁截圖＋console 錯誤／失敗請求）、
  run（照 YAML／JSON 劇本逐步操作與斷言 → PASS／FAIL／BLOCK＋report.md＋截圖＋trace 可重播）。
  DOM 頁面用 selector 與文字斷言；Canvas／WebGL 遊戲（PixiJS）用座標點擊＋頁面掛勾讀狀態＋軟體 GL。
  判定只由腳本做（AI 寫劇本、讀報告），exit code 0／1／2／3 可直接接 CI 或 agent 流程。
  使用此 Skill 當使用者提及：網頁測試、web 介面測試、瀏覽器測試、瀏覽器自動化、E2E 驗證、截圖驗證、
  看一下畫面、確認 UI、localhost 預覽、網頁冒煙測試、H5 遊戲測試、Canvas 遊戲測試、PixiJS 測試、
  Docker 部署的網頁驗收、響應式／手機尺寸檢查、Playwright 腳本、測試劇本。
  不適用於：大規模網頁內容擷取請用 ark-web-scraper；pytest 單元測試請用 ark-quality-gates；
  Android 模擬器（BlueStacks）上的 App 測試請用 ark-mobile-adb；Web 遊戲 Client 建置與 e2e 範本請用 ark-web-game。
metadata:
  schema_version: "1.2"
  # 只列測試實際跑過的：scripts/tests 以本機 HTML 端到端（13 passed）
  tested_against:
    playwright: "1.58.0"
    chromium: "headless shell（playwright install chromium）"
  status: active
  category: pipeline
  form: executor
  domain: general
  outputs:
    # report.json（browser-report/1）歸 data；report.md 給人與 AI
    - { format: data, audience: ai }
    - { format: md, audience: both }
  render: none
  depends_on: []
  # 4.0.0 拿掉 Webwright（需另一組 LLM key）與 webwright_run／webwright_craft MCP 工具
  replaces: [webwright, webwright-mcp]
  author: paddyyang
  version: "4.0.0"
  updated: 2026-11-09
---

# ark-browser-tool 4.0

> **一句話**：用一份劇本描述「怎麼操作、怎樣算對」，`browser_tool.py` 用 Playwright 照做並判定，留下截圖與可重播的 trace。
> 不呼叫任何 LLM：AI（或人）負責寫劇本與讀報告，**判定權在腳本**。

## 觸發條件

- 「網頁測試」「web 介面測試」「瀏覽器測試」「E2E」「截圖驗證」「看一下畫面」「確認 UI」
- 「localhost 預覽」「Docker 部署驗收」「H5／Canvas／PixiJS 遊戲測試」「手機尺寸」
- 前端或 Web 遊戲改完後的驗證階段

## Negative Trigger（指路）

| 需求 | 用 |
|---|---|
| 大量擷取網頁內容 | `ark-web-scraper` |
| pytest 單元測試 | `ark-quality-gates` |
| BlueStacks／Android App | `ark-mobile-adb` |
| 建 Web 遊戲 Client、Client 的 e2e 範本 | `ark-web-game` |

## 安裝

```bash
pip install -r requirements.txt          # playwright、pyyaml（Pillow 選配）
python -m playwright install chromium    # 約 150 MB，裝在使用者目錄
python scripts/browser_tool.py doctor --url http://localhost:3030
```

`doctor` 回 `ok: true` 才往下。

## 三個子命令

```bash
S=.kiro/skills/ark-browser-tool/scripts
# 1. 環境
python $S/browser_tool.py doctor [--url URL]
# 2. 單頁截圖＋健康資訊（看畫面、量座標）
python $S/browser_tool.py shot URL [--viewport 540x960 | --device "iPhone 13"] [--gl] [--wait-selector SEL] [--wait-ms 5000] [--out DIR]
# 3. 跑劇本
python $S/browser_tool.py run SCENARIO.yaml [--base-url URL] [--var k=v] [--out DIR] [--headed] [--video] [--no-trace]
```

| exit | 意義 |
|---|---|
| 0 | PASS |
| 1 | FAIL（步驟失敗、頁面錯誤、console error、4xx／5xx）|
| 2 | 環境或劇本錯誤（沒有 playwright、格式錯）|
| 3 | BLOCK（離開允許網域等，要人處理）|

stdout 是單一 JSON（verdict、失敗數、findings、報告路徑）；完整證據在輸出資料夾：`report.json`、`report.md`、`shots/`、`trace.zip`（`python -m playwright show-trace trace.zip` 重播）、`console.jsonl`。

## 劇本長這樣

```yaml
schema: browser-scenario/1
name: login-smoke
base_url: http://localhost:8080
viewport: {width: 1280, height: 720}
steps:
  - goto: /login
  - fill: {selector: "#user", value: "${user}"}
  - click: "button[type=submit]"
  - expect_url: /home
  - expect_text: {selector: ".welcome", contains: "歡迎"}
  - shot: home
```

完整動作（goto／click／fill／read／eval／wait_until／wait_stable／expect…／offline／repeat）與判定規則：`references/scenario-schema.md`。

## Canvas／WebGL 遊戲

- 劇本加 `browser: {gl: true}`；按鈕用 `click: {x, y}`（先 `shot` 量座標）
- 數值優先讀頁面掛勾（如 pixi-game-platform 的 `window.__pgp.hud`），用 `wait_until` 等一局結束
- 標準斷言：資產守恆、HUD＝Server 結算、0 頁面錯誤
- 範例：`assets/examples/pgp-slot-smoke.yaml`（aidev 豬來蓋福 Docker 部署實測 PASS）；細節 `references/canvas-games.md`

## 規則

1. **判定只在腳本**：不讓模型說「看起來成功」就算成功；沒有斷言的劇本只是操作，不是測試
2. **斷言要能抓錯**：新劇本寫完，故意改一個期望值跑一次，確認會 FAIL
3. **證據必留**：失敗當下自動截圖；預設錄 trace
4. **只讀不改**：`eval` 用來讀狀態或觸發 UI 本來就能做的事，不直接改遊戲或頁面狀態造假
5. **不可逆操作不自動做**：付費、刪除、送出正式表單、登入 MFA → 劇本停在前一步，請人處理
6. **網域守門**：預設只允許 `base_url` 的網域；要跨網域就明列 `allowed_origins`

## 與 Playwright MCP 的關係

IDE 裡想臨時「看一下」可以用 Playwright MCP（`npx @playwright/mcp@latest --headless`），但它每步一次 snapshot、不留可重跑的劇本。
要**測試**、要**留證據**、要**重跑**，一律寫劇本跑 `browser_tool.py run`。

## 升級說明（3.x → 4.0.0，Breaking）

- 移除 Webwright（需另一組 LLM API key、判定權在模型）與 `webwright_run`／`webwright_craft` MCP 工具
- 改為捆綁腳本：原「執行任務」→ `run` 劇本；原「產出可重用工具」→ 劇本本身就是可重跑的資產
