"""scaffold_scraper.py — 確定性產出新聞爬蟲 Skills + 設定檔。

用法：python .kiro/skills/ark-web-scraper/scripts/scaffold_scraper.py [project_dir]
產出：
  src/skills/internal/news_scraper.py    — 網頁爬蟲（httpx + BeautifulSoup + Playwright fallback）
  src/skills/internal/news_parser.py     — HTML → Markdown 素材
  src/skills/internal/news_structurer.py — LLM 結構化 JSON
  src/skills/internal/news_renderer.py   — Markdown/JSON → HTML 日報
  config/news_sources.yaml               — 新聞來源設定
"""
import sys
import textwrap
from pathlib import Path


def _write(project_dir: Path, rel_path: str, content: str) -> bool:
    """寫入檔案（已存在則跳過，冪等）。回傳是否新建。"""
    target = project_dir / rel_path
    if target.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(content), encoding="utf-8")
    return True


def scaffold(project_dir: Path) -> list[str]:
    """產出新聞爬蟲 Skills。回傳已建立的檔案路徑列表。"""
    created: list[str] = []

    def emit(rel_path: str, content: str) -> None:
        if _write(project_dir, rel_path, content):
            created.append(rel_path)

    # ── 1. news_scraper.py ──
    emit("src/skills/internal/news_scraper.py", '''\
        """news_scraper — 網頁爬蟲（httpx + BeautifulSoup，可選 Playwright JS 渲染）。"""

        import logging

        import httpx
        from bs4 import BeautifulSoup
        import yaml
        from pathlib import Path

        from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

        logger = logging.getLogger(__name__)

        HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        }


        def _playwright_available() -> bool:
            try:
                from playwright.async_api import async_playwright  # noqa: F401
                return True
            except ImportError:
                return False


        class NewsScraperParams(SkillParam):
            """news_scraper 輸入參數。"""
            url: str = ""
            selector: str = ""
            category: str = "news"
            config_path: str = ""
            max_items: int = 10


        class NewsScraperSkill(BaseSkill):
            """網頁爬蟲 — 抓取指定網址內容。"""

            skill_id = "news_scraper"
            skill_type = SkillType.PYTHON
            description = "網頁爬蟲 — httpx + BeautifulSoup + Playwright fallback"
            version = "1.0.0"
            input_schema = NewsScraperParams

            async def execute(self, params: dict) -> SkillResult:
                try:
                    p = NewsScraperParams(**params)
                    if p.config_path:
                        return await self._scrape_from_config(p.config_path)
                    if not p.url:
                        return SkillResult(success=False, error="需提供 url 或 config_path")
                    items = await self._scrape_url(p.url, p.selector, p.category, p.max_items)
                    return SkillResult(success=True, data={
                        "items": items, "count": len(items),
                        "source": p.url, "category": p.category,
                    })
                except Exception as e:
                    return SkillResult(success=False, error=f"抓取失敗: {e}")

            async def _scrape_from_config(self, config_path: str) -> SkillResult:
                """從 YAML 設定檔批次抓取。"""
                cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
                max_items = cfg.get("output", {}).get("max_items_per_source", 10)
                all_data: dict[str, list] = {}
                for source in cfg.get("sources", []):
                    try:
                        items = await self._scrape_url(
                            source["url"], source.get("selector", ""),
                            source["category"], max_items,
                        )
                        all_data.setdefault(source["category"], []).extend(items)
                    except Exception as e:
                        logger.warning("抓取 %s 失敗: %s", source.get("name", ""), e)
                return SkillResult(success=True, data={
                    "categories": all_data,
                    "total": sum(len(v) for v in all_data.values()),
                })

            async def _scrape_url(self, url: str, selector: str, category: str, max_items: int) -> list[dict]:
                """抓取單一網址（Playwright 優先，httpx fallback）。"""
                html = ""
                if _playwright_available():
                    try:
                        html = await self._fetch_playwright(url)
                    except Exception as e:
                        logger.warning("Playwright 失敗，fallback httpx: %s", e)
                if not html:
                    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30) as client:
                        resp = await client.get(url)
                        resp.raise_for_status()
                        html = resp.text

                soup = BeautifulSoup(html, "html.parser")
                items: list[dict] = []
                if selector:
                    for sel in selector.split(","):
                        for el in soup.select(sel.strip())[:max_items]:
                            item = self._parse_element(el, category)
                            if item:
                                items.append(item)
                        if items:
                            break
                if not items:
                    items = self._fallback_parse(soup, category, max_items)
                return items[:max_items]

            async def _fetch_playwright(self, url: str) -> str:
                from playwright.async_api import async_playwright
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    html = await page.content()
                    await browser.close()
                return html

            def _parse_element(self, el, category: str) -> dict | None:
                title, link, img, desc = "", "", "", ""
                title_el = el.select_one("h2, h3, h4, .title, .name")
                if title_el:
                    title = title_el.get_text(strip=True)
                    a = title_el.select_one("a")
                    if a:
                        link = a.get("href", "")
                if not title and el.name == "a":
                    title = el.get_text(strip=True)
                    link = el.get("href", "")
                if not link:
                    a = el.select_one("a")
                    if a:
                        link = a.get("href", "")
                        if not title:
                            title = a.get_text(strip=True)
                img_el = el.select_one("img")
                if img_el:
                    img = img_el.get("src", "") or img_el.get("data-src", "")
                desc_el = el.select_one("p, .description, .snippet")
                if desc_el:
                    desc = desc_el.get_text(strip=True)[:200]
                if not title or len(title) < 15:
                    return None
                return {"title": title, "link": link, "image": img, "description": desc, "category": category}

            def _fallback_parse(self, soup: BeautifulSoup, category: str, max_items: int) -> list[dict]:
                items = []
                for a in soup.select("a[href]")[:50]:
                    text = a.get_text(strip=True)
                    if 10 < len(text) < 200:
                        items.append({"title": text, "link": a.get("href", ""), "image": "", "description": "", "category": category})
                    if len(items) >= max_items:
                        break
                return items
    ''')

    # ── 2. news_parser.py ──
    emit("src/skills/internal/news_parser.py", '''\
        """news_parser — 將爬蟲結果解析為 Markdown 素材。"""
        from __future__ import annotations

        import re
        from datetime import datetime
        from pathlib import Path

        from bs4 import BeautifulSoup

        from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


        class NewsParserParams(SkillParam):
            """news_parser 輸入參數。"""
            data: dict = {}
            html_content: str = ""
            html_path: str = ""
            output_dir: str = "output/news/raw"


        class NewsParserSkill(BaseSkill):
            """將爬蟲結果解析為 Markdown 素材檔案。"""

            skill_id = "news_parser"
            skill_type = SkillType.PYTHON
            description = "將爬蟲結果解析為 Markdown 素材"
            version = "1.0.0"
            input_schema = NewsParserParams

            async def execute(self, params: dict) -> SkillResult:
                try:
                    p = NewsParserParams(**params)
                    out_dir = Path(p.output_dir)
                    out_dir.mkdir(parents=True, exist_ok=True)

                    if p.html_content or p.html_path:
                        html = p.html_content
                        if not html and p.html_path:
                            path = Path(p.html_path)
                            if not path.exists():
                                return SkillResult(success=False, error=f"檔案不存在: {p.html_path}")
                            html = path.read_text(encoding="utf-8")
                        items = self._parse_html(html)
                        categories = {"parsed": items}
                    else:
                        categories = p.data.get("categories", {})
                        if "items" in p.data and "categories" not in p.data:
                            categories = {p.data.get("category", "news"): p.data["items"]}

                    date_str = datetime.now().strftime("%Y-%m-%d")
                    files: list[str] = []
                    for cat, items in categories.items():
                        md = self._render_md(cat, items, date_str)
                        path = out_dir / f"{date_str}-{cat}.md"
                        path.write_text(md, encoding="utf-8")
                        files.append(str(path))

                    return SkillResult(success=True, data={
                        "files": files,
                        "count": sum(len(v) for v in categories.values()),
                    })
                except Exception as e:
                    return SkillResult(success=False, error=f"解析失敗: {e}")

            def _parse_html(self, html: str) -> list[dict]:
                soup = BeautifulSoup(html, "html.parser")
                items = []
                for a in soup.select("article a[href], h2 a[href], h3 a[href]"):
                    title = a.get_text(strip=True)
                    if len(title) > 10:
                        items.append({"title": title, "link": a.get("href", ""), "description": ""})
                if not items:
                    for a in soup.select("a[href]"):
                        title = a.get_text(strip=True)
                        if 10 < len(title) < 200:
                            items.append({"title": title, "link": a.get("href", ""), "description": ""})
                        if len(items) >= 20:
                            break
                return items

            def _render_md(self, category: str, items: list[dict], date: str) -> str:
                lines = [
                    "---",
                    f'source: "{items[0].get("link", "").split("/")[2] if items and items[0].get("link") else ""}"',
                    f"date: {date}",
                    f"category: {category}",
                    f"count: {len(items)}",
                    "---", "",
                    f"# {category} — {date}", "",
                ]
                for i, item in enumerate(items, 1):
                    title = item.get("title", "無標題")
                    link = item.get("link", "")
                    desc = item.get("description", "")
                    lines.append(f"## {i}. [{title}]({link})" if link else f"## {i}. {title}")
                    if desc:
                        lines.append(f"\\n{desc}")
                    lines.append("")
                return "\\n".join(lines)
    ''')

    # ── 3. news_structurer.py ──
    emit("src/skills/internal/news_structurer.py", '''\
        """news_structurer — 呼叫 LLM 將 Markdown 素材結構化為 JSON。"""
        from __future__ import annotations

        import json
        import re
        from pathlib import Path

        from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

        STRUCTURE_PROMPT = """你是新聞編輯。將以下 Markdown 新聞素材整理為結構化 JSON。
        每則新聞包含：topic, title, what, why, summary, tags[]。
        只回傳 JSON 陣列，不要解釋。

        素材：
        {content}
        """


        class NewsStructurerParams(SkillParam):
            """news_structurer 輸入參數。"""
            markdown_path: str = ""
            markdown_content: str = ""


        class NewsStructurerSkill(BaseSkill):
            """呼叫 LLM 將 Markdown 新聞素材結構化為 JSON。"""

            skill_id = "news_structurer"
            skill_type = SkillType.PYTHON
            description = "LLM 結構化新聞素材為 JSON"
            version = "1.0.0"
            input_schema = NewsStructurerParams

            async def execute(self, params: dict) -> SkillResult:
                try:
                    p = NewsStructurerParams(**params)
                    content = p.markdown_content
                    if not content and p.markdown_path:
                        path = Path(p.markdown_path)
                        if not path.exists():
                            return SkillResult(success=False, error=f"檔案不存在: {p.markdown_path}")
                        content = path.read_text(encoding="utf-8")
                    if not content:
                        return SkillResult(success=False, error="需提供 markdown_path 或 markdown_content")
                    structured = await self._call_llm(content)
                    return SkillResult(success=True, data={"articles": structured, "count": len(structured)})
                except Exception as e:
                    return SkillResult(success=False, error=f"結構化失敗: {e}")

            async def _call_llm(self, content: str) -> list[dict]:
                from src.skills.internal.llm_cli import LlmCliSkill
                llm = LlmCliSkill()
                prompt = STRUCTURE_PROMPT.format(content=content[:3000])
                result = await llm.execute({"prompt": prompt, "mode": "chat"})
                if result.success:
                    parsed = self._parse_json(result.data.get("output", ""))
                    if parsed:
                        return parsed
                return self._keyword_fallback(content)

            def _keyword_fallback(self, content: str) -> list[dict]:
                articles = []
                for match in re.finditer(r"^##\\s+\\d+\\.\\s+\\[?(.+?)\\]?(?:\\((.+?)\\))?$", content, re.MULTILINE):
                    title = match.group(1).rstrip("]")
                    articles.append({"topic": "news", "title": title, "what": title, "why": "", "summary": title[:30], "tags": []})
                return articles

            def _parse_json(self, text: str) -> list[dict]:
                match = re.search(r"\\[.*\\]", text, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except json.JSONDecodeError:
                        pass
                return []
    ''')

    # ── 4. news_renderer.py ──
    emit("src/skills/internal/news_renderer.py", '''\
        """news_renderer — Jinja2 套模板產出 HTML 日報。"""

        from datetime import datetime
        from pathlib import Path

        from jinja2 import Template

        from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

        HTML_TEMPLATE = """<!DOCTYPE html>
        <html lang="zh-TW"><head><meta charset="UTF-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>日報 — {{ date }}</title>
        <style>
        body{background:#0f172a;color:#e2e8f0;font-family:sans-serif;padding:20px}
        h1{color:#22d3ee;text-align:center}h2{color:#38bdf8;border-bottom:1px solid #334155;padding-bottom:8px;margin-top:25px}
        .card{background:#1e293b;border-radius:8px;padding:12px 16px;margin-bottom:10px;border-left:3px solid #22d3ee}
        .card a{color:#22d3ee;text-decoration:none}.card a:hover{text-decoration:underline}
        .desc{color:#94a3b8;font-size:0.9em;margin-top:4px}.footer{text-align:center;color:#475569;margin-top:40px;font-size:0.8em}
        </style></head><body>
        <h1>日報 — {{ date }}</h1>
        {% for cat, items in categories.items() %}
        <h2>{{ cat }}</h2>
        {% for item in items %}
        <div class="card">
        {% if item.link %}<a href="{{ item.link }}" target="_blank">{{ item.title }}</a>{% else %}{{ item.title }}{% endif %}
        {% if item.description %}<div class="desc">{{ item.description }}</div>{% endif %}
        </div>
        {% endfor %}
        {% endfor %}
        <div class="footer">由 ai-bot 自動產出 | {{ date }} {{ time }}</div>
        </body></html>"""


        class NewsRendererParams(SkillParam):
            """news_renderer 輸入參數。"""
            data: dict = {}
            output_path: str = ""
            template_path: str = ""


        class NewsRendererSkill(BaseSkill):
            """Jinja2 套模板產出 HTML 日報。"""

            skill_id = "news_renderer"
            skill_type = SkillType.PYTHON
            description = "Jinja2 套模板渲染新聞為 HTML 日報"
            version = "1.0.0"
            input_schema = NewsRendererParams

            async def execute(self, params: dict) -> SkillResult:
                try:
                    p = NewsRendererParams(**params)
                    now = datetime.now()
                    date_str = now.strftime("%Y-%m-%d")
                    time_str = now.strftime("%H:%M")

                    categories = p.data.get("categories", {})
                    if "items" in p.data and "categories" not in p.data:
                        categories = {p.data.get("category", "news"): p.data["items"]}

                    # 載入自訂模板或使用內建
                    tmpl_str = HTML_TEMPLATE
                    if p.template_path:
                        tmpl_path = Path(p.template_path)
                        if tmpl_path.exists():
                            tmpl_str = tmpl_path.read_text(encoding="utf-8")

                    template = Template(tmpl_str)
                    html = template.render(categories=categories, date=date_str, time=time_str)

                    output_path = p.output_path or f"output/news/daily_{date_str}.html"
                    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(output_path).write_text(html, encoding="utf-8")

                    return SkillResult(success=True, data={"path": output_path, "size": len(html), "date": date_str})
                except Exception as e:
                    return SkillResult(success=False, error=f"渲染失敗: {e}")
    ''')

    # ── 5. config/news_sources.yaml ──
    emit("config/news_sources.yaml", '''\
        sources:
          - name: "產業新聞"
            url: "https://www.vegasslotsonline.com/news/"
            selector: "article"
            category: news

          - name: "新遊戲資訊"
            url: "https://www.vegasslotsonline.com/new/"
            selector: "article, h2 a, h3 a"
            category: new_slots

        schedule:
          cron: "0 9 * * *"
          timezone: "Asia/Taipei"

        output:
          dir: "output/news"
          max_items_per_source: 10
    ''')

    return created


def main() -> None:
    project_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    project_dir = project_dir.resolve()

    print(f"🔧 scaffold_scraper: 產出新聞爬蟲 Skills 到 {project_dir}")
    created = scaffold(project_dir)
    print(f"✅ 完成！產出 {len(created)} 個檔案：")
    for f in created:
        print(f"   {f}")


if __name__ == "__main__":
    main()
