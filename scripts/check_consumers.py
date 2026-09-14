#!/usr/bin/env python3
"""check_consumers.py — 移除／改名 skill 前後，反向掃描「誰還在指著它」。

## 為什麼需要這支

消費端各自有 `sync_skills.py --check`，而且它**本來就會**在來源不存在時回 1。
問題不是偵測不到，是**沒有人會去跑它** —— 移除 skill 的人在上游 repo，
消費端在別的 repo、甚至別台機器上，要等到某天有人手動同步才會發現。

2026-09-14 一天內就發生兩次：兩個 skill 被併掉之後，3 個 sync 矩陣共 10 處、
9 份 SOUL.md、12 份已部署複本、1 份蒸餾設定仍指著舊名 ——
全部是**靜默失效**（sync 印一行「跳過」、蒸餾掃出零筆），沒有任何東西會變紅。

> 🔴 判準：**上游做移除，就要由上游負責掃消費端。**
> 「消費端自己會檢查」在多 repo／多機器的情況下等於沒有檢查。

## 掃描面（都是今天實際踩到的形態）

| 面 | 檔案 | 失效樣態 |
|---|---|---|
| 角色矩陣 | `*/scripts/sync_skills.py` 的 `MATRIX` / `COMMON` | sync 印「來源缺 X，跳過」 |
| 已部署複本 | `**/.kiro/skills/<name>/` | agent 讀到上游已刪的舊版 |
| 人格清單 | `**/steering/SOUL.md` 的 skill 條列 | agent 以為自己有這個能力 |
| 蒸餾來源 | `**/distill-sources.yaml` 的 `scan_paths` | 掃不存在的目錄 → 零筆，不報錯 |

用法：
    python check_consumers.py                      # 掃預設消費端根目錄
    python check_consumers.py --consumers ~/kiro-cli/projects
    python check_consumers.py --name ark-foo       # 只查某個名字（移除前先問「誰在用」）

Exit code：有懸空引用回 1；消費端根目錄不存在回 0（明說跳過，不假裝通過）。
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

SKILLS_REPO = Path(__file__).resolve().parent.parent
DEFAULT_CONSUMERS = SKILLS_REPO.parent.parent / "projects"

#: SOUL.md 的 skill 條列格式：- `ark-x` — `.kiro/skills/ark-x/SKILL.md`
SOUL_BULLET = re.compile(r"^-\s+`(ark-[a-z0-9-]+)`\s+—")
#: 蒸餾設定的 scan_paths 條目：  - ark-x/    # 註解
YAML_PATH = re.compile(r"^\s*-\s+(ark-[a-z0-9-]+)/\s*(?:#.*)?$")

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "state", ".index"}


def upstream_skills(repo: Path) -> set[str]:
    """上游現有的 skill（有 SKILL.md 才算 —— 只有 references/ 的目錄不是 skill）。"""
    return {d.name for d in repo.glob("ark-*") if (d / "SKILL.md").is_file()}


def _walk(root: Path, pattern: str):
    for p in root.rglob(pattern):
        if SKIP_DIRS & set(p.parts):
            continue
        yield p


def scan_matrices(root: Path) -> list[tuple[Path, str, set[str]]]:
    """讀每個 sync_skills.py 的 MATRIX / COMMON，扣掉它自己宣告的 LOCAL_ONLY。

    ⚠️ `MATRIX: dict[str, list[str]] = {...}` 是 **AnnAssign**（帶型別註記），
    只判 `ast.Assign` 會整個矩陣掃不到而回報「0 個引用」——
    2026-09-14 我第一版就是這樣，靠「引用 1 個」這個不合理的數字才發現。
    """
    out = []
    for f in _walk(root, "sync_skills.py"):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        vals: dict[str, object] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                tgt = getattr(node.targets[0], "id", "")
            elif isinstance(node, ast.AnnAssign):
                tgt = getattr(node.target, "id", "")
            else:
                continue
            if tgt in ("MATRIX", "COMMON", "LOCAL_ONLY", "ROOT_SOURCED"):
                try:
                    vals[tgt] = ast.literal_eval(node.value)
                except ValueError:
                    pass
        names: set[str] = set(vals.get("COMMON") or [])
        matrix = vals.get("MATRIX") or {}
        if isinstance(matrix, dict):
            names |= {s for lst in matrix.values() for s in lst}
        # LOCAL_ONLY 是「上游沒有的自建 skill」—— 不算懸空
        names -= set(vals.get("LOCAL_ONLY") or set())
        out.append((f, "matrix", {n for n in names if n.startswith("ark-")}))
    return out


def scan_deployed(root: Path) -> list[tuple[Path, str, set[str]]]:
    out = []
    for d in _walk(root, ".kiro"):
        sk = d / "skills"
        if not sk.is_dir():
            continue
        names = {p.name for p in sk.iterdir() if p.is_dir() and p.name.startswith("ark-")}
        if names:
            out.append((sk, "deployed", names))
    return out


def scan_souls(root: Path) -> list[tuple[Path, str, set[str]]]:
    out = []
    for f in _walk(root, "SOUL.md"):
        names = {m.group(1) for line in f.read_text(encoding="utf-8", errors="replace").splitlines()
                 if (m := SOUL_BULLET.match(line))}
        if names:
            out.append((f, "soul", names))
    return out


def scan_yaml_paths(root: Path) -> list[tuple[Path, str, set[str]]]:
    out = []
    for f in _walk(root, "*.yaml"):
        if "distill" not in f.name and "skill" not in f.name:
            continue
        names = {m.group(1) for line in f.read_text(encoding="utf-8", errors="replace").splitlines()
                 if (m := YAML_PATH.match(line))}
        if names:
            out.append((f, "yaml-path", names))
    return out


def self_built_skills(root: Path) -> set[str]:
    """各專案 `sync_skills.py` 宣告的自建 skill（上游沒有是正常的）。

    🔴 少了這一層，`ark-fish-daily-report`／`ark-policy-translate` 這種
    「唯一權威來源就在專案自己」的 skill 會被report成懸空 ——
    39 處假警報足以讓人直接忽略整份輸出。
    ⚠️ 收集成**全庫一份**而非專案級：`ark-policy-translate` 只在 slotverse／fish
    宣告 LOCAL_ONLY，卻也部署到 hoyeah 等專案（自建 skill 跨專案共用）。
    照專案切會讓沒宣告的那幾個專案繼續假警報。
    """
    out: set[str] = set()
    for f in _walk(root, "sync_skills.py"):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            tgt = (getattr(node.targets[0], "id", "") if isinstance(node, ast.Assign)
                   else getattr(node.target, "id", "") if isinstance(node, ast.AnnAssign)
                   else None)
            if tgt in ("LOCAL_ONLY", "ROOT_SOURCED"):
                try:
                    out.update(ast.literal_eval(node.value))
                except ValueError:
                    pass
    return out


def collect(root: Path):
    return (scan_matrices(root) + scan_deployed(root)
            + scan_souls(root) + scan_yaml_paths(root))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--consumers", type=Path, default=DEFAULT_CONSUMERS,
                    help=f"消費端根目錄（預設 {DEFAULT_CONSUMERS}）")
    ap.add_argument("--repo", type=Path, default=SKILLS_REPO, help="上游 skill 庫")
    ap.add_argument("--name", help="只查這個 skill 名字（移除前先問「誰在用」）")
    args = ap.parse_args()

    if not args.consumers.is_dir():
        # 明說跳過，不假裝通過 —— 「掃描回報成功而範圍是空的」是本 repo 記過的事故形態
        print(f"⏭  消費端根目錄不存在，跳過：{args.consumers}")
        return 0

    upstream = upstream_skills(args.repo)
    print(f"上游 {len(upstream)} 個 skill · 消費端根目錄 {args.consumers}")

    sites = collect(args.consumers)
    if not sites:
        print("⏭  沒有掃到任何消費端引用面（矩陣／複本／SOUL／蒸餾設定）")
        return 0

    if args.name:
        users = [(p, kind) for p, kind, names in sites if args.name in names]
        print(f"\n「{args.name}」的使用者：{len(users)} 處")
        for p, kind in users:
            print(f"  [{kind:8}] {p.relative_to(args.consumers)}")
        return 0

    allowed = upstream | self_built_skills(args.consumers)
    dangling: dict[str, list[tuple[str, Path]]] = {}
    for p, kind, names in sites:
        for n in sorted(names - allowed):
            dangling.setdefault(n, []).append((kind, p))

    scanned = len(sites)
    if not dangling:
        print(f"✅ 掃了 {scanned} 個引用面，懸空引用 0")
        return 0

    print(f"\n🔴 {len(dangling)} 個名字在上游已不存在，但消費端還指著它：")
    for n, where in sorted(dangling.items()):
        print(f"\n  {n}（{len(where)} 處）")
        for kind, p in where:
            print(f"    [{kind:8}] {p.relative_to(args.consumers)}")
    print(f"\n掃了 {scanned} 個引用面。移除／改名 skill 時，這些都要一起改。")
    return 1


if __name__ == "__main__":
    if {"-h", "--help"} & set(sys.argv[1:]):
        print(__doc__ or "")
        raise SystemExit(0)
    raise SystemExit(main())
