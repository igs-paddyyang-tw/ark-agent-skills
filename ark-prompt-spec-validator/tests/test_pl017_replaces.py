"""test_pl017_replaces.py — PL-017「引用已 deprecated 的 skill」不該誤判自己 replaces 列的舊名。

反證方向：
  - 正文提到別人的 deprecated skill → 必須報 PL-017
  - 提到自己 metadata.replaces 宣告取代的舊名 → 不該報（與 audit AL-016／AL-032 同判準）
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
LINT = SKILL_DIR / "scripts" / "prompt_lint.py"


def _skill(repo: Path, name: str, body: str, meta: str = "") -> Path:
    d = repo / name
    d.mkdir(parents=True)
    f = d / "SKILL.md"
    f.write_text(f"---\nname: {name}\ndescription: |\n  測試用。使用此 skill 當測試。不適用於：其他。\n"
                 f"metadata:\n  version: \"1.0.0\"\n{meta}---\n\n# {name}\n\n{body}\n", encoding="utf-8")
    return f


def _pl017(repo: Path, target: Path, tmp_path: Path) -> list[str]:
    out = tmp_path / "r.json"
    subprocess.run([sys.executable, str(LINT), "--type", "skill", "--repo", str(repo),
                    "--json", str(out), str(target)], capture_output=True, text=True)
    return [f["message"] for f in json.loads(out.read_text(encoding="utf-8"))["findings"]
            if (f.get("rule") or f.get("id")) == "PL-017"]


def test_replaced_names_are_exempt_but_others_are_not(tmp_path):
    repo = tmp_path / "repo"
    for old in ("ark-old", "ark-other-old"):
        _skill(repo, old, "轉址。", "  status: deprecated\n")
    target = _skill(repo, "ark-new", "原 ark-old 併入。另見 ark-other-old。", "  replaces: [ark-old]\n")
    msgs = _pl017(repo, target, tmp_path)
    assert not any("ark-old" in m and "other" not in m for m in msgs), msgs
    assert any("ark-other-old" in m for m in msgs), "沒有 replaces 的 deprecated 引用必須仍被報"
