#!/usr/bin/env python3
"""gen_manifest.py — 產 release/manifest.json + release/index.json（ADR-001/002）。

manifest = 這班列車每個 active skill 的 version/tree_hash/contract_hash/depends_on/status。
index = 累積的 tree_hash → {skill, version, release}，供消費端把「不知道哪來的複本」反查成版本。

tree_hash：sha256 於排序後的檔案清單（相對路徑 + 內容），排除 __pycache__/.pyc。
contract_hash：只對 contract_files（預設 scripts/** schemas/** references/*contract*.md
               references/*schema*.md assets/hooks/**）算 —— 契約變了才算破壞性。

CI 守門（W1 接入）：只在 audit P0/P1=0 且 AL-105=0 時允許打 tag。
用法：python gen_manifest.py --repo . --release skills-2026.09-r1 [--out release/]
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

DEFAULT_CONTRACT_GLOBS = [
    "scripts/**", "schemas/**",
    "references/*contract*.md", "references/*schema*.md",
    "assets/hooks/**",
]
FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _iter_files(skill_dir: Path):
    for p in sorted(skill_dir.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
            yield p


def _hash_files(skill_dir: Path, files) -> str:
    h = hashlib.sha256()
    for p in sorted(files, key=lambda x: str(x.relative_to(skill_dir))):
        h.update(str(p.relative_to(skill_dir)).encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return "sha256:" + h.hexdigest()


def tree_hash(skill_dir: Path) -> str:
    return _hash_files(skill_dir, list(_iter_files(skill_dir)))


def contract_hash(skill_dir: Path, globs: list[str]) -> str:
    matched = []
    for p in _iter_files(skill_dir):
        rel = str(p.relative_to(skill_dir))
        if any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(rel, g.replace("**", "*"))
               or (g.endswith("/**") and rel.startswith(g[:-3] + "/")) for g in globs):
            matched.append(p)
    return _hash_files(skill_dir, matched)


def parse_meta(skill_md: Path) -> dict:
    m = FM_RE.match(skill_md.read_text(encoding="utf-8"))
    if not m:
        return {}
    fm = yaml.safe_load(m.group(1)) or {}
    return fm.get("metadata") or {}


def build(repo: Path, release: str) -> tuple[dict, dict]:
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
    }
    # index：tree_hash → {skill, version, release}（累積）
    index = {}
    idx_path = repo / "release" / "index.json"
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
    manifest, index = build(repo, args.release)
    out = repo / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ manifest：{len(manifest['skills'])} skills · release {args.release} · index {len(index)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
