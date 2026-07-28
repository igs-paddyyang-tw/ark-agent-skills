"""WikiEngine — 四層搜尋金字塔統一介面。"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from .indexer import load_metadata, rebuild_index

log = logging.getLogger("wiki.engine")

BASE_DIR = Path(".")
KNOWLEDGE_DIR = BASE_DIR / "knowledge"


class WikiEngine:
    """三層 Wiki 引擎：查詢時 私有 → shared → project scope。"""

    def __init__(self, agent_id: str | None = None):
        self.agent_id = agent_id

        # Agent 私有
        if agent_id:
            agent_name = agent_id if agent_id.endswith("-agent") else f"{agent_id}-agent"
            self.agent_wiki = BASE_DIR / "agents" / agent_name / "knowledge" / "wiki"
        else:
            self.agent_wiki = None

        # 共用
        self.global_wiki = KNOWLEDGE_DIR / "shared" / "wiki"

    async def query(self, q: str, *, use_rag: bool = False) -> dict:
        """四層金字塔查詢。

        Returns:
            {results: [{file, title, snippet, score, match_type}], answer: str|None, sources: []}
        """
        from .search.layer0_exact import search_exact, search_substring
        from .search.layer1_bm25 import is_available as bm25_ok, search_bm25, build_bm25_index
        from .search.layer2_tfidf import is_available as tfidf_ok, search_hybrid, build_tfidf_index
        from .search.layer3_rerank import is_available as rerank_ok, rerank

        metadata = load_metadata()
        if not metadata:
            return {"results": [], "answer": None, "sources": []}

        # 篩選 scope：Agent 私有 + shared
        if self.agent_id:
            agent_name = self.agent_id if self.agent_id.endswith("-agent") else f"{self.agent_id}-agent"
            scoped = [m for m in metadata if m["agent"] in (agent_name, "_shared", "_project")]
        else:
            scoped = metadata

        # ── Layer 0: 精確匹配 ──
        exact_hits = search_exact(q, scoped)
        if exact_hits and exact_hits[0].get("score", 0) >= 1.0:
            results = self._format_results(exact_hits[:5])
            return {"results": results, "answer": None, "sources": []}

        # ── Layer 1: BM25 ──
        bm25_hits: list[dict] = []
        if bm25_ok():
            bm25_hits = search_bm25(q, scoped, top_k=10)
        else:
            # 嘗試現場建索引
            build_bm25_index(scoped)
            bm25_hits = search_bm25(q, scoped, top_k=10)

        # ── Layer 2: TF-IDF + RRF（可選）──
        hybrid_hits = bm25_hits
        if tfidf_ok() and bm25_hits:
            hybrid_hits = search_hybrid(q, bm25_hits, scoped, top_k=10)
        elif tfidf_ok():
            build_tfidf_index(scoped)
            hybrid_hits = search_hybrid(q, bm25_hits, scoped, top_k=10)

        # ── Layer 0 兜底 ──
        if not hybrid_hits and not exact_hits:
            hybrid_hits = search_substring(q, scoped, max_results=10)

        # 合併去重
        all_hits = (exact_hits or []) + hybrid_hits
        seen: set[str] = set()
        deduped: list[dict] = []
        for h in all_hits:
            if h["path"] not in seen:
                seen.add(h["path"])
                deduped.append(h)

        # ── Layer 3: Rerank（可選）──
        results = self._format_results(deduped[:10])
        if rerank_ok() and len(results) > 3:
            results = await rerank(q, results, top_k=5)

        return {"results": results, "answer": None, "sources": []}

    def _format_results(self, hits: list[dict]) -> list[dict]:
        """格式化為前端友善格式。"""
        return [
            {
                "file": h["path"],
                "title": h["title"],
                "snippet": h.get("body_preview", "")[:200],
                "score": h.get("score", 0),
                "match_type": h.get("match_type", ""),
            }
            for h in hits
        ]

    def _resolve_path(self, relative_path: str) -> Path | None:
        """解析相對路徑到實際 wiki 檔案。"""
        # 先查 shared
        p = self.global_wiki / relative_path
        if p.exists():
            return p
        # 再查 agent private
        if self.agent_wiki:
            p = self.agent_wiki / relative_path
            if p.exists():
                return p
        return None

    # ─── ingest ──────────────────────────────────────────

    def ingest(self, scope: str = "global", filename: str | None = None) -> list[str]:
        """將 raw/ 匯入 wiki/。"""
        if scope == "private" and self.agent_id:
            agent_name = self.agent_id if self.agent_id.endswith("-agent") else f"{self.agent_id}-agent"
            raw_dir = BASE_DIR / "agents" / agent_name / "knowledge" / "raw"
            wiki_dir = BASE_DIR / "agents" / agent_name / "knowledge" / "wiki"
        else:
            raw_dir = KNOWLEDGE_DIR / "shared" / "raw"
            wiki_dir = self.global_wiki

        wiki_dir.mkdir(parents=True, exist_ok=True)

        if filename:
            files = [raw_dir / filename]
        else:
            files = list(raw_dir.glob("*.md"))
            for sub in raw_dir.iterdir():
                if sub.is_dir() and not sub.name.startswith("."):
                    files.extend(sub.glob("*.md"))

        ingested: list[str] = []
        for src in files:
            if not src.exists():
                continue
            rel = src.relative_to(raw_dir)
            dest = wiki_dir / rel
            if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
                continue
            content = src.read_text(encoding="utf-8")
            if content.startswith("\ufeff"):
                content = content[1:]
            if not content.startswith("---"):
                title = self._extract_title(content)
                today = datetime.now().strftime("%Y-%m-%d")
                content = f'---\ntitle: "{title}"\ntype: concept\ntags: [wiki]\ncreated: {today}\nupdated: {today}\n---\n\n{content}'
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            ingested.append(str(rel))

        # 重建索引
        if ingested:
            rebuild_index()

        return ingested

    @staticmethod
    def _extract_title(content: str) -> str:
        m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        return m.group(1) if m else "Untitled"
