# ark-agent-bot-builder

> 產出 `ark_bot_agent` 套件消費端的 Bot workspace 骨架 —— **裝 wheel + 產設定檔**，
> 不手搭架構（runtime / Web UI / 記憶 / TG polling / 三模式路由全由套件內建）。

## 快速開始

```bash
# 1. 產骨架
python3 scripts/build_agent.py ./my-bot --name my-bot --codename 娜娜 --admin-chat-id <ID>
python3 scripts/validate_agent.py ./my-bot

# 2. 裝套件（wheel 從 Release 取）
cd my-bot && uv venv --python 3.13
uv pip install --python .venv/bin/python <ark_bot_agent-*.whl>

# 3. 補人格（ark-agent-init）+ 填 .env
# 4. 啟動
.venv/bin/python start.py            # 診斷：python -m ark_bot_agent paths
```

## 產出內容

| 檔/目錄 | 說明 |
|---------|------|
| `start.py` | 8 行 `run_bot()` 套件入口 |
| `bot.yaml` | 怎麼跑（server/modes/llm/backend/report/features/access） |
| `agents.yaml` | 有誰（default/manager/admin/leader/worker）← 專案根哨兵 |
| `.env` | 機密（TG token / API key） |
| `knowledge/shared/` | Wiki 引擎讀取層（🔴 少一層會靜默失效） |
| `memory/` | 套件記憶落點（daily/recent/memory.md） |
| `artifacts/reports/` | 產出目錄（取代舊 output/） |

## 定位

| 需求 | skill |
|------|-------|
| **單 bot（ark_bot_agent）** | **本 skill** |
| 多 agent 團隊（ark_team_agent） | `ark-agent-team-builder` |
| 非套件獨立 web 應用 | `ark-webapp-generator` |
| steering 人格 + 多 CLI 入口 | `ark-agent-init` |

## 環境需求

- Python 3.13
- `ark_bot_agent` wheel（[Release](https://github.com/igs-paddyyang-tw/ark_bot_agent/releases)）
- TG Token（選配，Tier 1）/ Gemini API Key（選配，Tier 2）/ kiro-cli（Tier 3）

---

> **v3.0（2026-09-08）**：原「手搭 bot 架構」（40+ Python 模板）已全數移除 ——
> 那些能力都套件化為 `ark_bot_agent`。現在只產設定骨架 + 裝 wheel。

*author: paddyyang ｜ 2026-09-08*
