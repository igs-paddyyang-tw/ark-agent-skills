"""align_sync apply（v2 規格 AC-11／AC-13）：從上游**列車 commit** 取檔、驗 tree_hash、寫 lock。

用假的上游 git repo＋假 team，不碰網路也不碰真的 projects/。
關鍵情境：列車之後上游又有新 commit 改了 skill —— apply 必須裝「列車那一版」，不是最新的 working tree。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
import gen_manifest  # noqa: E402

PY = sys.executable


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def _skill(repo: Path, name: str, version: str, body: str = "") -> None:
    d = repo / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: 測試\nmetadata:\n  version: \"{version}\"\n  status: active\n---\n# {name}\n{body}\n",
        encoding="utf-8")


@pytest.fixture()
def world(tmp_path):
    """上游：r1 列車（ark-base 1.0.0、ark-qa 1.0.0）→ 之後又改了 ark-qa（未發列車）。"""
    up = tmp_path / "upstream"
    up.mkdir()
    _git(up, "init", "-q")
    _git(up, "config", "user.email", "t@t")
    _git(up, "config", "user.name", "t")
    _skill(up, "ark-base", "1.0.0")
    _skill(up, "ark-qa", "1.0.0", "列車版內容")
    rsm = up / gen_manifest.ROLE_MAP
    rsm.parent.mkdir(parents=True)
    rsm.write_text("base_skills: [ark-base]\nrole_skills:\n  qa: [ark-qa]\n", encoding="utf-8")
    _git(up, "add", "-A")
    _git(up, "commit", "-qm", "content")
    manifest, _ = gen_manifest.build(up, "r1", out_dir=tmp_path / "out")
    mf = up / "ark-skills-align" / "release" / "manifest.json"
    mf.parent.mkdir(parents=True)
    mf.write_text(json.dumps(manifest), encoding="utf-8")
    _git(up, "add", "-A")
    _git(up, "commit", "-qm", "train r1")
    release_sha = _git(up, "rev-parse", "HEAD")
    _skill(up, "ark-qa", "1.0.0", "列車之後才改的內容（不該被裝）")
    _git(up, "commit", "-qam", "after train")

    team = tmp_path / "team"
    team.mkdir()
    served = tmp_path / "served-manifest.json"          # 模擬 raw.githubusercontent 上的 manifest
    served.write_text(json.dumps(manifest), encoding="utf-8")
    (team / "skills-matrix.yaml").write_text(yaml.safe_dump({
        "upstream": {"manifest_url": served.as_uri(), "release": "r1", "local_clone": str(up)},
        "agents": {"qa-agent": {"role": "qa", "wave": 1}},
    }), encoding="utf-8")
    return up, team, served, release_sha


def _run(team: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, str(SCRIPTS / "align_sync.py"), *args], cwd=team, capture_output=True, text=True)


def test_without_yes_lists_and_exits_10(world):
    _, team, _, _ = world
    r = _run(team, "apply", "--wave", "1")
    assert r.returncode == 10 and "ark-qa" in r.stdout
    assert not (team / ".kiro" / "skills").exists(), "沒帶 --yes 不得動檔"


def test_apply_installs_release_content_and_writes_lock(world):
    _, team, _, release_sha = world
    r = _run(team, "apply", "--wave", "1", "--yes")
    assert r.returncode == 0, r.stdout + r.stderr
    qa = (team / ".kiro" / "skills" / "ark-qa" / "SKILL.md").read_text(encoding="utf-8")
    assert "列車版內容" in qa and "不該被裝" not in qa, "裝到的是上游最新內容，不是列車那一版（AC-13）"
    lock = json.loads((team / ".kiro" / "skills.lock.json").read_text(encoding="utf-8"))
    entry = lock["agents"]["qa-agent"]["ark-qa"]
    assert lock["release"] == "r1" and entry["version"] == "1.0.0" and entry["tier"] == "role"
    assert entry["source"] == f"upstream@{release_sha[:7]}"
    assert set(lock["agents"]["qa-agent"]) == {"ark-base", "ark-qa"}
    assert _run(team, "plan").returncode == 0, "apply 後 plan 應無差異"


def test_tree_hash_mismatch_is_refused_and_keeps_existing(world):
    _, team, served, _ = world
    m = json.loads(served.read_text(encoding="utf-8"))
    m["skills"]["ark-qa"]["tree_hash"] = "sha256:" + "0" * 64       # 模擬 manifest 與內容對不上
    served.write_text(json.dumps(m), encoding="utf-8")
    old = team / ".kiro" / "skills" / "ark-qa"
    old.mkdir(parents=True)
    (old / "SKILL.md").write_text("原本的版本", encoding="utf-8")
    r = _run(team, "apply", "--wave", "1", "--yes")
    assert r.returncode == 1 and "tree_hash 與 manifest 不符" in r.stdout
    assert (old / "SKILL.md").read_text(encoding="utf-8") == "原本的版本", "驗證失敗卻動了原目錄"
    assert (team / ".kiro" / "skills" / "ark-base" / "SKILL.md").is_file(), "其他 skill 應照常安裝"


def test_release_missing_from_upstream_history_is_exit_2(world):
    _, team, served, _ = world
    m = json.loads(served.read_text(encoding="utf-8"))
    m["release"] = "r9-not-fetched"
    served.write_text(json.dumps(m), encoding="utf-8")
    r = _run(team, "apply", "--wave", "1", "--yes")
    assert r.returncode == 2 and "git fetch" in r.stderr


def test_find_release_commit_ignores_untrusted_commit_field(world):
    """manifest 的 commit 欄位可能是 amend 前的孤兒 —— 找 release 只看歷史裡 manifest 的內容。"""
    up, _, _, release_sha = world
    import align_sync
    assert align_sync.find_release_commit(up, "r1") == release_sha
    assert align_sync.find_release_commit(up, "nope") is None
