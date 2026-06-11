"""news_scraper — 科技新聞抓取（RSS + HTML 多來源併發）。"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx
import yaml
from bs4 import BeautifulSoup

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

logger = logging.getLogger(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0 Safari/537.36"}


class NewsScraperParams(SkillParam):
    """news_scraper 輸入參數。"""
    url: str = ""
    config_path: str = ""
    max_items: int = 5


class NewsScraperSkill(BaseSkill):
    """科技新聞抓取 — RSS 優先 + HTML fallback，多來源併發。"""

    skill_id = "news_scraper"
    skill_type = SkillType.PYTHON
    description = "科技新聞抓取（RSS + HTML 多來源併發）"
    version = "2.0.0"
    input_schema = NewsScraperParams

    async def execute(self, params: dict) -> SkillResult:
        """執行新聞抓取。"""
        try:
            p = NewsScraperParams(**params)

            if p.config_path:
                return await self._from_config(p.config_path, p.max_items)
            if p.url:
                items = await self._fetch_html(p.url, "a", p.max_items)
                return SkillResult(success=True, data={"items": items, "count": len(items)})
            return SkillResult(success=False, error="需提供 url 或 config_path")
        except Exception as e:
            return SkillResult(success=False, error=f"抓取失敗: {e}")

    async def _from_config(self, config_path: str, max_items: int) -> SkillResult:
        """從設定檔批次抓取（asyncio.gather 併發，Semaphore 限流 3）。"""
        cfg_path = Path(config_path)
        if not cfg_path.exists():
            return SkillResult(success=False, error=f"設定檔不存在: {config_path}")

        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        sources = cfg.get("sources", [])
        max_per = cfg.get("output", {}).get("max_items_per_source", max_items)
        sem = asyncio.Semaphore(3)

        all_data: dict[str, list] = {}
        failed: list[str] = []

        async def _fetch_one(src: dict) -> None:
            async with sem:
                cat = src.get("category", "news")
                try:
                    src_type = src.get("type", "html")
                    if src_type == "rss":
                        items = await self._fetch_rss(src["url"], max_per)
                    else:
                        selector = src.get("selector", "a")
                        items = await self._fetch_html(src["url"], selector, max_per)
                    all_data.setdefault(cat, []).extend(items)
                except Exception as e:
                    failed.append(f"{src.get('name', src['url'])}: {e}")
                    logger.warning("抓取 %s 失敗: %s", src.get("name"), e)

        await asyncio.gather(*[_fetch_one(s) for s in sources])

        return SkillResult(success=True, data={
            "categories": all_data,
            "total": sum(len(v) for v in all_data.values()),
            "failed_sources": failed,
        })

    async def _fetch_rss(self, url: str, max_items: int) -> list[dict]:
        """解析 RSS feed。"""
        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser 未安裝，跳過 RSS: %s", url)
            return []

        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        items: list[dict] = []
        for entry in feed.entries[:max_items]:
            title = entry.get("title", "").strip()
            if not title or len(title) < 5:
                continue
            # 取描述
            desc = ""
            if entry.get("summary"):
                soup = BeautifulSoup(entry.summary, "html.parser")
                desc = soup.get_text(strip=True)[:200]
            items.append({
                "title": title,
                "url": entry.get("link", ""),
                "description": desc,
                "source": url,
            })
        return items

    async def _fetch_html(self, url: str, selector: str, max_items: int) -> list[dict]:
        """抓取 HTML 頁面，用 CSS selector 解析。"""
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        items: list[dict] = []

        for el in soup.select(selector)[:max_items * 3]:
            title = el.get_text(strip=True)
            link = el.get("href", "")

            # 過濾：標題太短 / 太長 / 導航文字
            if not title or len(title) < 8 or len(title) > 200:
                continue
            if any(kw in title.lower() for kw in ["menu", "log in", "sign up", "cookie"]):
                continue

            items.append({
                "title": title,
                "url": link,
                "description": "",
                "source": url,
            })
            if len(items) >= max_items:
                break

        return items
