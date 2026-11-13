"""align_sync 角色集合：manifest 必須帶 tiers_default，拉不到就大聲失敗（2026-10-30）。

背景：align_sync 一直讀 manifest 的 tiers_default，但 gen_manifest 從沒產過；
拉不到 manifest 時也照常往下算 → 目標集合只剩 extra，plan 看起來「差異很少」。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parent.parent
REPO = SCRIPTS.parent.parent
sys.path.insert(0, str(SCRIPTS))
import gen_manifest  # noqa: E402


def test_manifest_carries_role_map_verbatim():
    rsm = yaml.safe_load((REPO / gen_manifest.ROLE_MAP).read_text(encoding="utf-8"))
    td = gen_manifest.tiers_default(REPO)
    assert td["base"] == rsm["base_skills"] and td["base"], "base 不可為空（掃描範圍是空的）"
    assert td["role"] == rsm["role_skills"]


def test_build_puts_tiers_default_into_manifest(tmp_path):
    manifest, _ = gen_manifest.build(REPO, "r-test", out_dir=tmp_path)
    assert manifest["tiers_default"] == gen_manifest.tiers_default(REPO)


def _team(tmp_path: Path, manifest: dict | None, url: str | None = None) -> Path:
    team = tmp_path / "team"
    team.mkdir()
    if manifest is not None:
        mf = tmp_path / "manifest.json"
        mf.write_text(json.dumps(manifest), encoding="utf-8")
        url = mf.as_uri()
    (team / "skills-matrix.yaml").write_text(yaml.safe_dump({
        "upstream": {"manifest_url": url, "release": "r1"},
        "agents": {"qa-agent": {"role": "qa", "wave": 1, "extra": ["ark-extra"]}},
    }), encoding="utf-8")
    return team


def _plan(team: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / "align_sync.py"), "plan"],
                          cwd=team, capture_output=True, text=True)


def test_plan_uses_base_role_and_extra(tmp_path):
    team = _team(tmp_path, {"release": "r1", "skills": {},
                            "tiers_default": {"base": ["ark-base"], "role": {"qa": ["ark-qa"]}}})
    r = _plan(team)
    assert r.returncode == 1, r.stdout + r.stderr          # 有差異（全部待 add）
    for sk in ("ark-base", "ark-qa", "ark-extra"):
        assert sk in r.stdout, f"{sk} 沒進目標集合：\n{r.stdout}"


def test_unreachable_manifest_fails_loudly(tmp_path):
    team = _team(tmp_path, None, url=(tmp_path / "nope.json").as_uri())
    r = _plan(team)
    assert r.returncode == 2 and "拉不到 manifest" in r.stderr
    assert "ark-extra" not in r.stdout, "拉不到 manifest 卻照常產出只含 extra 的 plan"


def test_manifest_without_tiers_default_fails_loudly(tmp_path):
    team = _team(tmp_path, {"release": "r0", "skills": {}})
    r = _plan(team)
    assert r.returncode == 2 and "tiers_default" in r.stderr
