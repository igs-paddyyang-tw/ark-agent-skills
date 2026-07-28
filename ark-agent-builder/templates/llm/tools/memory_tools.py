"""Tools: recall_memory + save_memory — 記憶存取。"""
from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
MEMORY_FILE = BASE_DIR / "memory" / "memory.md"


async def handle_recall_memory(args: dict) -> str:
    """查詢歷史記憶（FTS5）。"""
    query = args.get("query", "").strip()
    if not query:
        return "Error: query 不能為空"

    try:
        from src.memory.recall import recall
        results = recall("_default", query, k=5, include_shared=True)

        if not results:
            return f"查無記憶：「{query}」"

        lines = [f"recall「{query}」命中 {len(results)} 筆：\n"]
        for r in results:
            lines.append(f"- [{r.date}] ({r.source}) {r.title}: {r.body[:150]}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error: recall 失敗 — {e}"


async def handle_save_memory(args: dict) -> str:
    """將持久事實寫入 memory/memory.md。"""
    fact = args.get("fact", "").strip()
    section = args.get("section", "環境與慣例")

    if not fact:
        return "Error: fact 不能為空"
    if len(fact) > 500:
        return "Error: 單筆事實不超過 500 字"

    # 安全：不寫 .kiro/
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 讀取現有內容
    content = ""
    if MEMORY_FILE.exists():
        content = MEMORY_FILE.read_text(encoding="utf-8")

    # 找到對應 section 並 append
    section_header = f"## {section}"
    if section_header in content:
        # 在 section 最後一行（下一個 ## 前）插入
        lines = content.split("\n")
        insert_idx = None
        found_section = False
        for i, line in enumerate(lines):
            if line.strip() == section_header:
                found_section = True
                continue
            if found_section and line.startswith("## "):
                insert_idx = i
                break
        if insert_idx is None:
            insert_idx = len(lines)

        # 移除「（尚無記錄）」
        for j in range(insert_idx - 1, -1, -1):
            if "（尚無記錄）" in lines[j]:
                lines.pop(j)
                insert_idx -= 1
                break

        lines.insert(insert_idx, f"- {fact}")
        content = "\n".join(lines)
    else:
        content += f"\n\n{section_header}\n\n- {fact}\n"

    MEMORY_FILE.write_text(content, encoding="utf-8")
    return f"✅ 已記錄到 memory.md [{section}]：{fact[:50]}..."


def register_tools():
    from src.llm.tool_registry import Tool, registry

    registry.register(Tool(
        name="recall_memory",
        description="查詢歷史記憶。當使用者問「之前怎麼做的」、「上次...」時使用。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "查詢關鍵詞"},
            },
            "required": ["query"],
        },
        handler=handle_recall_memory,
    ))

    registry.register(Tool(
        name="save_memory",
        description="記錄持久事實到 memory.md。當學到新的環境慣例、工具怪癖、使用者偏好時使用。",
        parameters={
            "type": "object",
            "properties": {
                "fact": {"type": "string", "description": "要記錄的事實（一句話）"},
                "section": {
                    "type": "string",
                    "description": "分類：環境與慣例 / 工具怪癖 / 人與偏好 / 進行中的長期事項",
                    "enum": ["環境與慣例", "工具怪癖", "人與偏好", "進行中的長期事項"],
                },
            },
            "required": ["fact", "section"],
        },
        handler=handle_save_memory,
    ))
