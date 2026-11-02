"""2.4.4：kiro 信任工具名對齊 kiro-cli 2.34（新舊名並列）。

2026-11-02 實測 kiro-cli 2.34.2：只信任 `fs_read` → 讀工作區外的檔被擋（背景 job 的 prompt 檔在 ~/.ark/agent-jobs/）；`read_file` → 可讀；
新舊名混用可讀、寫入仍被擋。反證：換回 2.4.3 的映射 → 第一條紅。
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import agent_common as C  # noqa: E402


def _trusted(access):
    argv, _, _ = C.build_argv("kiro", "p", access=access, prompt_file=pathlib.Path("/tmp/_k.md"))
    flag = next(a for a in argv if a.startswith("--trust-tools="))
    return set(flag.split("=", 1)[1].split(","))


def test_read_only_trusts_new_and_old_read_names():
    t = _trusted("read-only")
    assert {"read_file", "fs_read"} <= t, "kiro 2.34 讀檔是 read_file；舊版 fs_read"
    assert not {"fs_write", "str_replace", "execute_bash", "fs_append"} & t, "唯讀不得信任寫入／執行"


def test_workspace_adds_write_tools():
    t = _trusted("workspace")
    assert _trusted("read-only") <= t and {"fs_write", "str_replace"} <= t
