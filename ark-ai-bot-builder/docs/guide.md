---
title: "AI Agent Bot 建置教學 — 使用 ark-ai-bot-builder"
type: guide
created: 2026-06-05
language: zh-TW
---

# 🤖 AI Agent Bot 建置教學

> 用 `ark-ai-bot-builder` 一鍵產出完整 AI Agent Bot，5 分鐘內 Telegram 能對話 + 產科技日報。

**操作位置圖示說明：**
- 📝 = 在 **AI IDE 聊天框**（Kiro / Antigravity）輸入
- 📱 = 在 **Telegram 聊天窗**
- 💻 = 在**終端機**執行指令

---

## 你需要準備的

| 項目 | 說明 | 必要 |
|------|------|------|
| Python 3.12+ | https://python.org | ✅ |
| Node.js 20+ | https://nodejs.org | ✅（CLI 需要） |
| Telegram 帳號 | @BotFather 建立 Bot 取得 Token | ✅ |
| AI IDE（擇一） | Kiro 或 Antigravity | ✅ |
| Gemini CLI | `npm i -g @google/gemini-cli` | 選配（AI 對話用） |
| Kiro CLI | `npm i -g kiro-cli` | 選配（AI 對話用） |
| Gemini API Key | https://aistudio.google.com/apikeys | 選配（即時對話用） |

---

## Step 0：取得 Skills + 環境確認

### 取得 ark-kiro-skills

```bash
# Kiro 使用者
git clone https://github.com/igs-paddyyang-tw/ark-kiro-skills .kiro/skills/

# Antigravity 使用者
git clone https://github.com/igs-paddyyang-tw/ark-kiro-skills .agents/skills/
```

### 安裝 Agent CLI（擇一或都裝）

```bash
# Gemini CLI（免費 1,000 req/day）
npm install -g @google/gemini-cli
gemini    # 首次啟動 → Login with Google

# Kiro CLI
npm install -g kiro-cli
kiro-cli login    # 瀏覽器授權
```

### 確認環境

**📝 在 AI IDE 聊天框輸入：**
```
檢查我的開發環境
```

全部 ✅ 即可進入 Step 1。

---

## Step 1：一鍵產出專案

### 方法 A：用 build_bot.py 腳本（推薦）

**💻 在終端機執行：**

```bash
py .kiro/skills/ark-ai-bot-builder/scripts/build_bot.py ./my-bot
```

自動產出 19 個檔案，結構完整可直接啟動。

### 方法 B：在 AI IDE 觸發 Skill

**📝 在 AI IDE 聊天框輸入：**

```
ark-ai-bot-builder，專案名稱 my-bot
```

AI 會根據 SKILL.md 的指引逐步產出所有檔案。

### 產出結構

```
my-bot/
├── src/
│   ├── skills/
│   │   ├── base.py              # Skill 介面
│   │   ├── registry.py          # auto_discover + hot_reload
│   │   └── internal/
│   │       ├── echo.py          # 回聲測試
│   │       ├── llm_cli.py       # ★ Agent CLI 大腦
│   │       ├── news_scraper.py  # 爬蟲
│   │       └── news_renderer.py # HTML 日報渲染
│   ├── bot/
│   │   ├── main.py              # Bot 入口
│   │   └── handlers.py          # 自然語言路由
│   ├── llm/
│   │   └── gemini_chat.py       # Gemini API 即時對話
│   └── conversation/
│       ├── session.py           # Session / Turn
│       ├── planner.py           # 意圖路由
│       └── memory_search.py     # FTS5 記憶
├── config/
│   ├── news_sources.yaml        # 新聞來源
│   └── llm_prompts.yaml         # 系統提詞
├── .env.example
├── requirements.txt
└── start.bat
```

---

## Step 2：設定環境變數

```bash
cd my-bot
cp .env.example .env
```

編輯 `.env`：

```bash
# ── 必填 ──
TELEGRAM_BOT_TOKEN=your_token    # 從 @BotFather 取得

# ── 選填（有就啟用更多功能）──
GEMINI_API_KEY=your_key          # Gemini API 即時對話
GEMINI_CLI_CMD=gemini.cmd        # Windows: gemini.cmd / Linux: gemini
```

### 建立 Telegram Bot

1. Telegram 搜尋 `@BotFather`
2. 輸入 `/newbot`
3. 取名 → 取 username（結尾必須是 `bot`）
4. 複製 Token 填入 `.env`

---

## Step 3：安裝依賴 + 啟動

```bash
pip install -r requirements.txt
```

**啟動：**

```bash
# Windows
start.bat

# 或直接
python -m src.bot.main
```

看到 `🤖 Bot started...` 即成功。

---

## Step 4：驗證功能

### 基礎功能（零配置）

| 📱 Telegram 輸入 | 預期結果 |
|------------------|---------|
| `/start` | 收到歡迎訊息 + 功能介紹 |
| `/skills` | 列出 4 個 Skills |
| `/daily` | 抓新聞 → 產出 HTML → 收到檔案 |
| 「今天有什麼新聞」 | 同 /daily（keyword 路由） |
| `/echo hello` | 回傳 echo 結果 |

### AI 對話（需 Agent CLI 或 API Key）

| 📱 Telegram 輸入 | 預期結果 |
|------------------|---------|
| 「什麼是 RAG」 | Agent CLI 回答 |
| 「幫我寫一個 HTTP 健康檢查 Skill」 | 產出程式碼 |
| `/chat 解釋 async await` | Gemini API 即時回應 |

---

## Step 5：科技日報驗證

### 方法 1：Telegram 一鍵觸發

```
📱 輸入：/daily

Bot：「📡 抓取新聞中...」
  → 從 HN + TechCrunch 抓取
  → 渲染暗黑風格 HTML
  → 發送 tech-daily-2026-06-05.html
```

瀏覽器開啟 HTML → 看到卡片式日報 ✅

### 方法 2：自然語言觸發

```
📱 輸入：今天有什麼科技新聞
```

Planner keyword 路由 → `news_scraper` → `news_renderer` → 發送

### 方法 3：直接在終端測試（不需 Bot）

```bash
py -c "import asyncio; from src.skills.internal.news_scraper import NewsScraperSkill; r=asyncio.run(NewsScraperSkill().execute({'config_path':'config/news_sources.yaml'})); print(f'抓到 {r.data[\"total\"]} 則')"
```

---

## 自然語言路由規則

Bot 收到文字後，ConversationPlanner 三層判斷：

```
1. keyword 快速路由（毫秒級）
   「新聞」「日報」→ news_scraper
   「程式」「code」→ llm_cli codegen
   「echo」→ echo

2. /skill_id 指令格式
   /news_scraper → 直接呼叫
   /echo hello → 呼叫 echo

3. 都不匹配 → Agent CLI 對話
   → llm_cli chat 模式
   → Gemini/Kiro/Claude 自動 fallback
```

---

## 擴充功能

產出的 Bot 支援 Skill 動態擴充 — 新 .py 放入 `src/skills/internal/` 即自動載入。

### 範例：加一個天氣 Skill

**📝 在 AI IDE 聊天框輸入：**

```
在 src/skills/internal/ 產出一個 weather Skill，
使用 httpx 呼叫 wttr.in API，回傳指定城市的天氣
```

或直接 📱 Telegram 告訴 Bot（需要 Agent CLI）：

```
幫我寫一個天氣查詢 Skill，呼叫 wttr.in API
```

→ llm_cli skill_gen 模式 → 產出 `src/skills/internal/weather.py` → hot_reload → 立即可用

### 擴充 keyword 路由

修改 `src/conversation/planner.py` 的 `_QUICK_ROUTE`：

```python
_QUICK_ROUTE = [
    (["新聞", "日報", "news", "daily"], "news_scraper", {"config_path": "config/news_sources.yaml"}),
    (["程式", "code", "寫一個", "generate"], "llm_cli", {"mode": "codegen"}),
    (["天氣", "weather"], "weather", {}),        # ← 新增
    (["echo", "回音"], "echo", {}),
]
```

---

## 常見問題

### Bot 沒回應

- 確認 `.env` 的 `TELEGRAM_BOT_TOKEN` 正確
- 確認 Bot 已啟動（終端看到 `🤖 Bot started...`）
- 確認 Telegram 先按過 `/start`

### /daily 失敗

- 確認有網路連線（要抓外部網站）
- 確認 `pip install httpx beautifulsoup4 pyyaml jinja2`
- 看終端錯誤訊息，通常是 httpx timeout

### Agent CLI 沒反應

- 確認已安裝：`gemini --version` 或 `kiro-cli --version`
- 確認已登入：`gemini`（首次要 Login）或 `kiro-cli login`
- Windows 確認 `GEMINI_CLI_CMD=gemini.cmd`（不是 `gemini`）

### validate 不通過

```bash
py .kiro/skills/ark-ai-bot-builder/scripts/validate_bot.py ./my-bot
```

按照錯誤提示補齊缺少的檔案。

---

## 與舊版 ai-bot-workshop 的差異

| | ai-bot-workshop（7 步驟） | ark-ai-bot-builder（一鍵） |
|---|---|---|
| 觸發方式 | 7 個獨立 Skill 分步觸發 | 1 個 `build_bot.py` 全部產出 |
| 耗時 | 2 堂 × 50 分鐘 | 5 分鐘 |
| 適合 | 學習者（逐步理解架構） | 熟手（快速產出 workspace） |
| 日報 | 需 LLM 結構化（Step 6） | 純 Python 直出（不需 LLM） |
| AI 對話 | Gemini API only | Agent CLI fallback chain |

---

## 快速指令表

```bash
# 產出
py .kiro/skills/ark-ai-bot-builder/scripts/build_bot.py ./my-bot

# 驗證
py .kiro/skills/ark-ai-bot-builder/scripts/validate_bot.py ./my-bot

# 設定
cd my-bot && cp .env.example .env

# 安裝
pip install -r requirements.txt

# 啟動
python -m src.bot.main

# 或 Windows
start.bat
```

---

*作者：paddyyang ｜ 2026-06-05*
