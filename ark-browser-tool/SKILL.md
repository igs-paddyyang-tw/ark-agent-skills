---
author: paddyyang
name: ark-browser-tool
description: |
  瀏覽器自動化工具：使用 Microsoft Webwright（terminal-native web agent 框架）。
  Code-first 範式 — 模型寫 Playwright 腳本而非逐步預測點擊，
  產出可重用程式 + 截圖 + 日誌。含 self-reflection 驗證機制。
  同時保留 Playwright MCP 作為輕量互動備選。
  使用此 Skill 當使用者提及瀏覽器自動化、Webwright、MCP browser、
  Playwright MCP、browser tool、網頁抓取、瀏覽器搜尋、web scraping、
  瀏覽器測試、截圖驗證、visual testing、看一下畫面、
  確認 UI、E2E 驗證、localhost 預覽、craft tool、
  或任何需要瀏覽器自動化或視覺化驗證 Web 產出的場景。
metadata:
  version: "3.0"
  updated: 2026-05-31
---

# ark-browser-tool

瀏覽器自動化工具 — 使用 Microsoft Webwright（code-first terminal-native web agent）。

## 觸發條件

- 「Webwright」、「瀏覽器自動化」、「MCP browser」
- 「browser tool」、「網頁抓取」、「web scraping」
- 「瀏覽器測試」、「截圖驗證」、「visual testing」
- 「看一下畫面」、「確認 UI」、「E2E 驗證」
- 「localhost 預覽」、「craft tool」、「可重用腳本」
- 前端任務完成後的驗證階段

## 核心理念

```
傳統 web agent：預測下一個 click → 逐步操作 → 無產出物
Webwright：寫 Playwright 腳本 → 執行 → 產出可重用程式
```

**範式轉移**：瀏覽器是可拋棄的工具，程式碼才是持久產出。

---

## 架構（~1K LoC harness）

```
┌─────────────────────────────────────────┐
│ Runner Loop                              │
│                                          │
│  1. Send context（task + workspace）→ Model │
│  2. Model emit bash command              │
│  3. Environment 執行 → 回傳 output       │
│  4. 迭代直到 final_script.py 通過驗證    │
└─────────────────────────────────────────┘
```

三個模組：
- **Runner** — 迴圈控制、context 組裝
- **Model** — LLM endpoint（GPT/Claude/Qwen）
- **Environment** — terminal 執行 + 檔案系統

---

## 兩種操作模式

### 模式 A：`webwright_run`（執行任務）

一次性完成瀏覽器任務，產出結果。

```
輸入：task description + start_url
輸出：final_script.py + screenshots/ + trajectory.json
```

適用：資料擷取、表單填寫、搜尋、驗證

### 模式 B：`webwright_craft`（產出可重用工具）

產出參數化 CLI 工具，可重複使用。

```
輸入：task description + start_url
輸出：可重用 CLI 工具（python script with argparse）
```

適用：重複性任務（航班比價、票務查詢、定期擷取）

---

## Self-Reflection 驗證

任務不是「模型說完成」就完成：

```
1. 產出 final_script.py
2. 在 fresh folder 重新執行（排除環境殘留）
3. 儲存 logs + screenshots
4. self_reflection 判斷是否真正成功
5. 失敗 → 回到 Runner Loop 修正
```

---

## 產出物結構

每次執行產出：

```
workspace/
├── final_script.py          # 最終可執行腳本
├── final_script_log.txt     # 執行日誌
├── screenshots/             # 關鍵截圖
├── self_reflect_result.json # 驗證結果
└── trajectory.json          # 完整操作軌跡
```

---

## MCP 整合

產出 2 個高階 MCP Tools（取代舊版 7 個細粒度 Tools）：

```python
@mcp.tool()
async def webwright_run(task: str, start_url: str, max_steps: int = 50) -> dict:
    """執行瀏覽器任務，回傳結果 + 截圖路徑。"""

@mcp.tool()
async def webwright_craft(task: str, start_url: str) -> dict:
    """產出可重用 CLI 工具腳本。"""
```

### MCP 設定

```json
{
  "mcpServers": {
    "webwright": {
      "command": "python",
      "args": ["-m", "webwright.mcp_server"],
      "env": {
        "WEBWRIGHT_MODEL": "gpt-5.4",
        "WEBWRIGHT_MAX_STEPS": "100"
      }
    }
  }
}
```

---

## 前置條件

- Python 3.10+
- Playwright：`pip install playwright && playwright install chromium`
- Webwright：`pip install webwright`（或 `pip install -e .` from repo）
- LLM API Key（使用現有 team 設定）

---

## 與 Playwright MCP 的關係

| | Webwright | Playwright MCP |
|---|---|---|
| **範式** | Code-first（寫腳本） | Tool-first（逐步呼叫） |
| **產出** | 可重用 script + 截圖 + log | 單次操作結果 |
| **驗證** | self-reflection + fresh rerun | 無 |
| **Token** | 批次生成，少量迭代 | 每步一次 snapshot |
| **適用** | 複雜/長任務、重複任務 | 簡單互動、快速預覽 |

**策略**：Webwright 為主要模式，Playwright MCP 作為輕量備選（快速截圖/簡單互動）。

### Playwright MCP 備選設定

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest", "--headless"]
    }
  }
}
```

---

## 常用場景

### 網頁資料擷取

```
webwright_run(
  task="搜尋 'LLM cost optimization 2026' 並擷取前 5 筆結果標題和連結",
  start_url="https://www.google.com"
)
```

### 產出可重用搜尋工具

```
webwright_craft(
  task="建立 Google 搜尋工具，接受 query 參數，回傳前 10 筆結果",
  start_url="https://www.google.com"
)
→ 產出 google_search_tool.py（可重複呼叫）
```

### 前端視覺驗證

```
webwright_run(
  task="開啟頁面，截圖 desktop/tablet/mobile 三種尺寸，確認佈局正確",
  start_url="http://localhost:3000"
)
```

### 表單 E2E 測試

```
webwright_run(
  task="填寫註冊表單（name=Test, email=test@example.com），提交並確認成功訊息",
  start_url="http://localhost:3000/register"
)
```

---

## 與開發流程整合

```
RED → GREEN → REFACTOR → WEBWRIGHT VERIFY → COMMIT
```

### 視覺檢查清單

Webwright 執行後自動產出截圖，確認：
- [ ] 頁面正常載入（無白屏/錯誤）
- [ ] 佈局符合設計
- [ ] 文字可讀（無溢出/截斷）
- [ ] 互動元素可操作
- [ ] 響應式正確

---

## 注意事項

- Webwright 需要 LLM API Key 才能運作（使用 team 現有設定）
- 設定 `max_steps` 上限避免 token 失控（預設 50，上限 100）
- 整合 `cost_guard` 監控每次執行的 token 消耗
- Pin Webwright 版本（preview 階段 API 可能變動）
- 長任務自動 context compaction（歷史摘要 + workspace 保留具體產出）
- 官方 repo：https://github.com/microsoft/Webwright
