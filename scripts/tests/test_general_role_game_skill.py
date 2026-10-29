"""AL-033 守門：通用角色不得列 domain: game 的 skill（盤點 O-1，2026-10-29）。

安裝走角色表（base ∪ 角色 ∪ extra）—— 角色表守住，非遊戲團隊就不會裝到遊戲 skill。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "_audit_skills_al033", ROOT / "ark-skills-align/scripts/audit_skills.py")
audit = importlib.util.module_from_spec(_spec)
sys.modules["_audit_skills_al033"] = audit
_spec.loader.exec_module(audit)


def _skill(repo: Path, name: str, domain: str) -> None:
    d = repo / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: |\n  測試用。不適用於：其他。\nmetadata:\n"
        f"  schema_version: \"1.2\"\n  status: active\n  author: t\n  category: process\n"
        f"  form: instruction\n  domain: {domain}\n  version: \"1.0.0\"\n  updated: 2026-10-29\n"
        f"  outputs:\n    - {{ format: md, audience: ai }}\n---\n\n# {name}\n", encoding="utf-8")


def _world(tmp_path: Path, role_map: str, role_yaml: str) -> Path:
    repo = tmp_path / "repo"
    _skill(repo, "ark-gamey", "game")
    _skill(repo, "ark-plain", "general")
    m = repo / "ark-agent-init" / "assets"
    m.mkdir(parents=True)
    (m / "role-skills-map.yaml").write_text(role_map, encoding="utf-8")
    r = repo / "ark-agent-role-profile" / "assets" / "roles"
    r.mkdir(parents=True)
    (r / "analyst.yaml").write_text(role_yaml, encoding="utf-8")
    return repo


def _hits(repo: Path) -> list[str]:
    return [f["message"] for f in audit.audit(repo, {})["findings"] if f["rule"] == "general-role-game-skill"]


def test_clean_roles_pass(tmp_path):
    repo = _world(tmp_path, "role_skills:\n  analyst: [ark-plain]\n",
                  "role_id: analyst\nskills: [ark-plain]\n")
    assert _hits(repo) == []


def test_role_map_with_game_skill_is_flagged(tmp_path):
    repo = _world(tmp_path, "role_skills:\n  analyst: [ark-plain, ark-gamey]\n",
                  "role_id: analyst\nskills: [ark-plain]\n")
    hits = _hits(repo)
    assert len(hits) == 1 and "role-skills-map.yaml:analyst" in hits[0] and "domain: game" in hits[0]


def test_role_profile_needs_domain_game_declaration(tmp_path):
    undeclared = _world(tmp_path / "a", "role_skills: {}\n", "role_id: analyst\nskills: [ark-gamey]\n")
    assert len(_hits(undeclared)) == 1
    declared = _world(tmp_path / "b", "role_skills: {}\n",
                      "role_id: analyst\ndomain: game\nskills: [ark-gamey]\n")
    assert _hits(declared) == []


def test_real_repo_has_no_general_role_with_game_skill():
    hits = _hits(ROOT)
    assert hits == [], hits
