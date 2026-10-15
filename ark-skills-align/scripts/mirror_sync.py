#!/usr/bin/env python3
"""mirror_sync.py — 消費端 `.kiro/skills` 整份複本對齊上游（規格：references/mirror-sync.md）。

適用沒有接 align_sync（無 skills-matrix / lock）的 team。逐檔以 git blob hash 判定：
本地內容曾存在於上游歷史 → 過期，可對齊；從未存在 → 本地修改，不覆蓋、列出待審。

用法:
    python mirror_sync.py plan  --upstream <skills repo> --target <team 根> [--keep PATH ...] [--json]
    python mirror_sync.py apply --upstream <skills repo> --target <team 根> [--keep PATH ...] [--only SKILL ...] --yes

exit: 0 正常；2 參數錯誤／apply 未帶 --yes；3 上游不是 git repo。
"""
from __future__ import annotations

import sys

if __name__ == "__main__" and any(a in ("-h", "--help") for a in sys.argv[1:]):
    print(__doc__)
    sys.exit(0)

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

IGNORE_DIRS = {"__pycache__"}
IGNORE_SUFFIXES = {".pyc"}


@dataclass
class SkillReport:
    """單一 skill 複本的判定結果。"""

    base: str                                    # 複本所在 team（相對 target）
    name: str
    status: str = "SAME"                         # SAME / STALE / LOCAL / NEWER
    local_version: str | None = None
    upstream_version: str | None = None
    stale: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    obsolete: list[str] = field(default_factory=list)
    local_data: list[str] = field(default_factory=list)
    keep: list[str] = field(default_factory=list)
    local_mod: list[str] = field(default_factory=list)


def _files(root: Path) -> dict[str, Path]:
    """列出 skill 目錄內的檔案（相對路徑 → 實體），略過快取。"""
    out = {}
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix in IGNORE_SUFFIXES:
            continue
        rel = p.relative_to(root)
        if IGNORE_DIRS.intersection(rel.parts):
            continue
        out[rel.as_posix()] = p
    return out


def blob_hash(path: Path) -> str:
    """與 `git hash-object` 相同的 blob sha1。"""
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _version(skill_md: Path) -> tuple[int, ...] | None:
    """讀 SKILL.md 的 metadata.version；缺則 None（視為最舊）。"""
    if not skill_md.exists():
        return None
    m = re.search(r'^\s+version:\s*"?(\d+(?:\.\d+)*)', skill_md.read_text(encoding="utf-8", errors="ignore"), re.M)
    if not m:
        return None
    nums = [int(x) for x in m.group(1).split(".")]
    return tuple((nums + [0, 0, 0])[:3])


def _fmt(v: tuple[int, ...] | None) -> str | None:
    return ".".join(map(str, v)) if v else None


def export_upstream(upstream: Path, dest: Path) -> set[str]:
    """把上游 HEAD 匯出到 dest（只含已追蹤檔），回傳上游歷史的 blob 集合。"""
    if subprocess.run(["git", "-C", str(upstream), "rev-parse", "--git-dir"],
                      capture_output=True).returncode != 0:
        raise NotADirectoryError(f"上游不是 git repo：{upstream}")
    tar = subprocess.run(["git", "-C", str(upstream), "archive", "--format=tar", "HEAD"],
                         capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as tf:
        try:
            tf.extractall(dest, filter="data")
        except TypeError:                          # Python < 3.11.4 無 filter 參數
            tf.extractall(dest)
    objs = subprocess.run(["git", "-C", str(upstream), "rev-list", "--all", "--objects"],
                          capture_output=True, text=True, check=True).stdout
    return {line.split(" ", 1)[0] for line in objs.splitlines() if line}


def _kept(rel: str, keep: list[str]) -> bool:
    return any(rel == k or rel.startswith(k.rstrip("/") + "/") for k in keep)


def skill_dirs(target: Path) -> list[Path]:
    """team 根與 projects/* 底下的 `.kiro/skills`（symlink 跳過）。"""
    cands = [target / ".kiro" / "skills"] + sorted((target / "projects").glob("*/.kiro/skills"))
    return [d for d in cands if d.is_dir() and not d.is_symlink()]


def ignored_by_upstream(upstream: Path, name: str, rels: list[str]) -> set[str]:
    """本地獨有檔中，符合上游 .gitignore 者（測試產物等）—— 不算本地資料、對齊時不保留。"""
    if not rels:
        return set()
    r = subprocess.run(["git", "-C", str(upstream), "check-ignore", "--no-index", "--stdin"],
                       input="\n".join(f"{name}/{x}" for x in rels), capture_output=True, text=True)
    return {line.split("/", 1)[1] for line in r.stdout.splitlines() if "/" in line}


def classify(local: Path, up: Path, history: set[str], keep: list[str], base: str,
             ignored: set[str] = frozenset()) -> SkillReport:
    """依規格逐檔判定一個 skill 複本。`ignored`：上游 .gitignore 命中的本地獨有檔。"""
    r = SkillReport(base=base, name=local.name)
    lv, uv = _version(local / "SKILL.md"), _version(up / "SKILL.md")
    r.local_version, r.upstream_version = _fmt(lv), _fmt(uv)
    lf, uf = _files(local), _files(up)
    for rel in sorted(lf.keys() & uf.keys()):
        if lf[rel].read_bytes() == uf[rel].read_bytes():
            continue
        if blob_hash(lf[rel]) in history:
            r.stale.append(rel)
        elif _kept(rel, keep):
            r.keep.append(rel)
        else:
            r.local_mod.append(rel)
    for rel in sorted(lf.keys() - uf.keys() - ignored):
        (r.obsolete if blob_hash(lf[rel]) in history else r.local_data).append(rel)
    r.missing = sorted(uf.keys() - lf.keys())

    if lv and uv and lv > uv:
        r.status = "NEWER"
    elif r.local_mod:
        r.status = "LOCAL"
    elif r.stale or r.missing or r.obsolete:
        r.status = "STALE"
    return r


def apply_one(local: Path, up: Path, r: SkillReport) -> None:
    """以上游內容重建複本，保留 keep 與 local-data 檔。"""
    staging = local.with_name(local.name + ".mirror-sync-tmp")
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(up, staging)
    for rel in r.keep + r.local_data:
        dst = staging / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local / rel, dst)
    shutil.rmtree(local)
    staging.rename(local)


def run(upstream: Path, target: Path, keep: list[str], only: list[str] | None,
        do_apply: bool) -> list[SkillReport]:
    """掃描 target 全部複本；do_apply 時對齊 STALE。"""
    reports: list[SkillReport] = []
    with tempfile.TemporaryDirectory() as tmp:
        up_root = Path(tmp)
        history = export_upstream(upstream, up_root)
        for d in skill_dirs(target):
            base = d.parent.parent.relative_to(target).as_posix()
            for local in sorted(p for p in d.iterdir() if p.is_dir() and not p.is_symlink()):
                up = up_root / local.name
                if not (up / "SKILL.md").exists() or not (local / "SKILL.md").exists():
                    continue                       # 本地獨有 skill（domain／local_only）不碰
                if only and local.name not in only:
                    continue
                only_local = sorted(set(_files(local)) - set(_files(up)))
                ign = ignored_by_upstream(upstream, local.name, only_local)
                r = classify(local, up, history, keep, base, ign)
                if r.status == "SAME":
                    continue
                if do_apply and r.status == "STALE":
                    apply_one(local, up, r)
                reports.append(r)
    return reports


def _print_human(reports: list[SkillReport], applied: bool) -> None:
    if not reports:
        print("✅ 全部與上游一致")
        return
    for r in reports:
        ver = f"{r.local_version or '?'}→{r.upstream_version or '?'}"
        print(f"[{r.status}] {r.base}/{r.name} ({ver}) stale={len(r.stale)} missing={len(r.missing)} "
              f"obsolete={len(r.obsolete)} 保留={len(r.keep) + len(r.local_data)}")
        for rel in r.local_mod:
            print(f"    ⚠️ 本地修改（上游從未有過）：{rel}")
    counts: dict[str, int] = {}
    for r in reports:
        counts[r.status] = counts.get(r.status, 0) + 1
    verb = "已對齊" if applied else "可對齊"
    print(f"\n{verb} STALE {counts.get('STALE', 0)}｜待審 LOCAL {counts.get('LOCAL', 0)}"
          f"｜本地較新 NEWER {counts.get('NEWER', 0)}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="消費端 .kiro/skills 整份複本對齊上游")
    ap.add_argument("verb", choices=["plan", "apply"])
    ap.add_argument("--upstream", required=True, type=Path, help="ark-agent-skills 本機 clone")
    ap.add_argument("--target", required=True, type=Path, help="team repo 根")
    ap.add_argument("--keep", action="append", default=[], help="保留本地版本的 skill 內相對路徑（可重複）")
    ap.add_argument("--only", action="append", help="只處理指定 skill（可重複）")
    ap.add_argument("--yes", action="store_true", help="apply 必填")
    ap.add_argument("--json", action="store_true", help="輸出 JSON")
    a = ap.parse_args(argv)

    if a.verb == "apply" and not a.yes:
        print("❌ apply 需帶 --yes（先跑 plan 確認）", file=sys.stderr)
        return 2
    try:
        reports = run(a.upstream.resolve(), a.target.resolve(), a.keep, a.only, a.verb == "apply")
    except NotADirectoryError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 3
    if a.json:
        print(json.dumps([r.__dict__ for r in reports], ensure_ascii=False, indent=2))
    else:
        _print_human(reports, a.verb == "apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
