""".ark 工具中立佈局雙讀（ark-agent-os ≥ 2.2）：skills-matrix 的版本鎖位置跟著佈局走。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import validate_team as V  # noqa: E402

TEAM = "instances:\n  a-agent:\n    role: manager\n    working_directory: .\nhealth_port: 23999\n"


def _team(tmp: Path, ark: bool) -> Path:
    (tmp / "team.yaml").write_text(TEAM, encoding="utf-8")
    (tmp / "skills-matrix.yaml").write_text("agents: {}\n", encoding="utf-8")
    if ark:
        (tmp / ".ark").mkdir()
        (tmp / ".ark" / "ark.yaml").write_text("schema: ark-workspace/1\n", encoding="utf-8")
    return tmp / "team.yaml"


def _lock_errors(path: Path) -> list[str]:
    return [e for e in V.validate(path) if "skills-matrix" in e]


def test_ark_layout_wants_ark_lock(tmp_path: Path):
    p = _team(tmp_path, ark=True)
    assert any(".ark/skills.lock" in e for e in _lock_errors(p))
    (tmp_path / ".ark" / "skills.lock").write_text("{}", encoding="utf-8")
    assert _lock_errors(p) == []


def test_legacy_layout_unchanged(tmp_path: Path):
    p = _team(tmp_path, ark=False)
    assert any(".kiro/skills.lock.json" in e for e in _lock_errors(p))
    (tmp_path / ".kiro").mkdir()
    (tmp_path / ".kiro" / "skills.lock.json").write_text("{}", encoding="utf-8")
    assert _lock_errors(p) == []
