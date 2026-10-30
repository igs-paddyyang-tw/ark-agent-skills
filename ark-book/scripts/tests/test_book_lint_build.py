"""ark-book 行為測試：book_lint 契約守門、book_build 雙軌戳記、book_register 圖書館登錄守門。

fixture 以 skill 自帶的 `references/examples/chapter-golden.md` 為底組一本一章的書，
確保「範例本身就過得了 lint」—— 範例與守門脫節時這裡會先紅。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("yaml")

SKILL = Path(__file__).resolve().parents[2]
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))
import book_lint  # noqa: E402

SLUG = "first-personal-agent"
CH = "01-give-it-a-soul"


def make_book(root: Path, status: str = "draft") -> Path:
    """在 root/books/<slug>/ 組一本一章的書（golden 範例改章號 3→1）。"""
    bd = root / "books" / SLUG
    (bd / "sources").mkdir(parents=True)
    (bd / "sources" / "agent-team-closed-loop-workflow.md").write_text("# src\n", encoding="utf-8")
    golden = (SKILL / "references" / "examples" / "chapter-golden.md").read_text(encoding="utf-8")
    ch = golden.replace("\nchapter: 3\n", "\nchapter: 1\n", 1).replace("status: published", f"status: {status}", 1)
    (bd / f"{CH}.md").write_text(ch, encoding="utf-8")
    meta = (SKILL / "assets" / "book.yaml.example").read_text(encoding="utf-8")
    meta = meta.replace("  - 00-preface\n  - 01-give-it-a-soul\n", f"  - {CH}\n").replace("status: draft", f"status: {status}")
    (bd / "book.yaml").write_text(meta, encoding="utf-8")
    return bd


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True, timeout=60)


def lint_fails(bd: Path) -> list[str]:
    return [f for r in book_lint.lint_book(bd, None) for f in r.fails]


# ── book_lint ─────────────────────────────────────


def test_golden_book_passes_lint(tmp_path):
    """正常路徑：用 golden 範例組的書零 FAIL，CLI --json 回 PASS、exit 0。"""
    bd = make_book(tmp_path)
    r = run("book_lint.py", str(bd), "--json")
    data = json.loads(r.stdout)
    assert r.returncode == 0 and data["status"] == "PASS", data


@pytest.mark.parametrize("old,new,expect", [
    ("> [!ASK]", "> [!NOTE]", "內文缺 `> [!ASK]`"),
    ("> [!MYTH]", "> [!NOTE]", "常見誤解缺 `> [!MYTH]`"),
    ('punchline: "人格不是形容詞，是一份寫著『絕不做什麼』的資料。"',
     'punchline: "' + "很長" * 25 + '"', "punchline 超過 40 字"),
    ("## 常見誤解", "## 雜談", "缺章節 `## 常見誤解`"),
    ("\nchapter: 1\n", "\nchapter: 2\n", "檔名章號 01 ≠ frontmatter chapter 2"),
    ("## 重點回顧\n", "## 重點回顧\n\n如上所述，\n", "chunk 自足禁詞「如上所述」"),
    ("## 下一章\n", "## 下一章\n\n<這裡填下一章標題>\n", "placeholder 殘留"),
], ids=["no-ask", "no-myth", "long-punchline", "missing-section", "chapter-mismatch",
        "forbidden-phrase", "placeholder"])
def test_chapter_violations_fail(tmp_path, old, new, expect):
    """反例：教學結構或 AI 可讀性違規，每種都要 FAIL 並指出原因。"""
    bd = make_book(tmp_path)
    p = bd / f"{CH}.md"
    text = p.read_text(encoding="utf-8")
    assert old in text, f"fixture 前提失效：{old!r}"
    p.write_text(text.replace(old, new), encoding="utf-8")  # 全部替換：範例可能有多個 callout
    fails = lint_fails(bd)
    assert any(expect in f for f in fails), fails


def test_toc_and_book_yaml_violations(tmp_path):
    """反例：目錄列了不存在的章、檔案未列目錄、slug 與目錄名不符、outcomes 只 1 條 → 各自 FAIL；CLI exit 1。"""
    bd = make_book(tmp_path)
    y = bd / "book.yaml"
    meta = y.read_text(encoding="utf-8")
    y.write_text(meta.replace(f"  - {CH}\n", f"  - {CH}\n  - 02-missing\n"), encoding="utf-8")
    (bd / "03-orphan.md").write_text((bd / f"{CH}.md").read_text(encoding="utf-8"), encoding="utf-8")
    fails = lint_fails(bd)
    assert any("`02-missing` 但檔案不存在" in f for f in fails)
    assert any("`03-orphan.md` 未列入" in f for f in fails)
    assert run("book_lint.py", str(bd)).returncode == 1

    bd2 = make_book(tmp_path / "b2")
    y2 = bd2 / "book.yaml"
    m2 = y2.read_text(encoding="utf-8").replace(f"slug: {SLUG}", "slug: other-book")
    m2 = m2.replace("  - 用 ark-agent-role-profile 產出含 hard_stops 的人格檔並通過 profile_lint\n", "")
    m2 = m2.replace("  - 讀懂 prompt-spec-validator 的 Drift Report 並決定該改規格還是改實作\n", "")
    y2.write_text(m2, encoding="utf-8")
    fails2 = lint_fails(bd2)
    assert any("與目錄名" in f for f in fails2)
    assert any("outcomes 需 2–5 條（現 1）" in f for f in fails2)


def test_published_book_requires_published_chapters(tmp_path):
    """邊界：書 status=published 但章節仍 draft → FAIL（不能把草稿掛上架）。"""
    bd = make_book(tmp_path, status="published")
    assert lint_fails(bd) == []
    p = bd / f"{CH}.md"
    p.write_text(p.read_text(encoding="utf-8").replace("status: published", "status: draft", 1), encoding="utf-8")
    assert any("書為 published 但章節" in f for f in lint_fails(bd))


@pytest.mark.xfail(strict=True, reason="BUG：book_lint.calibration_hit 是模組層全域 set、從不重置；"
                   "同一行程 lint 第二本書時沿用上一本的命中，漏報「_calibration.md 條目未反映」")
def test_calibration_hits_do_not_leak_between_books(tmp_path):
    """兩本書各有同一條 calibration；A 的章節有反映、B 沒有 → lint B 應 WARN。"""
    line = "人格不是形容詞要寫成資料這件事"
    a = make_book(tmp_path / "a")
    b = make_book(tmp_path / "b")
    for bd in (a, b):
        (bd / "_calibration.md").write_text(f"- {line}\n", encoding="utf-8")
    pa = a / f"{CH}.md"
    pa.write_text(pa.read_text(encoding="utf-8").replace("## 下一章\n", f"## 下一章\n\n{line}。\n", 1), encoding="utf-8")
    book_lint.lint_book(a, None)
    warns_b = [w for r in book_lint.lint_book(b, None) for w in r.warns]
    assert any("_calibration.md 條目未在任何章節反映" in w for w in warns_b)


# ── book_build ────────────────────────────────────


def test_build_stamps_and_detects_stale(tmp_path):
    """build 產 site/index.html 並嵌戳記 → --check OK；改章節 → STALE（exit 1）並點名該章；沒 build → NO-SITE。"""
    pytest.importorskip("markdown")
    bd = make_book(tmp_path)
    r = run("book_build.py", str(bd), "--check", "--json")
    assert r.returncode == 1 and json.loads(r.stdout)["status"] == "NO-SITE"
    r = run("book_build.py", str(bd))
    assert r.returncode == 0 and "pair: OK" in r.stdout
    site = (bd / "site" / "index.html").read_text(encoding="utf-8")
    assert f"content-src: {CH}.md sha256:" in site and "book-src: book.yaml" in site
    p = bd / f"{CH}.md"
    p.write_text(p.read_text(encoding="utf-8") + "\n補充一句。\n", encoding="utf-8")
    r = run("book_build.py", str(bd), "--check", "--json")
    res = json.loads(r.stdout)
    assert r.returncode == 1 and res["status"] == "STALE" and res["stale"] == [f"{CH}.md"]


# ── book_register ─────────────────────────────────


def test_register_rejects_stale_published_then_accepts_after_rebuild(tmp_path):
    """反例＋正常：published 書未 build（pair≠OK）→ REJECT exit 1、不寫 catalog；
    build 後登錄成功，重登同一本只更新不重複。"""
    pytest.importorskip("markdown")
    bd = make_book(tmp_path, status="published")
    lib = tmp_path / "library"
    r = run("book_register.py", str(bd), "--library", str(lib))
    assert r.returncode == 1 and "REJECT" in r.stdout
    assert not (lib / "catalog.json").exists()

    assert run("book_build.py", str(bd)).returncode == 0
    for _ in range(2):
        r = run("book_register.py", str(bd), "--library", str(lib))
        assert r.returncode == 0, r.stdout
    cat = json.loads((lib / "catalog.json").read_text(encoding="utf-8"))
    assert [b["slug"] for b in cat["books"]] == [SLUG]
    assert cat["books"][0]["lint"]["status"] == "PASS" and cat["books"][0]["pair"]["status"] == "OK"
    log_rows = [l for l in (lib / "log.md").read_text(encoding="utf-8").splitlines() if SLUG in l]
    assert [row.rsplit("|", 2)[-2].strip() for row in log_rows] == ["add", "update"]
