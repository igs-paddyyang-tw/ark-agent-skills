""".ark 佈局雙讀（S2 T2.1）：佈局判定、mirror_sync 落點、align_sync 鎖檔與驗證狀態檔。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import align_sync as A  # noqa: E402
import ark_layout as L  # noqa: E402
import mirror_sync as M  # noqa: E402


def _ark(root: Path) -> Path:
    (root / ".ark").mkdir(parents=True, exist_ok=True)
    (root / ".ark" / "ark.yaml").write_text("schema: ark-workspace/1\n", encoding="utf-8")
    return root


def test_legacy_when_no_ark(tmp_path: Path):
    assert L.find_ark_dirs(tmp_path) == (L.LEGACY, tmp_path / ".kiro")
    assert L.skills_dir(tmp_path) == tmp_path / ".kiro" / "skills"
    assert L.lock_path(tmp_path) == tmp_path / ".kiro" / "skills.lock.json"
    assert L.verify_path(tmp_path) == tmp_path / ".kiro" / "skills.verify.json"
    assert "尚未遷移" in L.layout_note(tmp_path)


def test_ark_when_manifest_exists(tmp_path: Path):
    _ark(tmp_path)
    (tmp_path / ".kiro" / "skills").mkdir(parents=True)        # 舊目錄還在 → 以 .ark 為準
    assert L.find_ark_dirs(tmp_path) == (L.ARK, tmp_path / ".ark")
    assert L.skills_dir(tmp_path) == tmp_path / ".ark" / "skills"
    assert L.lock_path(tmp_path) == tmp_path / ".ark" / "skills.lock"
    assert L.verify_path(tmp_path) == tmp_path / ".ark" / "runtime" / "skills.verify.json"


def test_ark_dir_without_manifest_is_legacy(tmp_path: Path):
    """遷移到一半（只建了 .ark/）不算已遷移。"""
    (tmp_path / ".ark" / "skills").mkdir(parents=True)
    assert L.find_ark_dirs(tmp_path)[0] == L.LEGACY


def test_mirror_sync_picks_one_dir_per_workspace(tmp_path: Path):
    (tmp_path / ".kiro" / "skills").mkdir(parents=True)                 # 根：legacy
    a = _ark(tmp_path / "projects" / "a")                               # a：已遷移，舊目錄殘留
    (a / ".ark" / "skills").mkdir()
    (a / ".kiro" / "skills").mkdir(parents=True)
    b = tmp_path / "projects" / "b"                                     # b：legacy
    (b / ".kiro" / "skills").mkdir(parents=True)
    c = tmp_path / "projects" / "c"                                     # c：symlink 跳過
    c.mkdir()
    (c / ".kiro").mkdir()
    (c / ".kiro" / "skills").symlink_to(tmp_path / ".kiro" / "skills")
    got = M.skill_dirs(tmp_path)
    assert got == [tmp_path / ".kiro" / "skills", a / ".ark" / "skills", b / ".kiro" / "skills"]


def test_align_sync_lock_follows_layout(tmp_path: Path):
    _ark(tmp_path)
    A.save_lock(tmp_path, {"agents": {"x": {}}})
    assert (tmp_path / ".ark" / "skills.lock").is_file()
    assert not (tmp_path / ".kiro").exists()
    assert A.load_lock(tmp_path) == {"agents": {"x": {}}}


def test_align_sync_lock_legacy_unchanged(tmp_path: Path):
    A.save_lock(tmp_path, {"agents": {}})
    assert json.loads((tmp_path / ".kiro" / "skills.lock.json").read_text(encoding="utf-8")) == {"agents": {}}
    assert not (tmp_path / ".ark").exists()
