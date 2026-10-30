"""ark-md-report 行為測試：report_lint 契約守門、report_pair 雙軌戳記、report_register 索引與 log。

以一份最小合法的 review 報告為基準，逐項改壞，確認 lint 會擋（FAIL → exit 1），
WARN 類問題不影響 exit code。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import report_lint  # noqa: E402
import report_pair  # noqa: E402

GOOD = """---
title: "ark-foo review"
type: review
subject: ark-foo
date: 2026-10-30
author: claude-code
source_skill: ark-md-report
verdict: needs-work
confidence: high
tags: [skill-review]
sources: [ark-foo/SKILL.md]
findings: {p0: 0, p1: 1, p2: 1, p3: 0}
---

# ark-foo review

## Verdict

needs-work：ark-foo 的錯誤路徑沒有測試。

## Findings

| ID | 嚴重度 | 標題 |
|---|---|---|
| F-1 | P1 | ark-foo 解析失敗時 exit 0 |
| F-2 | P2 | ark-foo 說明文字過長 |

## Evidence

- E-1：實跑 `foo.py bad.json` 回 0，支持 F-1

## Actions

| ID | 動作 | 對應 Finding |
|---|---|---|
| A-1 | 失敗改 exit 1 | F-1 |

## 邊界聲明

只審 ark-foo 1.0.0。
"""


def lint(tmp_path: Path, text: str, name: str = "2026-10-30-ark-foo-review.md"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return report_lint.check_file(p)


def run_cli(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True, timeout=30)


# ── report_lint ─────────────────────────────────────


def test_lint_passes_minimal_valid_review(tmp_path):
    """正常路徑：契約齊全的 review 報告零 FAIL、零 WARN，CLI exit 0。"""
    fails, warns = lint(tmp_path, GOOD)
    assert fails == [] and warns == []
    p = tmp_path / "2026-10-30-ark-foo-review.md"
    assert run_cli("report_lint.py", str(p)).returncode == 0


@pytest.mark.parametrize("old,new,expect", [
    ("verdict: needs-work", "verdict: ok", "verdict 'ok' 不在 review 型枚舉"),
    ("p1: 1, p2: 1", "p1: 2, p2: 1", "findings.p1=2"),
    ("支持 F-1", "支持 F-9", "F-1（P1）無對應 Evidence"),
    ("| F-2 | P2 |", "| F-3 | P2 |", "ID 不連續"),
    ("| A-1 | 失敗改 exit 1 | F-1 |", "| A-1 | 失敗改 exit 1 | F-7 |", "引用不存在的 F-7"),
    ("只審 ark-foo 1.0.0。", "如上所述，只審 1.0.0。", "如上所述"),
    ("## 邊界聲明", "## 其他", "缺少必要章節：## 邊界聲明"),
    ("confidence: high", "confidence: sure", "confidence 必須是"),
], ids=["verdict-enum", "severity-count", "p1-no-evidence", "id-gap", "action-dangling-ref",
        "forbidden-phrase", "missing-section", "confidence-enum"])
def test_lint_rejects_contract_violations(tmp_path, old, new, expect):
    """反例：每種契約違規都要 FAIL，且訊息指出是哪一條（可行動）。"""
    assert old in GOOD
    fails, _ = lint(tmp_path, GOOD.replace(old, new))
    assert any(expect in f for f in fails), fails


def test_lint_cli_exit_1_on_fail_and_warn_only_stays_0(tmp_path):
    """邊界：FAIL → exit 1；只有 WARN（檔名不符、高風險指涉詞）→ exit 0。"""
    bad = tmp_path / "2026-10-30-bad.md"
    bad.write_text(GOOD.replace("type: review", "type: essay"), encoding="utf-8")
    r = run_cli("report_lint.py", str(bad))
    assert r.returncode == 1 and "type 不在枚舉" in r.stdout

    warn = tmp_path / "Report_Final.md"
    warn.write_text(GOOD.replace("只審 ark-foo 1.0.0。", "前者只審 1.0.0。"), encoding="utf-8")
    r = run_cli("report_lint.py", str(warn))
    assert r.returncode == 0 and r.stdout.count("WARN") == 2


def test_lint_missing_frontmatter_and_tag_whitelist(tmp_path):
    """反例：沒有 frontmatter 直接 FAIL；給 wiki schema 時 tags 不在白名單也 FAIL。"""
    assert lint(tmp_path, "# 沒有 frontmatter\n")[0] == ["缺少 frontmatter"]
    schema = tmp_path / "schema.md"
    schema.write_text("## tags 白名單\n- `skill-review`\n- `incident`\n", encoding="utf-8")
    tags = report_lint.load_wiki_tags(schema)
    assert tags == {"skill-review", "incident"}
    p = tmp_path / "2026-10-30-x.md"
    p.write_text(GOOD.replace("tags: [skill-review]", "tags: [skill-review, made-up]"), encoding="utf-8")
    fails, _ = report_lint.check_file(p, tags)
    assert any("made-up" in f for f in fails)


# ── report_pair ─────────────────────────────────────


def test_pair_stamp_ok_then_stale_after_md_edit(tmp_path):
    """stamp 後 check=OK；MD 改一個字 → STALE（exit 1）；HTML 無戳記 → NO-STAMP；無 HTML → NO-HTML（exit 0）。"""
    md = tmp_path / "reports" / "2026-10-30-x.md"
    md.parent.mkdir()
    md.write_text(GOOD, encoding="utf-8")
    assert report_pair.check(md, quiet=True) == "NO-HTML"
    assert run_cli("report_pair.py", "check", str(md)).returncode == 0

    html = md.with_suffix(".html")
    html.write_text("<html><body>x</body></html>", encoding="utf-8")
    assert report_pair.check(md, quiet=True) == "NO-STAMP"

    report_pair.stamp(md, html)
    assert report_pair.check(md, quiet=True) == "OK"
    report_pair.stamp(md, html)  # 重複 stamp 只更新、不疊加
    assert html.read_text(encoding="utf-8").count("content-src:") == 1

    md.write_text(GOOD + "\n補一句", encoding="utf-8")
    assert report_pair.check(md, quiet=True) == "STALE"
    assert run_cli("report_pair.py", "check", str(md)).returncode == 1


# ── report_register ─────────────────────────────────


def test_register_appends_log_once_and_builds_index(tmp_path):
    """log.md 依 9 欄契約追加且重跑不重複；_index.md 依 type 分組列出。"""
    md = tmp_path / "docs" / "reports" / "review" / "2026-10-30-ark-foo-review.md"
    md.parent.mkdir(parents=True)
    md.write_text(GOOD, encoding="utf-8")
    for _ in range(2):
        assert run_cli("report_register.py", str(md)).returncode == 0
    root = tmp_path / "docs" / "reports"
    rows = [l for l in (root / "log.md").read_text(encoding="utf-8").splitlines() if l.startswith("2026-")]
    assert len(rows) == 1
    cols = [c.strip() for c in rows[0].split("|")]
    assert cols[:8] == ["2026-10-30", "review", "ark-foo", "needs-work", "0", "1", "1", "-"]
    index = (root / "_index.md").read_text(encoding="utf-8")
    assert "## review" in index and "| 0/1/1 |" in index


def test_register_rejects_report_without_frontmatter(tmp_path):
    """反例：沒有 frontmatter 的檔案不可註冊（exit 1、不建 log.md）。"""
    md = tmp_path / "reports" / "2026-10-30-x.md"
    md.parent.mkdir()
    md.write_text("# 無 frontmatter\n", encoding="utf-8")
    r = run_cli("report_register.py", str(md))
    assert r.returncode == 1
    assert not (tmp_path / "reports" / "log.md").exists()
