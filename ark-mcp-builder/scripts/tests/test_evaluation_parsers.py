"""mcp-builder 評測harness 的輸入契約守門。

## 為什麼是「解析器」而不是「產出 → 立刻驗」

本 skill 的 scripts 不是產生器，是**評測 harness**（拿 MCP server 跑題目、
用 Claude 打分）。真的跑一次需要 API 金鑰與一台 MCP server，不適合當守門。

可以、也值得離線驗的是它的**輸入契約**：
題庫 XML 怎麼解析、模型回覆怎麼抽標籤、`--header` / `--env` 怎麼拆。
這四支是純函式，錯了會讓整場評測靜默跑偏（少題、抓錯答案、標頭沒帶上）。

> 🔴 為了讓它們可測，2026-09-14 把 `anthropic` 與 `connections`（→ `mcp`）
> 從 module top-level 改成**用到才載入**。原本沒裝 SDK 就連 import 都做不到，
> 於是純函式也跟著測不了 —— 同一條判準本 repo 已用在 `--help` 攔截：
> **不需要依賴的路徑，就不該要求依賴。**
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import evaluation as ev  # noqa: E402


# ── 題庫 XML ───────────────────────────────────────────────────

QA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<evaluation>
  <qa_pair>
    <question>  有幾個玩家 VIP 大於 5？  </question>
    <answer> 42 </answer>
  </qa_pair>
  <qa_pair>
    <question>最高倍率的遊戲是哪一款？</question>
    <answer>Gates of Olympus</answer>
  </qa_pair>
</evaluation>
"""


def test_parses_every_qa_pair_and_strips_whitespace(tmp_path):
    f = tmp_path / "eval.xml"
    f.write_text(QA_XML, encoding="utf-8")
    pairs = ev.parse_evaluation_file(f)
    assert len(pairs) == 2, "少一題就是少驗一題，而回報仍然是綠的"
    assert pairs[0] == {"question": "有幾個玩家 VIP 大於 5？", "answer": "42"}


def test_qa_pair_missing_answer_is_dropped_not_half_parsed(tmp_path):
    f = tmp_path / "eval.xml"
    f.write_text("<evaluation><qa_pair><question>Q</question></qa_pair></evaluation>",
                 encoding="utf-8")
    assert ev.parse_evaluation_file(f) == []


def test_malformed_xml_returns_empty_instead_of_raising(tmp_path):
    """壞檔要回空清單（呼叫端已假設如此），但**不能**假裝解析成功"""
    f = tmp_path / "eval.xml"
    f.write_text("<evaluation><qa_pair>", encoding="utf-8")
    assert ev.parse_evaluation_file(f) == []


# ── 從模型回覆抽標籤 ───────────────────────────────────────────

def test_extract_takes_the_last_occurrence(text_tag="response"):
    """模型會在思考過程中先寫出草稿標籤 —— 取最後一個才是最終答案"""
    text = "<response>草稿</response> 想了一下 <response>最終</response>"
    assert ev.extract_xml_content(text, text_tag) == "最終"


def test_extract_spans_newlines():
    assert ev.extract_xml_content("<summary>第一行\n第二行</summary>", "summary") \
        == "第一行\n第二行"


def test_extract_returns_none_when_absent():
    assert ev.extract_xml_content("沒有標籤", "response") is None


# ── CLI 的 --header / --env 拆解 ────────────────────────────────

@pytest.mark.parametrize("fn,raw,expected", [
    (lambda x: ev.parse_headers(x), ["Authorization: Bearer abc"],
     {"Authorization": "Bearer abc"}),
    (lambda x: ev.parse_env_vars(x), ["API_KEY=sk-123"], {"API_KEY": "sk-123"}),
])
def test_key_value_parsing(fn, raw, expected):
    assert fn(raw) == expected


def test_value_containing_the_separator_is_kept_whole():
    """🔴 token 與 URL 裡本來就有 `:` 與 `=` —— 只能切第一個分隔符。

    切錯的後果是「標頭帶了一半」：連得上、但認證失敗，看起來像 server 的問題。
    """
    assert ev.parse_headers(["Authorization: Bearer a:b:c"]) \
        == {"Authorization": "Bearer a:b:c"}
    assert ev.parse_env_vars(["URL=https://x/y?a=1&b=2"]) \
        == {"URL": "https://x/y?a=1&b=2"}


def test_module_imports_without_the_heavy_sdks():
    """回歸：純函式不得再被 anthropic / mcp 的 top-level import 擋住"""
    src = (SCRIPTS / "evaluation.py").read_text(encoding="utf-8")
    head = src[:src.index("EVALUATION_PROMPT")]
    assert "\nfrom anthropic import" not in head, "anthropic 又被搬回 top-level"
    assert "\nfrom connections import" not in head, "connections 又被搬回 top-level"
