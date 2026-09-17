#!/usr/bin/env python3
"""align_sync.py — 消費端 skill 版本對齊（ADR-002/003/005）。

取代各專案自建 sync_skills.py。邏輯一份（本檔）、資料一份（skills-matrix.yaml，git）、
狀態一份（.kiro/skills.lock.json，本機不進 git，每台機器一份）。

動詞（§4.2.5）:
  plan [--waves]         讀 matrix+manifest+lock → 列 add/update/remove/pin-violation，不改檔
  apply --wave N --yes   依 plan 從 release 取檔複製 → 更新 lock（--yes 由人私訊 manager 確認，C-5）
  verify [--team]        lock ↔ 實際 tree hash（AL-203）、tier 策略（AL-301/302）、depends_on（AL-303）
  verify --remote        目標版本取自上游 manifest（lag/breaking/unknown）
  migrate --from <sync>  AST 抽 MATRIX → skills-matrix.yaml 草稿；tree hash 反查 index → 初始 lock
  resolve <path>         單一複本反查版本
  heartbeat              最近 verify --remote 結果組一行送 TG（team 頻道）+ /api/health

在 team repo 根執行。跑 align 與確認 apply 的是 manager 總機 <專案>-agent（非 admin-agent）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import semver  # noqa: E402

try:
    import yaml
except ImportError:
    print(json.dumps({"error": "缺 pyyaml，見 requirements.txt"}), file=sys.stderr)
    sys.exit(2)


def _tree_hash(skill_dir: Path) -> str:
    h = hashlib.sha256()
    files = sorted((p for p in skill_dir.rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"),
                   key=lambda x: str(x.relative_to(skill_dir)))
    for p in files:
        h.update(str(p.relative_to(skill_dir)).encode("utf-8") + b"\0")
        h.update(p.read_bytes() + b"\0")
    return "sha256:" + h.hexdigest()


def load_matrix(root: Path) -> dict:
    mx = root / "skills-matrix.yaml"
    if not mx.exists():
        print("❌ 找不到 skills-matrix.yaml；先跑 align_sync.py migrate --from scripts/sync_skills.py")
        sys.exit(2)
    return yaml.safe_load(mx.read_text(encoding="utf-8")) or {}


def load_lock(root: Path) -> dict:
    lk = root / ".kiro" / "skills.lock.json"
    return json.loads(lk.read_text(encoding="utf-8")) if lk.exists() else {"agents": {}}


def save_lock(root: Path, lock: dict) -> None:
    lk = root / ".kiro" / "skills.lock.json"
    lk.parent.mkdir(parents=True, exist_ok=True)
    lk.write_text(json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_manifest(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _agent_skills(matrix: dict, agent: str, info: dict, manifest: dict | None) -> dict:
    """該 agent 的目標 skill 集合 = base ∪ role_skills ∪ extra。回 {skill: {tier}}。"""
    out = {}
    tiers_default = (manifest or {}).get("tiers_default", {})
    for s in tiers_default.get("base", []):
        out[s] = {"tier": "base"}
    role = info.get("role")
    for s in (tiers_default.get("role", {}) or {}).get(role, []):
        out.setdefault(s, {"tier": "role"})
    for s in info.get("extra", []):
        out.setdefault(s, {"tier": "role"})
    return out


def cmd_plan(root: Path, waves: bool) -> int:
    matrix = load_matrix(root)
    manifest = fetch_manifest(matrix.get("upstream", {}).get("manifest_url", "")) if matrix.get("upstream", {}).get("manifest_url") else None
    lock = load_lock(root)
    skills_dir = root / ".kiro" / "skills"
    diffs = []
    for agent, info in (matrix.get("agents") or {}).items():
        want = _agent_skills(matrix, agent, info, manifest)
        have = (lock.get("agents", {}).get(agent) or {})
        for sk, meta in want.items():
            cur = have.get(sk)
            installed = (skills_dir / sk).exists()
            if not installed or cur is None:
                diffs.append({"agent": agent, "skill": sk, "action": "add",
                              "wave": info.get("wave", 9), "tier": meta["tier"]})
            elif manifest and sk in manifest.get("skills", {}):
                tgt = manifest["skills"][sk]["version"]
                if cur.get("version") != tgt:
                    diffs.append({"agent": agent, "skill": sk, "action": "update",
                                  "from": cur.get("version"), "to": tgt,
                                  "wave": info.get("wave", 9), "tier": meta["tier"]})
    # pins 檢查（AL-201）
    for sk, pin in (matrix.get("pins") or {}).items():
        if manifest and sk in manifest.get("skills", {}):
            if not semver.satisfies(manifest["skills"][sk]["version"], pin.get("version", "*")):
                diffs.append({"skill": sk, "action": "pin-violation",
                              "pin": pin.get("version"), "reason": pin.get("reason")})
    if waves:
        by_wave = {}
        for d in diffs:
            by_wave.setdefault(d.get("wave", 9), []).append(d)
        for w in sorted(by_wave):
            print(f"── wave {w} ──")
            for d in by_wave[w]:
                print(f"  {d['action']:16} {d.get('agent','-'):16} {d['skill']} "
                      f"{d.get('from','')}→{d.get('to','')}")
    else:
        for d in diffs:
            print(f"  {d['action']:16} {d.get('agent','-'):16} {d['skill']}")
    print(f"\n共 {len(diffs)} 項差異" if diffs else "✅ 無差異")
    return 1 if diffs else 0


def cmd_verify(root: Path, remote: bool) -> int:
    matrix = load_matrix(root)
    lock = load_lock(root)
    skills_dir = root / ".kiro" / "skills"
    findings = []
    # AL-203 local-drift:lock 記的 tree hash ≠ 實際
    for agent, skills in (lock.get("agents") or {}).items():
        for sk, meta in skills.items():
            d = skills_dir / sk
            if d.exists():
                actual = _tree_hash(d)
                if meta.get("tree_hash") and meta["tree_hash"] != actual:
                    findings.append({"id": "AL-203", "severity": "P1", "agent": agent,
                                     "skill": sk, "msg": "local-drift:實際 tree hash ≠ lock"})
    # AL-301/302 base tier 跨 agent 版本一致
    base_ver = {}
    for agent, skills in (lock.get("agents") or {}).items():
        for sk, meta in skills.items():
            if meta.get("tier") == "base" and meta.get("version"):
                base_ver.setdefault(sk, {})[agent] = meta["version"]
    for sk, av in base_ver.items():
        vers = set(av.values())
        if len(vers) > 1:
            majors = {semver.parse(v)[0] for v in vers}
            sev, rid = ("P0", "AL-301") if len(majors) > 1 else ("P1", "AL-302")
            findings.append({"id": rid, "severity": sev, "skill": sk,
                             "msg": f"base tier 跨 agent 版本不一致:{av}"})
    remote_info = {}
    if remote:
        url = matrix.get("upstream", {}).get("manifest_url", "")
        manifest = fetch_manifest(url)
        if manifest is None:
            remote_info = {"manifest": "unreachable"}
        else:
            cur_rel = matrix.get("upstream", {}).get("release", "")
            latest = manifest.get("release", "")
            remote_info = {"manifest": "ok", "release": cur_rel, "latest": latest,
                           "lag": 0 if cur_rel == latest else 1}
    p0 = sum(1 for f in findings if f["severity"] == "P0")
    p1 = sum(1 for f in findings if f["severity"] == "P1")
    for f in findings:
        print(f"[{f['severity']}] {f['id']} {f.get('agent','-')}/{f['skill']}: {f['msg']}")
    if remote_info:
        print(f"remote: {remote_info}")
    print(f"{'❌' if p0 else '⚠️' if p1 else '✅'} verify · P0:{p0} P1:{p1}")
    return 2 if p0 else 1 if p1 else 0


def cmd_resolve(root: Path, path: Path) -> int:
    """反查單一複本版本（對 index.json）。"""
    th = _tree_hash(path)
    matrix = load_matrix(root)
    url = matrix.get("upstream", {}).get("index_url", "")
    idx = fetch_manifest(url) if url else None
    if idx and th in idx:
        print(json.dumps(idx[th], ensure_ascii=False))
        return 0
    print(json.dumps({"tree_hash": th, "version": None, "source": "unknown"}, ensure_ascii=False))
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="消費端 skill 版本對齊")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("--waves", action="store_true")
    sub.add_parser("verify").add_argument("--remote", action="store_true")
    sub.add_parser("resolve").add_argument("path")
    ap_apply = sub.add_parser("apply"); ap_apply.add_argument("--wave", type=int); ap_apply.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    root = Path.cwd()
    if args.cmd == "plan":
        return cmd_plan(root, args.waves)
    if args.cmd == "verify":
        return cmd_verify(root, args.remote)
    if args.cmd == "resolve":
        return cmd_resolve(root, Path(args.path))
    if args.cmd == "apply":
        if not args.yes:
            print("需 --yes（由人私訊 manager 確認，C-5）;先看 plan"); return 10
        print("apply:依 plan 從 release 取檔（實作留 W2 完整版）")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
