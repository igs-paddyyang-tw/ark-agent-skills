"""ark-md-to-pixi-ast 轉換測試。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 加入 scripts 路徑
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.md_to_pixi_ast import convert, convert_and_validate
from scripts.parser import parse
from scripts.types import TokenType
from scripts.validator import validate


class TestEmptyInput:
    """空輸入測試。"""

    def test_empty_string(self):
        result = convert("")
        data = json.loads(result)
        assert data == {"nodes": []}

    def test_whitespace_only(self):
        result = convert("   \n\n   ")
        data = json.loads(result)
        assert data == {"nodes": []}


class TestSingleNodes:
    """單一節點測試。"""

    def test_heading1(self):
        result = convert("# Hello World")
        data = json.loads(result)
        assert len(data["nodes"]) == 1
        node = data["nodes"][0]
        assert node["nodeType"] == "Heading1"
        assert node["text"] == "Hello World"
        assert node["fontSize"] == 48
        assert node["fontFamily"] == "MSDF_Bold"
        assert node["yOffset"] == 0

    def test_heading2(self):
        result = convert("## Section")
        data = json.loads(result)
        assert data["nodes"][0]["nodeType"] == "Heading2"
        assert data["nodes"][0]["fontSize"] == 32

    def test_heading3(self):
        result = convert("### Sub")
        data = json.loads(result)
        assert data["nodes"][0]["nodeType"] == "Heading3"
        assert data["nodes"][0]["fontSize"] == 24

    def test_code_block(self):
        md = "```js\nconst x = 1;\n```"
        result = convert(md)
        data = json.loads(result)
        assert len(data["nodes"]) == 1
        node = data["nodes"][0]
        assert node["nodeType"] == "CodeBlock"
        assert node["text"] == "const x = 1;"
        assert node["fontFamily"] == "MSDF_Mono"
        assert node["backgroundColor"] == "#1E1E1E"

    def test_list_item(self):
        result = convert("- Item one")
        data = json.loads(result)
        assert data["nodes"][0]["nodeType"] == "ListItem"
        assert data["nodes"][0]["text"] == "• Item one"

    def test_blockquote(self):
        result = convert("> Quote text")
        data = json.loads(result)
        assert data["nodes"][0]["nodeType"] == "Blockquote"
        assert data["nodes"][0]["fontFamily"] == "MSDF_Italic"

    def test_divider(self):
        result = convert("---")
        data = json.loads(result)
        assert data["nodes"][0]["nodeType"] == "Divider"
        assert data["nodes"][0]["text"] == ""

    def test_paragraph(self):
        result = convert("Hello world")
        data = json.loads(result)
        assert data["nodes"][0]["nodeType"] == "Text"
        assert data["nodes"][0]["wordWrap"] is True
        assert data["nodes"][0]["maxWidth"] == 960


class TestFullExample:
    """完整範例測試（spec 中的範例）。"""

    def test_spec_example(self):
        md = "# Pixi 架構\n\n這是一個資料驅動的渲染系統。\n\n## 初始化\n\n```js\nconst app = new PIXI.Application();\n```"
        result, errors = convert_and_validate(md)
        assert errors == []
        data = json.loads(result)
        assert len(data["nodes"]) == 4
        assert data["nodes"][0]["nodeType"] == "Heading1"
        assert data["nodes"][1]["nodeType"] == "Text"
        assert data["nodes"][2]["nodeType"] == "Heading2"
        assert data["nodes"][3]["nodeType"] == "CodeBlock"
        # yOffset 單調遞增
        offsets = [n["yOffset"] for n in data["nodes"]]
        assert offsets == sorted(offsets)
        assert len(set(offsets)) == len(offsets)  # 全部不同


class TestInlineStripping:
    """行內格式去除測試。"""

    def test_bold(self):
        result = convert("**bold** text")
        data = json.loads(result)
        assert data["nodes"][0]["text"] == "bold text"

    def test_link(self):
        result = convert("[click here](https://example.com)")
        data = json.loads(result)
        assert data["nodes"][0]["text"] == "click here"


class TestIgnoredSyntax:
    """不支援語法忽略測試。"""

    def test_image(self):
        result = convert("![alt](image.png)")
        data = json.loads(result)
        assert data == {"nodes": []}

    def test_html(self):
        result = convert("<div>hello</div>")
        data = json.loads(result)
        assert data == {"nodes": []}


class TestMultipleListItems:
    """多列表項測試。"""

    def test_three_items(self):
        md = "- a\n- b\n- c"
        result = convert(md)
        data = json.loads(result)
        assert len(data["nodes"]) == 3
        assert all(n["nodeType"] == "ListItem" for n in data["nodes"])


class TestValidator:
    """Validator 測試。"""

    def test_valid_output(self):
        md = "# Test\n\nParagraph"
        output = convert(md)
        errors = validate(output)
        assert errors == []

    def test_invalid_json(self):
        errors = validate("not json")
        assert errors == ["json_invalid"]

    def test_determinism(self):
        """同輸入跑多次同輸出。"""
        md = "# Title\n\n## Sub\n\nText here\n\n```py\nx = 1\n```"
        results = [convert(md) for _ in range(10)]
        assert len(set(results)) == 1
