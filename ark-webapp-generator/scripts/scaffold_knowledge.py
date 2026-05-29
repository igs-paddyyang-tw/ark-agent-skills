"""scaffold_knowledge.py — 產出知識庫結構 + Agent 升級元素。

用法：python .kiro/skills/ark-webapp-generator/scripts/scaffold_knowledge.py [project_dir]
產出：
  knowledge/（schema + index + log + wiki/overview）
  src/skills/internal/wiki_manager.py
  src/skills/internal/cost_tracker.py
  src/agent/verifier.py
  src/agent/error_handler.py
  src/agent/event_log.py
  .kiro/steering/VERIFICATION.md
  .kiro/steering/KIRO.md
  .kiro/steering/USER.md
"""
import sys
from pathlib import Path

FILES: dict[str, str] = {}

FILES["knowledge/schema.md"] = '''# Wiki Schema v3.0

## 目錄結構

```
knowledge/
├── raw/          → 唯讀原始資料
├── wiki/         → 結構化知識頁面
├── schema.md     → 本文件
├── index.md      → 索引目錄
└── log.md        → 操作日誌（append-only）
```

## 頁面 Frontmatter（必要）

```yaml
---
title: "頁面標題"
type: concept | entity | source | synthesis | overview | system
tags: [tag1, tag2]
created: YYYY-MM-DD
updated: YYYY-MM-DD
status: seedling | developing | mature
---
```

## 操作規則

| 規則 | 說明 |
|------|------|
| raw/ 唯讀 | Bot 只讀不改 |
| 修改後同步 | 改 wiki → 更新 index.md + log.md |
| log append-only | 禁止刪除舊記錄 |
| 雙向連結 | `[[page_name]]` |
'''

FILES["knowledge/index.md"] = '''# 📇 知識索引

> 每次新增/修改 wiki 頁面時必須同步更新。

## 頁面列表

| 頁面 | 類型 | 標籤 | 狀態 |
|------|------|------|------|
| [[overview]] | overview | architecture | seedling |

---

*最後更新：初始化*
'''

FILES["knowledge/log.md"] = '''# 📝 知識庫操作日誌

> append-only，禁止刪除舊記錄。

- 初始化 | CREATE | 知識庫建立
'''

FILES["knowledge/raw/.gitkeep"] = ""

FILES["knowledge/wiki/overview.md"] = '''---
title: "知識庫概覽"
type: overview
tags: [architecture]
created: 2026-01-01
updated: 2026-01-01
status: seedling
---

# 知識庫概覽

本知識庫記錄 Bot 的運維經驗、Skill 開發紀錄、使用者偏好。
'''

FILES["src/skills/internal/wiki_manager.py"] = '''"""wiki_manager — 知識庫管理 Skill（query / ingest / list）。"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

KNOWLEDGE_DIR = Path("knowledge")
WIKI_DIR = KNOWLEDGE_DIR / "wiki"
INDEX_PATH = KNOWLEDGE_DIR / "index.md"
LOG_PATH = KNOWLEDGE_DIR / "log.md"


class WikiManagerParams(SkillParam):
    """wiki_manager 輸入參數。"""
    action: str = "query"
    query: str = ""
    source_path: str = ""
    title: str = ""
    tags: list[str] = []
    wiki_type: str = "concept"


class WikiManagerSkill(BaseSkill):
    """知識庫管理 — query/ingest/list。"""

    skill_id = "wiki_manager"
    skill_type = SkillType.PYTHON
    description = "知識庫管理 — 查詢、匯入、列表 wiki 頁面"
    version = "1.0.0"
    input_schema = WikiManagerParams

    async def execute(self, params: dict) -> SkillResult:
        try:
            p = WikiManagerParams(**params)
            if p.action == "query":
                return self._query(p.query)
            elif p.action == "ingest":
                return self._ingest(p.source_path, p.title, p.tags, p.wiki_type)
            elif p.action == "list":
                return self._list()
            else:
                return SkillResult(success=False, error="不支援的 action: %s" % p.action)
        except Exception as e:
            return SkillResult(success=False, error="wiki_manager 錯誤: %s" % e)

    def _query(self, query: str) -> SkillResult:
        if not query:
            return SkillResult(success=False, error="需提供 query")
        results: list[dict] = []
        keywords = query.lower().split()
        if not WIKI_DIR.exists():
            return SkillResult(success=True, data={"results": [], "count": 0})
        for md_file in WIKI_DIR.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8").lower()
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                title = md_file.stem
                title_match = re.search(r"^title:\\s*\\"?(.+?)\\"?\\s*$", content, re.MULTILINE)
                if title_match:
                    title = title_match.group(1)
                results.append({"path": str(md_file.relative_to(KNOWLEDGE_DIR)), "title": title, "score": score})
        results.sort(key=lambda x: x["score"], reverse=True)
        return SkillResult(success=True, data={"results": results[:10], "count": len(results)})

    def _ingest(self, source_path: str, title: str, tags: list[str], wiki_type: str) -> SkillResult:
        if not source_path:
            return SkillResult(success=False, error="需提供 source_path")
        src = Path(source_path)
        if not src.exists():
            return SkillResult(success=False, error="來源不存在: %s" % source_path)
        content = src.read_text(encoding="utf-8")
        slug = re.sub(r"[^\\w\\-]", "-", title.lower().strip())[:50] if title else src.stem
        today = datetime.now().strftime("%Y-%m-%d")
        WIKI_DIR.mkdir(parents=True, exist_ok=True)
        wiki_path = WIKI_DIR / ("%s.md" % slug)
        frontmatter = "---\\ntitle: \\"%s\\"\\ntype: %s\\ntags: [%s]\\ncreated: %s\\nupdated: %s\\nstatus: seedling\\n---\\n\\n" % (
            title or slug, wiki_type, ", ".join(tags), today, today
        )
        wiki_path.write_text(frontmatter + content, encoding="utf-8")
        self._append_log("INGEST", "wiki/%s.md" % slug, title or slug)
        return SkillResult(success=True, data={"path": str(wiki_path), "title": title or slug})

    def _list(self) -> SkillResult:
        if not INDEX_PATH.exists():
            return SkillResult(success=True, data={"pages": [], "count": 0})
        content = INDEX_PATH.read_text(encoding="utf-8")
        return SkillResult(success=True, data={"index": content, "count": content.count("[[")})

    def _append_log(self, action: str, path: str, note: str) -> None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not LOG_PATH.exists():
            LOG_PATH.write_text("# 操作日誌\\n\\n", encoding="utf-8")
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("- %s | %s | %s | %s\\n" % (now, action, path, note))
'''

FILES["src/skills/internal/cost_tracker.py"] = '''"""cost_tracker — LLM 呼叫成本追蹤。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

COSTS_PATH = Path("data/costs.json")
RATE_TABLE = {"gemini": {"input": 0.15, "output": 0.60}, "claude": {"input": 3.0, "output": 15.0}, "kiro": {"input": 3.0, "output": 15.0}, "static": {"input": 0.0, "output": 0.0}}


class CostTrackerParams(SkillParam):
    action: str = "report"
    backend: str = "gemini"
    tokens_in: int = 0
    tokens_out: int = 0


class CostTrackerSkill(BaseSkill):
    skill_id = "cost_tracker"
    skill_type = SkillType.PYTHON
    description = "追蹤 LLM API 呼叫成本"
    version = "1.0.0"
    input_schema = CostTrackerParams

    async def execute(self, params: dict) -> SkillResult:
        p = CostTrackerParams(**params)
        if p.action == "record":
            return self._record(p.backend, p.tokens_in, p.tokens_out)
        elif p.action == "report":
            return self._report()
        elif p.action == "reset":
            self._save({"records": [], "daily": {}})
            return SkillResult(success=True, data={"message": "已清除"})
        return SkillResult(success=False, error="不支援: %s" % p.action)

    def _load(self) -> dict:
        if COSTS_PATH.exists():
            return json.loads(COSTS_PATH.read_text(encoding="utf-8"))
        return {"records": [], "daily": {}}

    def _save(self, data: dict) -> None:
        COSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        COSTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _record(self, backend: str, tokens_in: int, tokens_out: int) -> SkillResult:
        rates = RATE_TABLE.get(backend, RATE_TABLE["gemini"])
        cost = (tokens_in * rates["input"] + tokens_out * rates["output"]) / 1_000_000
        data = self._load()
        today = datetime.now().strftime("%Y-%m-%d")
        data["records"].append({"ts": datetime.now().isoformat(), "backend": backend, "tokens_in": tokens_in, "tokens_out": tokens_out, "cost_usd": round(cost, 6)})
        if today not in data["daily"]:
            data["daily"][today] = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}
        d = data["daily"][today]
        d["calls"] += 1
        d["tokens_in"] += tokens_in
        d["tokens_out"] += tokens_out
        d["cost_usd"] = round(d["cost_usd"] + cost, 6)
        if len(data["records"]) > 1000:
            data["records"] = data["records"][-500:]
        self._save(data)
        return SkillResult(success=True, data={"cost_usd": cost, "today_total": d["cost_usd"]})

    def _report(self) -> SkillResult:
        data = self._load()
        today = datetime.now().strftime("%Y-%m-%d")
        d = data.get("daily", {}).get(today, {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0})
        return SkillResult(success=True, data=d)
'''

FILES["src/agent/verifier.py"] = '''"""CodeVerifier — 自動驗證產出的程式碼。"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass


@dataclass
class VerifyResult:
    passed: bool
    total: int = 0
    failed: int = 0
    output: str = ""
    error_summary: str = ""


class CodeVerifier:
    def __init__(self, test_dir: str = "tests", timeout: int = 30):
        self._test_dir = test_dir
        self._timeout = timeout

    def should_verify(self, file_path: str) -> bool:
        return file_path.startswith("src/") and file_path.endswith(".py")

    async def verify(self) -> VerifyResult:
        cmd = ["python", "-m", "pytest", self._test_dir, "--tb=short", "-q"]
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
            output = stdout.decode("utf-8").strip() if stdout else ""
            if proc.returncode == 0:
                m = re.search(r"(\\d+) passed", output)
                return VerifyResult(passed=True, total=int(m.group(1)) if m else 0, output=output)
            else:
                m_p = re.search(r"(\\d+) passed", output)
                m_f = re.search(r"(\\d+) failed", output)
                passed = int(m_p.group(1)) if m_p else 0
                failed = int(m_f.group(1)) if m_f else 0
                return VerifyResult(passed=False, total=passed+failed, failed=failed, output=output, error_summary=output[-200:])
        except asyncio.TimeoutError:
            return VerifyResult(passed=False, error_summary="pytest 超時")
        except Exception as e:
            return VerifyResult(passed=False, error_summary=str(e))
'''

FILES["src/agent/error_handler.py"] = '''"""ErrorHandler — 結構化錯誤分類 + 重試策略。"""
from __future__ import annotations

from enum import Enum


class ErrorCategory(str, Enum):
    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"
    PERMISSION = "permission"
    LLM_UNAVAILABLE = "llm_unavailable"
    PARSE_ERROR = "parse_error"
    SYNTAX = "syntax"
    RUNTIME = "runtime"
    UNKNOWN = "unknown"


class ErrorHandler:
    def __init__(self, max_retries: int = 2):
        self._history: list[tuple[ErrorCategory, str]] = []
        self._max_retries = max_retries

    def classify(self, error: Exception | str) -> ErrorCategory:
        msg = str(error).lower()
        if "timeout" in msg:
            return ErrorCategory.TIMEOUT
        if "not found" in msg or "不存在" in msg:
            return ErrorCategory.NOT_FOUND
        if "permission" in msg:
            return ErrorCategory.PERMISSION
        if "不可用" in msg or "unavailable" in msg:
            return ErrorCategory.LLM_UNAVAILABLE
        if "json" in msg or "parse" in msg:
            return ErrorCategory.PARSE_ERROR
        if "syntax" in msg:
            return ErrorCategory.SYNTAX
        if "traceback" in msg:
            return ErrorCategory.RUNTIME
        return ErrorCategory.UNKNOWN

    def should_retry(self, category: ErrorCategory) -> bool:
        count = sum(1 for c, _ in self._history if c == category)
        return count < self._max_retries

    def record(self, category: ErrorCategory, detail: str) -> None:
        self._history.append((category, detail))

    def suggest_alternative(self, category: ErrorCategory) -> str:
        alts = {
            ErrorCategory.TIMEOUT: "縮短 prompt 或切換 backend",
            ErrorCategory.LLM_UNAVAILABLE: "切換 fallback backend",
            ErrorCategory.PARSE_ERROR: "簡化 prompt 要求純 JSON",
        }
        return alts.get(category, "嘗試完全不同的方法")

    def reset(self) -> None:
        self._history.clear()
'''

FILES["src/agent/event_log.py"] = '''"""EventLog — append-only JSONL 操作日誌。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.skills.base import SkillResult

DEFAULT_PATH = Path("data/events.jsonl")


class EventLog:
    def __init__(self, path: str | Path = DEFAULT_PATH):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, skill_id: str, result: SkillResult | None = None, duration_ms: int = 0) -> None:
        entry = {"ts": datetime.now().isoformat(), "type": event_type, "skill_id": skill_id, "success": result.success if result else None, "duration_ms": duration_ms, "error": result.error if result and not result.success else ""}
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\\n")
        except Exception:
            pass

    def query(self, last_n: int = 20) -> list[dict]:
        if not self._path.exists():
            return []
        lines = self._path.read_text(encoding="utf-8").strip().split("\\n")
        return [json.loads(l) for l in lines[-last_n:] if l.strip()]

    def summary(self, last_n: int = 50) -> dict:
        events = self.query(last_n)
        success = sum(1 for e in events if e.get("success"))
        failed = sum(1 for e in events if e.get("success") is False)
        durations = [e["duration_ms"] for e in events if e.get("duration_ms")]
        return {"total": len(events), "success": success, "failed": failed, "avg_duration_ms": sum(durations) // len(durations) if durations else 0}
'''

FILES[".kiro/steering/VERIFICATION.md"] = '''---
inclusion: always
---

# VERIFICATION.md — 自我驗證規則

## 終端回饋處理

| exit_code | stderr 特徵 | 分類 | 處理 |
|-----------|------------|------|------|
| 0 | — | success | 繼續 |
| 非 0 | SyntaxError | syntax | 定位行號修復 |
| 非 0 | Traceback | runtime | 分析 root cause |
| 非 0 | Permission denied | permission | 檢查權限 |
| 非 0 | No such file | not_found | 確認路徑 |
| 非 0 | timeout | timeout | 加 timeout |

## 失敗模式

- 同一類錯誤連續 2 次 → 停止，換方法
- 禁止 3 次以上 incremental patch

## 自我驗證迴圈

修改 src/**/*.py 後：
1. pytest tests/ --tb=short -q
2. 失敗 → 立即修復
3. 通過 → 繼續
'''

FILES[".kiro/steering/KIRO.md"] = '''---
inclusion: fileMatch
fileMatchPattern: "src/**/*.py"
---

# Python 程式碼規範

- `from __future__ import annotations`
- 型別標註用 3.11+ 語法
- dataclass 優先
- log 用 %s 格式化
- asyncio: 不阻塞、保存 task 引用、wait_for 超時
- Token 從環境變數讀取
'''

FILES[".kiro/steering/USER.md"] = '''---
inclusion: always
---

# USER.md — 使用者百科

> 由 Bot 自動整理並持續更新。

## 個人特徵與偏好

- **偏好語言：** 繁體中文
- **技術偏好：** Python / FastAPI / async
'''


def scaffold(project_dir: Path) -> list[str]:
    """產出知識庫 + Agent 升級元素。"""
    created = []
    for rel_path, content in FILES.items():
        full = project_dir / rel_path
        if full.exists():
            continue
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        created.append(str(rel_path))
    return created


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    files = scaffold(target)
    print("✅ scaffold_knowledge: 產出 %d 個檔案到 %s" % (len(files), target))
    for f in files:
        print("   %s" % f)
