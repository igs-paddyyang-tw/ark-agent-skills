#!/usr/bin/env python3
"""align_sync.py — 消費端 skill 版本對齊（ADR-002/003/005）。

取代各專案自建 sync_skills.py。邏輯一份（本檔）、資料一份（skills-matrix.yaml，git）、
狀態一份（.kiro/skills.lock.json，本機不進 git，每台機器一份）。

動詞（§4.2.5）:
  plan [--waves]         讀 matrix+manifest+lock → 列 add/update/remove/pin-violation，不改檔
  apply --wave N --yes [--upstream <clone>]
                         依 plan 從上游列車 commit 取檔（git archive）→ 驗 manifest tree_hash → 換上 → 更新 lock
                         （--yes 由人私訊 manager 確認，C-5；未帶 --yes 只列出、exit 10）
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
    # 與 gen_manifest._iter_files 同規則（消費端複本多半不在 git，走明確排除）：
    # 執行期產物（__pycache__／.pytest_cache／node_modules／.pyc）與頂層 release/（列車資料）不算內容
    junk = {"__pycache__", ".pytest_cache", "node_modules"}
    files = sorted((p for p in skill_dir.rglob("*")
                    if p.is_file() and not junk & set(p.relative_to(skill_dir).parts) and p.suffix != ".pyc"
                    and p.relative_to(skill_dir).parts[0] != "release"),
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


def require_manifest(matrix: dict) -> dict | None:
    """plan 一定要有 manifest 且帶 tiers_default；缺任何一個就說清楚原因與修法，回 None。

    🔴 2026-10-30：原本拉不到 manifest（網址錯／斷網）或 manifest 沒有 tiers_default 時照常往下算，
    目標集合只剩 extra —— plan 看起來「差異很少」，其實是角色 skill 全部漏掉。
    """
    url = matrix.get("upstream", {}).get("manifest_url", "")
    if not url:
        print("❌ skills-matrix.yaml 沒有 upstream.manifest_url —— 無法得知角色該裝哪些 skill", file=sys.stderr)
        return None
    manifest = fetch_manifest(url)
    if manifest is None:
        print(f"❌ 拉不到 manifest：{url}\n   正確路徑：https://raw.githubusercontent.com/igs-paddyyang-tw/"
              "ark-agent-skills/main/ark-skills-align/release/manifest.json（舊的 main/release/… 是 404）",
              file=sys.stderr)
        return None
    if not (manifest.get("tiers_default") or {}).get("base"):
        print(f"❌ manifest（{manifest.get('release', '?')}）沒有 tiers_default —— 上游 r18 之前的列車不帶角色表，"
              "請改用最新列車", file=sys.stderr)
        return None
    return manifest


def compute_diffs(root: Path, matrix: dict, manifest: dict, lock: dict) -> list[dict]:
    """matrix（期望）× manifest（上游列車）× lock（本機現況）→ add／update／pin-violation 清單。"""
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
    return diffs


def cmd_plan(root: Path, waves: bool) -> int:
    matrix = load_matrix(root)
    manifest = require_manifest(matrix)
    if manifest is None:
        return 2
    diffs = compute_diffs(root, matrix, manifest, load_lock(root))
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


MANIFEST_PATH = "ark-skills-align/release/manifest.json"


def _git(upstream: Path, *args: str, binary: bool = False):
    import subprocess
    return subprocess.run(["git", "-C", str(upstream), *args], capture_output=True, text=not binary)


def find_release_commit(upstream: Path, release: str) -> str | None:
    """上游 clone 歷史中「manifest.json 的 release 等於 R」的 commit。

    🔴 不信 manifest 的 `commit` 欄位：r12～r18 的發版流程（commit → 產 manifest → amend）讓它指向
    amend 前、不在 main 上的孤兒 commit。含該 manifest 的 commit 本身才是那班列車的內容（AC-13）。
    """
    log = _git(upstream, "log", "--all", "--format=%H", "--", MANIFEST_PATH)
    if log.returncode != 0:
        return None
    for sha in log.stdout.split():
        show = _git(upstream, "show", f"{sha}:{MANIFEST_PATH}")
        if show.returncode == 0:
            try:
                if json.loads(show.stdout).get("release") == release:
                    return sha
            except json.JSONDecodeError:
                continue
    return None


def _extract(upstream: Path, sha: str, skill: str, dest: Path) -> bool:
    """git archive 取出 release commit 裡的 skill 目錄（不碰上游 working tree）。"""
    import io
    import tarfile
    arc = _git(upstream, "archive", "--format=tar", sha, skill, binary=True)
    if arc.returncode != 0:
        return False
    with tarfile.open(fileobj=io.BytesIO(arc.stdout)) as tf:
        try:
            tf.extractall(dest, filter="data")
        except TypeError:                      # Python < 3.11.4
            tf.extractall(dest)
    return (dest / skill / "SKILL.md").is_file()


def cmd_apply(root: Path, wave: int | None, yes: bool, upstream_arg: str | None) -> int:
    """依 plan 從**上游列車的 commit** 取檔 → 驗 manifest tree_hash → 換上 → 寫 lock（AC-11／AC-13）。"""
    import shutil
    import tempfile
    from datetime import datetime
    matrix = load_matrix(root)
    manifest = require_manifest(matrix)
    if manifest is None:
        return 2
    lock = load_lock(root)
    diffs = [d for d in compute_diffs(root, matrix, manifest, lock)
             if d["action"] in ("add", "update") and (wave is None or d.get("wave") == wave)]
    blocked = {d["skill"] for d in compute_diffs(root, matrix, manifest, lock) if d["action"] == "pin-violation"}
    if not yes:
        for d in diffs:
            print(f"  {d['action']:8} {d['agent']:16} {d['skill']}")
        print(f"需 --yes（由人私訊 manager 確認，C-5）；以上 {len(diffs)} 項未套用")
        return 10
    if wave is None:
        print("❌ apply 需指定 --wave N（逐波升級，每波 verify 過才下一波）", file=sys.stderr)
        return 2
    up = upstream_arg or (matrix.get("upstream") or {}).get("local_clone")
    if not up or not (Path(up).expanduser() / ".git").exists():
        print("❌ 找不到上游 ark-agent-skills 的本機 clone：用 --upstream <路徑> 或在 skills-matrix.yaml 設 upstream.local_clone",
              file=sys.stderr)
        return 2
    upstream = Path(up).expanduser()
    release = manifest.get("release", "")
    sha = find_release_commit(upstream, release)
    if not sha:
        print(f"❌ 上游 clone 的歷史裡找不到列車 {release}：先在 {upstream} 跑 git fetch", file=sys.stderr)
        return 2

    skills_dir = root / ".kiro" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    local_only = set(matrix.get("local_only") or [])
    done: dict[str, dict] = {}       # skill → lock 條目（同一 skill 多個 agent 只取檔一次）
    failed = []
    with tempfile.TemporaryDirectory() as td:
        for d in diffs:
            sk = d["skill"]
            if sk in done or sk in failed:
                continue
            want = (manifest.get("skills") or {}).get(sk)
            reason = ("local_only，不由上游管理" if sk in local_only else
                      "pin 不滿足（見 plan 的 pin-violation）" if sk in blocked else
                      f"不在列車 {release}（deprecated 或已移除）" if not want else "")
            if reason:
                print(f"  ⏭  {sk}：{reason}")
                failed.append(sk)
                continue
            stage = Path(td) / "stage"
            if not _extract(upstream, sha, sk, stage):
                print(f"  ❌ {sk}：無法從 {sha[:7]} 取出")
                failed.append(sk)
                continue
            got = _tree_hash(stage / sk)
            if got != want["tree_hash"]:
                print(f"  ❌ {sk}：取出的內容 tree_hash 與 manifest 不符（{got[:19]}… ≠ {want['tree_hash'][:19]}…），不安裝")
                failed.append(sk)
                shutil.rmtree(stage / sk)
                continue
            dst = skills_dir / sk
            tmp = skills_dir / f".{sk}.new"
            if tmp.exists():
                shutil.rmtree(tmp)
            shutil.move(str(stage / sk), tmp)          # 先放旁邊，換名才生效 —— 失敗不留半套
            if dst.exists():
                shutil.rmtree(dst)
            tmp.rename(dst)
            done[sk] = {"version": want["version"], "tree_hash": got, "source": f"upstream@{sha[:7]}"}
            print(f"  ✅ {d['action']:8} {sk} {want['version']}")
    for d in diffs:
        if d["skill"] in done:
            entry = dict(done[d["skill"]], tier=d["tier"], declared_by=["skills-matrix"])
            lock.setdefault("agents", {}).setdefault(d["agent"], {})[d["skill"]] = entry
    if done:
        lock["release"] = release
        lock["synced_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        save_lock(root, lock)
    print(f"\nwave {wave}：套用 {len(done)}、未套用 {len(failed)}（列車 {release} @ {sha[:7]}）")
    return 1 if failed else 0


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


def cmd_heartbeat(root: Path, force: bool) -> int:
    """最近一次 verify --remote 結果組一行送 TG（team 頻道，D-1）+ 寫 /api/health.skills。
    同版且無變化時只寫 health、不發 TG（force 例外）。TG chat id 走 ARK_TEAM_CHAT_ID。"""
    import os
    matrix = load_matrix(root)
    url = matrix.get("upstream", {}).get("manifest_url", "")
    manifest = fetch_manifest(url) if url else None
    cur_rel = matrix.get("upstream", {}).get("release", "")
    deployment = root.name
    if manifest is None:
        state = {"deployment": deployment, "release": cur_rel, "manifest": "unreachable"}
        changed = True
    else:
        latest = manifest.get("release", "")
        lag = 0 if cur_rel == latest else 1
        state = {"deployment": deployment, "release": cur_rel, "latest_release": latest,
                 "lag": lag, "manifest": "ok"}
        changed = lag > 0
    # 寫 /api/health 的 skills 區塊（本機檔，套件會讀）
    hp = root / ".kiro" / "skills.verify.json"
    hp.parent.mkdir(parents=True, exist_ok=True)
    prev = json.loads(hp.read_text(encoding="utf-8")) if hp.exists() else {}
    hp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    # 同版且與上次相同 → 只寫 health 不發 TG
    same_as_prev = (prev.get("release") == state.get("release")
                    and prev.get("lag") == state.get("lag")
                    and prev.get("manifest") == state.get("manifest"))
    line = (f"{deployment} · release {state.get('release')} → latest {state.get('latest_release','?')} "
            f"(lag {state.get('lag','?')}, manifest {state.get('manifest')})")
    if (changed or force) and not (same_as_prev and not force):
        chat = os.getenv("ARK_TEAM_CHAT_ID", "")
        print(f"[TG→team{'('+chat+')' if chat else ''}] {line}")
    else:
        print(f"[health-only] {line}（同版無變化，不發 TG）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="消費端 skill 版本對齊")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("--waves", action="store_true")
    sub.add_parser("verify").add_argument("--remote", action="store_true")
    sub.add_parser("resolve").add_argument("path")
    ap_apply = sub.add_parser("apply"); ap_apply.add_argument("--wave", type=int); ap_apply.add_argument("--yes", action="store_true")
    ap_apply.add_argument("--upstream", help="上游 ark-agent-skills 本機 clone（預設讀 matrix 的 upstream.local_clone）")
    ap_hb = sub.add_parser("heartbeat"); ap_hb.add_argument("--force", action="store_true")
    args = ap.parse_args()
    root = Path.cwd()
    if args.cmd == "plan":
        return cmd_plan(root, args.waves)
    if args.cmd == "verify":
        return cmd_verify(root, args.remote)
    if args.cmd == "resolve":
        return cmd_resolve(root, Path(args.path))
    if args.cmd == "heartbeat":
        return cmd_heartbeat(root, args.force)
    if args.cmd == "apply":
        return cmd_apply(root, args.wave, args.yes, args.upstream)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
