"""wiki_distill — 用 kiro-cli 將 knowledge/raw/ 蒸餾為 wiki/ 結構化頁面。"""
from __future__ import annotations

import asyncio
import os
import subprocess
from datetime import datetime
from pathlib import Path
from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

_RAW_DIR = Path("knowledge/raw")
_WIKI_DIR = Path("knowledge/wiki")
_LOG_PATH = Path("knowledge/log.md")
_INDEX_PATH = Path("knowledge/index.md")

_DISTILL_PROMPT = """你是知識庫管理員。請閱讀 knowledge/raw/ 目錄下的所有 .md 檔案，
將內容蒸餾為結構化 wiki 頁面，存放到 knowledge/wiki/ 對應子目錄。

規則：
1. 每個 wiki 頁面必須有 frontmatter：title/type/tags/created/updated/status/sources
2. 去除時間戳、過程細節、重複內容，只保留核心知識
3. 同主題的多個 raw 檔合併為一頁
4. 分類目錄：operations/（操作）、research/（調研）、patterns/（設計模式）、decisions/（決策）
5. 用 [[page_name]] 雙向連結相關頁面
6. 完成後更新 knowledge/index.md（頁面目錄表格）
7. 在 knowledge/log.md 末尾追加一行：- [distill] YYYY-MM-DD 蒸餾 N 頁

現在請執行蒸餾，讀取 raw/ 下的檔案並產出 wiki/ 頁面。"""


class WikiDistillParams(SkillParam):
    timeout: int = 300


class WikiDistillSkill(BaseSkill):
    skill_id = "wiki_distill"
    skill_type = SkillType.PYTHON
    description = "用 kiro-cli 蒸餾 knowledge/raw/ 為結構化 wiki 頁面（每日排程）"
    version = "1.0.0"
    input_schema = WikiDistillParams

    async def execute(self, params: dict) -> SkillResult:
        try:
            p = WikiDistillParams(**params)
            # 確保目錄存在
            _WIKI_DIR.mkdir(parents=True, exist_ok=True)

            # 用 kiro-cli 執行蒸餾
            cmd_path = os.getenv("KIRO_CLI_CMD", "kiro-cli")
            cwd = os.getenv("AI_BOT_WORKSPACE", str(Path.home()))

            cmd = subprocess.list2cmdline([
                cmd_path, "chat", "--no-interactive", "-a", "--wrap", "never",
                _DISTILL_PROMPT,
            ])

            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=p.timeout)
            out = stdout.decode("utf-8").strip() if stdout else ""
            err = stderr.decode("utf-8").strip() if stderr else ""

            if process.returncode != 0 and not out:
                return SkillResult(success=False, error=f"kiro-cli 失敗: {err[:300]}")

            # 統計產出
            wiki_pages = list(_WIKI_DIR.rglob("*.md"))
            count = len(wiki_pages)

            return SkillResult(success=True, data={
                "output": f"✅ 蒸餾完成，wiki/ 共 {count} 頁",
                "pages": count,
                "kiro_output": out[:500],
            })
        except asyncio.TimeoutError:
            return SkillResult(success=False, error=f"蒸餾超時（{params.get('timeout', 300)}s）")
        except Exception as e:
            return SkillResult(success=False, error=str(e))
