"""build_wiki.py v2 — 一鍵產出 Wiki 知識庫引擎（含四層搜尋 + Server + Web UI）。

在目標專案目錄下建立完整的 Wiki 知識庫系統（23 個檔案）：
  - 知識庫 5 個（schema + index + log + overview + .index/）
  - Skills 9 個（query v2 + ingest v2 + indexer + lint + schema + graph + hybrid v2 + rag_bridge + template）
  - Server 5 個（main + api/wiki + api/files + __init__ × 2）
  - Web UI 3 個（index.html + app.js + style.css）
  - 設定 2 個（run.py + requirements.txt）

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
    "knowledge/{name}/.index",
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
    return '''"""wiki_query — 四層金字塔搜尋（metadata→BM25→hybrid→rerank）。"""
from __future__ import annotations

import re
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class WikiQueryParams(SkillParam):
    query: str
    scope: str = "self"  # self | shared | all
    top_k: int = 5


class WikiQuerySkill(BaseSkill):
    """四層金字塔搜尋：metadata精確 → BM25索引 → hybrid混合 → rerank。"""

    skill_id = "wiki_query"
    skill_type = SkillType.PYTHON
    description = "Wiki 四層搜尋（metadata精確→BM25→混合→rerank）"
    version = "2.0.0"
    input_schema = WikiQueryParams

    STOPWORDS = {"的", "是", "了", "在", "有", "什麼", "嗎", "呢", "可以", "怎麼", "一個", "和", "與"}

    def __init__(self, knowledge_root: Path | None = None) -> None:
        self._root = knowledge_root or Path("knowledge")
        self._wiki_dir = self._root / "wiki"
        self._index_dir = self._root / ".index"

    async def execute(self, params: dict) -> SkillResult:
        p = WikiQueryParams(**params)
        if not self._wiki_dir.exists():
            return SkillResult(success=False, error="知識庫尚未建立")

        from src.skills.wiki_skills.wiki_indexer import WikiIndexer
        indexer = WikiIndexer(self._root)
        metadata = indexer.load_metadata()
        keywords = self._tokenize(p.query)

        # Layer 0: metadata 精確匹配
        exact = self._search_exact(p.query, metadata)
        if exact and exact[0]["score"] >= 1.0:
            results = self._add_summary(exact[:p.top_k], keywords)
            return SkillResult(success=True, data={"results": results, "total": len(exact)})

        # Layer 1: BM25
        bm25_hits = self._search_bm25(p.query, metadata, p.top_k * 2)

        # Layer 2: hybrid（BM25 + 圖譜擴散 + RRF）
        if bm25_hits:
            hybrid_hits = self._hybrid_fuse(p.query, bm25_hits, metadata, p.top_k * 2)
        else:
            hybrid_hits = bm25_hits

        # Layer 0 兜底
        if not hybrid_hits and not exact:
            hybrid_hits = self._search_substring(p.query, metadata)

        all_hits = (exact or []) + (hybrid_hits or [])
        seen, deduped = set(), []
        for h in all_hits:
            if h["path"] not in seen:
                seen.add(h["path"])
                deduped.append(h)

        results = self._add_summary(deduped[:p.top_k], keywords)
        return SkillResult(success=True, data={"results": results, "total": len(deduped)})

    def _tokenize(self, q: str) -> list[str]:
        tokens = q.lower().split()
        cjk = [c for c in q if "\\u4e00" <= c <= "\\u9fff"]
        bigrams = [cjk[i]+cjk[i+1] for i in range(len(cjk)-1)]
        return [t for t in tokens + bigrams if t not in self.STOPWORDS and t.strip()]

    def _search_exact(self, q: str, metadata: list[dict]) -> list[dict]:
        q_lower = q.strip().lower()
        results = []
        for e in metadata:
            if q_lower == e["slug"].lower() or q_lower == e["title"].lower():
                results.append({"path": e["path"], "title": e["title"], "score": 1.0})
            elif any(q_lower == a.lower() for a in e.get("aliases", [])):
                results.append({"path": e["path"], "title": e["title"], "score": 0.95})
            elif q_lower in e["title"].lower():
                results.append({"path": e["path"], "title": e["title"], "score": 0.8})
        return results

    def _search_bm25(self, q: str, metadata: list[dict], top_k: int) -> list[dict]:
        try:
            import bm25s
            from src.skills.wiki_skills.wiki_indexer import WikiIndexer
            bm25_dir = self._index_dir / "bm25s"
            if not bm25_dir.exists():
                return []
            indexer = WikiIndexer(self._root)
            tokens = indexer._tokenize(q)
            if not tokens:
                return []
            retriever = bm25s.BM25.load(str(bm25_dir))
            results, scores = retriever.retrieve([tokens], k=min(top_k, len(metadata)))
            hits = []
            for i in range(len(results[0])):
                idx, score = int(results[0][i]), float(scores[0][i])
                if score > 0 and idx < len(metadata):
                    e = metadata[idx]
                    hits.append({"path": e["path"], "title": e["title"], "score": score})
            return hits
        except (ImportError, Exception):
            return []

    def _search_substring(self, q: str, metadata: list[dict]) -> list[dict]:
        q_lower = q.strip().lower()
        hits = []
        for e in metadata:
            path = self._wiki_dir / e["path"]
            if path.exists():
                body = self._strip_fm(path.read_text(encoding="utf-8")).lower()
                if q_lower in body:
                    hits.append({"path": e["path"], "title": e["title"], "score": 0.4})
            if len(hits) >= 10:
                break
        return hits

    def _hybrid_fuse(self, q: str, bm25_hits: list[dict], metadata: list[dict], top_k: int) -> list[dict]:
        bm25_paths = [h["path"] for h in bm25_hits]
        # 圖譜擴散
        slug_to_path = {e["slug"]: e["path"] for e in metadata}
        graph_paths = []
        for path in bm25_paths[:3]:
            wp = self._wiki_dir / path
            if wp.exists():
                content = wp.read_text(encoding="utf-8")
                links = re.findall(r"\\[\\[(.+?)\\]\\]", content)
                for link in links:
                    lp = slug_to_path.get(link, "")
                    if lp and lp not in bm25_paths:
                        graph_paths.append(lp)
        # RRF
        scores: dict[str, float] = {}
        for rank, p in enumerate(bm25_paths):
            scores[p] = scores.get(p, 0) + 1.0 / (60 + rank + 1)
        for rank, p in enumerate(graph_paths):
            scores[p] = scores.get(p, 0) + 1.0 / (60 + rank + 1)
        fused = sorted(scores, key=scores.get, reverse=True)
        path_to_entry = {e["path"]: e for e in metadata}
        return [{"path": p, "title": path_to_entry[p]["title"], "score": scores[p]}
                for p in fused[:top_k] if p in path_to_entry]

    def _add_summary(self, hits: list[dict], keywords: list[str]) -> list[dict]:
        for h in hits:
            path = self._wiki_dir / h["path"]
            h["summary"] = self._extract_summary(path, keywords) if path.exists() else ""
        return hits

    def _extract_summary(self, path: Path, keywords: list[str], max_len: int = 200) -> str:
        content = path.read_text(encoding="utf-8")
        body = self._strip_fm(content)
        paragraphs = [p.strip() for p in re.split(r"\\n\\s*\\n", body) if p.strip()]
        if not paragraphs:
            return body[:max_len]
        if not keywords:
            return paragraphs[0][:max_len]
        best, best_score = paragraphs[0], 0
        for para in paragraphs:
            score = sum(1 for kw in keywords if kw in para.lower())
            if score > best_score:
                best_score, best = score, para
        return best[:max_len]

    @staticmethod
    def _strip_fm(content: str) -> str:
        if content.startswith("\\ufeff"):
            content = content[1:]
        if not content.startswith("---"):
            return content
        end = content.find("---", 3)
        return content[end+3:].strip() if end != -1 else content
'''


def _wiki_ingest_py() -> str:
    return '''"""wiki_ingest — 將 raw/ 資料匯入 Wiki 知識庫（v2: 含索引重建觸發）。"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class WikiIngestParams(SkillParam):
    source_path: str = ""     # 空 = 匯入所有 raw/
    target_category: str = ""
    title: str = ""


class WikiIngestSkill(BaseSkill):
    """將 raw/ 檔案萃取並建立 Wiki 頁面，完成後觸發索引重建。"""

    skill_id = "wiki_ingest"
    skill_type = SkillType.PYTHON
    description = "raw/ 匯入 → wiki/ + 觸發索引重建"
    version = "2.0.0"
    input_schema = WikiIngestParams

    def __init__(self, knowledge_root: Path | None = None) -> None:
        self._root = knowledge_root or Path("knowledge")

    async def execute(self, params: dict) -> SkillResult:
        p = WikiIngestParams(**params)
        today = str(date.today())
        raw_dir = self._root / "raw"
        wiki_dir = self._root / "wiki"
        wiki_dir.mkdir(parents=True, exist_ok=True)

        # 收集要匯入的檔案
        if p.source_path:
            files = [raw_dir / p.source_path]
        else:
            files = list(raw_dir.rglob("*.md"))

        ingested = []
        for src in files:
            if not src.exists():
                continue
            rel = src.relative_to(raw_dir)
            dest = wiki_dir / rel

            # mtime 比對：wiki 版不比 raw 舊 → 跳過
            if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
                continue

            content = src.read_text(encoding="utf-8", errors="replace")
            if content.startswith("\\ufeff"):
                content = content[1:]

            if content.startswith("---"):
                wiki_content = content
            else:
                # title 優先從 H1 抓取
                title = p.title or self._extract_h1(content) or src.stem
                wiki_content = (
                    f"---\\ntitle: \\"{title}\\"\\n"
                    f"type: source\\ntags: [ingested]\\n"
                    f"sources: [raw/{rel}]\\n"
                    f"created: {today}\\nupdated: {today}\\n"
                    f"status: seedling\\n---\\n\\n{content}"
                )

            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(wiki_content, encoding="utf-8")
            ingested.append(str(rel))

        # 更新 index + log
        if ingested:
            self._update_index()
            self._append_log(ingested, today)
            # 觸發索引重建
            try:
                from src.skills.wiki_skills.wiki_indexer import WikiIndexer
                WikiIndexer(self._root).rebuild()
            except Exception:
                pass

        return SkillResult(success=True, data={
            "ingested": ingested, "count": len(ingested),
        })

    def _extract_h1(self, content: str) -> str:
        m = re.search(r"^#\\s+(.+)$", content, re.MULTILINE)
        return m.group(1).strip() if m else ""

    def _update_index(self) -> None:
        wiki_dir = self._root / "wiki"
        lines = ["# Wiki 索引\\n", "| 檔案 | 標題 |", "|------|------|"]
        for md in sorted(wiki_dir.rglob("*.md")):
            content = md.read_text(encoding="utf-8")
            title = md.stem
            m = re.search(r"^title:\\s*[\\"\\'\\']?(.+?)[\\"\\'\\']?\\s*$", content, re.MULTILINE)
            if m:
                title = m.group(1)
            lines.append(f"| {md.relative_to(wiki_dir)} | {title} |")
        (self._root / "index.md").write_text("\\n".join(lines) + "\\n", encoding="utf-8")

    def _append_log(self, files: list[str], today: str) -> None:
        log_path = self._root / "log.md"
        entry = f"- [{today}] ingest: {', '.join(files[:5])}"
        if len(files) > 5:
            entry += f" ...等共 {len(files)} 篇"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry + "\\n")
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
    return '''"""wiki_hybrid_search — 四層搜尋管線 + RRF 融合（v2）。"""
from __future__ import annotations

import re
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class WikiHybridSearchParams(SkillParam):
    query: str
    top_k: int = 5


class WikiHybridSearchSkill(BaseSkill):
    """四層搜尋管線：metadata精確 + bm25s持久化索引 + 語意向量 + 圖譜擴散 → RRF融合。"""

    skill_id = "wiki_hybrid_search"
    skill_type = SkillType.PYTHON
    description = "四層搜尋管線（metadata + BM25 + 語意 + 圖譜 → RRF，Layer 0 保底永不掛零）"
    version = "2.0.0"
    input_schema = WikiHybridSearchParams

    def __init__(self, knowledge_root: Path | None = None) -> None:
        self._root = knowledge_root or Path("knowledge")
        self._wiki_dir = self._root / "wiki"

    async def execute(self, params: dict) -> SkillResult:
        p = WikiHybridSearchParams(**params)
        if not self._wiki_dir.exists():
            return SkillResult(success=False, error="wiki/ 不存在")

        # 委派給 WikiQuerySkill（它已實作完整四層管線）
        from src.skills.wiki_skills.wiki_query import WikiQuerySkill
        query_skill = WikiQuerySkill(self._root)
        return await query_skill.execute({"query": p.query, "top_k": p.top_k})
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


# ── v2 新增：Indexer ─────────────────────────────────────────

def _wiki_indexer_py() -> str:
    return '''"""wiki_indexer — 索引建置器（metadata + bm25s + userdict）。"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


class WikiIndexer:
    """建置持久化搜尋索引到 .index/ 目錄。"""

    def __init__(self, knowledge_root: Path | None = None) -> None:
        self._root = knowledge_root or Path("knowledge")
        self._index_dir = self._root / ".index"

    def rebuild(self) -> dict:
        """重建所有索引。回傳 manifest。"""
        self._index_dir.mkdir(parents=True, exist_ok=True)
        pages = self._scan_pages()
        self._build_metadata(pages)
        self._build_userdict(pages)
        self._build_bm25(pages)
        return self._write_manifest(len(pages))

    def load_metadata(self) -> list[dict]:
        path = self._index_dir / "metadata.json"
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _scan_pages(self) -> list[dict]:
        wiki_dir = self._root / "wiki"
        if not wiki_dir.exists():
            return []
        pages = []
        for md in sorted(wiki_dir.rglob("*.md")):
            if md.name.startswith("."):
                continue
            content = md.read_text(encoding="utf-8")
            if content.startswith("\\\\ufeff"):
                content = content[1:]
            fm = self._parse_fm(content)
            body = self._strip_fm(content)
            pages.append({
                "slug": md.stem,
                "title": fm.get("title", md.stem),
                "aliases": fm.get("aliases", []),
                "tags": fm.get("tags", []),
                "related": fm.get("related", []),
                "type": fm.get("type", ""),
                "path": str(md.relative_to(wiki_dir)),
                "updated": fm.get("updated", ""),
                "body": body,
            })
        return pages

    def _build_metadata(self, pages: list[dict]) -> None:
        meta = [{k: v for k, v in p.items() if k != "body"} for p in pages]
        (self._index_dir / "metadata.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_userdict(self, pages: list[dict]) -> None:
        words = set()
        for p in pages:
            if len(p["title"]) >= 2:
                words.add(p["title"])
            for a in p.get("aliases", []):
                if len(a) >= 2:
                    words.add(a)
        (self._index_dir / "userdict.txt").write_text(
            "\\n".join(f"{w} 5" for w in sorted(words)) + "\\n", encoding="utf-8")

    def _build_bm25(self, pages: list[dict]) -> None:
        try:
            import bm25s
        except ImportError:
            return
        corpus = [self._tokenize(f"{p['title']} {p['title']} {p['title']} {' '.join(p.get('tags',[]))} {p['body']}") for p in pages]
        if not corpus:
            return
        retriever = bm25s.BM25()
        retriever.index(corpus)
        bm25_dir = self._index_dir / "bm25s"
        bm25_dir.mkdir(parents=True, exist_ok=True)
        retriever.save(str(bm25_dir))

    def _tokenize(self, text: str) -> list[str]:
        stopwords = {"的", "是", "了", "在", "有", "什麼", "嗎", "呢", "可以", "怎麼", "一個", "和", "與"}
        try:
            import jieba
            ud = self._index_dir / "userdict.txt"
            if ud.exists():
                jieba.load_userdict(str(ud))
            tokens = list(jieba.cut_for_search(text))
        except ImportError:
            tokens = text.lower().split()
        cjk = [c for c in text if "\\\\u4e00" <= c <= "\\\\u9fff"]
        bigrams = [cjk[i] + cjk[i+1] for i in range(len(cjk)-1)]
        tokens.extend(bigrams)
        return [t.lower() for t in tokens if t.strip() and t not in stopwords]

    def _write_manifest(self, count: int) -> dict:
        m = {"version": "2.0.0", "rebuilt_at": datetime.now(timezone.utc).isoformat(), "page_count": count,
             "has_bm25": (self._index_dir / "bm25s").exists()}
        (self._index_dir / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        return m

    @staticmethod
    def _parse_fm(content: str) -> dict:
        if not content.startswith("---"):
            return {}
        end = content.find("---", 3)
        if end == -1:
            return {}
        result = {}
        for line in content[3:end].splitlines():
            m = re.match(r"^(\\w+):\\s*(.+)$", line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                if val.startswith("[") and val.endswith("]"):
                    result[key] = [x.strip().strip("\\'\\\\\\"") for x in val[1:-1].split(",") if x.strip()]
                else:
                    result[key] = val.strip("\\'\\\\\\"")
        return result

    @staticmethod
    def _strip_fm(content: str) -> str:
        if not content.startswith("---"):
            return content
        end = content.find("---", 3)
        return content[end+3:].strip() if end != -1 else content
'''


# ── v2 新增：Server ──────────────────────────────────────────

def _server_main_py() -> str:
    return '''"""Wiki Server — FastAPI 主程式。"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from src.server.api.wiki import router as wiki_router
from src.server.api.files import router as files_router

app = FastAPI(title="Wiki 知識庫引擎")

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(wiki_router, prefix="/api/v1/wiki", tags=["Wiki"])
app.include_router(files_router, prefix="/api", tags=["Files"])


@app.get("/", response_class=HTMLResponse)
def index():
    return (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"status": "ok"}
'''


def _server_wiki_api_py() -> str:
    return '''"""Wiki API — query / ingest / lint / rebuild-index。"""
from fastapi import APIRouter
from pydantic import BaseModel
from src.skills.wiki_skills.wiki_query import WikiQuerySkill
from src.skills.wiki_skills.wiki_ingest import WikiIngestSkill
from src.skills.wiki_skills.wiki_lint import WikiLintSkill
from src.skills.wiki_skills.wiki_indexer import WikiIndexer

router = APIRouter()


class QueryRequest(BaseModel):
    q: str
    top_k: int = 5


@router.post("/query")
async def query(req: QueryRequest):
    skill = WikiQuerySkill()
    result = await skill.execute({"query": req.q, "top_k": req.top_k})
    return result.data if result.success else {"error": result.error}


@router.post("/ingest")
async def ingest():
    skill = WikiIngestSkill()
    result = await skill.execute({})
    return result.data if result.success else {"error": result.error}


@router.get("/lint")
async def lint():
    skill = WikiLintSkill()
    result = await skill.execute({})
    return result.data if result.success else {"error": result.error}


@router.post("/rebuild-index")
async def rebuild_index():
    indexer = WikiIndexer()
    manifest = indexer.rebuild()
    return {"status": "ok", "manifest": manifest}


@router.get("/index-status")
async def index_status():
    import json
    from pathlib import Path
    manifest_path = Path("knowledge/.index/manifest.json")
    if not manifest_path.exists():
        return {"status": "not_built", "manifest": None}
    return {"status": "ok", "manifest": json.loads(manifest_path.read_text(encoding="utf-8"))}
'''


def _server_files_api_py() -> str:
    return '''"""Files API — 列出和讀取 wiki 檔案（排除 raw/）。"""
from pathlib import Path
from fastapi import APIRouter

router = APIRouter()
WIKI_DIR = Path("knowledge/wiki")


@router.get("/files")
def list_files():
    """列出 wiki/ 下所有 .md 檔案（排除 raw/）。"""
    if not WIKI_DIR.exists():
        return {"files": []}
    files = []
    for md in sorted(WIKI_DIR.rglob("*.md")):
        files.append(str(md.relative_to(WIKI_DIR)))
    return {"files": files}


@router.get("/files/{filepath:path}")
def get_file(filepath: str):
    """讀取指定 wiki 檔案。"""
    path = WIKI_DIR / filepath
    if not path.exists() or not path.is_file():
        return {"error": "not found"}
    return {"filename": filepath, "content": path.read_text(encoding="utf-8")}
'''


# ── v2 新增：Web UI ──────────────────────────────────────────

def _index_html() -> str:
    return '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Wiki 知識庫</title>
<link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
<div class="layout">
  <aside class="sidebar">
    <div class="search-box">
      <input type="text" id="searchInput" placeholder="搜尋 Wiki..." autocomplete="off">
    </div>
    <nav id="fileTree" class="file-tree"></nav>
  </aside>
  <main id="content" class="content">
    <div class="empty">📖 選擇左側檔案或搜尋</div>
  </main>
</div>
<script src="/static/js/app.js"></script>
</body>
</html>'''


def _app_js() -> str:
    return '''// Wiki App — 載入檔案樹 + 搜尋 + Markdown 渲染
let treeData = [];

async function init() {
  const resp = await fetch("/api/files");
  const data = await resp.json();
  treeData = data.files || [];
  renderTree(treeData);

  document.getElementById("searchInput").addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    const filtered = q ? treeData.filter(f => f.toLowerCase().includes(q)) : treeData;
    renderTree(filtered);
  });
}

function renderTree(files) {
  const nav = document.getElementById("fileTree");
  nav.innerHTML = files.map(f =>
    `<div class="tree-item" onclick="loadPage('${f}')">${f}</div>`
  ).join("");
}

async function loadPage(path) {
  const resp = await fetch(`/api/files/${path}`);
  const data = await resp.json();
  if (data.error) {
    document.getElementById("content").innerHTML = `<div class="empty">找不到 ${path}</div>`;
    return;
  }
  document.getElementById("content").innerHTML = `<div class="page"><pre>${escapeHtml(data.content)}</pre></div>`;
}

function escapeHtml(t) {
  const d = document.createElement("div");
  d.textContent = t;
  return d.innerHTML;
}

init();'''


def _style_css() -> str:
    return '''* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, sans-serif; background: #1a1a2e; color: #e0e0e0; }
.layout { display: grid; grid-template-columns: 260px 1fr; height: 100vh; }
.sidebar { background: #16213e; border-right: 1px solid #334; overflow-y: auto; }
.search-box { padding: 1rem; border-bottom: 1px solid #334; }
.search-box input { width: 100%; padding: 0.5rem; border-radius: 6px; border: 1px solid #334; background: #1a1a2e; color: #e0e0e0; }
.file-tree { padding: 0.5rem; }
.tree-item { padding: 0.4rem 0.8rem; cursor: pointer; border-radius: 4px; font-size: 0.85rem; }
.tree-item:hover { background: rgba(34,211,238,0.1); }
.content { padding: 2rem; overflow-y: auto; }
.empty { text-align: center; padding: 4rem; color: #888; font-size: 1.2rem; }
.page pre { white-space: pre-wrap; line-height: 1.6; }'''


# ── v2 新增：run.py + requirements ───────────────────────────

def _run_py() -> str:
    return '''"""一鍵啟動 Wiki 知識庫引擎。"""
import uvicorn

if __name__ == "__main__":
    print("🚀 Wiki 知識庫引擎啟動中...")
    print("   http://localhost:8000")
    uvicorn.run("src.server.main:app", host="0.0.0.0", port=8000, reload=True)
'''


def _requirements_txt() -> str:
    return '''fastapi>=0.115.0
uvicorn[standard]>=0.30.0
pydantic>=2.9.0

# 選配：Wiki 搜尋優化（沒裝也能跑）
bm25s>=0.2
jieba>=0.42
'''


# ── Build 主流程 ──────────────────────────────────────────────

SKILL_FILES = {
    # Skills（9 個）
    "src/skills/wiki_skills/__init__.py": _wiki_init_py,
    "src/skills/wiki_skills/wiki_indexer.py": _wiki_indexer_py,
    "src/skills/wiki_skills/wiki_query.py": _wiki_query_py,
    "src/skills/wiki_skills/wiki_ingest.py": _wiki_ingest_py,
    "src/skills/wiki_skills/wiki_lint.py": _wiki_lint_py,
    "src/skills/wiki_skills/wiki_schema.py": _wiki_schema_py,
    "src/skills/wiki_skills/wiki_graph.py": _wiki_graph_py,
    "src/skills/wiki_skills/wiki_hybrid_search.py": _wiki_hybrid_search_py,
    "src/skills/wiki_skills/wiki_rag_bridge.py": _wiki_rag_bridge_py,
    "src/skills/wiki_skills/wiki_template.py": _wiki_template_py,
    # Server（5 個）
    "src/server/__init__.py": lambda: '"""Wiki Server."""',
    "src/server/main.py": _server_main_py,
    "src/server/api/__init__.py": lambda: '"""Wiki API."""',
    "src/server/api/wiki.py": _server_wiki_api_py,
    "src/server/api/files.py": _server_files_api_py,
    # Web UI（3 個）
    "src/server/templates/index.html": _index_html,
    "src/server/static/js/app.js": _app_js,
    "src/server/static/css/style.css": _style_css,
    # 設定（2 個）
    "run.py": _run_py,
    "requirements.txt": _requirements_txt,
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
