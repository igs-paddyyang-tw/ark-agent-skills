""".ark 工具中立佈局雙讀（ark-agent-os ≥ 2.2）：派工 prompt 的 SOUL 路徑跟著 agent 工作目錄的佈局走。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_plan as R  # noqa: E402

TASK = {"id": "T1", "name": "demo", "role": "coder", "output_file": "out.md", "ac_id": "AC-1", "ac": "存在"}
PLAN = {"frontmatter": {}, "plan": "plan.md"}


def _soul(ws: Path, ark: bool) -> Path:
    d = ws / "agents" / "coder-agent"
    if ark:
        (d / ".ark" / "brain").mkdir(parents=True)
        (d / ".ark" / "ark.yaml").write_text("schema: ark-workspace/1\n", encoding="utf-8")
        p = d / ".ark" / "brain" / "SOUL.md"
    else:
        (d / ".kiro" / "steering").mkdir(parents=True)
        p = d / ".kiro" / "steering" / "SOUL.md"
    p.write_text("# coder\n", encoding="utf-8")
    return p


def test_ark_layout_uses_brain(tmp_path: Path):
    soul = _soul(tmp_path, ark=True)
    assert str(soul) in R.build_prompt(TASK, PLAN, tmp_path, 1, None)


def test_legacy_layout_unchanged(tmp_path: Path):
    soul = _soul(tmp_path, ark=False)
    assert str(soul) in R.build_prompt(TASK, PLAN, tmp_path, 1, None)
