#!/usr/bin/env python3
"""
team_spec_lint.py — team-spec.yaml 守門。

用法：
  python team_spec_lint.py team-spec.yaml [--roles-dir <ark-agent-role-profile/assets/roles>]
  python team_spec_lint.py --all-patterns
  python team_spec_lint.py --list-patterns

Exit：0 = P0/P1 清零；1 = 有 P0/P1；2 = 參數/檔案錯誤。
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
SCHEMA = SKILL_ROOT / "references" / "team-spec.schema.json"
PATTERNS = SKILL_ROOT / "assets" / "patterns"
DEFAULT_ROLES_DIR = SKILL_ROOT.parent / "ark-agent-role-profile" / "assets" / "roles"


class Findings:
    def __init__(self) -> None:
        self.items: list[tuple[str, str]] = []

    def add(self, lv: str, msg: str) -> None:
        self.items.append((lv, msg))

    def count(self, lv: str) -> int:
        return sum(1 for l, _ in self.items if l == lv)

    def blocking(self) -> bool:
        return self.count("P0") + self.count("P1") > 0


def load(path: Path) -> dict:
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(d, dict):
        raise ValueError("頂層必須是 mapping")
    return d


def schema_check(spec: dict, fx: Findings) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    try:
        import jsonschema  # type: ignore
    except ImportError:
        for k in schema["required"]:
            if k not in spec:
                fx.add("P0", f"缺必填 `{k}`（jsonschema 未安裝，僅必填檢查）")
        return
    v = jsonschema.Draft202012Validator(schema)
    for e in sorted(v.iter_errors(spec), key=lambda e: list(e.path)):
        loc = ".".join(str(p) for p in e.path) or "<root>"
        fx.add("P0", f"schema 不符 @ {loc}: {e.message}")


def has_cycle(edges: list[tuple[str, str]]) -> bool:
    graph: dict[str, list[str]] = {}
    for a, b in edges:
        graph.setdefault(a, []).append(b)
    state: dict[str, int] = {}

    def dfs(n: str) -> bool:
        state[n] = 1
        for m in graph.get(n, []):
            if state.get(m) == 1 or (state.get(m) is None and dfs(m)):
                return True
        state[n] = 2
        return False

    return any(state.get(n) is None and dfs(n) for n in graph)


def semantic_check(spec: dict, fx: Findings, roles_dir: Path | None) -> None:
    insts = spec.get("instances") or []
    ids = [i.get("id") for i in insts if isinstance(i, dict)]
    by_id = {i["id"]: i for i in insts if isinstance(i, dict) and "id" in i}
    if len(ids) != len(set(ids)):
        fx.add("P0", "instance id 重複")
    tiers = {t: [i["id"] for i in insts if i.get("tier") == t] for t in ("manager", "admin", "leader", "worker")}
    if not tiers["admin"]:
        fx.add("P0", "沒有 admin（admin 必有且不接業務）")
    if not tiers["leader"]:
        fx.add("P0", "沒有 leader")
    if len(tiers["manager"]) > 1:
        fx.add("P1", "manager 超過 1 個")
    if spec.get("entry") not in by_id:
        fx.add("P0", f"entry `{spec.get('entry')}` 不在 instances")
    if len(insts) > 8:
        fx.add("P1", f"instance {len(insts)} 個 > 8，建議拆兩支團隊")

    per_leader: dict[str, int] = {}
    for i in insts:
        if i.get("tier") == "worker":
            g = i.get("group")
            if not g:
                fx.add("P0", f"worker `{i['id']}` 缺 group")
            elif g not in by_id or by_id[g].get("tier") != "leader":
                fx.add("P0", f"worker `{i['id']}` 的 group `{g}` 不是 leader")
            else:
                per_leader[g] = per_leader.get(g, 0) + 1
        elif i.get("group"):
            fx.add("P1", f"`{i['id']}`（{i.get('tier')}）不該有 group，group 只給 worker")
    for l, n in per_leader.items():
        if n > 6:
            fx.add("P1", f"leader `{l}` 底下 worker {n} 個 > 6，必須切第二個 leader")
        elif n == 6:
            fx.add("P2", f"leader `{l}` 底下 worker 6 個已達上限；確認有 deterministic 的整理型 worker（triage/report）分擔收斂")

    # escalation
    edges = []
    for e in spec.get("escalation") or []:
        for k in ("from", "to"):
            if e.get(k) not in by_id:
                fx.add("P1", f"escalation 引用不存在的 id `{e.get(k)}`")
        edges.append((e.get("from"), e.get("to")))
    if has_cycle(edges):
        fx.add("P1", "escalation 有環")
    esc_from = {a for a, _ in edges}
    for w in tiers["worker"]:
        if w not in esc_from:
            fx.add("P2", f"worker `{w}` 沒有升報路徑")

    # decision locks
    locks = spec.get("decision_locks") or []
    if not any(l.get("approver") == "human" for l in locks):
        fx.add("P2", "沒有任何決策鎖由 human 批准——確認真的沒有需要人拍的事")
    for l in locks:
        for ref in [l.get("approver"), l.get("proposer"), *(l.get("allowed") or [])]:
            if ref and ref != "human" and ref not in by_id:
                fx.add("P1", f"decision_lock「{l.get('decision')}」引用不存在的 id `{ref}`")

    # base_role
    if roles_dir and roles_dir.exists():
        known = {p.stem for p in roles_dir.glob("*.yaml")} | {"admin"}
        for i in insts:
            br = i.get("base_role")
            if br and br != "custom" and br not in known:
                fx.add("P1", f"`{i['id']}` 的 base_role `{br}` 不在角色庫（{roles_dir}）；用 custom 或先建角色")

    # purpose similarity
    workers = [i for i in insts if i.get("tier") == "worker"]
    for a in range(len(workers)):
        for b in range(a + 1, len(workers)):
            r = difflib.SequenceMatcher(None, workers[a]["purpose"], workers[b]["purpose"]).ratio()
            if r > 0.8:
                fx.add("P2", f"`{workers[a]['id']}` 與 `{workers[b]['id']}` purpose 相似度 {r:.2f}，疑似可合併")
    if not spec.get("deliverables"):
        fx.add("P2", "deliverables 為空")


def lint(path: Path, roles_dir: Path | None) -> Findings:
    fx = Findings()
    try:
        spec = load(path)
    except Exception as e:  # noqa: BLE001
        fx.add("P0", f"讀取失敗：{e}")
        return fx
    schema_check(spec, fx)
    if fx.count("P0") == 0:
        semantic_check(spec, fx, roles_dir)
    return fx


def report(path: Path, fx: Findings) -> None:
    print(f"\n== {path} ==")
    for lv, m in fx.items:
        print(f"  [{lv}] {m}")
    print(f"  → P0 {fx.count('P0')} · P1 {fx.count('P1')} · P2 {fx.count('P2')}")


def list_patterns() -> None:
    print("| team_id | name | 人數 | 層級 | entry | human 鎖 |")
    print("|---|---|---|---|---|---|")
    for p in sorted(PATTERNS.glob("*.yaml")):
        s = load(p)
        tiers = {}
        for i in s["instances"]:
            tiers[i["tier"]] = tiers.get(i["tier"], 0) + 1
        tier_s = " / ".join(f"{k}×{v}" for k, v in tiers.items())
        human = sum(1 for l in s.get("decision_locks", []) if l.get("approver") == "human")
        print(f"| `{s['team_id']}` | {s['name']} | {len(s['instances'])} | {tier_s} | {s['entry']} | {human} |")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", nargs="?")
    ap.add_argument("--all-patterns", action="store_true")
    ap.add_argument("--list-patterns", action="store_true")
    ap.add_argument("--roles-dir", type=Path, default=DEFAULT_ROLES_DIR if DEFAULT_ROLES_DIR.exists() else None)
    a = ap.parse_args()
    if a.list_patterns:
        list_patterns()
        return 0
    targets = sorted(PATTERNS.glob("*.yaml")) if a.all_patterns else ([Path(a.spec)] if a.spec else [])
    if not targets:
        ap.print_help()
        return 2
    blocking = False
    for t in targets:
        fx = lint(t, a.roles_dir)
        report(t, fx)
        blocking |= fx.blocking()
    print("\n" + ("❌ P0/P1 未清零，不得生成" if blocking else "✅ P0/P1 清零，可生成"))
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
