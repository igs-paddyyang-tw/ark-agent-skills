"""skills_sync.py／upstream.py／skilltree.py 驗收 —— 合成上游 repo 與專案樹（references/sop-*.md）。"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
import mirror_sync as M  # noqa: E402
import skills_sync as S  # noqa: E402
import skilltree as T  # noqa: E402
import upstream as UP  # noqa: E402

MD = '---\nname: {n}\ndescription: |\n  {d}\nmetadata:\n  version: "{v}"\n  domain: {dom}\n  status: {st}\n---\n# {n}\n'


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _skill(root: Path, n: str, v="1.0.0", dom="general", st="active", d="demo") -> Path:
    sk = root / n
    (sk / "scripts").mkdir(parents=True, exist_ok=True)
    (sk / "SKILL.md").write_text(MD.format(n=n, d=d, v=v, dom=dom, st=st), encoding="utf-8")
    (sk / "scripts" / "run.py").write_text(f"print('{n} {v}')\n", encoding="utf-8")
    return sk


@pytest.fixture()
def env(tmp_path: Path, monkeypatch):
    up = tmp_path / "upstream"
    up.mkdir()
    _git(up, "init", "-q")
    _git(up, "config", "user.email", "t@t")
    _git(up, "config", "user.name", "t")
    _skill(up, "ark-demo", "1.0.0")
    _git(up, "add", "-A")
    _git(up, "commit", "-q", "-m", "v1")
    _skill(up, "ark-demo", "1.1.0")
    _skill(up, "ark-tool")
    _skill(up, "ark-game-x", dom="game")
    _skill(up, "ark-old", st="deprecated", d="[DEPRECATED — 已併入 ark-demo]")
    _git(up, "add", "-A")
    _git(up, "commit", "-q", "-m", "v1.1")
    proj = tmp_path / "proj"
    for d in (proj / ".kiro" / "skills", proj / "agents" / "qa-agent" / ".kiro" / "skills"):
        d.mkdir(parents=True)
    _git(proj, "init", "-q")
    _git(proj, "config", "user.email", "t@t")
    _git(proj, "config", "user.name", "t")
    for v in UP.ENV_VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(UP, "DEFAULT_LOCAL", str(tmp_path / "no-local-clone"))
    return up, proj


def _install(up: Path, dest: Path, n: str) -> None:
    shutil.copytree(up / n, dest / n)


def _manifest(proj: Path, body: str) -> None:
    (proj / ".kiro" / "skills-manifest.yaml").write_text(body, encoding="utf-8")


def _run(proj: Path, up: Path, *args: str) -> int:
    return S.main([args[0], "--root", str(proj), "--upstream", str(up), "--no-fetch", *args[1:]])


# ── skilltree ────────────────────────────────────────────────────────────────
def test_skill_state_ok_and_broken(tmp_path):
    ok = _skill(tmp_path, "ark-a")
    hollow = tmp_path / "ark-b" / "scripts" / "__pycache__"
    hollow.mkdir(parents=True)
    (hollow / "x.pyc").write_bytes(b"\0")
    assert T.skill_state(ok) == T.OK
    assert T.skill_state(tmp_path / "ark-b") == T.BROKEN
    (tmp_path / "ark-b" / "SKILL.md").write_text("no frontmatter", encoding="utf-8")
    assert T.skill_state(tmp_path / "ark-b") == T.BROKEN, "沒有 frontmatter name 也算壞"


def test_parse_frontmatter_deprecated_successor():
    fm = T.parse_frontmatter(MD.format(n="ark-old", d="[DEPRECATED — 已併入 ark-demo]", v="2.0.0", dom="general", st="deprecated"))
    assert fm["deprecated"] and fm["successor"] == "ark-demo" and fm["version"] == "2.0.0"


# ── upstream ─────────────────────────────────────────────────────────────────
def test_upstream_precedence_env_over_default(env, monkeypatch):
    up, _ = env
    monkeypatch.setenv("ARK_SKILLS_UPSTREAM", str(up))
    assert UP.resolve() == up
    monkeypatch.delenv("ARK_SKILLS_UPSTREAM")
    monkeypatch.setenv("ARK_AGENT_SKILLS_DIR", str(up))
    assert UP.describe_source()[1] == "$ARK_AGENT_SKILLS_DIR", "舊環境變數名視為別名"


def test_upstream_url_clones_full_history_to_cache(env, tmp_path):
    up, _ = env
    cache = tmp_path / "cache"
    got = UP.resolve(f"file://{up}", cache=cache)
    assert got == cache and (cache / ".git").exists()
    n = subprocess.run(["git", "-C", str(cache), "rev-list", "--count", "HEAD"], capture_output=True, text=True).stdout
    assert n.strip() == "2", "快取 clone 必須有完整歷史（STALE／LOCAL 判定要用）"


def test_upstream_bad_explicit_path_raises(env, tmp_path):
    with pytest.raises(UP.UpstreamError):
        UP.resolve(str(tmp_path / "nope"))


# ── status／update ───────────────────────────────────────────────────────────
def test_no_manifest_keeps_installed_set(env):
    up, proj = env
    _install(up, proj / ".kiro" / "skills", "ark-demo")
    assert _run(proj, up, "status") == 0, "沒有 manifest：以已裝的為準、不要求裝其他"


def test_manifest_missing_then_update_installs(env):
    up, proj = env
    _manifest(proj, "include_domains: [general]\n")
    assert _run(proj, up, "status") == 1, "缺 ark-demo／ark-tool 必須紅"
    assert _run(proj, up, "update", "--apply") == 0
    got = {p.name for p in (proj / ".kiro" / "skills").iterdir()}
    assert got == {"ark-demo", "ark-tool"}, "只裝 general、不裝 game 與已併入的舊名"


def test_hollow_dir_is_broken_not_skipped(env):
    up, proj = env
    hollow = proj / "agents" / "qa-agent" / ".kiro" / "skills" / "ark-demo" / "scripts" / "__pycache__"
    hollow.mkdir(parents=True)
    (hollow / "run.cpython-312.pyc").write_bytes(b"\0")
    reps = M.run(up, proj / "agents" / "qa-agent", [], None, do_apply=False, root_only=True)
    assert [r.status for r in reps] == ["BROKEN"], "mirror_sync 不可再把空殼當非 skill 略過"
    assert _run(proj, up, "status") == 1
    assert _run(proj, up, "update", "--apply") == 0
    assert (proj / "agents" / "qa-agent" / ".kiro" / "skills" / "ark-demo" / "SKILL.md").is_file()


def test_update_does_not_touch_local_mod(env):
    up, proj = env
    sk = proj / ".kiro" / "skills"
    _install(up, sk, "ark-demo")
    (sk / "ark-demo" / "SKILL.md").write_text(MD.format(n="ark-demo", d="本專案客製", v="1.1.0", dom="general", st="active"), encoding="utf-8")
    assert _run(proj, up, "update", "--apply") == 1, "LOCAL 要留給人判斷"
    assert "本專案客製" in (sk / "ark-demo" / "SKILL.md").read_text(encoding="utf-8")


def test_root_only_never_touches_projects(env):
    up, proj = env
    other = proj / "projects" / "other" / ".kiro" / "skills"
    other.mkdir(parents=True)
    shutil.copytree(up / "ark-demo", other / "ark-demo")
    (other / "ark-demo" / "scripts" / "run.py").write_text("print('ark-demo 1.0.0')\n", encoding="utf-8")
    _manifest(proj, "include_domains: [general]\n")
    _run(proj, up, "update", "--apply")
    assert (other / "ark-demo" / "scripts" / "run.py").read_text(encoding="utf-8") == "print('ark-demo 1.0.0')\n"


def test_install_refuses_deprecated_and_remove_git_rm(env):
    up, proj = env
    assert _run(proj, up, "install", "ark-old") == 2, "已併入的舊名要拒絕並提示接手者"
    assert _run(proj, up, "install", "ark-tool") == 0
    _git(proj, "add", "-A")
    _git(proj, "commit", "-q", "-m", "x")
    assert _run(proj, up, "remove", "ark-tool") == 0
    assert not (proj / ".kiro" / "skills" / "ark-tool").exists()


# ── doctor ───────────────────────────────────────────────────────────────────
def test_doctor_offline_repairs_from_bundle_only_missing_and_broken(env, tmp_path):
    up, proj = env
    bundle = tmp_path / "bundle"
    _skill(bundle, "ark-demo", "1.1.0")
    _skill(bundle, "ark-tool")
    sk = proj / ".kiro" / "skills"
    _install(up, sk, "ark-tool")
    (sk / "ark-tool" / "SKILL.md").write_text(MD.format(n="ark-tool", d="客製", v="1.0.0", dom="general", st="active"), encoding="utf-8")
    hollow = proj / "agents" / "qa-agent" / ".kiro" / "skills" / "ark-demo" / "x"
    hollow.mkdir(parents=True)
    rep = S.doctor(proj, {}, bundle, {"*": {"ark-demo"}}, repair=False, upstream_mode="off")
    assert not rep["ok"] and rep["summary"]["missing"] == 1 and rep["summary"]["broken"] == 1
    rep = S.doctor(proj, {}, bundle, {"*": {"ark-demo"}}, repair=True, upstream_mode="off")
    assert rep["ok"] and rep["summary"]["repaired"] == 2
    assert "客製" in (sk / "ark-tool" / "SKILL.md").read_text(encoding="utf-8"), "repair 不可碰非 MISSING／BROKEN"


def test_doctor_zero_targets_is_not_green(tmp_path):
    rep = S.doctor(tmp_path, {}, None, {}, repair=False, upstream_mode="off")
    assert not rep["ok"] and "0 個" in rep["note"]


def test_doctor_unreachable_upstream_is_not_failure(env, tmp_path):
    _, proj = env
    rep = S.doctor(proj, {}, None, {}, repair=False, upstream_mode=str(tmp_path / "nope"))
    assert rep["ok"] and rep["upstream"].startswith("unreachable")


def test_doctor_flags_local_deprecated_residue_offline(env):
    up, proj = env
    _install(up, proj / ".kiro" / "skills", "ark-old")
    rep = S.doctor(proj, {}, None, {}, repair=False, upstream_mode="off")
    assert rep["targets"][0]["residue"] == ["ark-old"]
