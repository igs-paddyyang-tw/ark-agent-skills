"""Markdown Parser — 逐行狀態機，產出 Token 列表。"""
from __future__ import annotations

import re

from .types import Token, TokenType

# 行內格式清除 pattern
_INLINE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),       # **bold**
    (re.compile(r"\*(.+?)\*"), r"\1"),            # *italic*
    (re.compile(r"`(.+?)`"), r"\1"),              # `code`
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),  # [text](url)
]

# 忽略的行 pattern
_IGNORE_PATTERNS: list[re.Pattern] = [
    re.compile(r"^!\[.*\]\(.*\)"),   # 圖片
    re.compile(r"^<[^>]+>"),          # HTML 標籤
]


def _strip_inline(text: str) -> str:
    """移除行內格式標記，保留文字。"""
    for pattern, repl in _INLINE_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def _should_ignore(line: str) -> bool:
    """判斷是否為不支援的語法（應忽略）。"""
    return any(p.match(line) for p in _IGNORE_PATTERNS)


def parse(markdown: str) -> list[Token]:
    """將 Markdown 文字解析為 Token 列表。

    使用逐行狀態機，支援 8 種節點類型。
    """
    tokens: list[Token] = []
    paragraph_buffer: list[str] = []
    code_buffer: list[str] = []
    in_code_block = False
    code_lang = ""

    def flush_paragraph() -> None:
        if paragraph_buffer:
            text = " ".join(paragraph_buffer)
            tokens.append(Token(TokenType.TEXT, _strip_inline(text)))
            paragraph_buffer.clear()

    for line in markdown.split("\n"):
        # 程式碼區塊狀態
        if in_code_block:
            if line.startswith("```"):
                content = "\n".join(code_buffer)
                tokens.append(Token(
                    TokenType.CODE_BLOCK,
                    content,
                    {"language": code_lang} if code_lang else {},
                ))
                code_buffer.clear()
                in_code_block = False
                code_lang = ""
            else:
                code_buffer.append(line)
            continue

        # 程式碼區塊開始
        if line.startswith("```"):
            flush_paragraph()
            in_code_block = True
            code_lang = line[3:].strip()
            continue

        # 忽略不支援的語法
        if _should_ignore(line.strip()):
            continue

        # 標題
        if line.startswith("### "):
            flush_paragraph()
            tokens.append(Token(TokenType.HEADING3, _strip_inline(line[4:])))
        elif line.startswith("## "):
            flush_paragraph()
            tokens.append(Token(TokenType.HEADING2, _strip_inline(line[3:])))
        elif line.startswith("# "):
            flush_paragraph()
            tokens.append(Token(TokenType.HEADING1, _strip_inline(line[2:])))
        # 列表
        elif line.startswith("- "):
            flush_paragraph()
            tokens.append(Token(TokenType.LIST_ITEM, _strip_inline(line[2:])))
        # 引用
        elif line.startswith("> "):
            flush_paragraph()
            tokens.append(Token(TokenType.BLOCKQUOTE, _strip_inline(line[2:])))
        # 分隔線
        elif line.strip() == "---" or line.strip() == "***" or line.strip() == "___":
            flush_paragraph()
            tokens.append(Token(TokenType.DIVIDER, ""))
        # 空行 → flush 段落
        elif not line.strip():
            flush_paragraph()
        # 一般文字 → 段落 buffer
        else:
            paragraph_buffer.append(line.strip())

    # 結尾 flush
    flush_paragraph()

    # 未關閉的程式碼區塊
    if in_code_block and code_buffer:
        content = "\n".join(code_buffer)
        tokens.append(Token(TokenType.CODE_BLOCK, content))

    return tokens
