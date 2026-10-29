"""AL-032 守門：active skill 的 depends_on／description／*.yaml 不得指向 deprecated stub。

背景（2026-10-29）：8 個產碼食譜併入 ark-pipeline-recipes，舊目錄留 stub 轉址。
stub 存在，所以既有的斷鏈檢查（AL-015／016）都會放行；但角色對照表若還指舊名，
新裝的 agent 只拿到空殼，而 mirror_sync 不會自動裝新 skill → 能力在消費端靜默消失。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "_audit_skills_dep032", ROOT / "ark-skills-align/scripts/audit_skills.py")
audit = importlib.util.module_from_spec(_spec)
sys.modules["_audit_skills_dep032"] = audit
_spec.loader.exec_module(audit)


def _skill(repo: Path, name: str, *, desc: str = "測試用。", deps: str = "[]",
           status: str = "active", replaces: str = "[]") -> Path:
    d = repo / name
    d.mkdir(parents=True)
    if status == "deprecated":
        desc = f"[DEPRECATED — 已併入 ark-new] {desc}"
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: |\n  {desc}\nmetadata:\n"
        f"  schema_version: \"1.2\"\n  status: {status}\n  author: t\n  category: pipeline\n"
        f"  form: instruction\n  domain: general\n  version: \"1.0.0\"\n  updated: 2026-10-29\n"
        f"  outputs:\n    - {{ format: md, audience: ai }}\n  depends_on: {deps}\n"
        f"  replaces: {replaces}\n---\n\n# {name}\n",
        encoding="utf-8")
    return d


def _hits(repo: Path) -> list[dict]:
    report = audit.audit(repo, {})
    return [f for f in report["findings"] if f["rule"] == "ref-to-deprecated"]


def _base(repo: Path) -> None:
    _skill(repo, "ark-old", status="deprecated")
    _skill(repo, "ark-new", replaces="[ark-old]", desc="取代 ark-old 的新 skill。")


def test_clean_repo_has_no_hits(tmp_path):
    """反證的「綠」：新 skill 在 replaces 裡提到舊名不算違規。"""
    _base(tmp_path)
    _skill(tmp_path, "ark-user", deps='[{ name: ark-new, version: "^1.0.0" }]')
    assert _hits(tmp_path) == []


def test_depends_on_deprecated_is_p1(tmp_path):
    _base(tmp_path)
    _skill(tmp_path, "ark-user", deps='[{ name: ark-old, version: "^1.0.0" }]')
    hits = _hits(tmp_path)
    assert [(h["severity"], h["skill"]) for h in hits] == [("P1", "ark-user")]
    assert "改指 ark-new" in hits[0]["message"]  # 訊息要可行動


def test_description_deprecated_is_p1(tmp_path):
    _base(tmp_path)
    _skill(tmp_path, "ark-user", desc="不適用於：畫圖請用 ark-old。")
    assert [h["skill"] for h in _hits(tmp_path)] == ["ark-user"]


def test_yaml_role_map_deprecated_is_p1(tmp_path):
    _base(tmp_path)
    d = _skill(tmp_path, "ark-user")
    (d / "assets").mkdir()
    (d / "assets/role-skills-map.yaml").write_text(
        "role_skills:\n  analyst: [ark-old, ark-new]\n", encoding="utf-8")
    hits = _hits(tmp_path)
    assert len(hits) == 1 and "role-skills-map.yaml" in hits[0]["message"]


def test_real_repo_has_no_refs_to_deprecated():
    """本 repo 現況：所有 active skill 都已改指新名（8 個產碼食譜 → ark-pipeline-recipes）。"""
    hits = _hits(ROOT)
    assert hits == [], [h["message"] for h in hits]
