"""Tool: save_to_wiki — 寫入知識庫。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
WIKI_DIR = BASE_DIR / "knowledge" / "shared" / "wiki"

# 白名單：只能寫入這個目錄
ALLOWED_DIR = WIKI_DIR


async def handle_save_to_wiki(args: dict) -> str:
    """將內容寫入 knowledge/shared/wiki/{slug}.md。"""
    slug = args.get("slug", "").strip()
    title = args.get("title", slug)
    content = args.get("content", "")
    tags = args.get("tags", [])

    if not slug:
        return "Error: slug 不能為空"
    if not content:
        return "Error: content 不能為空"

    # 安全檢查：slug 不能含 ../ 或絕對路徑
    if ".." in slug or "/" in slug or "\\" in slug:
        return "Error: slug 不能含路徑分隔符號"

    # 加 frontmatter
    today = datetime.now().strftime("%Y-%m-%d")
    tags_str = ", ".join(f"'{t}'" for t in tags) if tags else ""
    wiki_type = args.get("type", "synthesis")
    frontmatter = (
        f"---\n"
        f"title: \"{title}\"\n"
        f"type: {wiki_type}\n"
        f"status: developing\n"
        f"tags: [{tags_str}]\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        f"---\n\n"
    )

    full_content = frontmatter + content

    # 寫入
    ALLOWED_DIR.mkdir(parents=True, exist_ok=True)
    filepath = ALLOWED_DIR / f"{slug}.md"
    filepath.write_text(full_content, encoding="utf-8")

    # 更新索引（wiki 搜尋索引 + memory FTS5）
    try:
        from src.wiki.indexer import rebuild_index
        rebuild_index()
    except Exception:
        pass
    try:
        from src.memory.indexer import index_shared_wiki
        index_shared_wiki()
    except Exception:
        pass

    return f"✅ 已寫入 knowledge/shared/wiki/{slug}.md（{len(content)} 字）"


def register_tools():
    from src.llm.tool_registry import Tool, registry
    registry.register(Tool(
        name="save_to_wiki",
        description=(
            "將內容寫入知識庫。使用者說「存進知識庫」「記錄下來」時使用。"
            "如果使用者說「把這個存進知識庫」但沒提供具體內容，"
            "你應該從對話歷史中找到上一輪的回覆內容，自動生成 slug（kebab-case）和 title，不要反問使用者。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "檔案名稱（kebab-case，不含 .md）"},
                "title": {"type": "string", "description": "知識頁面標題"},
                "content": {"type": "string", "description": "Markdown 內容（不含 frontmatter）"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "標籤列表"},
            },
            "required": ["slug", "title", "content"],
        },
        handler=handle_save_to_wiki,
    ))
