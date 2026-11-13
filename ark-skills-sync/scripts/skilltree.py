#!/usr/bin/env python3
"""skilltree.py — skill 目錄的共用判定（ark-skills-sync 共用模組 C-3／C-4）。

一份 skill 的「內容是什麼、算不算裝好」只能有一套算法：列車 manifest（gen_manifest）、
稽核（audit_skills）、版本鎖（mirror_sync）、啟動檢查（skills_sync doctor）都 import 這裡。

- tree_hash／contract_hash：搬自 gen_manifest（2026-11-13，演算法逐字不變；gen_manifest 仍 re-export 舊名）
- parse_frontmatter：SKILL.md frontmatter → name／description／status／domain／version／successor
- skill_state：OK｜BROKEN（目錄在但缺 SKILL.md、或 frontmatter 讀不出 name）
"""
from __future__ import annotations

import fnmatch
import hashlib
import re
import subprocess
from pathlib import Path

import yaml

DEFAULT_CONTRACT_GLOBS = [
    "scripts/**", "schemas/**",
    "references/*contract*.md", "references/*schema*.md",
    "assets/hooks/**",
]
FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


#: 不計入 tree_hash 的頂層目錄 —— `release/` 是本工具產的列車資料（manifest／index），
#: 計入的話每次重產都會讓 ark-skills-sync 自己的 tree_hash 變動、卻沒有升版（自我參照）。
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
    # 路徑一律用 posix（/）：Windows 的 str(Path) 是「\」，雜湊與 glob 比對會和 Linux 不同（2.x 修，Linux 結果不變）
    for p in sorted(files, key=lambda x: x.relative_to(skill_dir).as_posix()):
        h.update(p.relative_to(skill_dir).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return "sha256:" + h.hexdigest()


def tree_hash(skill_dir: Path) -> str:
    return _hash_files(skill_dir, list(_iter_files(skill_dir)))


def contract_hash(skill_dir: Path, globs: list[str]) -> str:
    matched = []
    for p in _iter_files(skill_dir):
        rel = p.relative_to(skill_dir).as_posix()
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


#: skill 健全性
OK, BROKEN = "OK", "BROKEN"
_SUCC_RE = re.compile(r"已併入\s*(ark-[a-z0-9-]+)")


def parse_frontmatter(text: str) -> dict:
    """SKILL.md 全文 → 常用欄位；讀不出 frontmatter 回 {}。"""
    m = FM_RE.match(text.replace("\r\n", "\n"))
    if not m:
        return {}
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(fm, dict):
        return {}
    meta = fm.get("metadata") or {}
    desc = str(fm.get("description") or "")
    status = str(meta.get("status") or fm.get("status") or "active")
    deprecated = status == "deprecated" or desc.lstrip().startswith("[DEPRECATED")
    succ = _SUCC_RE.search(desc)
    return {"name": fm.get("name"), "description": desc, "status": status,
            "domain": meta.get("domain") or fm.get("domain") or "general",
            "version": str(meta.get("version") or ""), "deprecated": deprecated,
            "successor": succ.group(1) if succ else None}


def skill_state(skill_dir: Path) -> str:
    """目錄在、有 SKILL.md 且 frontmatter 有 name → OK；否則 BROKEN（例：只剩 __pycache__ 的空殼）。"""
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return BROKEN
    try:
        fm = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return BROKEN
    return OK if fm.get("name") else BROKEN
