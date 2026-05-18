"""Layout Engine — Token → Node，計算位置與樣式。"""
from __future__ import annotations

from .types import LayoutConfig, Node, Token

# Typography 映射：nodeType → (fontSize, fontFamily)
TYPOGRAPHY: dict[str, tuple[int, str]] = {
    "Heading1": (48, "MSDF_Bold"),
    "Heading2": (32, "MSDF_Regular"),
    "Heading3": (24, "MSDF_Regular"),
    "Text": (16, "MSDF_Regular"),
    "CodeBlock": (14, "MSDF_Mono"),
    "ListItem": (16, "MSDF_Regular"),
    "Blockquote": (16, "MSDF_Italic"),
    "Divider": (0, ""),
}


def layout(tokens: list[Token], config: LayoutConfig | None = None) -> list[Node]:
    """將 Token 列表轉換為帶位置資訊的 Node 列表。

    yOffset 從 0 開始，每個節點累加前一節點的 spacing。
    """
    if config is None:
        config = LayoutConfig()

    nodes: list[Node] = []
    y_offset = 0

    for i, token in enumerate(tokens):
        node_type = token.token_type.value
        font_size, font_family = TYPOGRAPHY[node_type]

        # 文字處理
        text = token.content
        if node_type == "ListItem":
            text = f"• {text}"

        node = Node(
            id=f"n{i + 1}",
            node_type=node_type,
            text=text,
            font_size=font_size,
            font_family=font_family,
            x=config.margin_left,
            y_offset=y_offset,
        )

        # 條件欄位
        if node_type in ("Text", "CodeBlock"):
            node.max_width = config.max_width
        if node_type == "Text":
            node.word_wrap = True
        if node_type == "CodeBlock":
            node.background_color = "#1E1E1E"

        nodes.append(node)

        # 累加 yOffset
        y_offset += config.spacing.get(node_type, 40)

    return nodes
