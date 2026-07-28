"""Tool Handlers — read_file / write_file / list_files 的實際執行。

每個 handler 接收 args dict，回傳結果字串。
路徑安全由 registry.validate_*_path() 保護。
"""
from __future__ import annotations

import logging
from pathlib import Path

from src.tools.registry import validate_read_path, validate_write_path

log = logging.getLogger("tools.handlers")

# 專案根目錄（start.py 啟動時會 os.chdir 到此）
BASE_DIR = Path(".")


def handle_read_file(args: dict) -> str:
    """讀取檔案內容。"""
    path = args.get("path", "")
    if not path:
        return "❌ 缺少 path 參數"

    allowed, reason = validate_read_path(path)
    if not allowed:
        log.warning("read_file blocked: %s — %s", path, reason)
        return f"❌ {reason}"

    full_path = BASE_DIR / path
    if not full_path.exists():
        return f"❌ 檔案不存在：{path}"
    if not full_path.is_file():
        return f"❌ {path} 不是檔案（可能是目錄，請用 list_files）"

    try:
        content = full_path.read_text(encoding="utf-8")
        # 截斷過長檔案
        if len(content) > 8000:
            content = content[:8000] + f"\n\n... (截斷，原檔 {len(content)} 字元)"
        return content
    except Exception as e:
        return f"❌ 讀取失敗：{e}"


def handle_write_file(args: dict) -> str:
    """寫入檔案。"""
    path = args.get("path", "")
    content = args.get("content", "")

    if not path:
        return "❌ 缺少 path 參數"
    if not content:
        return "❌ 缺少 content 參數"

    allowed, reason = validate_write_path(path)
    if not allowed:
        log.warning("write_file blocked: %s — %s", path, reason)
        return f"❌ {reason}"

    full_path = BASE_DIR / path
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        size = len(content.encode("utf-8"))
        log.info("write_file: %s (%d bytes)", path, size)

        # 若寫入 knowledge/shared/raw/ → 自動觸發 ingest
        normalized = path.replace("\\", "/")
        if normalized.startswith("knowledge/shared/raw/"):
            try:
                from src.wiki.engine import WikiEngine
                engine = WikiEngine()
                filename = normalized.replace("knowledge/shared/raw/", "")
                ingested = engine.ingest(scope="global", filename=filename)
                if ingested:
                    log.info("auto-ingest: %s → wiki", ingested)
                    return f"✅ 已寫入 {path}（{size} bytes）並自動匯入知識庫索引"
            except Exception as e:
                log.warning("auto-ingest failed: %s", e)

        return f"✅ 已寫入 {path}（{size} bytes）"
    except Exception as e:
        return f"❌ 寫入失敗：{e}"


def handle_list_files(args: dict) -> str:
    """列出目錄內容。"""
    path = args.get("path", "")
    if not path:
        return "❌ 缺少 path 參數"

    allowed, reason = validate_read_path(path)
    if not allowed:
        log.warning("list_files blocked: %s — %s", path, reason)
        return f"❌ {reason}"

    full_path = BASE_DIR / path
    if not full_path.exists():
        return f"❌ 目錄不存在：{path}"
    if not full_path.is_dir():
        return f"❌ {path} 不是目錄"

    try:
        entries: list[str] = []
        for item in sorted(full_path.iterdir()):
            if item.name.startswith("."):
                continue
            prefix = "📁" if item.is_dir() else "📄"
            size = ""
            if item.is_file():
                size = f" ({item.stat().st_size} bytes)"
            entries.append(f"{prefix} {item.name}{size}")

        if not entries:
            return f"📂 {path}/ — 空目錄"

        header = f"📂 {path}/ — {len(entries)} 項：\n"
        return header + "\n".join(entries)
    except Exception as e:
        return f"❌ 列出失敗：{e}"


# ── Dispatch ──────────────────────────────────────────────

TOOL_HANDLERS = {
    "read_file": handle_read_file,
    "write_file": handle_write_file,
    "list_files": handle_list_files,
}


def dispatch_tool(name: str, args: dict) -> str:
    """根據 tool name 分派到對應 handler。"""
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return f"❌ 未知的 tool：{name}"
    try:
        return handler(args)
    except Exception as e:
        log.error("Tool %s execution error: %s", name, e)
        return f"❌ 工具執行失敗：{e}"
