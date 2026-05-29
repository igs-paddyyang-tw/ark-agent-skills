#!/usr/bin/env python3
"""scaffold_scraper.py — 確定性產出爬蟲 + 新聞處理 Skills。

使用方式：
    python scaffold_scraper.py <project_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

NEWS_SCRAPER_PY = '''\
"""news_scraper — 網頁爬蟲 Skill（httpx + BeautifulSoup）。"""
from __future__ import annotations

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class NewsScraperParams(SkillParam):
    """news_scraper 輸入參數。"""
    url: str
    selector: str = "article"
    max_items: int = 10


class NewsScraperSkill(BaseSkill):
    """抓取網頁新聞內容。"""

    skill_id = "news_scraper"
    skill_type = SkillType.PYTHON
    description = "網頁爬蟲 — httpx + BeautifulSoup 抓取新聞"
    version = "1.0.0"
    input_schema = NewsScraperParams

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    async def execute(self, params: dict) -> SkillResult:
        try:
            import httpx
            from bs4 import BeautifulSoup

            p = NewsScraperParams(**params)
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                resp = await client.get(p.url, headers=self.HEADERS)

            if resp.status_code >= 400:
                return SkillResult(success=False, error=f"HTTP {resp.status_code}")

            soup = BeautifulSoup(resp.text, "html.parser")
            elements = soup.select(p.selector)[:p.max_items]

            items = []
            for el in elements:
                title_el = el.select_one("h2, h3, .title, a")
                items.append({
                    "title": title_el.get_text(strip=True) if title_el else "",
                    "text": el.get_text(strip=True)[:500],
                    "href": title_el.get("href", "") if title_el else "",
                })

            return SkillResult(success=True, data={
                "items": items, "count": len(items), "url": p.url,
            })
        except Exception as e:
            return SkillResult(success=False, error=f"爬蟲失敗: {e}")
'''

NEWS_PARSER_PY = '''\
"""news_parser — HTML 解析為 Markdown 素材。"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class NewsParserParams(SkillParam):
    """news_parser 輸入參數。"""
    items: list
    output_dir: str = "output/news/raw"
    source: str = ""


class NewsParserSkill(BaseSkill):
    """將爬蟲結果轉為 Markdown 素材檔。"""

    skill_id = "news_parser"
    skill_type = SkillType.PYTHON
    description = "將爬蟲 HTML 解析為 Markdown 素材"
    version = "1.0.0"
    input_schema = NewsParserParams

    async def execute(self, params: dict) -> SkillResult:
        try:
            p = NewsParserParams(**params)
            out_dir = Path(p.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)

            today = date.today().isoformat()
            files: list[str] = []

            for i, item in enumerate(p.items):
                title = item.get("title", f"article-{i}")
                slug = title[:30].replace(" ", "-").lower()
                filename = f"{today}-{slug}.md"
                content = (
                    f"---\\n"
                    f"source: {p.source}\\n"
                    f"date: {today}\\n"
                    f"url: {item.get('href', '')}\\n"
                    f"---\\n\\n"
                    f"# {title}\\n\\n"
                    f"{item.get('text', '')}\\n"
                )
                (out_dir / filename).write_text(content, encoding="utf-8")
                files.append(str(out_dir / filename))

            return SkillResult(success=True, data={"files": files, "count": len(files)})
        except Exception as e:
            return SkillResult(success=False, error=f"解析失敗: {e}")
'''

NEWS_STRUCTURER_PY = '''\
"""news_structurer — LLM 結構化新聞（呼叫 llm_cli）。"""
from __future__ import annotations

import json
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class NewsStructurerParams(SkillParam):
    """news_structurer 輸入參數。"""
    markdown_path: str = ""
    markdown_content: str = ""


class NewsStructurerSkill(BaseSkill):
    """用 LLM 將 Markdown 素材結構化為 JSON。"""

    skill_id = "news_structurer"
    skill_type = SkillType.PYTHON
    description = "LLM 結構化新聞（Markdown → JSON）"
    version = "1.0.0"
    input_schema = NewsStructurerParams

    PROMPT_TEMPLATE = (
        "你是科技日報編輯。將以下新聞轉為 JSON：\\n"
        "{{\\"topic\\": \\"分類\\", \\"title\\": \\"10字標題\\", "
        "\\"what\\": \\"100字摘要\\", \\"why\\": \\"80字影響\\", "
        "\\"summary\\": \\"一句話\\", \\"tags\\": [{{\\"icon\\": \\"emoji\\", \\"text\\": \\"8字\\"}}]}}\\n\\n"
        "新聞：\\n{content}\\n\\n只回傳 JSON。"
    )

    async def execute(self, params: dict) -> SkillResult:
        try:
            p = NewsStructurerParams(**params)
            content = p.markdown_content
            if not content and p.markdown_path:
                content = Path(p.markdown_path).read_text(encoding="utf-8")
            if not content:
                return SkillResult(success=False, error="無輸入內容")

            prompt = self.PROMPT_TEMPLATE.format(content=content[:3000])

            # 呼叫 llm_cli
            from src.skills.internal.llm_cli import LlmCliSkill
            llm = LlmCliSkill()
            result = await llm.execute({"prompt": prompt, "mode": "chat"})

            if not result.success:
                return SkillResult(success=False, error=f"LLM 失敗: {result.error}")

            # 嘗試解析 JSON
            import re
            output = result.data.get("output", "")
            m = re.search(r"\\{.*\\}", output, re.DOTALL)
            if m:
                structured = json.loads(m.group(0))
                return SkillResult(success=True, data=structured)

            return SkillResult(success=True, data={"raw": output})
        except Exception as e:
            return SkillResult(success=False, error=f"結構化失敗: {e}")
'''

NEWS_RENDERER_PY = '''\
"""news_renderer — Jinja2 套用 HTML 模板產出日報。"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class NewsRendererParams(SkillParam):
    """news_renderer 輸入參數。"""
    data: dict | list
    template: str = "templates/tech-daily.html"
    output_path: str = ""


class NewsRendererSkill(BaseSkill):
    """套用 Jinja2 模板產出 HTML 日報。"""

    skill_id = "news_renderer"
    skill_type = SkillType.PYTHON
    description = "Jinja2 套用 HTML 模板產出科技日報"
    version = "1.0.0"
    input_schema = NewsRendererParams

    async def execute(self, params: dict) -> SkillResult:
        try:
            from jinja2 import Template

            p = NewsRendererParams(**params)
            tmpl_path = Path(p.template)

            if not tmpl_path.exists():
                return SkillResult(success=False, error=f"模板不存在: {p.template}")

            template = Template(tmpl_path.read_text(encoding="utf-8"))
            today = date.today().strftime("%Y.%m.%d")

            # data 可以是單一 dict 或 list
            cards = p.data if isinstance(p.data, list) else [p.data]
            html = template.render(date=today, cards=cards)

            output = p.output_path or f"output/tech-daily-news/tech-daily-{date.today().isoformat()}.html"
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            Path(output).write_text(html, encoding="utf-8")

            return SkillResult(success=True, data={"path": output, "cards": len(cards)})
        except Exception as e:
            return SkillResult(success=False, error=f"渲染失敗: {e}")
'''

NEWS_SOURCES_YAML = '''\
# 新聞來源設定
sources:
  - name: "AI 焦點"
    url: "https://techcrunch.com/category/artificial-intelligence/"
    selector: "article.post-block"
    category: ai_focus

  - name: "開發工具"
    url: "https://www.infoq.com/news/"
    selector: ".news_type_block"
    category: dev_tools

schedule:
  cron: "0 8 * * *"
  timezone: "Asia/Taipei"
'''

FILES: dict[str, str] = {
    "src/skills/internal/news_scraper.py": NEWS_SCRAPER_PY,
    "src/skills/internal/news_parser.py": NEWS_PARSER_PY,
    "src/skills/internal/news_structurer.py": NEWS_STRUCTURER_PY,
    "src/skills/internal/news_renderer.py": NEWS_RENDERER_PY,
    "config/news_sources.yaml": NEWS_SOURCES_YAML,
}


def scaffold(project_dir: Path) -> list[str]:
    """產出爬蟲 + 新聞處理 Skills。"""
    created: list[str] = []
    for rel, content in FILES.items():
        full = project_dir / rel
        if full.exists():
            continue
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        created.append(rel)
    return created


def main() -> None:
    if len(sys.argv) < 2:
        print("使用方式: python scaffold_scraper.py <project_dir>")
        sys.exit(1)
    project_dir = Path(sys.argv[1])
    project_dir.mkdir(parents=True, exist_ok=True)
    created = scaffold(project_dir)
    if created:
        print(f"✅ 產出 {len(created)} 個檔案：")
        for f in created:
            print(f"   • {f}")
    else:
        print("✅ 所有檔案已存在。")


if __name__ == "__main__":
    main()
