"""主入口 — 串接 Parser → Layout → Emitter。"""
from __future__ import annotations

import sys

from .emitter import emit
from .layout import layout
from .parser import parse
from .types import LayoutConfig
from .validator import validate


def convert(markdown: str, config: LayoutConfig | None = None) -> str:
    """將 Markdown 轉換為 PixiJS AST JSON。

    Args:
        markdown: Markdown 文字輸入
        config: Layout 參數（可選，使用預設值）

    Returns:
        JSON 字串（扁平 nodes 陣列）
    """
    tokens = parse(markdown)
    nodes = layout(tokens, config)
    return emit(nodes)


def convert_and_validate(markdown: str, config: LayoutConfig | None = None) -> tuple[str, list[str]]:
    """轉換並驗證，回傳 (json_output, errors)。"""
    output = convert(markdown, config)
    errors = validate(output)
    return output, errors


def main() -> None:
    """CLI 入口：python -m scripts.md_to_pixi_ast input.md"""
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.md_to_pixi_ast <input.md>", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    with open(input_path, encoding="utf-8") as f:
        markdown = f.read()

    output, errors = convert_and_validate(markdown)

    if errors:
        print(f"⚠️ Validation errors: {errors}", file=sys.stderr)

    print(output)


if __name__ == "__main__":
    main()
