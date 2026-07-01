"""web_search — DuckDuckGo 網頁搜尋。"""
from __future__ import annotations

import httpx
from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class WebSearchParams(SkillParam):
    query: str = ""
    max_results: int = 5


class WebSearchSkill(BaseSkill):
    skill_id = "web_search"
    skill_type = SkillType.PYTHON
    description = "網頁搜尋（DuckDuckGo），回傳前 N 筆結果"
    version = "1.0.0"
    input_schema = WebSearchParams

    async def execute(self, params: dict) -> SkillResult:
        try:
            p = WebSearchParams(**params)
            if not p.query:
                return SkillResult(success=False, error="需提供 query")
            results = await self._search(p.query, p.max_results)
            output = "\n\n".join(f"**{r['title']}**\n{r['url']}\n{r['snippet']}" for r in results)
            return SkillResult(success=True, data={"results": results, "output": output, "count": len(results)})
        except Exception as e:
            return SkillResult(success=False, error=f"搜尋失敗: {e}")

    async def _search(self, query: str, max_results: int) -> list:
        url = "https://html.duckduckgo.com/html/"
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15) as client:
            resp = await client.post(url, data={"q": query})
            resp.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for r in soup.select(".result")[:max_results]:
            title_el = r.select_one(".result__title a")
            snippet_el = r.select_one(".result__snippet")
            if title_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "url": title_el.get("href", ""),
                    "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                })
        return results
