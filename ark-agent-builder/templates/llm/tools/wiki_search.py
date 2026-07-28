"""Tool: search_wiki — 搜尋知識庫。"""
from __future__ import annotations


async def handle_search_wiki(args: dict) -> str:
    """搜尋知識庫（四層金字塔）。"""
    query = args.get("query", "").strip()
    if not query:
        return "Error: query 不能為空"

    try:
        from src.wiki.engine import WikiEngine
        engine = WikiEngine()
        result = await engine.query(query, use_rag=False)

        hits = result.get("results", [])
        if not hits:
            return f"知識庫查無「{query}」相關結果。請使用 web_search tool 搜尋外部資訊。"

        lines = [f"搜尋「{query}」找到 {len(hits)} 筆：\n"]
        for h in hits[:5]:
            title = h.get("title", "")
            snippet = h.get("snippet", "")[:200]
            lines.append(f"### {title}\n{snippet}\n")

        return "\n".join(lines)
    except Exception as e:
        return f"Error: 搜尋失敗 — {e}"


def register_tools():
    from src.llm.tool_registry import Tool, registry
    registry.register(Tool(
        name="search_wiki",
        description="搜尋知識庫。當需要查事實、規格、競品資料時使用。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜尋關鍵詞"},
            },
            "required": ["query"],
        },
        handler=handle_search_wiki,
    ))
