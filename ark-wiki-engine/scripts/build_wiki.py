"""build_wiki.py — 一鍵產出 Wiki 知識庫引擎（8 Skills + API + Web UI）。

在目標專案目錄下建立完整的 Wiki 知識庫系統。
可獨立運作，也可整合進既有 FastAPI 專案。

Usage:
    python build_wiki.py <output_dir> [project_name]
    python build_wiki.py --validate <project_dir>

Examples:
    python build_wiki.py ./output/my-project my-project
    python build_wiki.py --validate ./output/my-project
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import date

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = SKILL_ROOT / "templates"

TODAY = str(date.today())


# ── 目錄結構 ──────────────────────────────────────────────────

DIRS = [
    "knowledge/{name}/raw",
    "knowledge/{name}/wiki",
    "src/skills/wiki_skills",
    "src/server/api",
    "src/server/templates",
    "src/server/static/js",
    "src/server/static/css",
]


# ── Wiki 基礎檔案 ────────────────────────────────────────────

def _schema_md(name: str) -> str:
    return f'''---
title: "Schema 規則"
version: "3.0"
updated: {TODAY}
---

# {name} 知識庫 Schema v3.0

## 頁面類型（type）

| type | 說明 |
|------|------|
| concept | 概念說明、方法論 |
| entity | 實體（工具、服務、框架） |
| source | 原始資料萃取 |
| synthesis | 多來源綜合分析 |
| comparison | 比較對照 |
| overview | 總覽索引 |
| system | 系統規範 |

## 成熟度（status）

| status | 說明 |
|--------|------|
| seedling | 剛建立，待充實 |
| developing | 有內容但不完整 |
| mature | 完整可參考 |

## Frontmatter 必填欄位

```yaml
---
title: "頁面標題"
type: concept | entity | source | synthesis | comparison | overview | system
tags: [tag1, tag2]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

## 連結規則

- 雙向連結：`[[page_name]]`（不含 .md、不含路徑）
- 矛盾標記：`> ⚠️ **矛盾**：來源 A 說 X，來源 B 說 Y，待釐清。`
- 不確定：`(?)`

## 操作規則

- `raw/` 唯讀（LLM 只讀不改）
- 修改 wiki 後必須更新 `index.md` + `log.md`
- 禁止刪除 `log.md` 舊記錄（append-only）
- 禁止自行解決矛盾（只能標記）
'''


def _index_md(name: str) -> str:
    return f'''---
title: "{name} 知識庫索引"
updated: {TODAY}
---

# {name} 知識庫

## 頁面索引

- [[overview]]

## 分類

（待新增）
'''


def _log_md() -> str:
    return f'''# 操作日誌

> Append-only，禁止刪除舊記錄。

- **{TODAY}** | init | 知識庫初始化
'''


def _overview_md(name: str) -> str:
    return f'''---
title: "{name} 總覽"
type: overview
tags: [index]
created: {TODAY}
updated: {TODAY}
status: seedling
---

# {name}

專案總覽頁面。

## 架構

（待補充）

## 關鍵頁面

（待新增知識後自動更新）
'''


# ── 8 個 Wiki Skills ──────────────────────────────────────────

def _wiki_init_py() -> str:
    return '''"""Wiki Skills — 知識庫操作 Skills。"""
'''


def _wiki_query_py() -> str:
    return '''"""wiki_query — 搜尋知識庫頁面。"""
from __future__ import annotations

from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class WikiQueryParams(SkillParam):
    query: str
    scope: str = "self"  # self | shared | all
    top_k: int = 5


class WikiQuerySkill(BaseSkill):
    """搜尋 Wiki 知識庫（BM25-like 關鍵字匹配）。"""

    skill_id = "wiki_query"
    skill_type = SkillType.PYTHON
    description = "搜尋 Wiki 知識庫頁面"
    version = "1.0.0"
    input_schema = WikiQueryParams

    def __init__(self, knowledge_root: Path | None = None) -> None:
        self._root = knowledge_root or Path("knowledge")

    async def execute(self, params: dict) -> SkillResult:
        p = WikiQueryParams(**params)
        keywords = p.query.lower().split()

        wiki_dir = self._root / "wiki"
        if not wiki_dir.exists():
            return SkillResult(success=False, error="知識庫尚未建立")

        results: list[dict] = []
        for md_file in wiki_dir.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
                content_lower = content.lower()
                score = sum(content_lower.count(kw) for kw in keywords)
                if score == 0:
                    continue

                title = md_file.stem
                for line in content.split("\\n"):
                    if line.startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip(\\'"\\')
                        break

                summary = ""
                in_fm = False
                for line in content.split("\\n"):
                    if line.strip() == "---":
                        in_fm = not in_fm
                        continue
                    if in_fm:
                        continue
                    if line.strip() and not line.startswith("#"):
                        summary = line.strip()[:120]
                        break

                results.append({
                    "title": title,
                    "path": str(md_file.relative_to(self._root)),
                    "score": score,
                    "summary": summary,
                })
            except (OSError, UnicodeDecodeError):
                continue

        results.sort(key=lambda x: x["score"], reverse=True)
        return SkillResult(success=True, data={"results": results[:p.top_k], "total": len(results)})
'''


def _wiki_ingest_py() -> str:
    return '''"""wiki_ingest — 將 raw/ 資料匯入 Wiki 知識庫。"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class WikiIngestParams(SkillParam):
    source_path: str
    target_category: str = ""
    title: str = ""


class WikiIngestSkill(BaseSkill):
    """將 raw/ 檔案萃取並建立 Wiki 頁面。"""

    skill_id = "wiki_ingest"
    skill_type = SkillType.PYTHON
    description = "將 raw/ 資料匯入 Wiki 知識庫"
    version = "1.0.0"
    input_schema = WikiIngestParams

    def __init__(self, knowledge_root: Path | None = None) -> None:
        self._root = knowledge_root or Path("knowledge")

    async def execute(self, params: dict) -> SkillResult:
        p = WikiIngestParams(**params)
        today = str(date.today())

        raw_file = self._root / "raw" / p.source_path
        if not raw_file.exists():
            raw_file = Path(p.source_path)
        if not raw_file.exists():
            return SkillResult(success=False, error=f"找不到來源檔案：{p.source_path}")

        content = raw_file.read_text(encoding="utf-8", errors="replace")
        page_name = p.title or raw_file.stem

        wiki_dir = self._root / "wiki"
        if p.target_category:
            wiki_dir = wiki_dir / p.target_category
        wiki_dir.mkdir(parents=True, exist_ok=True)

        page_path = wiki_dir / f"{page_name}.md"
        page_content = (
            f"---\\ntitle: \\"{page_name}\\"\\n"
            f"type: source\\ntags: [ingested]\\n"
            f"sources: [raw/{p.source_path}]\\n"
            f"created: {today}\\nupdated: {today}\\n"
            f"status: seedling\\n---\\n\\n"
            f"# {page_name}\\n\\n"
            f"> 匯入自 `raw/{p.source_path}`\\n\\n"
            f"{content[:3000]}\\n"
        )
        page_path.write_text(page_content, encoding="utf-8")

        # Update index.md
        index_path = self._root / "index.md"
        if index_path.exists():
            idx = index_path.read_text(encoding="utf-8")
            if f"[[{page_name}]]" not in idx:
                idx += f"- [[{page_name}]]\\n"
                index_path.write_text(idx, encoding="utf-8")

        # Update log.md
        log_path = self._root / "log.md"
        if log_path.exists():
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"- **{today}** | ingest | `{p.source_path}` → `{page_path.relative_to(self._root)}`\\n")

        return SkillResult(success=True, data={
            "page": str(page_path.relative_to(self._root)),
            "title": page_name,
        })
'''


def _wiki_lint_py() -> str:
    return '''"""wiki_lint — 知識庫健康檢查。"""
from __future__ import annotations

import re
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class WikiLintParams(SkillParam):
    fix: bool = False


class WikiLintSkill(BaseSkill):
    """檢查知識庫 frontmatter、孤立頁面、斷裂連結。"""

    skill_id = "wiki_lint"
    skill_type = SkillType.PYTHON
    description = "Wiki 知識庫健康檢查"
    version = "1.0.0"
    input_schema = WikiLintParams

    def __init__(self, knowledge_root: Path | None = None) -> None:
        self._root = knowledge_root or Path("knowledge")

    async def execute(self, params: dict) -> SkillResult:
        wiki_dir = self._root / "wiki"
        if not wiki_dir.exists():
            return SkillResult(success=False, error="wiki/ 目錄不存在")

        issues: list[str] = []
        all_pages: set[str] = set()
        all_links: set[str] = set()
        required_fields = {"title", "type", "created", "updated"}

        for md in wiki_dir.rglob("*.md"):
            page_name = md.stem
            all_pages.add(page_name)
            content = md.read_text(encoding="utf-8", errors="replace")

            # Check frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm_text = parts[1]
                    fm_keys = {line.split(":")[0].strip() for line in fm_text.strip().split("\\n") if ":" in line}
                    missing = required_fields - fm_keys
                    if missing:
                        issues.append(f"⚠️ {page_name}: frontmatter 缺少 {missing}")
                else:
                    issues.append(f"⚠️ {page_name}: frontmatter 格式錯誤")
            else:
                issues.append(f"⚠️ {page_name}: 缺少 frontmatter")

            # Collect wikilinks
            links = re.findall(r"\\[\\[([^\\]]+)\\]\\]", content)
            all_links.update(links)

        # Broken links
        for link in all_links:
            if link not in all_pages:
                issues.append(f"🔗 斷裂連結：[[{link}]]")

        # Orphan pages (no incoming links, not overview)
        linked_pages = all_links & all_pages
        orphans = all_pages - linked_pages - {"overview", "index"}
        for orphan in sorted(orphans):
            issues.append(f"🏝️ 孤立頁面：{orphan}")

        return SkillResult(success=True, data={
            "total_pages": len(all_pages),
            "total_links": len(all_links),
            "issues": issues,
            "healthy": len(issues) == 0,
        })
'''


def _wiki_graph_py() -> str:
    return '''"""wiki_graph — 知識圖譜分析。"""
from __future__ import annotations

import re
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class WikiGraphParams(SkillParam):
    pass


class WikiGraphSkill(BaseSkill):
    """分析 [[wikilink]] 建構知識圖譜。"""

    skill_id = "wiki_graph"
    skill_type = SkillType.PYTHON
    description = "知識圖譜分析（節點、邊、hub/orphan）"
    version = "1.0.0"
    input_schema = WikiGraphParams

    def __init__(self, knowledge_root: Path | None = None) -> None:
        self._root = knowledge_root or Path("knowledge")

    async def execute(self, params: dict) -> SkillResult:
        wiki_dir = self._root / "wiki"
        if not wiki_dir.exists():
            return SkillResult(success=False, error="wiki/ 目錄不存在")

        nodes: dict[str, int] = {}  # page → incoming link count
        edges: list[dict] = []

        for md in wiki_dir.rglob("*.md"):
            page = md.stem
            nodes.setdefault(page, 0)
            content = md.read_text(encoding="utf-8", errors="replace")
            links = re.findall(r"\\[\\[([^\\]]+)\\]\\]", content)
            for link in links:
                nodes[link] = nodes.get(link, 0) + 1
                edges.append({"from": page, "to": link})

        # Hub = top 5 most linked
        hubs = sorted(nodes.items(), key=lambda x: x[1], reverse=True)[:5]
        orphans = [p for p, c in nodes.items() if c == 0 and p != "overview"]

        return SkillResult(success=True, data={
            "nodes": len(nodes),
            "edges": len(edges),
            "hubs": [{"page": p, "links": c} for p, c in hubs],
            "orphans": orphans,
        })
'''


def _wiki_hybrid_search_py() -> str:
    return '''"""wiki_hybrid_search — BM25 + 全文搜尋 + RRF 融合。"""
from __future__ import annotations

import math
import re
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class WikiHybridSearchParams(SkillParam):
    query: str
    top_k: int = 5


class WikiHybridSearchSkill(BaseSkill):
    """混合搜尋：BM25 關鍵字 + 全文匹配 + RRF 排序。"""

    skill_id = "wiki_hybrid_search"
    skill_type = SkillType.PYTHON
    description = "Wiki 混合搜尋（BM25 + 全文 + RRF）"
    version = "1.0.0"
    input_schema = WikiHybridSearchParams

    def __init__(self, knowledge_root: Path | None = None) -> None:
        self._root = knowledge_root or Path("knowledge")

    async def execute(self, params: dict) -> SkillResult:
        p = WikiHybridSearchParams(**params)
        wiki_dir = self._root / "wiki"
        if not wiki_dir.exists():
            return SkillResult(success=False, error="wiki/ 不存在")

        query_terms = p.query.lower().split()
        docs: list[dict] = []

        for md in wiki_dir.rglob("*.md"):
            content = md.read_text(encoding="utf-8", errors="replace")
            lower = content.lower()
            words = re.findall(r"\\w+", lower)
            doc_len = len(words)

            # BM25 scoring
            bm25_score = 0.0
            k1, b, avg_dl = 1.5, 0.75, 500
            for term in query_terms:
                tf = words.count(term)
                if tf > 0:
                    idf = math.log(1 + 1)  # simplified
                    bm25_score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_dl))

            # Exact phrase bonus
            phrase_bonus = 2.0 if p.query.lower() in lower else 0.0

            total = bm25_score + phrase_bonus
            if total > 0:
                title = md.stem
                for line in content.split("\\n"):
                    if line.startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip(\\'"\\')
                        break
                docs.append({"title": title, "path": str(md.relative_to(self._root)), "score": total})

        docs.sort(key=lambda x: x["score"], reverse=True)
        return SkillResult(success=True, data={"results": docs[:p.top_k], "total": len(docs)})
'''


def _wiki_rag_bridge_py() -> str:
    return '''"""wiki_rag_bridge — LLM 呼叫前自動注入 Wiki context。"""
from __future__ import annotations

from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class WikiRagBridgeParams(SkillParam):
    query: str
    top_k: int = 3
    max_chars: int = 2000


class WikiRagBridgeSkill(BaseSkill):
    """RAG 橋接：搜尋 Wiki 並格式化為 LLM context。"""

    skill_id = "wiki_rag_bridge"
    skill_type = SkillType.PYTHON
    description = "RAG 橋接 — 自動注入 Wiki context 到 LLM 對話"
    version = "1.0.0"
    input_schema = WikiRagBridgeParams

    def __init__(self, knowledge_root: Path | None = None) -> None:
        self._root = knowledge_root or Path("knowledge")
        self._query_skill = None

    async def execute(self, params: dict) -> SkillResult:
        p = WikiRagBridgeParams(**params)

        # 延遲 import 避免循環
        if not self._query_skill:
            from src.skills.wiki_skills.wiki_query import WikiQuerySkill
            self._query_skill = WikiQuerySkill(self._root)

        result = await self._query_skill.execute({"query": p.query, "top_k": p.top_k})
        if not result.success or not result.data.get("results"):
            return SkillResult(success=True, data={"context": "", "sources": []})

        # 格式化為 LLM system prompt context
        snippets: list[str] = []
        sources: list[str] = []
        char_count = 0
        for r in result.data["results"]:
            snippet = f"[{r[\'title\']}] {r.get(\'summary\', \'\')}"
            if char_count + len(snippet) > p.max_chars:
                break
            snippets.append(snippet)
            sources.append(r["title"])
            char_count += len(snippet)

        context = "[知識庫參考]\\n" + "\\n".join(snippets) if snippets else ""
        return SkillResult(success=True, data={"context": context, "sources": sources})
'''


def _wiki_template_py() -> str:
    return '''"""wiki_template — 產生標準化 Wiki 頁面模板。"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class WikiTemplateParams(SkillParam):
    title: str
    page_type: str = "concept"  # concept | entity | source | synthesis
    category: str = ""
    tags: list[str] = []


class WikiTemplateSkill(BaseSkill):
    """產生標準化 Wiki 頁面模板。"""

    skill_id = "wiki_template"
    skill_type = SkillType.PYTHON
    description = "產生 Wiki 頁面模板（entity/concept/source）"
    version = "1.0.0"
    input_schema = WikiTemplateParams

    def __init__(self, knowledge_root: Path | None = None) -> None:
        self._root = knowledge_root or Path("knowledge")

    async def execute(self, params: dict) -> SkillResult:
        p = WikiTemplateParams(**params)
        today = str(date.today())
        tags_str = ", ".join(p.tags) if p.tags else p.page_type

        template = (
            f"---\\ntitle: \\"{p.title}\\"\\n"
            f"type: {p.page_type}\\ntags: [{tags_str}]\\n"
            f"created: {today}\\nupdated: {today}\\n"
            f"status: seedling\\n---\\n\\n"
            f"# {p.title}\\n\\n"
        )

        if p.page_type == "entity":
            template += "## 概要\\n\\n（說明）\\n\\n## 特性\\n\\n-\\n\\n## 相關\\n\\n-\\n"
        elif p.page_type == "concept":
            template += "## 定義\\n\\n（說明）\\n\\n## 應用場景\\n\\n-\\n\\n## 參考\\n\\n-\\n"
        elif p.page_type == "source":
            template += "> 來源：`raw/...`\\n\\n## 摘要\\n\\n（內容摘要）\\n"
        elif p.page_type == "synthesis":
            template += "## 結論\\n\\n（綜合分析）\\n\\n## 來源\\n\\n-\\n"

        # Write if category provided
        if p.category:
            wiki_dir = self._root / "wiki" / p.category
            wiki_dir.mkdir(parents=True, exist_ok=True)
            page_path = wiki_dir / f"{p.title.lower().replace(\' \', \'-\')}.md"
            page_path.write_text(template, encoding="utf-8")
            return SkillResult(success=True, data={"path": str(page_path), "content": template})

        return SkillResult(success=True, data={"content": template})
'''


def _wiki_schema_py() -> str:
    return '''"""wiki_schema — 驗證 Wiki 頁面 type/status 合法值。"""
from __future__ import annotations

from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

VALID_TYPES = {"concept", "entity", "source", "synthesis", "comparison", "overview", "system"}
VALID_STATUS = {"seedling", "developing", "mature"}


class WikiSchemaParams(SkillParam):
    pass


class WikiSchemaSkill(BaseSkill):
    """驗證 Wiki 頁面的 type/status 欄位是否合法。"""

    skill_id = "wiki_schema"
    skill_type = SkillType.PYTHON
    description = "驗證 Wiki 頁面 Schema（type/status）"
    version = "1.0.0"
    input_schema = WikiSchemaParams

    def __init__(self, knowledge_root: Path | None = None) -> None:
        self._root = knowledge_root or Path("knowledge")

    async def execute(self, params: dict) -> SkillResult:
        wiki_dir = self._root / "wiki"
        if not wiki_dir.exists():
            return SkillResult(success=False, error="wiki/ 不存在")

        violations: list[str] = []
        for md in wiki_dir.rglob("*.md"):
            content = md.read_text(encoding="utf-8", errors="replace")
            if not content.startswith("---"):
                continue
            parts = content.split("---", 2)
            if len(parts) < 3:
                continue
            fm = parts[1]
            for line in fm.strip().split("\\n"):
                if line.startswith("type:"):
                    val = line.split(":", 1)[1].strip()
                    if val not in VALID_TYPES:
                        violations.append(f"{md.stem}: type \\"{val}\\" 不合法")
                if line.startswith("status:"):
                    val = line.split(":", 1)[1].strip()
                    if val not in VALID_STATUS:
                        violations.append(f"{md.stem}: status \\"{val}\\" 不合法")

        return SkillResult(success=True, data={
            "valid": len(violations) == 0,
            "violations": violations,
        })
'''


# ── Build 主流程 ──────────────────────────────────────────────

SKILL_FILES = {
    "src/skills/wiki_skills/__init__.py": _wiki_init_py,
    "src/skills/wiki_skills/wiki_query.py": _wiki_query_py,
    "src/skills/wiki_skills/wiki_ingest.py": _wiki_ingest_py,
    "src/skills/wiki_skills/wiki_lint.py": _wiki_lint_py,
    "src/skills/wiki_skills/wiki_schema.py": _wiki_schema_py,
    "src/skills/wiki_skills/wiki_graph.py": _wiki_graph_py,
    "src/skills/wiki_skills/wiki_hybrid_search.py": _wiki_hybrid_search_py,
    "src/skills/wiki_skills/wiki_rag_bridge.py": _wiki_rag_bridge_py,
    "src/skills/wiki_skills/wiki_template.py": _wiki_template_py,
}


def build_wiki(output_dir: Path, project_name: str = "default") -> list[str]:
    """產出完整 Wiki 知識庫引擎。回傳已建立的檔案清單。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []

    # ── 1. 目錄結構 ──────────────────────────────────────────
    for d in DIRS:
        (output_dir / d.format(name=project_name)).mkdir(parents=True, exist_ok=True)

    # ── 2. 知識庫基礎檔案 ────────────────────────────────────
    kb_root = output_dir / "knowledge" / project_name
    files_to_write = {
        kb_root / "schema.md": _schema_md(project_name),
        kb_root / "index.md": _index_md(project_name),
        kb_root / "log.md": _log_md(),
        kb_root / "wiki" / "overview.md": _overview_md(project_name),
    }
    for path, content in files_to_write.items():
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created.append(str(path.relative_to(output_dir)))

    # ── 3. Wiki Skills ───────────────────────────────────────
    for rel_path, gen_fn in SKILL_FILES.items():
        dst = output_dir / rel_path
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(gen_fn(), encoding="utf-8")
            created.append(rel_path)

    return created


def validate_wiki(project_dir: Path) -> tuple[list[str], list[str]]:
    """驗證 Wiki 引擎產出完整性。回傳 (found, missing)。"""
    found: list[str] = []
    missing: list[str] = []

    required = list(SKILL_FILES.keys()) + [
        "knowledge/*/schema.md",
        "knowledge/*/index.md",
        "knowledge/*/log.md",
        "knowledge/*/wiki/overview.md",
    ]

    for rel in SKILL_FILES:
        if (project_dir / rel).exists():
            found.append(rel)
        else:
            missing.append(rel)

    # Check knowledge dirs (any project name)
    kb_dirs = list((project_dir / "knowledge").iterdir()) if (project_dir / "knowledge").exists() else []
    kb_files = ["schema.md", "index.md", "log.md", "wiki/overview.md"]
    for kb_dir in kb_dirs:
        if not kb_dir.is_dir() or kb_dir.name.startswith("."):
            continue
        for f in kb_files:
            rel = f"knowledge/{kb_dir.name}/{f}"
            if (kb_dir / f).exists():
                found.append(rel)
            else:
                missing.append(rel)

    return found, missing


def main() -> None:
    """CLI 入口。"""
    if len(sys.argv) < 2:
        print("Usage: python build_wiki.py <output_dir> [project_name]")
        print("       python build_wiki.py --validate <project_dir>")
        sys.exit(1)

    if sys.argv[1] == "--validate":
        if len(sys.argv) < 3:
            print("Usage: python build_wiki.py --validate <project_dir>")
            sys.exit(1)
        project_dir = Path(sys.argv[2])
        found, missing = validate_wiki(project_dir)
        total = len(found) + len(missing)
        if not missing:
            print(f"✅ 驗證通過：{len(found)}/{total} 個檔案皆已產出")
        else:
            print(f"❌ 驗證失敗：{len(found)}/{total}，缺 {len(missing)} 個")
            for m in missing:
                print(f"  - {m}")
            sys.exit(1)
    else:
        output_dir = Path(sys.argv[1])
        project_name = sys.argv[2] if len(sys.argv) > 2 else "default"
        created = build_wiki(output_dir, project_name)
        print(f"✅ Wiki 引擎產出完成：{len(created)} 個檔案")
        for f in created:
            print(f"  + {f}")


if __name__ == "__main__":
    main()
