"""Tool Registry — Gemini Function Calling 的 tool 定義與路徑安全。

架構參考 Hermes Agent 的 registry.register() 模式，
但簡化為 dict-based（不需要 AST 掃描）。
"""
from __future__ import annotations

from pathlib import Path

# ── 路徑安全規則 ──────────────────────────────────────────

# 可讀路徑前綴（read_file / list_files）
READABLE_PREFIXES = [
    "knowledge/",
    "output/",
    "agents/",
    "docs/",
    "memory/",
    "config/",
]

# 禁止讀取
BLOCKED_READ_PATTERNS = [
    ".env",
    ".kiro/",
    "venv/",
    "__pycache__",
    ".git/",
]

# 可寫路徑前綴（write_file）
WRITABLE_PREFIXES = [
    "output/reports/",
    "output/skills/",
    "output/exports/",
    "output/drafts/",
    "knowledge/shared/raw/",
]


def validate_read_path(path: str) -> tuple[bool, str]:
    """驗證讀取路徑是否允許。回傳 (allowed, reason)。"""
    normalized = path.replace("\\", "/").lstrip("./")

    # 檢查禁止清單
    for blocked in BLOCKED_READ_PATTERNS:
        if blocked in normalized:
            return False, f"拒絕存取：{blocked} 為受保護路徑"

    # 檢查是否在允許範圍
    for prefix in READABLE_PREFIXES:
        if normalized.startswith(prefix):
            return True, ""

    return False, f"路徑 {normalized} 不在可讀範圍內（允許：{', '.join(READABLE_PREFIXES)}）"


def validate_write_path(path: str) -> tuple[bool, str]:
    """驗證寫入路徑是否允許。回傳 (allowed, reason)。"""
    normalized = path.replace("\\", "/").lstrip("./")

    for prefix in WRITABLE_PREFIXES:
        if normalized.startswith(prefix):
            return True, ""

    return False, (
        f"拒絕寫入 {normalized}。"
        f"允許的寫入路徑：{', '.join(WRITABLE_PREFIXES)}"
    )


# ── Gemini Function Declarations ──────────────────────────

TOOL_DECLARATIONS = [
    {
        "name": "read_file",
        "description": (
            "讀取專案內的檔案內容。"
            "用於查看知識庫文章、報告、設定檔等。"
            "不可讀取 .env、.kiro/ 等受保護檔案。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相對於專案根目錄的檔案路徑，如 knowledge/shared/wiki/overview.md",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "寫入檔案。僅在使用者明確要求產出報告、存入知識庫、匯出資料時使用。"
            "允許路徑：output/reports/、output/skills/、output/exports/、output/drafts/、"
            "knowledge/shared/raw/。"
            "存知識庫時寫入 knowledge/shared/raw/（系統會自動匯入索引）。"
            "寫入前必須告知使用者要寫什麼和寫到哪裡。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相對路徑，如 output/reports/2026-07-13_analysis.md 或 knowledge/shared/raw/topic-name.md",
                },
                "content": {
                    "type": "string",
                    "description": "檔案完整內容（Markdown 或 HTML）",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": (
            "列出指定目錄下的檔案清單。"
            "用於確認知識庫或 output 裡有什麼檔案。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相對路徑，如 knowledge/shared/wiki 或 output/reports",
                }
            },
            "required": ["path"],
        },
    },
]
