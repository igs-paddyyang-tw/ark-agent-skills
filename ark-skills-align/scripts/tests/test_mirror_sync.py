"""mirror_sync.py 驗收（references/mirror-sync.md §驗收 1~7）—— 合成上游 repo 與 team 樹。"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
import mirror_sync as M  # noqa: E402

SKILL_V = '---\nname: ark-demo\nmetadata:\n  version: "{v}"\n---\n# demo {v}\n'


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture()
def env(tmp_path: Path):
    """上游兩個 commit：1.0.0（含 old.py）→ 1.1.0（old.py 移除、run.py 改版）。"""
    up = tmp_path / "skills"
    sk = up / "ark-demo"
    (sk / "scripts").mkdir(parents=True)
    _git(up, "init", "-q")
    _git(up, "config", "user.email", "t@t")
    _git(up, "config", "user.name", "t")
    (sk / "SKILL.md").write_text(SKILL_V.format(v="1.0.0"), encoding="utf-8")
    (sk / "scripts" / "run.py").write_text("print('v1')\n", encoding="utf-8")
    (sk / "scripts" / "old.py").write_text("old\n", encoding="utf-8")
    _git(up, "add", "-A")
    _git(up, "commit", "-q", "-m", "v1")
    v1 = tmp_path / "v1-snapshot"
    shutil.copytree(sk, v1)
    (sk / "SKILL.md").write_text(SKILL_V.format(v="1.1.0"), encoding="utf-8")
    (sk / "scripts" / "run.py").write_text("print('v1.1')\n", encoding="utf-8")
    (sk / "scripts" / "old.py").unlink()
    _git(up, "add", "-A")
    _git(up, "commit", "-q", "-m", "v1.1")
    (up / ".gitignore").write_text("ark-demo/scripts/.index/\n", encoding="utf-8")
    _git(up, "add", ".gitignore")
    _git(up, "commit", "-q", "-m", "ignore")
    # 上游工作樹的未追蹤產物（驗收 6）
    (sk / "scripts" / ".index").mkdir()
    (sk / "scripts" / ".index" / "junk.json").write_text("{}", encoding="utf-8")
    team = tmp_path / "team"
    return up, v1, team


def _place(team: Path, sub: str, src: Path) -> Path:
    dst = team / sub / ".kiro" / "skills" / "ark-demo"
    shutil.copytree(src, dst)
    return dst


def _tracked_upstream(up: Path) -> dict[str, bytes]:
    return {k: v.read_bytes() for k, v in M._files(up / "ark-demo").items() if ".index" not in k}


def test_stale_copy_aligned_and_untracked_not_copied(env):
    up, v1, team = env
    local = _place(team, ".", v1)
    [r] = M.run(up, team, [], None, do_apply=False)
    assert r.status == "STALE" and r.obsolete == ["scripts/old.py"]
    M.run(up, team, [], None, do_apply=True)
    got = {k: v.read_bytes() for k, v in M._files(local).items()}
    assert got == _tracked_upstream(up), "apply 後應與上游 HEAD 逐檔相同"
    assert not (local / "scripts" / ".index").exists(), "上游未追蹤產物不可帶入"


def test_local_data_preserved(env):
    up, v1, team = env
    local = _place(team, "projects/a", v1)
    (local / "artifacts").mkdir()
    (local / "artifacts" / "shot.png").write_bytes(b"\x89PNG-local")
    [r] = M.run(up, team, [], None, do_apply=True)
    assert r.status == "STALE" and r.local_data == ["artifacts/shot.png"]
    assert (local / "artifacts" / "shot.png").read_bytes() == b"\x89PNG-local"
    assert not (local / "scripts" / "old.py").exists()


def test_local_modification_blocks_skill(env):
    up, v1, team = env
    local = _place(team, ".", v1)
    (local / "scripts" / "run.py").write_text("print('aikb fix')\n", encoding="utf-8")
    [r] = M.run(up, team, [], None, do_apply=True)
    assert r.status == "LOCAL" and r.local_mod == ["scripts/run.py"]
    assert (local / "scripts" / "run.py").read_text(encoding="utf-8") == "print('aikb fix')\n", "LOCAL 不可覆蓋"
    assert (local / "scripts" / "old.py").exists(), "LOCAL 整個 skill 都不動"


def test_keep_preserves_modified_file(env):
    up, v1, team = env
    local = _place(team, ".", v1)
    (local / "scripts" / "run.py").write_text("registry\n", encoding="utf-8")
    [r] = M.run(up, team, ["scripts/run.py"], None, do_apply=True)
    assert r.status == "STALE" and r.keep == ["scripts/run.py"]
    assert (local / "scripts" / "run.py").read_text(encoding="utf-8") == "registry\n"
    assert "1.1.0" in (local / "SKILL.md").read_text(encoding="utf-8")


def test_newer_local_version_untouched(env):
    up, v1, team = env
    local = _place(team, ".", v1)
    (local / "SKILL.md").write_text(SKILL_V.format(v="2.0.0"), encoding="utf-8")
    [r] = M.run(up, team, [], None, do_apply=True)
    assert r.status == "NEWER"
    assert "2.0.0" in (local / "SKILL.md").read_text(encoding="utf-8")


def test_same_copy_not_reported(env):
    up, _, team = env
    dst = team / ".kiro" / "skills" / "ark-demo"
    dst.parent.mkdir(parents=True)
    for rel, data in _tracked_upstream(up).items():
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        (dst / rel).write_bytes(data)
    assert M.run(up, team, [], None, do_apply=False) == []


def test_apply_requires_yes_and_bad_upstream(env, tmp_path):
    up, v1, team = env
    _place(team, ".", v1)
    assert M.main(["apply", "--upstream", str(up), "--target", str(team)]) == 2
    assert M.main(["plan", "--upstream", str(tmp_path / "nope"), "--target", str(team)]) == 3


def test_help_is_readonly(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPTS / "mirror_sync.py"), "--help"],
                       cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0 and "mirror_sync" in r.stdout
    assert list(tmp_path.iterdir()) == []


def test_local_ignored_artifacts_not_preserved(env):
    """本地跑測試產生、上游 .gitignore 命中的檔 → 不算本地資料，對齊後不留。"""
    up, v1, team = env
    local = _place(team, ".", v1)
    (local / "scripts" / ".index").mkdir()
    (local / "scripts" / ".index" / "manifest.json").write_text("{}", encoding="utf-8")
    [r] = M.run(up, team, [], None, do_apply=True)
    assert r.local_data == [], f"ignored 產物被當成本地資料：{r.local_data}"
    assert not (local / "scripts" / ".index").exists()
