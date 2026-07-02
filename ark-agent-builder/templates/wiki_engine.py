"""Wiki 知識庫引擎。"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "knowledge" / "raw"
WIKI_DIR = BASE_DIR / "knowledge" / "wiki"
INDEX_PATH = BASE_DIR / "knowledge" / "index.md"
LOG_PATH = BASE_DIR / "knowledge" / "log.md"

REQUIRED_FIELDS = {"title", "type", "tags", "created", "updated"}


class WikiEngine:
    """最小 Wiki 引擎：query / ingest / lint。"""

    # ─── query ───────────────────────────────────────────

    async def query(self, q: str, *, use_rag: bool = False) -> dict:
        """全文搜尋 wiki/ 中的 md 檔案，Tier 2 時用 Gemini 合成答案。"""
        results = self._fulltext_search(q)
        if not use_rag or not results:
            return {"results": results, "answer": None}

        # Tier 2: Gemini RAG
        answer = await self._rag_answer(q, results)
        return {"results": results, "answer": answer}

    def _fulltext_search(self, q: str) -> list[dict]:
        """簡易全文搜尋，回傳匹配片段。"""
        hits: list[dict] = []
        if not WIKI_DIR.exists():
            return hits
        keywords = q.lower().split()
        for md in WIKI_DIR.rglob("*.md"):
            content = md.read_text(encoding="utf-8")
            lower_content = content.lower()
            if any(kw in lower_content for kw in keywords):
                title = self._extract_title(content)
                snippet = self._extract_snippet(content, keywords)
                hits.append({"file": md.name, "title": title, "snippet": snippet})
        return hits

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
        """使用 Gemini 合成答案。"""
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key or api_key == "your_gemini_api_key_here":
            return None

        context = "\n\n".join(
            f"[{r['title']}]\n{r['snippet']}" for r in results[:5]
        )
        prompt = (
            f"根據以下知識庫內容回答問題，回答使用繁體中文，並在結尾標註引用來源。\n\n"
            f"知識庫內容：\n{context}\n\n問題：{question}"
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
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

    def ingest(self, filename: str | None = None) -> list[str]:
        """將 raw/ 檔案匯入 wiki/，加上 frontmatter，更新 index.md。"""
        WIKI_DIR.mkdir(parents=True, exist_ok=True)
        files = [RAW_DIR / filename] if filename else list(RAW_DIR.glob("*.md"))
        ingested: list[str] = []

        for src in files:
            if not src.exists():
                continue
            content = src.read_text(encoding="utf-8")
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

            dest = WIKI_DIR / src.name
            dest.write_text(wiki_content, encoding="utf-8")
            ingested.append(src.name)

        self._update_index()
        self._append_log(ingested)
        return ingested

    def _update_index(self) -> None:
        """重建 index.md。"""
        lines = ["# Wiki 索引\n", "| 檔案 | 標題 |", "|------|------|"]
        for md in sorted(WIKI_DIR.rglob("*.md")):
            if md.name == ".gitkeep":
                continue
            content = md.read_text(encoding="utf-8")
            title = self._extract_title(content)
            lines.append(f"| {md.name} | {title} |")
        INDEX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _append_log(self, files: list[str]) -> None:
        """追加操作日誌。"""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"- [{ts}] ingest: {', '.join(files)}\n"
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(entry)

    # ─── lint ────────────────────────────────────────────

    def lint(self) -> list[dict]:
        """檢查 wiki/ 頁面的 frontmatter 完整性。"""
        issues: list[dict] = []
        if not WIKI_DIR.exists():
            return issues
        for md in WIKI_DIR.rglob("*.md"):
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
        if not content.startswith("---"):
            return list(REQUIRED_FIELDS)
        end = content.find("---", 3)
        if end == -1:
            return list(REQUIRED_FIELDS)
        fm_block = content[3:end]
        found = {m.group(1) for m in re.finditer(r"^(\w+):", fm_block, re.MULTILINE)}
        return sorted(REQUIRED_FIELDS - found)
