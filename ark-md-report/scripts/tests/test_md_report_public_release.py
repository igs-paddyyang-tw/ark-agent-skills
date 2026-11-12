"""ark-md-report 公開版工具的行為測試：public_scan（兩層規則）、public_edit（must）、build_report_html（無 mermaid 路徑、後處理）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import build_report_html  # noqa: E402
import public_edit  # noqa: E402
import public_scan  # noqa: E402

CLEAN = "# 公開版\n\n決策 D-073、測試 TestFoo、套件 internal/ark-go。顏色 #0b66c3，行數 39,397，日期 2026-11-12。\n"


def _scan(tmp_path: Path, text: str, *extra: str) -> int:
    f = tmp_path / "r.md"
    f.write_text(text, encoding="utf-8")
    return public_scan.main([str(f), *extra])


# ── public_scan ─────────────────────────────────────────────

def test_clean_text_passes(tmp_path):
    assert _scan(tmp_path, CLEAN) == 0


@pytest.mark.parametrize("leak", [
    "commit a8748b8）",
    "主機 10.2.3.4 上",
    "路徑 /home/someone/proj",
    "API_KEY=abcd1234efgh5678",
    "寄到 someone@example.com",
    "verdict: needs-work",
    "<span>verdict <b>sound</b></span>",
    "## Findings\n",
])
def test_generic_rules_catch_leaks(tmp_path, leak):
    """每一類通用規則各放一個樣本，都必須紅（反證：刪掉任一條規則 → 對應參數紅）。"""
    assert _scan(tmp_path, CLEAN + leak + "\n") == 1


def test_word_verdict_alone_is_not_a_leak(tmp_path):
    """介紹報告契約時會寫「frontmatter 有 verdict、confidence」，這不是評等值。"""
    assert _scan(tmp_path, CLEAN + "frontmatter 有 verdict、findings 統計、confidence。\n") == 0


def test_project_rules_extend_generic(tmp_path):
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps({"rules": [{"name": "內部 repo", "pattern": "secret-repo"}]}), encoding="utf-8")
    assert _scan(tmp_path, CLEAN + "來自 secret-repo\n", "--rules", str(rules)) == 1
    assert _scan(tmp_path, CLEAN + "來自 secret-repo\n") == 0  # 沒給專案規則就抓不到：內部詞要放專案規則


def test_no_generic_keeps_only_project_rules(tmp_path):
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps({"rules": [{"name": "x", "pattern": "zzz"}]}), encoding="utf-8")
    assert _scan(tmp_path, CLEAN + "commit a8748b8）\n", "--rules", str(rules), "--no-generic") == 0


def test_zero_files_is_failure(tmp_path):
    (tmp_path / "empty").mkdir()
    assert public_scan.main([str(tmp_path / "empty")]) == 1


@pytest.mark.parametrize("bad", ['{"rules": []}', '{"rules": [{"name": "x"}]}', '[]', '{"rules": [{"name": "x", "pattern": "("}]}'])
def test_bad_rules_file_exit_2(tmp_path, bad):
    rules = tmp_path / "rules.json"
    rules.write_text(bad, encoding="utf-8")
    assert _scan(tmp_path, CLEAN, "--rules", str(rules)) == 2


def test_json_output(tmp_path, capsys):
    assert _scan(tmp_path, CLEAN + "commit a8748b8）\n", "--json") == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and out["hits"] == 1 and out["report"][0]["hits"][0]["rule"] == "commit 編號"


# ── public_edit ─────────────────────────────────────────────

def test_must_replaces_exactly_once():
    assert public_edit.must("a b c", "b", "B") == "a B c"


@pytest.mark.parametrize("text", ["a c", "b b"])
def test_must_rejects_zero_or_many(text):
    with pytest.raises(public_edit.EditMiss):
        public_edit.must(text, "b", "B")


def test_must_all_and_strip_frontmatter():
    fm, body = public_edit.strip_frontmatter('---\ntitle: "x"\n---\n內文 A\n')
    assert fm.startswith("---") and body == "內文 A\n"
    assert public_edit.must_all(body, [("內文", "正文"), ("A", "B")]) == "正文 B\n"


# ── build_report_html ───────────────────────────────────────

REPORT = """---
title: "示範報告"
type: review
date: 2026-11-12
verdict: needs-work
confidence: high
findings: {p0: 0, p1: 1, p2: 0, p3: 0}
---

# 示範報告

## 結論

| ID | 嚴重度 |
|---|---|
| F-001 | P1 |
"""


def test_build_internal_shows_review_badges():
    page, n = build_report_html.build(REPORT, src_label="r.md", asof="資料截至 2026-11-12", kpis=["3|款"],
                                      kick="示範", public=False, back="")
    assert n == 0 and "<title>示範報告</title>" in page
    assert "verdict <b>needs-work</b>" in page and 'class="sev p1"' in page and "Content 軌" in page


def test_build_public_hides_review_badges_and_passes_generic_scan(tmp_path):
    page, _ = build_report_html.build(REPORT.replace("| F-001 | P1 |", "| 1 | 待辦 |"), src_label="r.md",
                                      asof="資料截至 2026-11-12", kpis=[], kick="示範", public=True,
                                      back="/showcase/team/x|← 回到案例")
    assert "verdict" not in page and "公開版" in page and 'href="/showcase/team/x"' in page
    f = tmp_path / "p.html"
    f.write_text(page, encoding="utf-8")
    assert public_scan.main([str(f)]) == 0


def test_postprocess_drops_unreferenced_symbols_only():
    page = ('<style></style><figure class="fig mm"><svg><defs>'
            '<symbol id="used"><path d="M1"/></symbol><symbol id="db"><path d=".256.0.255.0"/></symbol>'
            '</defs><use href="#used"/></svg></figure>')
    out, removed = build_report_html.postprocess(page)
    assert removed == 1 and 'id="used"' in out and 'id="db"' not in out
    assert build_report_html.MERMAID_CSS in out


def test_tidy_svg_rounds_long_floats():
    assert build_report_html.tidy_svg('<rect x="25.040000000000003" width="33.333%"/>') == '<rect x="25.0" width="33%"/>'
