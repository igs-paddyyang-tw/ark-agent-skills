#!/usr/bin/env python3
"""scaffold_kiro_config.py — 產出 .kiro/ + .agents/ 預設 AI IDE 配置。

讓 CLI（Gemini/Kiro/Claude/Antigravity）在專案目錄執行時，
能讀到系統提詞、角色定義、Skill 產出規範。

使用方式：
    python scaffold_kiro_config.py <project_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# ─── 檔案內容定義 ─────────────────────────────────────────

AGENT_JSON = json.dumps({
    "name": "ai-bot",
    "description": "科技日報 AI Bot — 對話、產出 Skill、自動化新聞",
    "prompt": "file://.kiro/steering/SOUL.md",
    "model": "claude-sonnet-4",
    "tools": ["*"],
    "allowedTools": ["*"],
    "resources": [
        "file://.kiro/steering/**/*.md",
        "skill://.kiro/skills/**/SKILL.md"
    ]
}, ensure_ascii=False, indent=2)

SOUL_MD = """\
# 🤖 AI Bot — 科技日報助手

> 所有回覆使用繁體中文。

## 你的身份

- 科技日報 AI Bot，能對話、產出程式碼、自動抓取新聞
- 支援 Skill 系統：使用者說需求 → 你產出 Skill → auto_discover 載入

## 核心能力

1. 自然語言對話（意圖路由）
2. 產出 BaseSkill .py 檔案（放入 src/skills/internal/）
3. 抓取新聞 → LLM 結構化 → HTML 日報
4. Workflow 排程自動化

## 產出 Skill 規則

- 繼承 BaseSkill（from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType）
- 必須有 skill_id、description、input_schema、execute
- 存放路徑：src/skills/internal/{skill_id}.py
- Python 3.12 語法、繁中 docstring
- execute 方法為 async，回傳 SkillResult

## Skill 模板

```python
from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

class MyParams(SkillParam):
    \"\"\"輸入參數。\"\"\"
    param1: str

class MySkill(BaseSkill):
    skill_id = "my_skill"
    skill_type = SkillType.PYTHON
    description = "一句話描述"
    version = "1.0.0"
    input_schema = MyParams

    async def execute(self, params: dict) -> SkillResult:
        p = MyParams(**params)
        return SkillResult(success=True, data={"result": p.param1})
```
"""

AGENTS_MD = """\
# 全域行為準則

> All tools are trusted.

## 工具使用規則

- 產出檔案用 fs_write，路徑相對於專案根目錄
- 新 Skill 放入 src/skills/internal/
- 修改後確認 import 不報錯

## 回報格式

```
✅ 完成：{做了什麼}
📁 產出：{檔案路徑}
```

## 目錄結構

```
src/
├── skills/
│   ├── base.py          ← BaseSkill 介面
│   ├── registry.py      ← SkillRegistry
│   └── internal/        ← 所有 Skill 放這裡
├── bot/                 ← Telegram Bot
├── server/              ← FastAPI
├── workflow/            ← WorkflowEngine
├── scheduler/           ← ScheduleEngine
└── llm/                 ← LLM 整合
```
"""

MEMORY_MD = """\
# 🧠 專案記憶

> 每次對話自動載入。每完成一個段落必須更新。

## 專案快照

- **名稱：** ai-bot
- **版本：** 0.1.0
- **技術棧：** Python 3.12 / FastAPI / python-telegram-bot / Gemini CLI

## 待辦

- [ ] （使用者填入）

## 近期進度

（自動累積）
"""

GEN_SKILL_PROMPT = """\
# @gen-skill — 產出新 Skill

根據使用者需求產出 BaseSkill .py 檔案。

{{user_input}}

---

## 請產出：

1. SkillParam 子類別（定義輸入參數，含 Field description）
2. BaseSkill 子類別（skill_id + skill_type + description + input_schema + execute）
3. execute 方法為 async，回傳 SkillResult(success=True, data={...})
4. 存入 src/skills/internal/{skill_id}.py
5. Python 3.12 語法、繁中 docstring
"""

DAILY_NEWS_PROMPT = """\
# @daily-news — 科技日報結構化

你是科技日報編輯。將新聞素材轉化為結構化格式。

{{raw_content}}

---

## 請產出 JSON：

```json
{
  "topic": "焦點分類（如 AI 焦點、開發工具）",
  "title": "10 字內標題",
  "what": "100 字內摘要，關鍵詞用 <span class=\\"hl\\">包裹</span>",
  "why": "80 字內影響分析",
  "summary": "一句話總結（15 字內）",
  "tags": [
    {"icon": "emoji", "text": "8 字內啟發"}
  ]
}
```
"""

# ─── Scaffold 邏輯 ────────────────────────────────────────

FILES: dict[str, str] = {
    "agents/ai-bot.json": AGENT_JSON,
    "steering/SOUL.md": SOUL_MD,
    "steering/AGENTS.md": AGENTS_MD,
    "steering/MEMORY.md": MEMORY_MD,
    "prompts/gen-skill.md": GEN_SKILL_PROMPT,
    "prompts/daily-news.md": DAILY_NEWS_PROMPT,
}


def scaffold(project_dir: Path) -> list[str]:
    """產出 .kiro/ + .agents/ 預設配置。回傳已產出的檔案清單。"""
    created: list[str] = []

    for ide_dir in (".kiro", ".agents"):
        base = project_dir / ide_dir
        for rel_path, content in FILES.items():
            full = base / rel_path
            if full.exists():
                continue  # 冪等：不覆寫
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
            created.append(f"{ide_dir}/{rel_path}")

    return created


def main() -> None:
    if len(sys.argv) < 2:
        print("使用方式: python scaffold_kiro_config.py <project_dir>")
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    if not project_dir.exists():
        project_dir.mkdir(parents=True)

    created = scaffold(project_dir)

    if created:
        print(f"✅ 產出 {len(created)} 個檔案：")
        for f in created:
            print(f"   • {f}")
    else:
        print("✅ 所有檔案已存在，無需產出。")


if __name__ == "__main__":
    main()
