"""news_renderer — 科技日報 HTML 渲染（使用外部模板）。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

_TEMPLATE_PATH = Path("templates/tech-daily.html")
_CARD_START = "<!-- ══════════════ 卡片模板開始 ══════════════ -->"
_CARD_END = "<!-- ══════════════ 卡片模板結束 ══════════════ -->"

_TOPIC_MAP = {
    "ai": ("🤖", "AI 焦點"), "ai_focus": ("🤖", "AI 焦點"),
    "tech_general": ("💡", "科技趨勢"), "dev_tools": ("🔧", "開發工具"),
    "coding": ("💻", "程式開發"), "default": ("📰", "科技新聞"),
}


class NewsRendererParams(SkillParam):
    articles: list = []
    output_path: str = ""


class NewsRendererSkill(BaseSkill):
    skill_id = "news_renderer"
    skill_type = SkillType.PYTHON
    description = "科技日報 HTML 渲染（暗黑科技風格）"
    version = "2.1.0"
    input_schema = NewsRendererParams

    async def execute(self, params: dict) -> SkillResult:
        try:
            p = NewsRendererParams(**params)
            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            date_display = now.strftime("%Y.%m.%d")

            template = _TEMPLATE_PATH.read_text(encoding="utf-8")
            s = template.find(_CARD_START)
            e = template.find(_CARD_END)
            if s == -1 or e == -1:
                return SkillResult(success=False, error="模板缺少卡片標記")

            page_before = template[:s]
            # 移除使用說明註解區塊
            import re as _re
            page_before = _re.sub(r'<!--[\s\S]*?-->', '', page_before)
            # 替換頁面標頭的日期
            page_before = page_before.replace("{{DATE}}", date_display)
            card_tpl = template[s + len(_CARD_START):e].strip()
            page_after = template[e + len(_CARD_END):]

            cards = []
            for i, art in enumerate(p.articles):
                topic_key = art.get("topic", "default").lower()
                emoji, topic_name = _TOPIC_MAP.get(topic_key, _TOPIC_MAP["default"])
                tags = art.get("tags", [])

                card = card_tpl
                card = card.replace("{{DATE}}", date_display)
                card = card.replace("{{TOPIC}}", f"{emoji} {topic_name}")
                card = card.replace("{{TITLE}}", art.get("title", "")[:60])
                card = card.replace("{{IMG_SRC}}", art.get("img", ""))
                card = card.replace("{{IMG_ALT}}", art.get("title", "")[:30])
                card = card.replace("{{SOURCE}}", art.get("source", "Auto"))
                card = card.replace("{{NEWS_DATE}}", date_display)
                card = card.replace("{{WHAT}}", art.get("what", art.get("description", art.get("title", "")))[:300])
                card = card.replace("{{WHY}}", art.get("why", ""))
                card = card.replace("{{SUMMARY}}", art.get("summary", art.get("title", "")[:30]))
                card = card.replace("{{TAG1_ICON}}", "🔍")
                card = card.replace("{{TAG1_TEXT}}", tags[0] if len(tags) > 0 else "技術趨勢")
                card = card.replace("{{TAG2_ICON}}", "💡")
                card = card.replace("{{TAG2_TEXT}}", tags[1] if len(tags) > 1 else "值得關注")
                card = card.replace("{{TAG3_ICON}}", "🚀")
                card = card.replace("{{TAG3_TEXT}}", tags[2] if len(tags) > 2 else "持續追蹤")
                card = card.replace("{{PAGE}}", f"{i+1} / {len(p.articles)}")
                cards.append(card)

            html = page_before + "\n".join(cards) + page_after
            output_path = p.output_path or f"output/news/tech-daily-{date_str}.html"
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(html, encoding="utf-8")

            return SkillResult(success=True, data={
                "path": output_path, "count": len(p.articles), "size": len(html),
            })
        except Exception as e:
            return SkillResult(success=False, error=f"渲染失敗: {e}")
