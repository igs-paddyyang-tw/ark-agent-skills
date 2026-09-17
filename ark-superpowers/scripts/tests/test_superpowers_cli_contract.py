#!/usr/bin/env python3
"""test_cli_contract.py — build_docs.py / doc_lint.py 的 CLI 契約（補 F-11）。

build_docs.py 與 check_doc_completeness.py 的註解都引用這支測試「在驗」，但它先前不存在。
W0 補上，鎖定：
  - build_docs new 產物的工具型 placeholder 零殘留（消 F-2，new/upgrade 兩路徑一致）
  - 八型骨架跑 doc_lint 皆 exit 2（骨架必 FAIL，ADR-001）
  - build_docs --help 不產檔（唯讀）
  - 非 ASCII 標題無 --slug → exit 1（不靜默產亂碼檔名）
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
BUILD = SCRIPTS / "build_docs.py"
DOC_LINT = SCRIPTS / "doc_lint.py"

TOOL_PLACEHOLDER = re.compile(r"\{名稱\}|\{專案名稱\}|\{Project Name\}|\{作者\}|\{Author\}")
# new 的八型（build_docs TEMPLATE_MAP）
TYPES = ["spec", "design", "plan", "spec-onepager", "design-onepager",
         "plan-onepager", "onepager", "adr"]


def _run(argv, cwd):
    return subprocess.run([sys.executable, str(BUILD), *argv],
                          capture_output=True, text=True, cwd=str(cwd))


@pytest.fixture()
def project(tmp_path):
    _run(["--init"], tmp_path)
    return tmp_path


def _all_docs(project):
    return list((project / "docs").rglob("*.md"))


# ── F-2：工具型 placeholder 零殘留（new 路徑）──────────────────

@pytest.mark.parametrize("dtype", TYPES)
def test_new_leaves_no_tool_placeholder(project, dtype):
    r = _run([dtype, "Auth System"], project)
    assert r.returncode == 0, f"{dtype} 產出失敗：{r.stderr}"
    for md in _all_docs(project):
        hit = TOOL_PLACEHOLDER.findall(md.read_text(encoding="utf-8"))
        assert not hit, f"{dtype} → {md.name} 殘留工具型 placeholder：{hit}"


def test_en_new_leaves_no_tool_placeholder(project):
    r = _run(["--lang", "en", "spec", "Billing"], project)
    assert r.returncode == 0
    md = project / "docs" / "specs" / "billing-spec.md"
    assert not TOOL_PLACEHOLDER.findall(md.read_text(encoding="utf-8"))


# ── ADR-001：八型骨架 doc_lint 必 exit 2 ──────────────────────

@pytest.mark.parametrize("dtype", TYPES)
def test_skeleton_fails_doc_lint(project, dtype):
    _run([dtype, "Auth System"], project)
    # 找剛產出的檔（該型的最新，排除 adr 的 _index.md 索引）
    docs = sorted((p for p in _all_docs(project) if p.name != "_index.md"),
                  key=lambda p: p.stat().st_mtime)
    target = docs[-1]
    r = subprocess.run([sys.executable, str(DOC_LINT), str(target)],
                       capture_output=True, text=True)
    assert r.returncode == 2, f"{dtype} 骨架未被 doc_lint 擋下（exit {r.returncode}），應為 2：\n{r.stdout}"


# ── CLI 契約 ──────────────────────────────────────────────────

def test_help_does_not_create_files(tmp_path):
    before = set(tmp_path.rglob("*"))
    _run(["--help"], tmp_path)
    after = set(tmp_path.rglob("*"))
    assert before == after, "--help 不該產生任何檔案"


def test_non_ascii_title_without_slug_exits_nonzero(project):
    r = _run(["spec", "認證系統"], project)  # 中文標題、無 --slug
    assert r.returncode != 0, "非 ASCII 標題無 --slug 應 exit≠0（避免亂碼檔名）"
