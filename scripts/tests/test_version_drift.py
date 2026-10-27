"""版號漂移守門（AL-102／103／108）與 tree_hash 只算 git 看得到的檔。

背景（2026-10-27）：v2 規格 AC-07 登記了 AL-102／103／106 但只有代號沒有實作；補實作時又抓到
gen_manifest 把 `.pytest_cache`（被 git 忽略）算進 tree_hash —— 先跑測試再產 manifest，記下的就是被污染的值。
比對基準 = repo 內上一班 `ark-skills-align/release/manifest.json`，所以 audit 要在 gen_manifest 之前跑。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "ark-skills-align" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


audit = _load("ark-skills-align/scripts/audit_skills.py", "_audit_drift")
gen = _load("ark-skills-align/scripts/gen_manifest.py", "_gen_drift")


def _write_skill(repo: Path, version: str, extra_body: str = "", script: str = "print(1)\n") -> None:
    d = repo / "ark-demo"
    (d / "scripts").mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "---\nname: ark-demo\ndescription: |\n  測試用。不適用於：其他。\nmetadata:\n"
        "  schema_version: \"1.2\"\n  status: active\n  author: t\n  category: process\n"
        f"  form: executor\n  domain: general\n  version: \"{version}\"\n  updated: 2026-10-27\n"
        "  outputs:\n    - { format: md, audience: ai }\n  depends_on: []\n---\n\n# ark-demo\n"
        f"{extra_body}", encoding="utf-8")
    (d / "scripts" / "run.py").write_text(script, encoding="utf-8")


@pytest.fixture()
def repo(tmp_path):
    """git repo＋一個 skill＋以當下內容產的 baseline manifest（模擬「上一班列車」）。"""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _write_skill(tmp_path, "1.0.0")
    manifest, _ = gen.build(tmp_path, "test-r1", tmp_path / "ark-skills-align" / "release")
    rel = tmp_path / "ark-skills-align" / "release"
    rel.mkdir(parents=True)
    (rel / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def _rules(repo: Path) -> set[tuple[str, str]]:
    report = audit.audit(repo, audit.DEFAULT_EXCLUSIVE_TRIGGERS)
    return {(f["severity"], f["rule"]) for f in report["findings"] if f["skill"] == "ark-demo"}


def test_unchanged_skill_is_clean(repo):
    rules = {r for _, r in _rules(repo)}
    assert not rules & {"contract-changed-no-bump", "content-changed-no-bump", "major-no-breaking"}


def test_contract_change_without_bump_is_p1(repo):
    _write_skill(repo, "1.0.0", script="print(2)\n")
    assert ("P1", "contract-changed-no-bump") in _rules(repo)


def test_doc_only_change_without_bump_is_p2(repo):
    _write_skill(repo, "1.0.0", extra_body="多一段說明\n")
    rules = _rules(repo)
    assert ("P2", "content-changed-no-bump") in rules
    assert ("P1", "contract-changed-no-bump") not in rules


def test_bumped_change_is_clean(repo):
    _write_skill(repo, "1.1.0", script="print(2)\n")
    rules = {r for _, r in _rules(repo)}
    assert not rules & {"contract-changed-no-bump", "content-changed-no-bump"}


def test_major_bump_needs_breaking_note(repo):
    _write_skill(repo, "2.0.0", script="print(2)\n")
    assert ("P2", "major-no-breaking") in _rules(repo)
    _write_skill(repo, "2.0.0", script="print(2)\n",
                 extra_body="\n## 版本\n\n| 2.0.0 | 2026-10-27 | **Breaking**：run.py 參數改名，舊參數移除 |\n")
    assert ("P2", "major-no-breaking") not in _rules(repo)


def test_tree_hash_ignores_git_ignored_runtime_junk(repo):
    """回歸：.pytest_cache（自帶 `.gitignore: *`）不得改變 tree_hash。"""
    d = repo / "ark-demo"
    before = gen.tree_hash(d)
    cache = d / "scripts" / ".pytest_cache"
    cache.mkdir()
    (cache / ".gitignore").write_text("*\n", encoding="utf-8")
    (cache / "README.md").write_text("cache\n", encoding="utf-8")
    assert gen.tree_hash(d) == before


def test_tree_hash_counts_new_untracked_files(repo):
    """未 commit 的新檔要算進去（發版流程是先產 manifest 再 commit）。"""
    d = repo / "ark-demo"
    before = gen.tree_hash(d)
    (d / "scripts" / "new_tool.py").write_text("x = 1\n", encoding="utf-8")
    assert gen.tree_hash(d) != before
