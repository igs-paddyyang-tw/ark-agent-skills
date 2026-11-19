"""md_to_a4 守門：A4 分頁規則、五種風格 token、BOM／CRLF、重複 H1、deterministic、雙軌戳記、mermaid 退路、路徑不洩漏。"""
from __future__ import annotations
import pathlib, re, sys
import pytest

pytest.importorskip("markdown")
SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
import md_to_a4 as A  # noqa: E402

SAMPLE = """---
title: "範例專案計畫書"
version: 1.0
created: 2026-11-19
status: active
---

# 範例專案計畫書

## 1. 目標

| # | 目標 | 成功標準 |
|---|---|---|
| G1 | 行為等價 | 0 差 |

> 引言：以原稿為準。

```bash
make verify
```
"""


@pytest.fixture
def chdir_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write(p: pathlib.Path, text: str, *, bom=False, crlf=False) -> pathlib.Path:
    if crlf:
        text = text.replace("\n", "\r\n")
    p.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
    return p


def test_five_styles_parsed_with_tokens():
    styles = A.load_styles()
    assert list(styles) == ["boardroom", "terminal", "midnight", "editorial", "paperprint"]
    for name, s in styles.items():
        for var in ("--bg", "--surface", "--accent", "--text", "--border", "--font-body"):
            assert var in s["root"], f"{name} 缺 {var}"


def test_a4_print_rules_and_header(chdir_tmp):
    src = write(chdir_tmp / "plan.md", SAMPLE)
    page = A.build(src, kick="demo ・ 計畫書", webfont=False)
    assert "@page{size:A4" in page and "counter(pages)" in page
    assert "break-inside:avoid" in page and "break-after:avoid" in page
    assert "<table>" in page and "<blockquote>" in page and "<pre><code" in page
    assert "版本：1.0" in page and "狀態：active" in page and "demo ・ 計畫書" in page
    assert "fonts.googleapis.com" not in page  # --no-webfont
    assert "原稿（Content 軌）：<code>plan.md</code>" in page


def test_style_switch_changes_tokens(chdir_tmp):
    src = write(chdir_tmp / "p.md", SAMPLE)
    styles = A.load_styles()
    for name in styles:
        accent = re.search(r"--accent:\s*([^;]+);", styles[name]["root"]).group(1)
        assert f"--accent:{accent}" in A.build(src, style=name, webfont=False).replace(" ", "")


def test_unknown_style_lists_choices(chdir_tmp):
    src = write(chdir_tmp / "p.md", SAMPLE)
    with pytest.raises(SystemExit) as ei:
        A.build(src, style="nope")
    assert "paperprint" in str(ei.value) and "boardroom" in str(ei.value)


@pytest.mark.parametrize("bom,crlf", [(True, False), (False, True), (True, True)])
def test_bom_and_crlf_frontmatter(chdir_tmp, bom, crlf):
    src = write(chdir_tmp / "p.md", SAMPLE, bom=bom, crlf=crlf)
    page = A.build(src, webfont=False)
    assert "<title>範例專案計畫書</title>" in page
    assert "title:" not in page  # frontmatter 沒有漏進內文


def test_duplicate_h1_dropped_but_different_h1_kept(chdir_tmp):
    page = A.build(write(chdir_tmp / "a.md", SAMPLE), webfont=False)
    assert page.count("範例專案計畫書</h1>") == 1
    other = SAMPLE.replace("# 範例專案計畫書", "# 另一個標題")
    page2 = A.build(write(chdir_tmp / "b.md", other), webfont=False)
    assert "<h1>另一個標題</h1>" in page2


def test_deterministic(chdir_tmp):
    src = write(chdir_tmp / "p.md", SAMPLE)
    assert A.build(src) == A.build(src)


def test_stamp_auto_for_md_report_and_matches_report_pair(chdir_tmp):
    rep = SAMPLE.replace("status: active", "status: active\nsource_skill: ark-md-report")
    src = write(chdir_tmp / "r.md", rep)
    page = A.build(src, webfont=False)
    m = re.search(r"<!-- content-src: (\S+) sha256:([0-9a-f]{16}) -->", page)
    assert m and m.group(1) == "r.md"
    assert "content-src" not in A.build(write(chdir_tmp / "plain.md", SAMPLE), webfont=False)
    assert "content-src" not in A.build(src, webfont=False, stamp=False)
    pair_dir = A.MD_REPORT_SCRIPTS
    if (pair_dir / "report_pair.py").exists():
        sys.path.insert(0, str(pair_dir))
        import report_pair  # noqa: E402
        (chdir_tmp / "r.html").write_text(page, encoding="utf-8")
        assert report_pair.check(src, quiet=True) == "OK"
        write(src, rep + "\n補一段\n")
        assert report_pair.check(src, quiet=True) == "STALE"


def test_mermaid_kept_when_cannot_render(chdir_tmp, capsys):
    src = write(chdir_tmp / "m.md", SAMPLE + "\n```mermaid\ngraph LR\nA-->B\n```\n")
    page = A.build(src, webfont=False, playwright_dir="")
    assert "graph LR" in page
    assert "mermaid" in capsys.readouterr().err


def test_source_path_outside_cwd_uses_name_only(tmp_path, monkeypatch):
    (tmp_path / "secret-dir").mkdir()
    src = write(tmp_path / "secret-dir" / "doc.md", SAMPLE)
    sub = tmp_path / "elsewhere"
    sub.mkdir()
    monkeypatch.chdir(sub)
    page = A.build(src, webfont=False)
    assert "<code>doc.md</code>" in page and str(tmp_path) not in page


def test_cli_list_styles_and_render(chdir_tmp, capsys):
    assert A.main(["--list-styles"]) == 0
    assert "paperprint" in capsys.readouterr().out
    write(chdir_tmp / "p.md", SAMPLE)
    assert A.main(["p.md", "out/p.html", "--no-webfont"]) == 0
    assert (chdir_tmp / "out" / "p.html").read_text(encoding="utf-8").startswith("<!doctype html>")
