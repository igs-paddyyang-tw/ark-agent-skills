"""test_pl012_path_ref.py — PL-012「引用路徑不存在」規則的反證測試。

PL-012 用意：SKILL.md 提到的檔案路徑要真的存在（防斷鏈）。
但它不該誤判兩種東西：
  ① fenced code block（```bash）裡的命令 —— 那是教使用者在自己 repo 跑的，非本 skill 檔案引用
  ② glob 萬用字元路徑（team*.yaml）—— 實際檔存在，只是用 * 描述一組

反證方向：
  - 真斷鏈（正文引用不存在的 scripts/ghost.py）→ 必須報 PL-012
  - fence 內命令（scripts/sync_skills.py 不存在於本 skill）→ 不該報
  - glob（references/templates/team*.yaml，實際有 team.yaml.tpl）→ 不該報
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
LINT = SKILL_DIR / "scripts" / "prompt_lint.py"


def _make_skill(tmp_path: Path, body: str, extra_files: list[str] = ()) -> Path:
    """建一個最小 skill：SKILL.md + 指定的實體檔案。"""
    skill = tmp_path / "ark-fixture"
    (skill / "scripts").mkdir(parents=True)
    (skill / "references" / "templates").mkdir(parents=True)
    for rel in extra_files:
        f = skill / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x", encoding="utf-8")
    fm = ("---\nname: ark-fixture\ndescription: |\n  測試用 fixture skill。\n"
          "metadata:\n  category: executor\n  version: \"1.0\"\n---\n\n")
    (skill / "SKILL.md").write_text(fm + body, encoding="utf-8")
    return skill / "SKILL.md"


def _lint(skill_md: Path) -> str:
    r = subprocess.run([sys.executable, str(LINT), str(skill_md)],
                       capture_output=True, text=True)
    return r.stdout + r.stderr


def test_real_dangling_path_is_reported(tmp_path):
    """真斷鏈：正文引用不存在的 scripts/ghost.py → 必須報 PL-012。"""
    md = _make_skill(tmp_path, "# X\n\n見 `scripts/ghost.py` 的實作。\n")
    out = _lint(md)
    assert "PL-012" in out and "ghost.py" in out, f"真斷鏈未被抓：\n{out}"


def test_command_in_fenced_block_not_reported(tmp_path):
    """fence 內命令：scripts/sync_skills.py 是教使用者在自己 repo 跑的，不該報 PL-012。"""
    body = "# X\n\n上游同步：\n\n```bash\npython3 scripts/sync_skills.py --check\n```\n"
    md = _make_skill(tmp_path, body)
    out = _lint(md)
    assert "sync_skills.py" not in out, f"fence 內命令被誤判為斷鏈：\n{out}"


def test_glob_path_not_reported(tmp_path):
    """glob：references/templates/team*.yaml 實際有 team.yaml.tpl，不該報。"""
    body = "# X\n\n範本見 `references/templates/team*.yaml`。\n"
    md = _make_skill(tmp_path, body, extra_files=["references/templates/team.yaml.tpl"])
    out = _lint(md)
    assert "PL-012" not in out or "team" not in out, f"glob 路徑被誤判：\n{out}"
