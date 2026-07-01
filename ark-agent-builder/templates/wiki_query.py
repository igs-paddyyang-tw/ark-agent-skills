"""wiki_query — 知識庫搜尋 + LLM 合成回答。"""
from __future__ import annotations

import re
from pathlib import Path
from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

_WIKI_DIR = Path("knowledge")


class WikiQueryParams(SkillParam):
    query: str = ""
    action: str = "search"  # search / list
    top_k: int = 3


class WikiQuerySkill(BaseSkill):
    skill_id = "wiki_query"
    skill_type = SkillType.PYTHON
    description = "知識庫搜尋（keyword 匹配 + LLM 合成回答）"
    version = "1.0.0"
    input_schema = WikiQueryParams

    async def execute(self, params: dict) -> SkillResult:
        try:
            p = WikiQueryParams(**params)
            if p.action == "list":
                return self._list_pages()
            if not p.query:
                return SkillResult(success=False, error="需提供 query")
            return await self._search(p.query, p.top_k)
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    def _list_pages(self) -> SkillResult:
        pages = []
        for f in sorted(_WIKI_DIR.rglob("*.md")):
            rel = f.relative_to(_WIKI_DIR)
            title = f.stem.replace("-", " ").replace("_", " ")
            pages.append(f"• {rel}")
        output = f"📚 知識庫（{len(pages)} 頁）\n\n" + "\n".join(pages)
        return SkillResult(success=True, data={"output": output, "count": len(pages)})

    async def _search(self, query: str, top_k: int) -> SkillResult:
        keywords = [w.lower() for w in re.split(r'\s+', query) if len(w) > 1]
        scored = []
        for f in _WIKI_DIR.rglob("*.md"):
            content = f.read_text(encoding="utf-8", errors="ignore")
            content_lower = content.lower()
            score = sum(content_lower.count(kw) for kw in keywords)
            if score > 0:
                # 取包含關鍵字的段落
                snippet = self._extract_snippet(content, keywords)
                scored.append({"path": str(f.relative_to(_WIKI_DIR)), "score": score, "snippet": snippet})

        scored.sort(key=lambda x: x["score"], reverse=True)
        top = scored[:top_k]

        if not top:
            return SkillResult(success=True, data={"output": f"📚 找不到「{query}」相關內容", "results": []})

        # 嘗試 Gemini 合成
        context_text = "\n\n".join(f"[{r['path']}]\n{r['snippet']}" for r in top)
        answer = await self._synthesize(query, context_text)

        sources = "\n".join(f"• {r['path']}" for r in top)
        output = f"📚 {answer}\n\n---\n📎 來源：\n{sources}"
        return SkillResult(success=True, data={"output": output, "results": top})

    def _extract_snippet(self, content: str, keywords: list, max_len: int = 500) -> str:
        lines = content.splitlines()
        best_start = 0
        best_score = 0
        for i, line in enumerate(lines):
            line_lower = line.lower()
            score = sum(1 for kw in keywords if kw in line_lower)
            if score > best_score:
                best_score = score
                best_start = i
        # 取前後 5 行
        start = max(0, best_start - 2)
        end = min(len(lines), best_start + 5)
        snippet = "\n".join(lines[start:end])
        return snippet[:max_len]

    async def _synthesize(self, query: str, context: str) -> str:
        try:
            from src.llm.gemini_chat import chat, is_available
            if not is_available():
                return context[:800]
            prompt = (
                f"根據以下知識庫資料，用繁體中文簡潔回答問題。\n"
                f"問題：{query}\n\n資料：\n{context[:3000]}"
            )
            return await chat(prompt)
        except Exception:
            return context[:800]
