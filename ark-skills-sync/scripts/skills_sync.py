#!/usr/bin/env python3
"""skills_sync.py — 專案（消費端）skills 的安裝／更新／健檢入口（ark-skills-sync）。

規範（SKILL.md「規範」段）：專案只裝自己需要的 skill，**實體複本**進自己的 git；
更新來源＝本機上游 clone 或 GitHub（`upstream.py` 的優先序）。

動詞（預設唯讀；會寫檔的只有 update --apply、install、remove、doctor --repair）：
    status                       每個目錄：需要／已裝／缺少／空殼／舊名殘留／STALE／LOCAL
    plan                         = update 預覽
    update [--apply] [--prune]   補裝缺的與空殼 → mirror_sync 對齊 STALE；--prune 另 git rm 不需要的與舊名
    install NAME… [--to DIR]     從上游裝指定 skill（拒絕已併入他處的舊名，提示接手者）
    remove NAME… [--from DIR]    git rm 指定 skill 複本，列出文件中仍引用它的地方
    doctor [--bundle DIR] [--require T=a,b] [--repair] [--upstream auto|off|SRC]
                                 啟動檢查（套件呼叫；離線可用）：MISSING／BROKEN／RESIDUE，可選比對上游
    residue                      轉呼上游 scripts/check_consumers.py（舊名引用、缺接手者）

需要哪些：`<.kiro|.ark>/skills-manifest.yaml`（見 references/sop-install-remove.md）；沒有 manifest 時
根目錄與 agents/* 都「以已安裝的為準」（只對齊、不增刪）。
不 commit、不 push：寫入後印出 pathspec 提交指令。LOCAL（本地改過）永不覆蓋。
exit：0 一致／1 有差異或待處理／2 參數或上游錯誤
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mirror_sync as M  # noqa: E402
import upstream as UP  # noqa: E402
from ark_layout import find_ark_dirs, skills_dir  # noqa: E402
from skilltree import BROKEN, parse_frontmatter, skill_state  # noqa: E402

import yaml  # noqa: E402

DEFAULT_TARGETS = [".", "agents/*"]


# ── manifest 與上游 ─────────────────────────────────────────────────────────────
def manifest_path(root: Path) -> Path:
    return find_ark_dirs(root)[1] / "skills-manifest.yaml"


def load_manifest(root: Path, explicit: str | None) -> tuple[dict, Path | None]:
    p = Path(explicit) if explicit else manifest_path(root)
    if not p.is_file():
        if explicit:
            raise SystemExit(f"❌ 找不到 manifest：{p}")
        return {}, None
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}, p


def _git(repo: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", check=check)


def upstream_skills(U: Path) -> dict[str, dict]:
    """上游 HEAD 的 ark-* skill → frontmatter 摘要（含 deprecated／successor）。"""
    out: dict[str, dict] = {}
    names = _git(U, "ls-tree", "--name-only", "HEAD").stdout.split()
    for n in names:
        if not n.startswith("ark-"):
            continue
        r = _git(U, "show", f"HEAD:{n}/SKILL.md")
        if r.returncode == 0:
            fm = parse_frontmatter(r.stdout)
            if fm:
                out[n] = fm
    return out


# ── 本地 ──────────────────────────────────────────────────────────────────────
def expand_targets(root: Path, patterns: list[str]) -> list[Path]:
    seen: list[Path] = []
    for pat in patterns:
        for p in sorted(glob.glob(str(root / pat))):
            pp = Path(p)
            if pp.is_dir() and skills_dir(pp).is_dir() and not skills_dir(pp).is_symlink() and pp not in seen:
                seen.append(pp)
    return seen


def installed(target: Path) -> tuple[set[str], set[str]]:
    """(健全的 skill, 空殼／壞掉的)。只看 ark-* 目錄。"""
    ok, broken = set(), set()
    for d in sorted(skills_dir(target).glob("ark-*")):
        if d.is_dir() and not d.is_symlink():
            (broken if skill_state(d) == BROKEN else ok).add(d.name)
    return ok, broken


def local_deprecated(target: Path, names: set[str]) -> list[str]:
    """離線也能判的舊名：本地複本自己的 frontmatter 就標了 deprecated。"""
    out = []
    for n in sorted(names):
        md = skills_dir(target) / n / "SKILL.md"
        if parse_frontmatter(md.read_text(encoding="utf-8", errors="replace")).get("deprecated"):
            out.append(n)
    return out


def needed(rel: str, ok: set[str], broken: set[str], up: dict[str, dict], mf: dict) -> set[str]:
    per = mf.get("target_needs") or {}
    if rel in per:
        return {n for n in per[rel] if n in up}
    if rel == "." and mf.get("include_domains") is not None:
        doms = mf.get("include_domains") or []
        names = {n for n, s in up.items() if not s["deprecated"] and ("all" in doms or s["domain"] in doms)}
        names |= {n for n in mf.get("include", []) if n in up}
        return names - set(mf.get("exclude", []))
    # agents/*（或沒有 manifest）：以已有的目錄為準 —— 角色子集刻意不同
    return {n for n in (ok | broken) if n in up and not up[n]["deprecated"]}


def analyse(root: Path, mf: dict, U: Path, up: dict[str, dict]) -> list[dict]:
    rows = []
    for t in expand_targets(root, mf.get("targets") or DEFAULT_TARGETS):
        rel = os.path.relpath(t, root)
        ok, broken = installed(t)
        need = needed(rel, ok, broken, up, mf)
        by: dict[str, list[str]] = {}
        for r in M.run(U, t, [], None, do_apply=False, root_only=True):
            by.setdefault(r.status, []).append(r.name)
        row = {"target": rel, "need": len(need), "installed": len(ok),
               "missing": sorted(need - ok - broken),
               "broken": sorted(n for n in broken if n in up),
               "residue": sorted(n for n in ok if n in up and up[n]["deprecated"]),
               "extra": sorted(n for n in ok if n in up and not up[n]["deprecated"] and n not in need),
               "plan": by}
        row["ok"] = not (row["missing"] or row["broken"] or by.get("STALE") or by.get("LOCAL") or by.get("BROKEN"))
        rows.append(row)
    return rows


# ── 動作 ──────────────────────────────────────────────────────────────────────
def install(U: Path, target: Path, names: list[str]) -> None:
    """git archive 上游 HEAD 的指定 skill 解到 target 的 skills 目錄（覆蓋同名檔、不刪多餘檔）。"""
    if not names:
        return
    dest = skills_dir(target)
    dest.mkdir(parents=True, exist_ok=True)
    arch = subprocess.Popen(["git", "-C", str(U), "archive", "HEAD", *names], stdout=subprocess.PIPE)
    tar = subprocess.run(["tar", "-x", "-C", str(dest)], stdin=arch.stdout)
    arch.stdout.close()
    if arch.wait() != 0 or tar.returncode != 0:
        raise SystemExit(f"❌ 安裝失敗：{names}")


def prune(root: Path, target: Path, names: list[str], force: bool = False) -> list[str]:
    """只 git rm 已進版控的複本；未追蹤的列出交人處理（不做遞迴刪除）。

    目錄內有未提交修改時預設不刪（可能是本地客製）；確認可丟（例：剛被 update 換成 stub）才帶 force。
    """
    done = []
    for n in names:
        p = skills_dir(target) / n
        rel = os.path.relpath(p, root)
        if _git(root, "ls-files", "--error-unmatch", "--", str(p / "SKILL.md")).returncode != 0:
            print(f"  ⚠ {rel} 未進版控，不代刪：請自行處理")
            continue
        dirty = _git(root, "status", "--porcelain", "--", str(p)).stdout.strip()
        if dirty and not force:
            print(f"  ⚠ {rel} 有未提交的修改，不刪（確認可丟再加 --force）：\n    " + dirty.replace("\n", "\n    ")[:400])
            continue
        r = _git(root, "rm", "-r", "-q", *(["-f"] if force else []), "--", str(p))
        if r.returncode != 0:
            print(f"  ⚠ {rel} git rm 失敗：{(r.stderr or r.stdout).strip()[:200]}")
            continue
        done.append(n)
    return done


def references_to(root: Path, names: list[str]) -> list[str]:
    pat = "|".join(re.escape(n) for n in names)
    r = subprocess.run(["grep", "-rnE", "--exclude-dir=.git", "--exclude-dir=skills", "--exclude-dir=memory",
                        "--exclude-dir=output", "--exclude-dir=knowledge", "--exclude-dir=node_modules",
                        "--exclude-dir=projects", "--exclude-dir=github", pat, "."],
                       cwd=root, capture_output=True, text=True)
    return [h for h in r.stdout.splitlines() if "/skills/" not in h][:15]


# ── doctor（套件啟動檢查；離線可用） ──────────────────────────────────────────
def parse_require(items: list[str]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for it in items:
        t, _, names = it.partition("=")
        out.setdefault(t.strip() or ".", set()).update(n.strip() for n in names.split(",") if n.strip())
    return out


def doctor(root: Path, mf: dict, bundle: Path | None, require: dict[str, set[str]], repair: bool,
           upstream_mode: str) -> dict:
    bundled = {d.name for d in bundle.iterdir() if (d / "SKILL.md").is_file()} if bundle and bundle.is_dir() else set()
    U = up = None
    up_note = "off"
    if upstream_mode != "off":
        try:
            U = UP.resolve(None if upstream_mode == "auto" else upstream_mode, mf.get("upstream"), fetch=False)
            up = upstream_skills(U)
            up_note = UP.head(U)
        except (UP.UpstreamError, OSError) as e:
            up_note = f"unreachable：{str(e)[:120]}"
    rows = []
    for t in expand_targets(root, mf.get("targets") or DEFAULT_TARGETS):
        rel = os.path.relpath(t, root)
        ok, broken = installed(t)
        req = require.get(rel, set()) | require.get("*", set())
        if up is not None:
            req |= needed(rel, ok, broken, up, mf) if mf.get("include_domains") is not None and rel == "." else set()
        row = {"target": rel, "installed": len(ok), "missing": sorted(req - ok - broken), "broken": sorted(broken),
               "residue": local_deprecated(t, ok), "repaired": [], "stale": [], "local": []}
        if repair:
            for n in row["missing"] + row["broken"]:
                if n in bundled:
                    shutil.copytree(bundle / n, skills_dir(t) / n, dirs_exist_ok=True,
                                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                    row["repaired"].append(n)
            if row["repaired"]:
                ok2, broken2 = installed(t)             # 以重掃為準
                row["missing"] = sorted(req - ok2 - broken2)
                row["broken"] = sorted(broken2)
        if U is not None:
            for r in M.run(U, t, [], None, do_apply=False, root_only=True):
                if r.status in ("STALE", "LOCAL"):
                    row[r.status.lower()].append(r.name)
        rows.append(row)
    summary = {k: sum(len(r[k]) for r in rows) for k in ("missing", "broken", "residue", "stale", "local", "repaired")}
    return {"root": str(root), "targets": rows, "summary": summary, "upstream": up_note,
            "ok": bool(rows) and not (summary["missing"] or summary["broken"]),
            "note": "" if rows else "掃到 0 個 skills 目錄 —— 範圍錯了，不是全部通過"}


# ── CLI ──────────────────────────────────────────────────────────────────────
def _print_rows(rows: list[dict], U: Path, up: dict[str, dict]) -> None:
    print(f"上游：{U}\n      {UP.head(U)}（{len(up)} 個 skill，其中 {sum(s['deprecated'] for s in up.values())} 個為轉址 stub）")
    if not rows:
        print("\n⚠️ 掃到 0 個 skills 目錄 —— 範圍錯了（manifest targets？），不是全部通過")
    for r in rows:
        pl = "、".join(f"{k} {len(v)}" for k, v in r["plan"].items()) or "全部一致"
        print(f"\n{'✅' if r['ok'] else '⚠️ '} {r['target']:<22} 需要 {r['need']:>2}｜已裝 {r['installed']:>2}｜對齊：{pl}")
        for key, label in (("missing", "缺少（需要但沒裝）"), ("broken", "空殼／壞掉（缺 SKILL.md）"),
                           ("residue", "已併入他處的舊名（--prune 可移除）"), ("extra", "裝了但 manifest 不需要（--prune 可移除）")):
            if r[key]:
                print(f"   {label}：{', '.join(r[key])}")
        if r["plan"].get("LOCAL"):
            print(f"   LOCAL（本地改過，不覆蓋；判斷是否回貢上游）：{', '.join(r['plan']['LOCAL'])}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="專案 skills 安裝／更新／健檢（ark-skills-sync）")
    ap.add_argument("cmd", choices=["status", "plan", "update", "install", "remove", "doctor", "residue"])
    ap.add_argument("names", nargs="*")
    ap.add_argument("--root", default=".")
    ap.add_argument("--manifest")
    ap.add_argument("--upstream", help="本機上游目錄或 git URL；doctor 另接受 auto／off（預設 off）")
    ap.add_argument("--cache", default=UP.DEFAULT_CACHE)
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--to", default=".")
    ap.add_argument("--from", dest="frm", default=".")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--prune", action="store_true")
    ap.add_argument("--force", action="store_true", help="remove／--prune：目錄有未提交修改也刪")
    ap.add_argument("--bundle", help="doctor：套件內建 templates/skills（可修 MISSING／BROKEN）")
    ap.add_argument("--require", action="append", default=[], help="doctor：TARGET=a,b（TARGET 用 * 表全部）")
    ap.add_argument("--repair", action="store_true", help="doctor：只從 --bundle 補 MISSING／BROKEN")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_intermixed_args(argv)          # 允許 `install NAME --to DIR NAME2` 混排
    root = Path(a.root).resolve()
    mf, mpath = load_manifest(root, a.manifest)

    if a.cmd == "doctor":
        rep = doctor(root, mf, Path(a.bundle) if a.bundle else None, parse_require(a.require), a.repair,
                     a.upstream or "off")
        if a.json:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            s = rep["summary"]
            print(rep["note"] or f"{'✅' if rep['ok'] else '⚠️ '} skills doctor：缺 {s['missing']}、壞 {s['broken']}、"
                  f"舊名 {s['residue']}、已修 {s['repaired']}｜上游 {rep['upstream']}")
            for r in rep["targets"]:
                bad = {k: r[k] for k in ("missing", "broken", "residue", "repaired", "stale", "local") if r[k]}
                if bad:
                    print(f"   {r['target']}: {bad}")
        return 0 if rep["ok"] else 1

    try:
        U = UP.resolve(a.upstream, mf.get("upstream"), fetch=(a.cmd == "update" and not a.no_fetch), cache=a.cache)
    except UP.UpstreamError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    if a.cmd == "residue":
        cc = U / "scripts" / "check_consumers.py"
        return subprocess.run([sys.executable, str(cc), "--repo", str(U), "--consumers", str(root), *a.names]).returncode

    up = upstream_skills(U)
    if a.cmd in ("install", "remove"):
        if not a.names:
            print("❌ 請列出 skill 名稱", file=sys.stderr)
            return 2
        t = (root / (a.to if a.cmd == "install" else a.frm)).resolve()
        if a.cmd == "install":
            bad = [n for n in a.names if n not in up]
            dep = [(n, up[n]["successor"]) for n in a.names if n in up and up[n]["deprecated"]]
            if bad or dep:
                print(f"❌ 上游沒有：{bad}；已併入他處（請改裝接手者）：{dep}", file=sys.stderr)
                return 2
            install(U, t, a.names)
            print(f"✅ 已安裝 {', '.join(a.names)} → {os.path.relpath(skills_dir(t), root)}（未 commit）")
        else:
            gone = prune(root, t, a.names, a.force)
            print(f"✅ 已 git rm：{', '.join(gone) or '（無）'}（未 commit）")
            hits = references_to(root, a.names)
            print("文件中仍引用（改成接手者或拿掉）：" + ("\n  " + "\n  ".join(hits) if hits else "無"))
        return 0

    rows = analyse(root, mf, U, up)
    if a.cmd == "plan":
        a.cmd, a.apply = "update", False
    if a.cmd == "update" and a.apply:
        for r in rows:
            t = root / r["target"]
            install(U, t, sorted(set(r["missing"]) | set(r["broken"])))
            if a.prune:
                prune(root, t, (r["extra"] if r["target"] == "." and mpath else []) + r["residue"], a.force)
            M.run(U, t, [], None, do_apply=True, root_only=True)
        rows = analyse(root, mf, U, up)                 # 結果以重掃為準，不信剛才的動作
    if a.json:
        print(json.dumps({"upstream": str(U), "head": UP.head(U), "manifest": str(mpath) if mpath else None,
                          "targets": rows}, ensure_ascii=False, indent=2))
    else:
        if mpath is None:
            print("ℹ️ 沒有 skills-manifest.yaml：各目錄以已安裝的為準（只對齊、不增刪）")
        _print_rows(rows, U, up)
        if a.cmd == "update" and not a.apply:
            print("\n（預覽，未寫入。--apply 執行；--prune 一併移除不需要的與舊名）")
        if a.cmd == "update" and a.apply:
            sd = os.path.relpath(skills_dir(root), root)            # .ark/skills 或 .kiro/skills（依佈局）
            print("\n提交（pathspec，禁 git add -A）：\n"
                  f"  git add --all -- ':(glob)agents/*/{sd}/**' {sd} {os.path.relpath(manifest_path(root), root)}\n"
                  "  git diff --cached --name-only | grep -v 'skills'   # 應為空\n"
                  "  git commit -m 'chore(skills): skills_sync 對齊上游 <commit>'")
    return 0 if rows and all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
