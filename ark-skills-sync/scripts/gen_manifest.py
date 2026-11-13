#!/usr/bin/env python3
"""gen_manifest.py — 產 release/manifest.json + release/index.json（ADR-001/002）。

manifest = 這班列車每個 active skill 的 version/tree_hash/contract_hash/depends_on/status。
index = 累積的 tree_hash → {skill, version, release}，供消費端把「不知道哪來的複本」反查成版本。

tree_hash：sha256 於排序後的檔案清單（相對路徑 + 內容）；在 git repo 只算 git 看得到的檔（照 .gitignore），
          另排除 __pycache__/.pytest_cache/node_modules/.pyc 與頂層 release/。
contract_hash：只對 contract_files（預設 scripts/** schemas/** references/*contract*.md
               references/*schema*.md assets/hooks/**）算 —— 契約變了才算破壞性。

CI 守門（W1 接入）：只在 audit P0/P1=0 且 AL-105=0 時允許打 tag。
用法：python gen_manifest.py --repo . --release skills-2026.09-r2 [--out release/]
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 雜湊與 frontmatter 共用算法搬到 skilltree（2026-11-13）；舊名 re-export，audit_skills 等呼叫端不用改
from skilltree import (DEFAULT_CONTRACT_GLOBS, FM_RE, HASH_EXCLUDE_DIRS, JUNK_DIRS,  # noqa: E402,F401
                       contract_hash, parse_meta, tree_hash)


ROLE_MAP = Path("ark-agent-init") / "assets" / "role-skills-map.yaml"


def tiers_default(repo: Path) -> dict:
    """角色 → skill 清單（align_sync 據此算每個 agent 的目標集合）。

    唯一權威是 ark-agent-init 的 role-skills-map.yaml；manifest 只是帶著它出貨。
    🔴 2026-10-30 補：align_sync 一直讀 `tiers_default`，但本檔從沒產過 → 角色集合恆為空、只剩 extra。
    """
    f = repo / ROLE_MAP
    if not f.is_file():
        return {"base": [], "role": {}}
    data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return {"base": list(data.get("base_skills") or []),
            "role": {k: list(v or []) for k, v in (data.get("role_skills") or {}).items()}}


def build(repo: Path, release: str, out_dir: Path | None = None) -> tuple[dict, dict]:
    skills = {}
    for d in sorted(repo.iterdir()):
        sk = d / "SKILL.md"
        if not (d.is_dir() and d.name.startswith("ark-") and sk.exists()):
            continue
        meta = parse_meta(sk)
        if meta.get("status", "active") != "active":
            continue
        globs = meta.get("contract_files") or DEFAULT_CONTRACT_GLOBS
        skills[d.name] = {
            "version": str(meta.get("version", "")),
            "tree_hash": tree_hash(d),
            "contract_hash": contract_hash(d, globs),
            "status": "active",
            "category": meta.get("category", ""),
            "depends_on": meta.get("depends_on", []),
            "replaces": meta.get("replaces", []),
            "updated": str(meta.get("updated", "")),
        }
    commit = ""
    try:
        import subprocess
        commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True).stdout.strip()
    except Exception:
        pass
    manifest = {
        "release": release, "commit": commit,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "skills": skills,
        "tiers_default": tiers_default(repo),
    }
    # index：tree_hash → {skill, version, release}（累積）
    # 🔴 讀舊 index 必須用「實際輸出路徑」（--out），不能寫死 repo/release
    #    否則 --out 指向別處時讀不到舊 index → 歷史 tree_hash 反查全失（累積失效）
    index = {}
    idx_path = (out_dir or (repo / "release")) / "index.json"
    if idx_path.exists():
        index = json.loads(idx_path.read_text(encoding="utf-8"))
    for name, s in skills.items():
        index[s["tree_hash"]] = {"skill": name, "version": s["version"], "release": release}
    return manifest, index


def main() -> int:
    ap = argparse.ArgumentParser(description="產 release manifest + index")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--release", required=True, help="列車號 skills-YYYY.MM-rN")
    ap.add_argument("--out", default="release")
    args = ap.parse_args()
    repo = Path(args.repo)
    out = repo / args.out
    manifest, index = build(repo, args.release, out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ manifest：{len(manifest['skills'])} skills · release {args.release} · index {len(index)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
