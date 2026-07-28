"""Wiki 知識庫引擎 — 兩層查詢（私有 + 全域）。"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
GLOBAL_SHARED = KNOWLEDGE_DIR / "shared"
INDEX_PATH = GLOBAL_SHARED / "index.md"
LOG_PATH = GLOBAL_SHARED / "log.md"

REQUIRED_FIELDS = {"title", "type", "tags", "created", "updated"}


class WikiEngine:
    """三層 Wiki 引擎：查詢時 私有 → shared → 其他 scope。"""

    def __init__(self, agent_id: str | None = None):
        self.agent_id = agent_id

        # Layer 1: Agent 私有
        if agent_id:
            agent_name = agent_id if agent_id.endswith("-agent") else f"{agent_id}-agent"
            self.agent_raw = BASE_DIR / "agents" / agent_name / "knowledge" / "raw"
            self.agent_wiki = BASE_DIR / "agents" / agent_name / "knowledge" / "wiki"
        else:
            self.agent_raw = None
            self.agent_wiki = None

        # Layer 2: 共用 (knowledge/shared/)
        self.global_raw = GLOBAL_SHARED / "raw"
        self.global_wiki = GLOBAL_SHARED / "wiki"

        # Layer 3: 其他 scope（掃 knowledge/ 下非 shared 的目錄）
        self.project_wikis: list[tuple[str, Path]] = []
        if KNOWLEDGE_DIR.exists():
            for d in sorted(KNOWLEDGE_DIR.iterdir()):
                if d.is_dir() and d.name not in ("shared", ".index") and not d.name.startswith("."):
                    wiki_dir = d / "wiki"
                    if wiki_dir.exists():
                        self.project_wikis.append((d.name, wiki_dir))

    # ─── query ───────────────────────────────────────────

    async def query(self, q: str, *, use_rag: bool = False) -> dict:
        """四層金字塔查詢：metadata → BM25 → hybrid → rerank。

        介面不變：回傳 {results, answer, sources}。
        """
        from src.wiki.indexer import load_metadata
        from src.wiki.search.layer0_exact import search_exact, search_substring, extract_summary
        from src.wiki.search.layer1_bm25 import is_available as bm25_available, search_bm25
        from src.wiki.search.layer2_hybrid import search_hybrid
        from src.wiki.search.layer3_rerank import is_available as rerank_available, rerank

        metadata = load_metadata()
        keywords = self._tokenize(q)

        # ── Layer 0: 精確匹配 ──
        exact_hits = search_exact(q, metadata) if metadata else []
        if exact_hits and exact_hits[0].get("score", 0) >= 1.0:
            # 完全命中，直接回
            results = self._format_hits(exact_hits, keywords)
            if not use_rag:
                return {"results": results, "answer": None, "sources": []}
            answer = await self._rag_answer(q, results)
            return {"results": results, "answer": answer, "sources": [r["file"] for r in results[:5]]}

        # ── Layer 1: BM25 ──
        bm25_hits = []
        if bm25_available() and metadata:
            bm25_hits = search_bm25(q, metadata, top_k=10)

        # ── Layer 2: 三路混合（BM25 + 語意 + 圖譜）→ RRF ──
        if bm25_hits and metadata:
            hybrid_hits = search_hybrid(q, bm25_hits, metadata, top_k=10)
        else:
            hybrid_hits = bm25_hits

        # ── Layer 0 兜底：如果上面都沒結果 ──
        if not hybrid_hits and not exact_hits:
            if metadata:
                hybrid_hits = search_substring(q, metadata, max_results=10)
            else:
                # 無 metadata（索引未建），走舊邏輯
                private_results = self._search_dir(self.agent_wiki, q) if self.agent_wiki else []
                global_results = self._search_dir(self.global_wiki, q)
                for r in private_results:
                    r["scope"] = "private"
                for r in global_results:
                    r["scope"] = "global"
                results = private_results + global_results
                if not use_rag or not results:
                    return {"results": results, "answer": None, "sources": []}
                answer = await self._rag_answer(q, results)
                return {"results": results, "answer": answer, "sources": [r["file"] for r in results[:5]]}

        # 合併：exact_hits（低分的） + hybrid_hits，去重
        all_hits = exact_hits + hybrid_hits
        seen_paths = set()
        deduped = []
        for h in all_hits:
            if h["path"] not in seen_paths:
                seen_paths.add(h["path"])
                deduped.append(h)

        # ── Layer 3: Rerank（選配）──
        results = self._format_hits(deduped, keywords)
        if rerank_available() and len(results) > 3:
            results = await rerank(q, results, top_k=5)

        if not use_rag or not results:
            return {"results": results, "answer": None, "sources": []}

        answer = await self._rag_answer(q, results)
        sources = [r["file"] for r in results[:5]]
        return {"results": results, "answer": answer, "sources": sources}

    def _format_hits(self, hits: list[dict], keywords: list[str]) -> list[dict]:
        """把 search layer 的 hits 格式化為前端可用的結果。"""
        from src.wiki.search.layer0_exact import extract_summary

        results = []
        for h in hits[:10]:
            wiki_path = self.global_wiki / h["path"]
            if not wiki_path.exists() and self.agent_wiki:
                wiki_path = self.agent_wiki / h["path"]

            summary = extract_summary(wiki_path, keywords) if wiki_path.exists() else ""
            results.append({
                "file": h["path"],
                "title": h["title"],
                "snippet": summary,
                "score": h.get("score", 0),
                "match_type": h.get("match_type", ""),
            })
        return results

    def _search_dir(self, wiki_dir: Path | None, q: str) -> list[dict]:
        """搜尋指定 wiki 目錄。"""
        hits: list[dict] = []
        if not wiki_dir or not wiki_dir.exists():
            return hits
        keywords = self._tokenize(q)
        for md in wiki_dir.rglob("*.md"):
            if md.name == ".gitkeep":
                continue
            content = md.read_text(encoding="utf-8")
            lower_content = content.lower()
            if any(kw in lower_content for kw in keywords):
                title = self._extract_title(content)
                snippet = self._extract_snippet(content, keywords)
                hits.append({"file": md.name, "title": title, "snippet": snippet})
        return hits

    @staticmethod
    def _tokenize(q: str) -> list[str]:
        """分詞：空格分割 + 中文每 2 字一組（bigram）。"""
        tokens: list[str] = []
        for part in q.lower().split():
            tokens.append(part)
            # 中文 bigram
            cjk_chars = [c for c in part if '\u4e00' <= c <= '\u9fff']
            if len(cjk_chars) >= 2:
                for i in range(len(cjk_chars) - 1):
                    tokens.append(cjk_chars[i] + cjk_chars[i + 1])
        return list(set(tokens))

    @staticmethod
    def _extract_title(content: str) -> str:
        m = re.search(r"^title:\s*[\"']?(.+?)[\"']?\s*$", content, re.MULTILINE)
        if m:
            return m.group(1)
        m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        return m.group(1) if m else "Untitled"

    @staticmethod
    def _extract_snippet(content: str, keywords: list[str], max_len: int = 200) -> str:
        lines = content.split("\n")
        for line in lines:
            if any(kw in line.lower() for kw in keywords):
                return line[:max_len]
        return lines[0][:max_len] if lines else ""

    async def _rag_answer(self, question: str, results: list[dict]) -> str | None:
        """使用 Gemini 合成答案，傳入完整文件內容。"""
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key or api_key == "your_gemini_api_key_here":
            return None

        # 讀取完整 wiki 檔案（每篇限 2000 字，最多 5 篇）
        context_parts = []
        for r in results[:5]:
            wiki_path = self.global_wiki / r["file"] if self.global_wiki else None
            if not wiki_path or not wiki_path.exists():
                # 試私有
                if self.agent_wiki:
                    wiki_path = self.agent_wiki / r["file"]
            if wiki_path and wiki_path.exists():
                content = wiki_path.read_text(encoding="utf-8")[:2000]
                context_parts.append(f"[{r['title']}]\n{content}")
            else:
                context_parts.append(f"[{r['title']}]\n{r['snippet']}")
        
        context = "\n\n---\n\n".join(context_parts)
        prompt = (
            f"根據以下知識庫內容回答問題，回答使用繁體中文。\n"
            f"在回答結尾用「📚 參考：」列出引用的來源檔案名。\n"
            f"如果知識庫沒有相關內容，請誠實說「目前知識庫沒有這方面的資料」。\n\n"
            f"知識庫內容：\n{context}\n\n問題：{question}"
        )

        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                return None
            data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return None

    # ─── ingest ──────────────────────────────────────────

    def ingest(self, scope: str = "global", filename: str | None = None) -> list[str]:
        """將 raw/ 匯入 wiki/。只匯入新的或有更新的（比對修改時間）。

        - 只掃 raw/ 下最多 2 層（避免吞入別人的專案）
        - wiki/ 已有且不比 raw 舊 → 跳過
        - raw 比 wiki 新 → 更新
        """
        if scope == "private" and self.agent_raw and self.agent_wiki:
            raw_dir = self.agent_raw
            wiki_dir = self.agent_wiki
        else:
            raw_dir = self.global_raw
            wiki_dir = self.global_wiki

        wiki_dir.mkdir(parents=True, exist_ok=True)

        # 收集檔案（限制深度 2 層：raw/*.md + raw/一層子資料夾/*.md）
        if filename:
            files = [raw_dir / filename]
        else:
            files = list(raw_dir.glob("*.md"))  # 第一層
            for sub in raw_dir.iterdir():
                if sub.is_dir() and not sub.name.startswith("."):
                    files.extend(sub.glob("*.md"))  # 第二層

        ingested: list[str] = []

        for src in files:
            if not src.exists():
                continue

            # 保持相對路徑
            rel_path = src.relative_to(raw_dir)
            dest = wiki_dir / rel_path

            # 比對修改時間：wiki 版本不比 raw 舊 → 跳過
            if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
                continue

            content = src.read_text(encoding="utf-8")
            # Strip BOM
            if content.startswith("\ufeff"):
                content = content[1:]
            if content.startswith("---"):
                wiki_content = content
            else:
                title = self._extract_title(content)
                today = datetime.now().strftime("%Y-%m-%d")
                frontmatter = (
                    f"---\ntitle: \"{title}\"\n"
                    f"type: concept\ntags: [wiki]\n"
                    f"created: {today}\nupdated: {today}\n---\n\n"
                )
                wiki_content = frontmatter + content

            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(wiki_content, encoding="utf-8")
            ingested.append(str(rel_path))

        if scope == "global":
            self._update_index()
        self._append_log(ingested, scope)

        # 觸發搜尋索引重建
        if ingested:
            try:
                from src.wiki.indexer import rebuild_index
                rebuild_index()
            except Exception as e:
                import logging
                logging.getLogger("wiki.engine").warning("Index rebuild failed: %s", e)

        return ingested

    def _update_index(self) -> None:
        """重建全域 index.md（帶相對路徑 + 按資料夾分類）。"""
        lines = ["# Wiki 索引\n"]
        
        # 收集所有檔案（帶相對路徑）
        entries: dict[str, list] = {}  # folder -> [(rel_path, title)]
        for md in sorted(GLOBAL_WIKI.rglob("*.md")):
            if md.name in (".gitkeep", "index.md", "log.md", "schema.md"):
                continue
            rel = md.relative_to(GLOBAL_WIKI)
            content = md.read_text(encoding="utf-8")
            title = self._extract_title(content)
            folder = str(rel.parent) if rel.parent != Path(".") else "(根層)"
            if folder not in entries:
                entries[folder] = []
            entries[folder].append((str(rel), title))
        
        # 按資料夾分類輸出
        for folder in sorted(entries.keys()):
            if folder == "(根層)":
                lines.append(f"\n## 📄 根層\n")
            else:
                lines.append(f"\n## 📁 {folder}\n")
            lines.append("| 檔案 | 標題 |")
            lines.append("|------|------|")
            for rel_path, title in entries[folder]:
                lines.append(f"| {rel_path} | {title} |")
        
        INDEX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _append_log(self, files: list[str], scope: str = "global") -> None:
        """追加操作日誌（只在有實際變動時）。"""
        if not files:
            return  # 沒有變動不追加
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        agent_tag = f" [{self.agent_id}]" if self.agent_id and scope == "private" else ""
        entry = f"- [{ts}]{agent_tag} ingest ({scope}): {len(files)} 篇 — {', '.join(files[:5])}"
        if len(files) > 5:
            entry += f" ...等共 {len(files)} 篇"
        entry += "\n"
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(entry)

    # ─── lint ────────────────────────────────────────────

    def lint(self, scope: str = "global") -> list[dict]:
        """檢查 wiki/ 頁面的 frontmatter 完整性。"""
        if scope == "private" and self.agent_wiki:
            wiki_dir = self.agent_wiki
        else:
            wiki_dir = self.global_wiki

        issues: list[dict] = []
        if not wiki_dir.exists():
            return issues
        for md in wiki_dir.rglob("*.md"):
            if md.name == ".gitkeep":
                continue
            content = md.read_text(encoding="utf-8")
            missing = self._check_frontmatter(content)
            if missing:
                issues.append({"file": md.name, "missing_fields": missing})
        return issues

    @staticmethod
    def _check_frontmatter(content: str) -> list[str]:
        """檢查必要 frontmatter 欄位。"""
        # Strip UTF-8 BOM（Windows PowerShell 產生的）
        if content.startswith("\ufeff"):
            content = content[1:]
        if not content.startswith("---"):
            return list(REQUIRED_FIELDS)
        # 找行首的 --- 作為 frontmatter 結束標記（避免 URL 中的 --- 誤判）
        m = re.search(r"\r?\n---\s*(?:\r?\n|$)", content[3:])
        if not m:
            return list(REQUIRED_FIELDS)
        fm_block = content[3:3 + m.start()]
        found = {mg.group(1) for mg in re.finditer(r"^(\w+):", fm_block, re.MULTILINE)}
        return sorted(REQUIRED_FIELDS - found)
