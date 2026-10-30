"""ark-release-notes 行為測試 —— changelog_gen.py（git log → 分類 changelog，零 LLM）。

## 驗什麼

- 分類規則：Conventional Commits 的 type／scope／`!`／`BREAKING CHANGE` 歸類正確，
  非規範或未知 type 落 other。
- 解析：欄位用 \\x1f／\\x1e 切，commit 訊息含 `|`、多行 body 都不能切錯。
- 端到端：在 tmp_path 建臨時 git repo，跑 main() 寫檔，章節順序（breaking 最前、other 最後）與統計正確。
- 反例：沒有 commit 的 repo、不是 git repo → exit 1（不能產一份空 changelog 假裝成功）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import changelog_gen as cg  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=Tester", "-c", "user.email=t@example.com",
                    "-c", "commit.gpgsign=false", *args], cwd=repo, check=True, capture_output=True)


def _commit(repo: Path, fname: str, msg: str, lines: int = 1) -> None:
    (repo / fname).write_text("x\n" * lines, encoding="utf-8")
    _git(repo, "add", fname)
    _git(repo, "commit", "-q", "-m", msg)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """含 4 筆 commit 的臨時 repo，cwd 切過去（腳本對 cwd 跑 git）。"""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _commit(r, "a.txt", "chore: init")
    _commit(r, "b.txt", "feat(api): 新增報表端點", lines=3)
    _commit(r, "c.txt", "fix!: 改掉回傳格式", lines=2)
    _commit(r, "d.txt", "隨手修一下 | 沒照規範")
    monkeypatch.chdir(r)
    return r


# ── 分類規則（純函式）──────────────────────────────────────────

@pytest.mark.parametrize("subject,body,expected", [
    ("feat(api): add x", "", ("feat", "api", "add x")),
    ("fix: y", "", ("fix", "", "y")),
    ("refactor(core)!: drop z", "", ("breaking", "core", "drop z")),
    ("feat: w", "說明\n\nBREAKING CHANGE: 欄位改名", ("breaking", "", "w")),
    ("FEAT: upper", "", ("feat", "", "upper")),          # type 不分大小寫
    ("wip: unknown type", "", ("other", "", "unknown type")),
    ("Merge branch 'x'", "", ("other", "", "Merge branch 'x'")),
    ("Merge branch 'x'", "BREAKING-CHANGE: y", ("breaking", "", "Merge branch 'x'")),
])
def test_classify(subject, body, expected):
    """各種標題／body 組合的歸類 —— breaking 優先於 type。"""
    assert cg._classify(subject, body) == expected


def test_parse_commits_handles_pipes_and_multiline_body():
    """subject 含 `|`、body 多行時，以 \\x1f／\\x1e 切欄位仍正確；sha 截 7 碼；殘缺紀錄略過。"""
    raw = ("a" * 40 + "\x1fAlice\x1ffeat(ui): a | b\x1fline1\nline2\x1e\n"
           + "b" * 40 + "\x1fBob\x1fdocs: readme\x1f\x1e\n"
           + "broken-record\x1e")
    cs = cg.parse_commits(raw)
    assert [c["sha"] for c in cs] == ["aaaaaaa", "bbbbbbb"]
    assert cs[0] == {"sha": "aaaaaaa", "author": "Alice", "section": "feat",
                     "scope": "ui", "subject": "a | b"}


# ── 端到端 ───────────────────────────────────────────────────

def test_end_to_end_writes_ordered_changelog(repo, capsys):
    """--last 3 --output：只含最近 3 筆、breaking 在最前、other 在最後、統計正確。"""
    out = repo / "CHANGELOG.md"
    assert cg.main(["--last", "3", "--output", str(out)]) == 0
    md = out.read_text(encoding="utf-8")
    assert "init" not in md, "--last 3 不該含第 1 筆"
    i_brk, i_feat, i_other = (md.index("💥 Breaking Changes"), md.index("✨ Features"), md.index("📌 Other"))
    assert i_brk < i_feat < i_other
    assert "- **api**: 新增報表端點 (`" in md
    assert "- Commits：3" in md
    assert "- 檔案變動：3" in md          # b/c/d 三個檔
    assert "- 行數變動：6" in md          # 3 + 2 + 1 行新增
    assert "- 貢獻者（1）：Tester" in md
    assert "已寫入" in capsys.readouterr().out


def test_range_selects_only_commits_in_range(repo, capsys):
    """--range HEAD~1..HEAD 只取最後一筆（非規範 commit → other）。"""
    assert cg.main(["--range", "HEAD~1..HEAD"]) == 0
    md = capsys.readouterr().out
    assert "- Commits：1" in md and "📌 Other" in md and "✨ Features" not in md


# ── 反例 ─────────────────────────────────────────────────────

def test_empty_repo_returns_1(tmp_path, monkeypatch, capsys):
    """還沒有任何 commit 的 repo → git log 失敗 → exit 1，不產檔。"""
    _git(tmp_path, "init", "-q")
    monkeypatch.chdir(tmp_path)
    assert cg.main(["--last", "5", "--output", str(tmp_path / "C.md")]) == 1
    assert not (tmp_path / "C.md").exists()


def test_not_a_git_repo_returns_1(tmp_path, monkeypatch, capsys):
    """不是 git repo → exit 1，stderr 說明 git log 失敗。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    assert cg.main(["--last", "1"]) == 1
    assert "git log 失敗" in capsys.readouterr().err


def test_mutually_exclusive_range_flags():
    """--last 與 --range 互斥 → argparse 直接以 exit 2 拒絕。"""
    with pytest.raises(SystemExit) as ei:
        cg.main(["--last", "1", "--range", "a..b"])
    assert ei.value.code == 2


# ── 邊界 ─────────────────────────────────────────────────────

@pytest.mark.xfail(strict=True, reason=(
    "_diff_stat 用 `HEAD~N..HEAD` 算統計；--last N 涵蓋到第一筆 commit 時 HEAD~N 不存在，"
    "例外被吞掉回 (0, 0) → changelog 寫「檔案變動：0」，與實際不符"))
def test_last_n_covering_root_commit_reports_real_stats(repo, capsys):
    """--last 4（= 全部歷史）時，統計應反映 4 個檔案的變動，而不是 0。"""
    assert cg.main(["--last", "4"]) == 0
    md = capsys.readouterr().out
    assert "- Commits：4" in md
    assert "- 檔案變動：4" in md
