---
name: ark-browser-tool
description: |
  產出 agent-browser MCP Server 封裝與業務 Skill 抽象。
  底層使用 vercel-labs/agent-browser（Rust CLI 瀏覽器自動化工具），
  透過 FastMCP 封裝成 MCP Server，供 Workflow 和 Bot 呼叫。
  使用此 Skill 當使用者提及 agent-browser、瀏覽器自動化、MCP browser、
  browser tool、網頁抓取 MCP、瀏覽器搜尋、web scraping MCP、
  或任何需要將 agent-browser 封裝為 MCP Server 的場景。
---

# ark-browser-tool

產出 agent-browser MCP Server 封裝，採用「MCP 封裝 + 業務 Skill 抽象」策略。
底層使用 [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)（Rust CLI），
透過 FastMCP 封裝成 MCP Server，可獨立運作。

## 觸發條件

使用者提及以下關鍵字時觸發：
- 「agent-browser」、「瀏覽器自動化」、「MCP browser」
- 「browser tool」、「網頁抓取 MCP」
- 「瀏覽器搜尋」、「web scraping MCP」

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
