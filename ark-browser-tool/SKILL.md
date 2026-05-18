---
author: paddyyang
name: ark-browser-tool
description: |
  完整瀏覽器開發測試工具：MCP Server 封裝（agent-browser CLI）+ 視覺測試驗證（Playwright）。
  提供 7 個 MCP Tools（open/snapshot/click/fill/screenshot/getText/close）+
  視覺測試工作流（截圖驗證、互動測試、響應式檢查、前後對比）。
  使用此 Skill 當使用者提及 agent-browser、瀏覽器自動化、MCP browser、
  browser tool、網頁抓取 MCP、瀏覽器搜尋、web scraping MCP、
  瀏覽器測試、截圖驗證、visual testing、dev-browser、看一下畫面、
  確認 UI、E2E 驗證、localhost 預覽、
  或任何需要瀏覽器自動化或視覺化驗證 Web 產出的場景。
metadata:
  version: "2.0"
  updated: 2026-05-18
---

# ark-browser-tool

完整瀏覽器開發測試工具 — MCP 自動化 + 視覺測試驗證。

## 觸發條件

使用者提及以下關鍵字時觸發：
- 「agent-browser」、「瀏覽器自動化」、「MCP browser」
- 「browser tool」、「網頁抓取 MCP」
- 「瀏覽器搜尋」、「web scraping MCP」
- 「瀏覽器測試」、「截圖驗證」、「visual testing」
- 「看一下畫面」、「確認 UI」、「E2E 驗證」
- 「localhost 預覽」、「開啟頁面」
- 前端任務完成後的驗證階段

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `project_dir` | `str` | ✅ | — | 專案目錄路徑 |

## 前置條件

- 已安裝 `agent-browser` CLI：`npm install -g agent-browser && agent-browser install`
- Python 3.12 + `fastmcp` 套件

## 產出指引

### 步驟 1：安裝 agent-browser

```bash
npm install -g agent-browser
agent-browser install  # 下載 Chrome for Testing（首次）
```

Linux 需額外安裝系統依賴：`agent-browser install --with-deps`

### 步驟 2：產出 MCP Server

產出目錄結構：

```
{project_dir}/
└── mcp-servers/
    └── agent-browser/
        ├── server.py          # FastMCP Server（呼叫 agent-browser CLI）
        └── requirements.txt   # fastmcp
```

**`server.py`** — 使用 FastMCP 封裝 agent-browser CLI 指令為 MCP Tools：

| MCP Tool | CLI 指令 | 功能 |
|----------|---------|------|
| `browser_open` | `agent-browser open <url>` | 開啟網頁 |
| `browser_snapshot` | `agent-browser snapshot` | 取得 accessibility tree（AI 最佳格式） |
| `browser_click` | `agent-browser click <ref>` | 點擊元素（ref 來自 snapshot） |
| `browser_fill` | `agent-browser fill <ref> <text>` | 填入文字 |
| `browser_screenshot` | `agent-browser screenshot [path]` | 網頁截圖 |
| `browser_get_text` | `agent-browser get text <ref>` | 取得元素文字 |
| `browser_close` | `agent-browser close` | 關閉瀏覽器 |

每個 Tool 透過 `asyncio.create_subprocess_exec` 呼叫 CLI，回傳 stdout 結果。

### 步驟 3：產出業務 Skill 抽象

產出 `src/skills/internal/browser_search.py`：

```python
class BrowserSearchSkill(BaseSkill):
    """透過 agent-browser MCP 執行搜尋。"""
    skill_id = "browser_search"
    skill_type = SkillType.MCP
    description = "透過瀏覽器搜尋引擎查詢資訊"
    version = "1.0.0"
    input_schema = BrowserSearchParams

    async def execute(self, params: dict) -> SkillResult:
        # 1. browser_open → 搜尋引擎 URL
        # 2. browser_fill → 填入搜尋關鍵字
        # 3. browser_click → 點擊搜尋按鈕
        # 4. browser_snapshot → 取得結果 accessibility tree
        # 5. 解析結果回傳
```

底層 MCP Server 提供通用瀏覽器能力，業務邏輯封裝在 Skill 中。

### 步驟 4：產出 MCP 設定

產出或更新 `.kiro/settings/mcp.json`：

```json
{
  "mcpServers": {
    "agent-browser": {
      "command": "python",
      "args": ["mcp-servers/agent-browser/server.py"],
      "disabled": false
    }
  }
}
```

### 步驟 5：驗證

```bash
# 確認 agent-browser CLI 可用
agent-browser --version

# 測試 MCP Server
python mcp-servers/agent-browser/server.py
```

---

## 注意事項

- agent-browser 是 Rust CLI，需要 npm 或 cargo 安裝
- 首次使用需執行 `agent-browser install` 下載 Chrome for Testing
- MCP Server 透過 `subprocess` 呼叫 CLI，每個 Tool 是獨立的 CLI 呼叫
- `browser_snapshot` 回傳 accessibility tree，是 AI agent 最佳的頁面理解格式
- 瀏覽器 session 在 CLI daemon 中維持，多個 Tool 呼叫共享同一個瀏覽器實例

---

## 視覺測試驗證（Playwright）

讓 Agent 看見自己的產出，閉合開發回饋迴圈。

### 核心原則

```
沒有瀏覽器的 Agent = 盲人寫 UI
→ 寫完 code 必須看到結果才算完成
```

### 截圖驗證

```python
from playwright.sync_api import sync_playwright

def screenshot(url: str, output: str = "screenshot.png", width: int = 1280, height: int = 720):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(url, wait_until="networkidle")
        page.screenshot(path=output, full_page=True)
        browser.close()
```

### 互動測試

```python
page.click("button#submit")
page.fill("input[name='email']", "test@example.com")
assert page.locator(".success-message").is_visible()
```

### 響應式檢查

```python
viewports = [
    {"width": 375, "height": 812, "name": "mobile"},
    {"width": 768, "height": 1024, "name": "tablet"},
    {"width": 1280, "height": 720, "name": "desktop"},
]
for vp in viewports:
    page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
    page.screenshot(path=f"screenshot-{vp['name']}.png")
```

### 視覺檢查清單

截圖後確認：
- [ ] 頁面正常載入（無白屏/錯誤）
- [ ] 佈局符合設計（元素位置正確）
- [ ] 文字可讀（無溢出/截斷）
- [ ] 互動元素可見（按鈕/連結）
- [ ] 響應式正確

### 使用場景

| 場景 | 動作 | 驗證 |
|------|------|------|
| 前端開發完成 | 截圖 localhost | 佈局正確 |
| CSS 修改 | 前後截圖對比 | 無意外變化 |
| 表單功能 | 填寫 + 提交 | 成功訊息出現 |
| 響應式 | 多尺寸截圖 | 各斷點正常 |

### 與 ark-superpowers 整合

在 ④ Execute 階段的 TDD 循環中：
```
RED → GREEN → REFACTOR → VISUAL VERIFY → COMMIT
```

### 前置需求

- Playwright：`pip install playwright && playwright install chromium`
- 截圖存放：`artifacts/screenshots/`（不入版控）
