"""depends_on 守門：物件格式 {name, version}、範圍可滿足（AL-105）、語法可解析（AL-031）、無環（AL-030）。

背景（2026-10-20）：全庫 38 條 depends_on 都是字串（無版本範圍，AL-104），AL-105 只登記了代號沒有實作，
而 audit 的斷鏈檢查與反向依賴用 `str(ref)` 取名稱 —— 改物件格式後會**靜默失效**。另有
ark-game-prob ⇄ ark-game-quicktest 互相依賴。
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "_audit_skills_dep", ROOT / "ark-skills-align/scripts/audit_skills.py")
audit = importlib.util.module_from_spec(_spec)
sys.modules["_audit_skills_dep"] = audit
_spec.loader.exec_module(audit)


def _skill(repo: Path, name: str, version: str, deps: str = "[]") -> None:
    d = repo / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: |\n  測試用 {name}。不適用於：其他。\nmetadata:\n"
        f"  schema_version: \"1.2\"\n  status: active\n  author: t\n  category: process\n"
        f"  form: instruction\n  domain: general\n  version: \"{version}\"\n  updated: 2026-10-20\n"
        f"  outputs:\n    - {{ format: md, audience: ai }}\n  depends_on: {deps}\n---\n\n# {name}\n",
        encoding="utf-8")


def _rules(repo: Path) -> set[tuple[str, str, str]]:
    report = audit.audit(repo, audit.DEFAULT_EXCLUSIVE_TRIGGERS)
    return {(f["severity"], f["rule"], f["skill"]) for f in report["findings"]}


def test_dangling_dep_detected_in_object_form(tmp_path):
    """回歸：物件格式的斷鏈依賴必須被抓（原本 str(ref) 會讓它靜默通過）。"""
    _skill(tmp_path, "ark-a", "1.0.0", '[{ name: ark-ghost, version: "^1.0.0" }]')
    assert ("P1", "dangling-skill-ref", "ark-a") in _rules(tmp_path)


def test_unsatisfiable_range_is_p0(tmp_path):
    _skill(tmp_path, "ark-b", "1.2.0")
    _skill(tmp_path, "ark-a", "1.0.0", '[{ name: ark-b, version: "^2.0.0" }]')
    assert ("P0", "upstream-dep-unsatisfiable", "ark-a") in _rules(tmp_path)


def test_unparsable_range_is_p1_not_p0(tmp_path):
    """寫錯的範圍報 AL-031（P1），不能被 satisfies() 的 False 誤報成 P0。"""
    _skill(tmp_path, "ark-b", "1.2.0")
    _skill(tmp_path, "ark-a", "1.0.0", '[{ name: ark-b, version: "latest" }]')
    rules = _rules(tmp_path)
    assert ("P1", "invalid-dep-range", "ark-a") in rules
    assert ("P0", "upstream-dep-unsatisfiable", "ark-a") not in rules


def test_cycle_is_p1(tmp_path):
    _skill(tmp_path, "ark-a", "1.0.0", '[{ name: ark-b, version: "^1.0.0" }]')
    _skill(tmp_path, "ark-b", "1.0.0", '[{ name: ark-a, version: "^1.0.0" }]')
    assert any(r[1] == "depends-on-cycle" and r[0] == "P1" for r in _rules(tmp_path))


def test_dep_name_handles_both_forms():
    assert audit.dep_name("ark-a") == "ark-a"
    assert audit.dep_name({"name": "ark-a", "version": "^1.0.0"}) == "ark-a"
    assert audit.dep_range("ark-a") == "*"
    assert audit.dep_range({"name": "ark-a", "version": "^1.0.0"}) == "^1.0.0"


def test_valid_range_syntax():
    for ok in ("*", "", "^1.4.0", ">=2.0 <3", "~1.2.3", "1.0.0"):
        assert audit.valid_range(ok), ok
    for bad in ("latest", "^x.y", ">= 1.0"):
        assert not audit.valid_range(bad), bad


def test_find_dep_cycles():
    assert audit.find_dep_cycles({"a": ["b"], "b": ["a"]}) == [["a", "b", "a"]]
    assert audit.find_dep_cycles({"a": ["b"], "b": ["c"], "c": []}) == []


def test_real_repo_deps_are_ranged_satisfiable_and_acyclic():
    """全庫：depends_on 全為物件、範圍可解析且被上游現行版本滿足、無環。"""
    fm_re = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
    meta = {}
    for md in sorted(ROOT.glob("ark-*/SKILL.md")):
        m = (yaml.safe_load(fm_re.match(md.read_text(encoding="utf-8")).group(1)) or {}).get("metadata") or {}
        if m.get("status") != "deprecated":
            meta[md.parent.name] = m
    bad, graph = [], {}
    for name, m in meta.items():
        graph[name] = []
        for ref in m.get("depends_on") or []:
            if not isinstance(ref, dict):
                bad.append(f"{name}: 字串形式 {ref!r}")
                continue
            target, rng = audit.dep_name(ref), audit.dep_range(ref)
            graph[name].append(target)
            if target not in meta:
                bad.append(f"{name}: 依賴不存在 {target}")
            elif not audit.valid_range(rng):
                bad.append(f"{name}: {target} 範圍無法解析 {rng!r}")
            elif not audit.semver.satisfies(str(meta[target]["version"]), rng):
                bad.append(f"{name}: {target} 要求 {rng}，上游為 {meta[target]['version']}")
    assert not bad, "\n".join(bad)
    assert audit.find_dep_cycles(graph) == []
