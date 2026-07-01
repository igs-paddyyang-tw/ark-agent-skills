# ark-agent-builder

> 一鍵產出 AI Agent Bot Workspace — Agent CLI 為大腦，Telegram 自然語言對話讓 Bot 做事。

## 快速開始

```bash
# 產出專案
py scripts/build_agent.py ./output/my-bot

# 驗證結構
py scripts/validate_agent.py ./output/my-bot

# 設定 + 啟動
cd output/my-bot
cp .env.example .env          # 填入 TELEGRAM_BOT_TOKEN
pip install -r requirements.txt
python -m src.bot.main
```

## 目錄結構

```
ark-agent-builder/
├── SKILL.md              # 執行計畫 + 完整範例程式碼
├── README.md             # 本文件
├── assets/               # 靜態資源（直接複製到目標）
│   ├── env.example       # → .env.example
│   ├── gitignore.txt     # → .gitignore
│   ├── llm_prompts.yaml  # → config/llm_prompts.yaml
│   ├── news_sources.yaml # → config/news_sources.yaml
│   ├── requirements.txt  # → requirements.txt
│   └── start.bat         # → start.bat
├── templates/            # 程式碼樣板（複製為最終 .py）
│   ├── base.py           # → src/skills/base.py
│   ├── registry.py       # → src/skills/registry.py
│   ├── echo.py           # → src/skills/internal/echo.py
│   ├── llm_cli.py        # → src/skills/internal/llm_cli.py
│   ├── news_scraper.py   # → src/skills/internal/news_scraper.py
│   ├── news_renderer.py  # → src/skills/internal/news_renderer.py
│   ├── session.py        # → src/conversation/session.py
│   ├── planner.py        # → src/conversation/planner.py
│   ├── memory_search.py  # → src/conversation/memory_search.py
│   ├── gemini_chat.py    # → src/llm/gemini_chat.py
│   ├── bot_main.py       # → src/bot/main.py
│   └── handlers.py       # → src/bot/handlers.py
├── scripts/              # 產出 + 驗證腳本
│   ├── build_agent.py      # 一鍵產出整個專案（19 個檔案）
│   └── validate_agent.py   # 驗證結構完整性
└── docs/                 # 教學文件
    ├── guide.md          # 建置教學（Markdown）
    └── guide.html        # 建置教學（HTML，暗黑風格）
```

## 產出的 Bot 能做什麼

| 功能 | 觸發方式 | 需要 |
|------|---------|------|
| 科技日報 | `/daily` 或「今天有什麼新聞」 | 網路 |
| AI 對話 | 直接打字 | Gemini/Kiro/Claude CLI |
| 程式碼產出 | 「幫我寫一個 XXX」 | Agent CLI |
| Skill 擴充 | 新 .py 放 internal/ | 無 |

## 核心設計

- **Agent CLI 為大腦** — Gemini/Kiro/Claude 自動偵測 + fallback chain
- **自然語言進 CLI** — 不用記指令，說話就好
- **Skill 即功能** — 新 .py 放入 `internal/` 即自動載入
- **零配置日報** — 只要有網路，`/daily` 就能跑（不需 LLM）

## 環境需求

- Python 3.12+
- Telegram Bot Token（必填）
- Gemini CLI 或 Kiro CLI（選配，AI 對話用）
- Gemini API Key（選配，即時對話用）

## 教學文件

- [`docs/guide.md`](docs/guide.md) — Markdown 版教學
- [`docs/guide.html`](docs/guide.html) — HTML 版教學（瀏覽器直接開）

## 參考來源

- ninja-bot 原始碼（BaseSkill / Planner / LLMRouter / MemorySearch）
- ai-bot-build-guide.md（7 步驟教學架構）
- ark-agent-team-builder（assets + templates + scripts 模式）

---

*author: paddyyang ｜ 2026-06-05*
