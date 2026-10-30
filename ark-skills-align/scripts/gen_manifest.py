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

DEFAULT_CONTRACT_GLOBS = [
    "scripts/**", "schemas/**",
    "references/*contract*.md", "references/*schema*.md",
    "assets/hooks/**",
]
FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


#: 不計入 tree_hash 的頂層目錄 —— `release/` 是本工具產的列車資料（manifest／index），
#: 計入的話每次重產都會讓 ark-skills-align 自己的 tree_hash 變動、卻沒有升版（自我參照）。
#: align_sync._tree_hash 必須同步排除，否則兩邊算出的 hash 不一致。
HASH_EXCLUDE_DIRS = ("release",)


#: 執行期產物目錄 —— 非 git 環境（消費端複本）時的明確排除；align_sync._tree_hash 用同一份清單
JUNK_DIRS = {"__pycache__", ".pytest_cache", "node_modules"}


def _git_listed(skill_dir: Path) -> list[Path] | None:
    """git 管理的檔（已追蹤＋未被 .gitignore 忽略的新檔）；不在 git repo → None。

    🔴 2026-10-27：原本 rglob 全掃，`.pytest_cache`（自帶 `.gitignore: *`、根 .gitignore 沒列）被算進 hash
    —— 先跑測試再產 manifest，記下的就是被污染的 tree_hash，乾淨 checkout 永遠對不上。
    `--exclude-standard` 會照每一層的 .gitignore 判斷，跟 git 看到的內容一致。
    """
    import subprocess
    r = subprocess.run(["git", "-C", str(skill_dir), "ls-files", "-co", "--exclude-standard", "-z", "--", "."],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return [skill_dir / rel for rel in r.stdout.split("\0") if rel]


def _iter_files(skill_dir: Path):
    listed = _git_listed(skill_dir)
    files = listed if listed is not None else [p for p in skill_dir.rglob("*") if p.is_file()]
    for p in sorted(files):
        rel = p.relative_to(skill_dir)
        if not p.is_file() or JUNK_DIRS & set(rel.parts) or p.suffix == ".pyc":
            continue
        if rel.parts[0] in HASH_EXCLUDE_DIRS:
            continue
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
